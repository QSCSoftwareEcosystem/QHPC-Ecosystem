from __future__ import annotations

import json
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pytest

from qhpc_ecosystem.api import APIContext, handler_for
from qhpc_ecosystem.contract import load_document
from qhpc_ecosystem.engine import WorkflowEngine
from test_engine import make_runner
from test_workflow import example_registry


ROOT = Path(__file__).resolve().parents[1]


class FakeChatQEC:
    def __init__(self) -> None:
        self.requests: list[dict] = []

    def status(self) -> dict:
        return {
            "status": "ok",
            "mode": "canonical-extractive",
            "corpus_revision": "sha256:" + ("a" * 64),
            "documents": 60,
        }

    def ask(
        self,
        question: str,
        *,
        conversation_id: str,
        history: list[dict],
        correlation_id: str | None,
    ) -> dict:
        self.requests.append(
            {
                "question": question,
                "conversation_id": conversation_id,
                "history": history,
                "correlation_id": correlation_id,
            }
        )
        return {
            "answer": "The surface code is a topological quantum error-correcting code.",
            "citations": [
                {
                    "title": "Surface Code",
                    "url": "https://chatqec.org/knowledge/surface-code",
                }
            ],
        }


class FakeRepositoryUpdates:
    def __init__(self) -> None:
        self.checked: list[list[str] | None] = []
        self.staged: list[tuple[str, str | None]] = []
        self.discarded: list[str] = []

    def list(self) -> dict:
        return {
            "enabled": True,
            "items": [
                {
                    "component_id": "stabsim",
                    "status": "not-checked",
                }
            ],
        }

    def check(self, component_ids=None) -> dict:
        self.checked.append(component_ids)
        return {
            "enabled": True,
            "items": [
                {
                    "component_id": "stabsim",
                    "status": "update-available",
                    "latest_revision": "b" * 40,
                }
            ],
        }

    def stage(self, component_id, candidate_revision=None) -> dict:
        self.staged.append((component_id, candidate_revision))
        return {
            "component_id": component_id,
            "status": "prepared",
            "staged_revision": candidate_revision,
        }

    def discard(self, component_id) -> dict:
        self.discarded.append(component_id)
        return {
            "component_id": component_id,
            "status": "update-available",
        }


class FakeKnowledge:
    def summary(self) -> dict:
        return {
            "available": True,
            "stats": {"content_nodes": 4, "edges": 3, "communities": 2},
            "communities": [],
            "community_edges": [],
        }

    def search(self, term, **filters) -> dict:
        return {
            "query": term,
            "filters": filters,
            "total": 1,
            "items": [{"id": "packages/openqevo", "title": "OpenQEvo"}],
        }

    def shortest_path(self, source, target) -> dict:
        return {"found": True, "path": [source, target], "nodes": [], "edges": []}

    def community(self, index, *, limit) -> dict:
        return {"community": {"index": index}, "limit": limit, "nodes": [], "edges": []}

    def neighborhood(self, node_id, *, depth, limit) -> dict:
        return {
            "center": node_id,
            "depth": depth,
            "limit": limit,
            "nodes": [],
            "edges": [],
        }

    def node(self, node_id) -> dict:
        return {"id": node_id, "title": "OpenQEvo", "citations": []}


class FakeDatabucket:
    bucket = "proj-materials-db"

    def __init__(self) -> None:
        self.requested_prefixes: list[str] = []

    def list_objects(self, prefix: str = ""):
        from qhpc_ecosystem.s3_client import ObjectSummary

        self.requested_prefixes.append(prefix)
        return [
            ObjectSummary(
                key=f"{prefix}materials-schema-v0.1.yaml",
                size=512,
                last_modified="2026-08-31T00:00:00.000Z",
                etag="abc123",
            )
        ]


def request_json(
    base: str,
    path: str,
    body: dict | None = None,
    *,
    method: str | None = None,
):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = Request(
        base + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method=method or ("POST" if body is not None else "GET"),
    )
    with urlopen(request, timeout=3) as response:
        return response.status, json.load(response)


