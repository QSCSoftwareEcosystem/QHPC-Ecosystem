from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

import pytest

from eqo import (
    EQOAPIError,
    EQOClient,
    EQOConnectionError,
    EQOProtocolError,
    EQOTimeoutError,
    Run,
    render_artifact,
    render_citations,
    render_run,
)
from qhpc_ecosystem.api import APIContext, handler_for
from qhpc_ecosystem.contract import load_document
from qhpc_ecosystem.engine import WorkflowEngine
from test_engine import make_runner
from test_workflow import example_registry


ROOT = Path(__file__).resolve().parents[1]


class FakeChatQEC:
    def status(self) -> dict:
        return {"status": "ok", "mode": "canonical-corpus-extractive-fallback"}

    def ask(
        self,
        question: str,
        *,
        conversation_id: str,
        history: list[dict],
        correlation_id: str | None,
    ) -> dict:
        assert question
        assert conversation_id.startswith("notebook-")
        assert history == []
        assert correlation_id and correlation_id.startswith("sdk-")
        return {
            "answer": "A citation-backed fallback answer.",
            "citations": [{"title": "Fixture", "url": "https://example.invalid/fixture"}],
        }


def test_sdk_uses_the_same_api_for_artifacts_runs_and_assistant(tmp_path: Path) -> None:
    engine = WorkflowEngine(tmp_path / "engine.sqlite", tmp_path / "artifacts")
    registry = example_registry()
    workflow = load_document(ROOT / "examples/contracts/valid/workflow.yaml")
    registered = engine.register_workflow(workflow, registry, created_by="sdk-test")
    requirements = engine.workflow_execution_requirements(
        registered["id"], registered["version"], execution_target="local-development"
    )
    engine.register_worker(
        "sdk-test-worker",
        kind="local",
        metadata={
            "execution": "synchronous",
            "execution_targets": ["local-development"],
            "execution_classes": ["interactive-local"],
            "runtime_digests": sorted({item["runtime_digest"] for item in requirements}),
        },
    )
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        handler_for(APIContext(engine=engine, registry=registry, chatqec=FakeChatQEC())),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    client = EQOClient.connect(f"http://127.0.0.1:{server.server_port}")
    try:
        assert client.health()["api"] == "qhpc/v1"
        # A new client has no client-side session or worker state to restore.
        assert EQOClient.connect(f"http://127.0.0.1:{server.server_port}").health()["api"] == "qhpc/v1"
        assert client.capabilities.list()[0]["id"] == "example-toolkit"
        resources = client.engagement.list()
        assert resources[0]["id"] == "hpc-ai-qc-crash-course"
        assert resources[0]["admission"] == "read-only-external-resource"
        assert client.workflows.get(registered["id"], registered["version"])["id"] == registered["id"]
        assert client.workflows.latest(registered["id"])["version"] == registered["version"]
        assert client.assistant.status()["available"]
        assert client.assistant.ask("What is this?")["citations"][0]["title"] == "Fixture"

        input_artifact = client.artifacts.create_input(
            "qhpc.quantum-circuit@1",
            "OPENQASM 2.0;\nqreg q[1];\n",
            name="input.qasm",
            created_by="sdk-test",
        )
        assert input_artifact.read_text() == "OPENQASM 2.0;\nqreg q[1];\n"
        artifact_view = render_artifact(input_artifact)
        assert "OPENQASM" in artifact_view._repr_html_()
        destination = input_artifact.download(tmp_path / "notebook" / "input.qasm")
        assert destination.read_text(encoding="utf-8") == "OPENQASM 2.0;\nqreg q[1];\n"

        run = client.workflows.submit(
            registered["id"],
            registered["version"],
            created_by="sdk-test",
        )
        assert run.state == "queued"
        engine.run_until_idle(make_runner())
        completed = run.wait(timeout=2, poll_interval=0.01)
        assert completed.state == "succeeded"
        assert completed.export()["kind"] == "RunBundle"
        assert len(completed.artifacts) == 2
        assert completed.artifacts.by_type("qhpc.quantum-circuit@1").read_text().startswith("OPENQASM")
        assert "succeeded" in render_run(completed)._repr_html_()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


