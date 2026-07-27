from __future__ import annotations

import json
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from qhpc_ecosystem.api import APIContext, handler_for
from qhpc_ecosystem.contract import load_document
from qhpc_ecosystem.engine import WorkflowEngine
from test_engine import make_runner
from test_workflow import example_registry


ROOT = Path(__file__).resolve().parents[1]


def request_json(base: str, path: str, body: dict | None = None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = Request(
        base + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST" if body is not None else "GET",
    )
    with urlopen(request, timeout=3) as response:
        return response.status, json.load(response)


def test_api_serves_workbench_and_run_lifecycle(tmp_path: Path) -> None:
    engine = WorkflowEngine(tmp_path / "engine.sqlite", tmp_path / "artifacts")
    context = APIContext(engine=engine, registry=example_registry())
    try:
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(context))
    except PermissionError:
        pytest.skip("test runner does not permit binding a localhost socket")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        status, health = request_json(base, "/api/v1/health")
        assert status == 200
        assert health == {
            "api": "qhpc/v1",
            "execution": "external-worker",
            "status": "ok",
        }
        status, workers = request_json(base, "/api/v1/workers")
        assert status == 200
        assert workers == []

        with urlopen(base + "/", timeout=3) as response:
            assert response.status == 200
            assert b"QHPC Workbench" in response.read()

        status, artifact = request_json(
            base,
            "/api/v1/artifacts",
            {
                "artifact_type": "qhpc.quantum-circuit@1",
                "name": "input.qasm",
                "content": "OPENQASM 2.0;\nqreg q[1];\n",
                "created_by": "api-test",
            },
        )
        assert status == 201
        assert artifact["provenance"] == "input"
        status, artifacts = request_json(base, "/api/v1/artifacts")
        assert status == 200
        assert artifacts[0]["id"] == artifact["id"]

        workflow = load_document(ROOT / "examples/contracts/valid/workflow.yaml")
        status, registered = request_json(
            base,
            "/api/v1/workflows",
            {"workflow": workflow, "created_by": "api-test"},
        )
        assert status == 201

        status, run = request_json(
            base,
            "/api/v1/runs",
            {
                "workflow_id": registered["id"],
                "version": registered["version"],
                "execution_target": "local-development",
                "created_by": "api-test",
            },
        )
        assert status == 202
        assert run["state"] == "queued"

        with pytest.raises(HTTPError) as error:
            request_json(base, f"/api/v1/runs/{run['id']}/execute", {})
        assert error.value.code == 410
        assert "worker processes" in json.load(error.value)["error"]

        assert engine.run_until_idle(make_runner()) == 2
        status, completed = request_json(base, f"/api/v1/runs/{run['id']}")
        assert status == 200
        assert completed["state"] == "succeeded"

        status, bundle = request_json(base, f"/api/v1/runs/{run['id']}/export")
        assert status == 200
        assert bundle["kind"] == "RunBundle"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_workbench_queues_runs_and_polls_asynchronous_state() -> None:
    script = (ROOT / "src/qhpc_ecosystem/workbench/app.js").read_text(encoding="utf-8")

    assert "/execute" not in script
    assert "setInterval(refreshActiveRuns, 2000)" in script
    assert "queued for a worker" in script