def test_api_serves_workbench_and_run_lifecycle(tmp_path: Path) -> None:
    engine = WorkflowEngine(tmp_path / "engine.sqlite", tmp_path / "artifacts")
    chatqec = FakeChatQEC()
    context = APIContext(
        engine=engine,
        registry=example_registry(),
        chatqec=chatqec,
    )
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
        status, capabilities = request_json(base, "/api/v1/capabilities")
        assert status == 200
        assert capabilities[0]["name"] == "Example Quantum Toolkit"
        assert capabilities[0]["capability_name"] == "Example Quantum Operations"
        assert capabilities[0]["description"].startswith("Illustrative operations")
        assert capabilities[0]["guidance"]["use_when"]
        assert capabilities[0]["guidance"]["quick_start"]
        status, workers = request_json(base, "/api/v1/workers")
        assert status == 200
        assert workers == []
        status, updates = request_json(base, "/api/v1/repository-updates")
        assert status == 200
        assert updates == {"enabled": False, "items": []}
        status, assistant = request_json(
            base,
            "/api/v1/assistant/chatqec/status",
        )
        assert status == 200
        assert assistant["available"]
        assert assistant["mode"] == "canonical-extractive"
        status, answer = request_json(
            base,
            "/api/v1/assistant/chatqec/answers",
            {
                "question": "What is the surface code?",
                "conversation_id": "conversation-api-test",
                "history": [],
            },
        )
        assert status == 200
        assert answer["citations"][0]["title"] == "Surface Code"
        assert chatqec.requests[0]["conversation_id"] == "conversation-api-test"
        with pytest.raises(HTTPError) as unsupported_identity:
            request_json(
                base,
                "/api/v1/assistant/chatqec/answers",
                {
                    "question": "What is the surface code?",
                    "conversation_id": "conversation-api-test",
                    "authorized_subject": "browser-selected-identity",
                },
            )
        assert unsupported_identity.value.code == 400

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
        with urlopen(
            base + f"/api/v1/artifacts/{artifact['id']}/content?download=1",
            timeout=3,
        ) as response:
            assert response.status == 200
            assert response.read() == b"OPENQASM 2.0;\nqreg q[1];\n"
            assert response.headers["Content-Disposition"].startswith("attachment;")
            assert response.headers["ETag"] == f'"{artifact["checksum"]}"'

        workflow = load_document(ROOT / "examples/contracts/valid/workflow.yaml")
        status, registered = request_json(
            base,
            "/api/v1/workflows",
            {"workflow": workflow, "created_by": "api-test"},
        )
        assert status == 201

        status, draft = request_json(
            base,
            "/api/v1/workflow-drafts",
            {"workflow": workflow, "created_by": "api-test"},
        )
        assert status == 201
        assert draft["metadata"]["revision"] == 1
        status, drafts = request_json(
            base,
            "/api/v1/workflow-drafts?owner=api-test",
        )
        assert status == 200
        assert [item["metadata"]["id"] for item in drafts] == [
            draft["metadata"]["id"]
        ]
        status, updated_draft = request_json(
            base,
            f"/api/v1/workflow-drafts/{draft['metadata']['id']}",
            {
                "workflow": workflow,
                "layout": draft["spec"]["layout"],
                "expected_revision": 1,
            },
            method="PUT",
        )
        assert status == 200
        assert updated_draft["metadata"]["revision"] == 2
        with pytest.raises(HTTPError) as stale:
            request_json(
                base,
                f"/api/v1/workflow-drafts/{draft['metadata']['id']}",
                {
                    "workflow": workflow,
                    "layout": draft["spec"]["layout"],
                    "expected_revision": 1,
                },
                method="PUT",
            )
        assert stale.value.code == 409
        status, validation = request_json(
            base,
            f"/api/v1/workflow-drafts/{draft['metadata']['id']}/validate",
            {"expected_revision": 2},
        )
        assert status == 200
        assert validation["valid"]
        status, published = request_json(
            base,
            f"/api/v1/workflow-drafts/{draft['metadata']['id']}/publish",
            {"expected_revision": 2, "created_by": "api-test"},
        )
        assert status == 201
        assert published["workflow"]["digest"] == registered["digest"]

        with pytest.raises(HTTPError) as unavailable:
            request_json(
                base,
                "/api/v1/runs",
                {
                    "workflow_id": registered["id"],
                    "version": registered["version"],
                    "execution_target": "local-development",
                    "created_by": "api-test",
                },
            )
        assert unavailable.value.code == 503
        unavailable_body = json.load(unavailable.value)
        assert "no healthy compatible worker" in unavailable_body["error"]
        assert not unavailable_body["details"]["ready"]
        assert request_json(base, "/api/v1/runs")[1] == []

        requirements = engine.workflow_execution_requirements(
            registered["id"],
            registered["version"],
            execution_target="local-development",
        )
        engine.register_worker(
            "api-test-worker",
            kind="local",
            metadata={
                "execution": "synchronous",
                "execution_targets": ["local-development"],
                "execution_classes": ["interactive-local"],
                "runtime_digests": sorted(
                    {item["runtime_digest"] for item in requirements}
                ),
            },
        )
        query = urlencode(
            [
                ("execution_target", "local-development"),
                ("execution_class", "interactive-local"),
                *[
                    ("runtime_digest", item["runtime_digest"])
                    for item in requirements
                ],
            ]
        )
        status, readiness = request_json(base, f"/api/v1/readiness?{query}")
        assert status == 200
        assert readiness["ready"]

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


