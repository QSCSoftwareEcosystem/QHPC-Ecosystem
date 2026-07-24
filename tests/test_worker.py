from __future__ import annotations

import copy
from pathlib import Path

from qhpc_ecosystem.contract import document_digest, load_document
from qhpc_ecosystem.engine import WorkflowEngine
from qhpc_ecosystem.worker import RegistryBoundRunner, Worker
from test_engine import make_runner
from test_workflow import example_registry


ROOT = Path(__file__).resolve().parents[1]


def queued_engine(tmp_path: Path) -> tuple[WorkflowEngine, str]:
    engine = WorkflowEngine(tmp_path / "engine.sqlite", tmp_path / "artifacts")
    workflow = load_document(ROOT / "examples/contracts/valid/workflow.yaml")
    engine.register_workflow(workflow, example_registry(), created_by="test-user")
    run = engine.submit_run(
        workflow["metadata"]["id"],
        workflow["metadata"]["version"],
        inputs={},
        execution_target="local-development",
        created_by="test-user",
    )
    return engine, run["id"]


def test_worker_drains_persistent_tasks_outside_the_api(tmp_path: Path) -> None:
    engine, run_id = queued_engine(tmp_path)
    worker = Worker(
        engine,
        RegistryBoundRunner(make_runner(), example_registry()),
        poll_interval_seconds=0.01,
    )

    assert worker.drain() == 2
    assert engine.get_run(run_id)["state"] == "succeeded"


def test_worker_rejects_operation_missing_from_deployment_registry(
    tmp_path: Path,
) -> None:
    engine, run_id = queued_engine(tmp_path)
    restricted = copy.deepcopy(example_registry())
    capability = restricted["spec"]["entries"][0]["capability"]
    capability["metadata"]["id"] = "allowed-toolkit"
    restricted["spec"]["entries"][0]["descriptor_digest"] = document_digest(
        capability
    )
    worker = Worker(
        engine,
        RegistryBoundRunner(make_runner(), restricted),
        poll_interval_seconds=0.01,
    )

    assert worker.drain() == 1
    failed = engine.get_run(run_id)
    assert failed["state"] == "failed"
    assert failed["tasks"][0]["error"] == {
        "code": "TaskRejectedError",
        "message": (
            "operation is not admitted by the deployment registry: "
            "example-toolkit@0.1.0/generate"
        ),
        "retryable": False,
    }