class _RefreshClient:
    def __init__(self, state: str) -> None:
        self._state = state
        self.runs = SimpleNamespace(get=self.get)

    def get(self, run_id: str) -> Run:
        return Run(self, {"id": run_id, "state": self._state})


def test_sdk_notebook_views_and_failure_boundaries() -> None:
    citations = render_citations(
        [{"title": "<script>unsafe</script>", "url": "https://example.invalid", "source_revision": "r1"}]
    )
    assert "&lt;script&gt;unsafe&lt;/script&gt;" in citations._repr_html_()
    assert "<script>" not in citations._repr_html_()

    svg = SimpleNamespace(
        id="svg-fixture",
        artifact_type="image/svg+xml",
        read_bytes=lambda: b"<svg><script>alert(1)</script></svg>",
    )
    assert "SVG preview suppressed" in render_artifact(svg)._repr_html_()

    failed = Run(_RefreshClient("failed"), {"id": "run-failed", "state": "running"})
    assert failed.wait(timeout=1, poll_interval=0.001).state == "failed"
    with pytest.raises(EQOTimeoutError):
        Run(_RefreshClient("running"), {"id": "run-timeout", "state": "running"}).wait(
            timeout=0, poll_interval=0.001
        )
    with pytest.raises(EQOConnectionError):
        EQOClient("http://127.0.0.1:1", timeout=0.01).health()

    class TooLargeResponse:
        headers = {"Content-Length": str(16 * 1024 * 1024 + 1)}

        def read(self, amount: int) -> bytes:
            raise AssertionError(f"read should not be called for a declared oversized response: {amount}")

    with pytest.raises(EQOProtocolError, match="size limit"):
        EQOClient._read_bounded(TooLargeResponse())


def test_sdk_establishes_workbench_csrf_session_for_mutating_requests() -> None:
    requests: list[tuple[str, str | None, str | None]] = []

    class CSRFWorkbenchHandler(BaseHTTPRequestHandler):
        def _json(self, status: int, payload: dict) -> None:
            encoded = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self) -> None:  # noqa: N802 - standard-library callback name
            requests.append((self.path, self.headers.get("Cookie"), self.headers.get("X-CSRFToken")))
            if self.path == "/":
                encoded = b"<html></html>"
                self.send_response(200)
                self.send_header("Set-Cookie", "csrftoken=notebook-token; Path=/")
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)
                return
            if self.path == "/api/v1/health":
                self._json(200, {"api": "qhpc/v1"})
                return
            self._json(404, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802 - standard-library callback name
            requests.append((self.path, self.headers.get("Cookie"), self.headers.get("X-CSRFToken")))
            if (
                self.path == "/api/v1/artifacts"
                and self.headers.get("Cookie") == "csrftoken=notebook-token"
                and self.headers.get("X-CSRFToken") == "notebook-token"
            ):
                self._json(
                    201,
                    {
                        "id": "artifact-csrf",
                        "artifact_type": "qhpc.quantum-circuit@1",
                        "checksum": "sha256:" + "0" * 64,
                    },
                )
                return
            self._json(403, {"error": "CSRF validation failed"})

        def log_message(self, _format: str, *_args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), CSRFWorkbenchHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    client = EQOClient.connect(f"http://127.0.0.1:{server.server_port}")
    try:
        artifact = client.artifacts.create_input(
            "qhpc.quantum-circuit@1", "OPENQASM 2.0;", name="csrf.qasm"
        )
        assert artifact.id == "artifact-csrf"
        assert [request[0] for request in requests] == [
            "/api/v1/health",
            "/",
            "/api/v1/artifacts",
        ]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_sdk_rejects_unsafe_endpoints_and_maps_api_errors(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="HTTP"):
        EQOClient("ftp://example.invalid")
    with pytest.raises(ValueError, match="credentials"):
        EQOClient("https://user:secret@example.invalid")

    engine = WorkflowEngine(tmp_path / "engine.sqlite", tmp_path / "artifacts")
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        handler_for(APIContext(engine=engine, registry=example_registry())),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    client = EQOClient.connect(f"http://127.0.0.1:{server.server_port}")
    try:
        with pytest.raises(EQOAPIError) as missing:
            client.artifacts.get("artifact-missing")
        assert missing.value.status == 404
        assert "not found" in missing.value.message
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