def test_api_repository_updates_use_allowlisted_fields(tmp_path: Path) -> None:
    engine = WorkflowEngine(tmp_path / "engine.sqlite", tmp_path / "artifacts")
    updates = FakeRepositoryUpdates()
    context = APIContext(
        engine=engine,
        registry=example_registry(),
        repository_updates=updates,
    )
    try:
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(context))
    except PermissionError:
        pytest.skip("test runner does not permit binding a localhost socket")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        status, listing = request_json(base, "/api/v1/repository-updates")
        assert status == 200
        assert listing["items"][0]["component_id"] == "stabsim"

        status, checked = request_json(
            base,
            "/api/v1/repository-updates/check",
            {"component_ids": ["stabsim"]},
        )
        assert status == 200
        assert checked["items"][0]["status"] == "update-available"
        assert updates.checked == [["stabsim"]]

        candidate = "b" * 40
        status, staged = request_json(
            base,
            "/api/v1/repository-updates/stage",
            {
                "component_id": "stabsim",
                "candidate_revision": candidate,
            },
        )
        assert status == 201
        assert staged["status"] == "prepared"
        assert updates.staged == [("stabsim", candidate)]

        status, discarded = request_json(
            base,
            "/api/v1/repository-updates/discard",
            {"component_id": "stabsim"},
        )
        assert status == 200
        assert discarded["status"] == "update-available"
        assert updates.discarded == ["stabsim"]

        with pytest.raises(HTTPError) as unsupported:
            request_json(
                base,
                "/api/v1/repository-updates/stage",
                {
                    "component_id": "stabsim",
                    "candidate_revision": candidate,
                    "repository_url": "https://attacker.invalid/repository",
                },
            )
        assert unsupported.value.code == 400
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_api_exposes_read_only_knowledge_queries(tmp_path: Path) -> None:
    engine = WorkflowEngine(tmp_path / "engine.sqlite", tmp_path / "artifacts")
    context = APIContext(
        engine=engine,
        registry=example_registry(),
        knowledge=FakeKnowledge(),
    )
    try:
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(context))
    except PermissionError:
        pytest.skip("test runner does not permit binding a localhost socket")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        status, summary = request_json(base, "/api/v1/knowledge")
        assert status == 200
        assert summary["available"]

        status, search = request_json(
            base,
            "/api/v1/knowledge/nodes?query=openqevo&type=package&limit=12",
        )
        assert status == 200
        assert search["items"][0]["id"] == "packages/openqevo"
        assert search["filters"]["node_type"] == "package"
        assert search["filters"]["limit"] == 12

        status, community = request_json(
            base,
            "/api/v1/knowledge/communities/2?limit=40",
        )
        assert status == 200
        assert community["community"]["index"] == 2
        assert community["limit"] == 40

        status, neighborhood = request_json(
            base,
            "/api/v1/knowledge/neighborhood/packages%2Fopenqevo?depth=2",
        )
        assert status == 200
        assert neighborhood["center"] == "packages/openqevo"
        assert neighborhood["depth"] == 2

        status, node = request_json(
            base,
            "/api/v1/knowledge/nodes/packages%2Fopenqevo",
        )
        assert status == 200
        assert node["id"] == "packages/openqevo"

        status, path = request_json(
            base,
            "/api/v1/knowledge/path?source=packages%2Fopenqevo"
            "&target=concepts%2Fqec%2Fsurface",
        )
        assert status == 200
        assert path["found"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_api_data_objects_reports_unavailable_without_databucket(
    tmp_path: Path,
) -> None:
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
        status, body = request_json(base, "/api/v1/data/objects")
        assert status == 200
        assert body == {
            "available": False,
            "reason": "databucket/Garage is not configured",
        }
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_api_data_objects_lists_bucket_contents(tmp_path: Path) -> None:
    engine = WorkflowEngine(tmp_path / "engine.sqlite", tmp_path / "artifacts")
    databucket = FakeDatabucket()
    context = APIContext(
        engine=engine,
        registry=example_registry(),
        databucket=databucket,
    )
    try:
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(context))
    except PermissionError:
        pytest.skip("test runner does not permit binding a localhost socket")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        status, body = request_json(base, "/api/v1/data/objects?prefix=materials-db/")
        assert status == 200
        assert body["available"] is True
        assert body["bucket"] == "proj-materials-db"
        assert body["prefix"] == "materials-db/"
        assert body["objects"] == [
            {
                "key": "materials-db/materials-schema-v0.1.yaml",
                "size": 512,
                "last_modified": "2026-08-31T00:00:00.000Z",
                "etag": "abc123",
            }
        ]
        assert databucket.requested_prefixes == ["materials-db/"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_workbench_queues_runs_and_polls_asynchronous_state() -> None:
    script = (ROOT / "src/qhpc_ecosystem/workbench/app.js").read_text(encoding="utf-8")

    assert "/execute" not in script
    assert "setInterval(refreshOperationalState, 5000)" in script
    assert 'api("/workers")' in script
    assert "queued for a worker" in script
    assert "requireWorkerReadiness" in script
    assert "/readiness?" in script
