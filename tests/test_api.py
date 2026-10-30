from __future__ import annotations

import base64
import hashlib
import hmac
import json
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

import pytest

from qhpc_ecosystem.api import APIContext, handler_for
from qhpc_ecosystem.contract import load_document
from qhpc_ecosystem.engine import WorkflowEngine
from qhpc_ecosystem.repository_updates import RepositoryUpdateDetector
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

    def stream(
        self,
        question: str,
        *,
        conversation_id: str,
        history: list[dict],
        correlation_id: str | None,
    ) -> tuple[dict, ...]:
        answer = self.ask(
            question,
            conversation_id=conversation_id,
            history=history,
            correlation_id=correlation_id,
        )
        return (
            {
                "request_id": "req-api-stream",
                "sequence": 0,
                "event": "token",
                "data": {"text": answer["answer"]},
            },
            {
                "request_id": "req-api-stream",
                "sequence": 1,
                "event": "citation",
                "data": {"citation": answer["citations"][0]},
            },
            {
                "request_id": "req-api-stream",
                "sequence": 2,
                "event": "final",
                "data": {"response": answer},
            },
        )


class FakeRepositoryUpdates:
    def __init__(self) -> None:
        self.checked: list[list[str] | None] = []
        self.staged: list[tuple[str, str | None]] = []
        self.discarded: list[str] = []
        self.built: list[str] = []

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

    def build(self, component_id) -> dict:
        self.built.append(component_id)
        return {
            "component_id": component_id,
            "status": "built",
            "candidate_build": {"state": "succeeded"},
        }


class FakeComponentOnboarding:
    def __init__(self) -> None:
        self.inspections: list[dict] = []
        self.built: list[str] = []
        self.activated: list[str] = []
        self.update_checks: list[list[str] | None] = []
        self.prepared_updates: list[tuple[str, str | None]] = []
        self.discarded_updates: list[str] = []

    def list(self) -> dict:
        return {"enabled": True, "items": self.inspections}

    def inspect(self, repository_url, *, ref="HEAD", subdirectory="", template=None) -> dict:
        item = {
            "id": "onboarding-example",
            "source": {
                "repository_url": repository_url,
                "requested_ref": ref,
                "subdirectory": subdirectory or None,
            },
            "draft": {"template": template or "python-operation"},
        }
        self.inspections = [item]
        return item

    def update_draft(self, draft_id, changes) -> dict:
        assert draft_id == "onboarding-example"
        self.inspections[0]["draft"]["template"] = changes["template"]
        return self.inspections[0]

    def build(self, draft_id) -> dict:
        assert draft_id == "onboarding-example"
        self.built.append(draft_id)
        self.inspections[0]["status"] = "built"
        return self.inspections[0]

    def refresh(self, draft_id) -> dict:
        assert draft_id == "onboarding-example"
        self.inspections[0]["refresh"] = {"state": "up-to-date"}
        return self.inspections[0]

    def activate(self, draft_id) -> dict:
        assert draft_id == "onboarding-example"
        self.activated.append(draft_id)
        self.inspections[0]["status"] = "active"
        return self.inspections[0]

    def repository_update_list(self) -> dict:
        return {
            "enabled": True,
            "items": [
                {
                    "component_id": "onboarding:adapter",
                    "status": "not-checked",
                }
            ],
        }

    def check_repository_updates(self, component_ids=None) -> dict:
        self.update_checks.append(component_ids)
        return self.repository_update_list()

    def prepare_repository_update(self, component_id, candidate_revision=None) -> dict:
        self.prepared_updates.append((component_id, candidate_revision))
        return {"component_id": component_id, "status": "prepared"}

    def discard_repository_update(self, component_id) -> dict:
        self.discarded_updates.append(component_id)
        return {"component_id": component_id, "status": "update-available"}


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
        self.requested_keys: list[str] = []
        self.objects_by_key = {
            "materials-db/v0.1.0/KCuF3_Hamiltonian.yaml": b"material: KCuF3\n",
        }

    def get_object(self, key: str) -> bytes:
        from qhpc_ecosystem.s3_client import S3ClientError

        self.requested_keys.append(key)
        try:
            return self.objects_by_key[key]
        except KeyError:
            raise S3ClientError(f"S3 GET {key!r} failed: 404") from None

    def list_objects(self, prefix: str = ""):
        from qhpc_ecosystem.s3_client import ObjectSummary

        self.requested_prefixes.append(prefix)
        return [
            ObjectSummary(
                key=f"{prefix}v0.1.0/KCuF3_Hamiltonian.yaml",
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


def request_signed_json(
    base: str,
    path: str,
    payload: bytes,
    headers: dict[str, str],
):
    request = Request(
        base + path,
        data=payload,
        headers={"Content-Type": "application/json", **headers},
        method="POST",
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
        status, engagement = request_json(base, "/api/v1/engagement-resources")
        assert status == 200
        assert engagement["kind"] == "EngagementResources"
        assert engagement["read_only"] is True
        assert [item["id"] for item in engagement["resources"]] == [
            "hpc-ai-qc-crash-course",
            "quantum-computing-user-training",
            "fall-2026-qcup-hackathon",
        ]
        assert all(
            item["admission"] == "read-only-external-resource"
            for item in engagement["resources"]
        )
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
        stream_request = Request(
            base + "/api/v1/assistant/chatqec/answers/stream",
            data=json.dumps(
                {
                    "question": "What is the surface code?",
                    "conversation_id": "conversation-api-stream",
                    "history": [],
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(stream_request, timeout=3) as stream:
            assert stream.headers["Content-Type"].startswith("text/event-stream")
            payload = stream.read().decode("utf-8")
        assert "event: token" in payload
        assert "event: citation" in payload
        assert "event: final" in payload
        assert chatqec.requests[-1]["conversation_id"] == "conversation-api-stream"
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

        status, preflight = request_json(
            base,
            "/api/v1/workflow-preflight",
            {
                "workflow_id": registered["id"],
                "version": registered["version"],
                "execution_target": "local-development",
            },
        )
        assert status == 200
        assert preflight["state"] == "unavailable"
        assert not preflight["can_queue"]
        assert any(
            check["id"] == "compatible-worker" and check["state"] == "blocked"
            for check in preflight["checks"]
        )

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
                # Preflight responses must never relay worker metadata such as
                # credential references to the browser.
                "credential_reference": "secret://env/API_TEST_TOKEN",
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

        status, preflight = request_json(
            base,
            "/api/v1/workflow-preflight",
            {
                "workflow_id": registered["id"],
                "version": registered["version"],
                "execution_target": "local-development",
            },
        )
        assert status == 200
        assert preflight["state"] == "ready"
        assert preflight["can_queue"]
        assert "secret://env/API_TEST_TOKEN" not in json.dumps(preflight)

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


def test_api_preflight_validates_supplied_input_artifacts(tmp_path: Path) -> None:
    engine = WorkflowEngine(tmp_path / "engine.sqlite", tmp_path / "artifacts")
    workflow = load_document(ROOT / "examples/contracts/valid/workflow.yaml")
    workflow["metadata"].update(
        {
            "id": "api-preflight-input-artifacts",
            "name": "API preflight input artifacts",
        }
    )
    workflow["spec"]["nodes"] = [workflow["spec"]["nodes"][1]]
    workflow["spec"]["edges"] = []
    workflow["spec"]["inputs"] = {
        "circuit": {
            "artifact_type": "qhpc.quantum-circuit@1",
            "to": {"node": "simulate", "port": "circuit"},
        }
    }
    registered = engine.register_workflow(
        workflow,
        example_registry(),
        created_by="api-test",
    )
    requirements = engine.workflow_execution_requirements(
        registered["id"],
        registered["version"],
        execution_target="local-development",
    )
    engine.register_worker(
        "api-preflight-input-worker",
        kind="local",
        metadata={
            "execution_targets": ["local-development"],
            "execution_classes": ["interactive-local"],
            "runtime_digests": sorted(
                {item["runtime_digest"] for item in requirements}
            ),
        },
    )
    context = APIContext(engine=engine, registry=example_registry())
    try:
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(context))
    except PermissionError:
        pytest.skip("test runner does not permit binding a localhost socket")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    payload = {
        "workflow_id": registered["id"],
        "version": registered["version"],
        "execution_target": "local-development",
    }
    try:
        status, circuit = request_json(
            base,
            "/api/v1/artifacts",
            {
                "artifact_type": "qhpc.quantum-circuit@1",
                "name": "bell.qasm",
                "content": "OPENQASM 2.0;\nqreg q[2];\n",
                "created_by": "api-test",
            },
        )
        assert status == 201
        status, wrong = request_json(
            base,
            "/api/v1/artifacts",
            {
                "artifact_type": "qhpc.measurement-results@1",
                "name": "counts.json",
                "content": "{}",
                "created_by": "api-test",
            },
        )
        assert status == 201

        status, missing = request_json(
            base,
            "/api/v1/workflow-preflight",
            {**payload, "inputs": {}},
        )
        assert status == 200
        assert missing["state"] == "unavailable"
        assert missing["reason"] == "Required input artifact missing: circuit."

        status, unknown = request_json(
            base,
            "/api/v1/workflow-preflight",
            {**payload, "inputs": {"unknown": circuit["id"]}},
        )
        assert status == 200
        assert unknown["state"] == "unavailable"
        assert unknown["reason"] == "The published workflow does not declare input unknown."

        status, absent = request_json(
            base,
            "/api/v1/workflow-preflight",
            {**payload, "inputs": {"circuit": "artifact-not-present"}},
        )
        assert status == 200
        assert absent["state"] == "unavailable"
        assert absent["reason"] == (
            "Input artifact for circuit was not found: artifact-not-present."
        )

        status, mismatch = request_json(
            base,
            "/api/v1/workflow-preflight",
            {**payload, "inputs": {"circuit": wrong["id"]}},
        )
        assert status == 200
        assert mismatch["state"] == "unavailable"
        assert "requires qhpc.quantum-circuit@1" in mismatch["reason"]

        status, accepted = request_json(
            base,
            "/api/v1/workflow-preflight",
            {**payload, "inputs": {"circuit": circuit["id"]}},
        )
        assert status == 200
        assert accepted["state"] == "ready"
        assert any(
            check["id"] == "input-artifacts" and check["state"] == "passed"
            for check in accepted["checks"]
        )

        with pytest.raises(HTTPError) as rejected_run:
            request_json(
                base,
                "/api/v1/runs",
                {**payload, "inputs": {"circuit": wrong["id"]}},
            )
        assert rejected_run.value.code == 503
        rejected = json.load(rejected_run.value)
        assert "requires qhpc.quantum-circuit@1" in rejected["error"]
        assert any(
            check["id"] == "input-artifacts" and check["state"] == "blocked"
            for check in rejected["details"]["checks"]
        )
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

        status, built = request_json(
            base,
            "/api/v1/repository-updates/build",
            {"component_id": "stabsim"},
        )
        assert status == 200
        assert built["status"] == "built"
        assert updates.built == ["stabsim"]

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


def test_api_github_update_webhook_triggers_detection_only(tmp_path: Path) -> None:
    engine = WorkflowEngine(tmp_path / "engine.sqlite", tmp_path / "artifacts")
    updates = FakeRepositoryUpdates()
    completed = threading.Event()

    def check() -> None:
        updates.check()
        completed.set()

    secret = b"github-webhook-test-secret"
    detector = RepositoryUpdateDetector([check])
    context = APIContext(
        engine=engine,
        registry=example_registry(),
        repository_updates=updates,
        repository_update_detector=detector,
        github_webhook_secret=secret,
    )
    try:
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(context))
    except PermissionError:
        pytest.skip("test runner does not permit binding a localhost socket")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    payload = b'{"ref":"refs/heads/main"}'
    try:
        with pytest.raises(HTTPError) as rejected:
            request_signed_json(
                base,
                "/api/v1/repository-updates/webhooks/github",
                payload,
                {
                    "X-GitHub-Event": "push",
                    "X-Hub-Signature-256": "sha256=not-a-valid-signature",
                },
            )
        assert rejected.value.code == 401
        assert not completed.is_set()

        signature = "sha256=" + hmac.new(
            secret,
            payload,
            hashlib.sha256,
        ).hexdigest()
        status, accepted = request_signed_json(
            base,
            "/api/v1/repository-updates/webhooks/github",
            payload,
            {
                "X-GitHub-Event": "push",
                "X-Hub-Signature-256": signature,
            },
        )
        assert status == 202
        assert accepted == {
            "accepted": True,
            "provider": "github",
            "event": "push",
            "detection_only": True,
            "ignored": False,
            "check_started": True,
        }
        assert completed.wait(timeout=1)
        assert updates.checked == [None]
        assert updates.staged == []
        assert updates.discarded == []
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
        detector.stop()


def test_api_gitlab_update_webhook_triggers_detection_only(tmp_path: Path) -> None:
    engine = WorkflowEngine(tmp_path / "engine.sqlite", tmp_path / "artifacts")
    updates = FakeRepositoryUpdates()
    completed = threading.Event()

    def check() -> None:
        updates.check()
        completed.set()

    signing_key = b"gitlab-webhook-test-secret"
    signing_token = "whsec_" + base64.b64encode(signing_key).decode("ascii")
    detector = RepositoryUpdateDetector([check])
    context = APIContext(
        engine=engine,
        registry=example_registry(),
        repository_updates=updates,
        repository_update_detector=detector,
        gitlab_webhook_signing_token=signing_token,
    )
    try:
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(context))
    except PermissionError:
        pytest.skip("test runner does not permit binding a localhost socket")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    payload = b'{"ref":"refs/heads/main"}'
    message_id = "msg-123"
    timestamp = str(int(time.time()))
    signed_body = f"{message_id}.{timestamp}.".encode("utf-8") + payload
    signature = "v1," + base64.b64encode(
        hmac.new(signing_key, signed_body, hashlib.sha256).digest()
    ).decode("ascii")
    try:
        status, accepted = request_signed_json(
            base,
            "/api/v1/repository-updates/webhooks/gitlab",
            payload,
            {
                "X-Gitlab-Event": "Push Hook",
                "webhook-id": message_id,
                "webhook-timestamp": timestamp,
                "webhook-signature": signature,
            },
        )
        assert status == 202
        assert accepted["provider"] == "gitlab"
        assert accepted["detection_only"] is True
        assert accepted["check_started"] is True
        assert completed.wait(timeout=1)
        assert updates.checked == [None]
        assert updates.staged == []
        assert updates.discarded == []
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
        detector.stop()


def test_api_repository_updates_include_locally_admitted_components(
    tmp_path: Path,
) -> None:
    engine = WorkflowEngine(tmp_path / "engine.sqlite", tmp_path / "artifacts")
    onboarding = FakeComponentOnboarding()
    context = APIContext(
        engine=engine,
        registry=example_registry(),
        component_onboarding=onboarding,
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
        assert listing["enabled"] is True
        assert listing["items"][0]["component_id"] == "onboarding:adapter"

        status, checked = request_json(
            base,
            "/api/v1/repository-updates/check",
            {"component_ids": ["onboarding:adapter"]},
        )
        assert status == 200
        assert checked["enabled"] is True
        assert onboarding.update_checks == [["onboarding:adapter"]]

        candidate = "a" * 40
        status, staged = request_json(
            base,
            "/api/v1/repository-updates/stage",
            {
                "component_id": "onboarding:adapter",
                "candidate_revision": candidate,
            },
        )
        assert status == 201
        assert staged["status"] == "prepared"
        assert onboarding.prepared_updates == [("onboarding:adapter", candidate)]

        status, discarded = request_json(
            base,
            "/api/v1/repository-updates/discard",
            {"component_id": "onboarding:adapter"},
        )
        assert status == 200
        assert discarded["status"] == "update-available"
        assert onboarding.discarded_updates == ["onboarding:adapter"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_api_transpilation_converts_only_existing_circuit_artifacts(
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
        status, source = request_json(
            base,
            "/api/v1/artifacts",
            {
                "artifact_type": "qhpc.quantum-circuit@1",
                "name": "bell.qasm",
                "content": """OPENQASM 2.0;
include \"qelib1.inc\";
qreg q[2];
creg c[2];
h q[0];
cx q[0],q[1];
measure q[0] -> c[0];
measure q[1] -> c[1];
""",
            },
        )
        assert status == 201

        status, binary = request_json(
            base,
            "/api/v1/artifacts",
            {
                "artifact_type": "qhpc.quantum-circuit@1",
                "name": "binary.qpy",
                "content_base64": base64.b64encode(b"\x00qpy\xff").decode("ascii"),
            },
        )
        assert status == 201
        with urlopen(base + f"/api/v1/artifacts/{binary['id']}/content", timeout=3) as response:
            assert response.read() == b"\x00qpy\xff"

        status, conversion = request_json(
            base,
            "/api/v1/transpilation/convert",
            {
                "source_artifact_id": source["id"],
                "source_format": "openqasm-2",
                "target_format": "openqasm-3",
            },
        )
        assert status == 201
        assert conversion["normalized_artifact"]["artifact_type"] == "qhpc.circuit-exchange@1"
        assert conversion["report"]["source"]["artifact_id"] == source["id"]

        with pytest.raises(HTTPError) as unsupported:
            request_json(
                base,
                "/api/v1/transpilation/convert",
                {
                    "source_artifact_id": source["id"],
                    "source_format": "openqasm-2",
                    "target_format": "openqasm-3",
                    "python": "import qiskit",
                },
            )
        assert unsupported.value.code == 400
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_api_component_onboarding_accepts_only_reviewable_source_fields(
    tmp_path: Path,
) -> None:
    engine = WorkflowEngine(tmp_path / "engine.sqlite", tmp_path / "artifacts")
    onboarding = FakeComponentOnboarding()
    context = APIContext(
        engine=engine,
        registry=example_registry(),
        component_onboarding=onboarding,
    )
    try:
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(context))
    except PermissionError:
        pytest.skip("test runner does not permit binding a localhost socket")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        status, listing = request_json(base, "/api/v1/component-onboarding")
        assert status == 200
        assert listing == {"enabled": True, "items": []}

        status, draft = request_json(
            base,
            "/api/v1/component-onboarding/inspect",
            {
                "repository_url": "https://github.com/example/adapter",
                "ref": "refs/tags/v0.1.0",
                "subdirectory": "adapter",
                "template": "compiler-transpiler",
            },
        )
        assert status == 201
        assert draft["draft"]["template"] == "compiler-transpiler"
        assert onboarding.inspections[0]["source"] == {
            "repository_url": "https://github.com/example/adapter",
            "requested_ref": "refs/tags/v0.1.0",
            "subdirectory": "adapter",
        }

        status, edited = request_json(
            base,
            "/api/v1/component-onboarding/drafts/onboarding-example",
            {"template": "simulator"},
        )
        assert status == 200
        assert edited["draft"]["template"] == "simulator"

        status, built = request_json(
            base,
            "/api/v1/component-onboarding/drafts/onboarding-example/build",
            {},
        )
        assert status == 201
        assert built["status"] == "built"
        assert onboarding.built == ["onboarding-example"]

        status, refreshed = request_json(
            base,
            "/api/v1/component-onboarding/drafts/onboarding-example/refresh",
            {},
        )
        assert status == 201
        assert refreshed["refresh"] == {"state": "up-to-date"}

        status, activated = request_json(
            base,
            "/api/v1/component-onboarding/drafts/onboarding-example/activate",
            {},
        )
        assert status == 201
        assert activated["status"] == "active"
        assert onboarding.activated == ["onboarding-example"]

        with pytest.raises(HTTPError) as unsupported:
            request_json(
                base,
                "/api/v1/component-onboarding/inspect",
                {
                    "repository_url": "https://github.com/example/adapter",
                    "credential": "not accepted",
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
                "key": "materials-db/v0.1.0/KCuF3_Hamiltonian.yaml",
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


def test_api_data_object_content_downloads_bytes(tmp_path: Path) -> None:
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
    key = "materials-db/v0.1.0/KCuF3_Hamiltonian.yaml"
    try:
        request = Request(
            f"{base}/api/v1/data/objects/content?key={quote(key, safe='')}"
        )
        with urlopen(request, timeout=3) as response:
            assert response.status == 200
            assert response.read() == b"material: KCuF3\n"
            assert response.headers["Content-Type"] == "text/plain"
            assert "inline" in response.headers["Content-Disposition"]
        assert databucket.requested_keys == [key]

        download_request = Request(
            f"{base}/api/v1/data/objects/content?key={quote(key, safe='')}&download=1"
        )
        with urlopen(download_request, timeout=3) as response:
            assert "attachment" in response.headers["Content-Disposition"]

        missing_request = Request(
            f"{base}/api/v1/data/objects/content?key="
            f"{quote('materials-db/missing.yaml', safe='')}"
        )
        with pytest.raises(HTTPError) as error:
            urlopen(missing_request, timeout=3)
        assert error.value.status == 502
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_api_data_object_content_unavailable_without_databucket(
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
        request = Request(f"{base}/api/v1/data/objects/content?key={quote('k', safe='')}")
        with pytest.raises(HTTPError) as error:
            urlopen(request, timeout=3)
        assert error.value.status == 503
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
