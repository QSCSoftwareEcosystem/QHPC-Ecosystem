from __future__ import annotations

import copy
import json
from pathlib import Path

from qhpc_ecosystem.contract import document_digest, load_document
from qhpc_ecosystem.engine import (
    ArtifactResult,
    TaskRequest,
    TaskResult,
    WorkflowEngine,
)
from qhpc_ecosystem.worker import (
    AsyncWorker,
    RegistryBoundAsyncRunner,
    RegistryBoundRunner,
    TargetStatus,
    TargetSubmission,
    Worker,
)
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
    restricted["spec"]["entries"][0]["descriptor_digest"] = document_digest(capability)
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


def test_worker_only_claims_its_explicit_execution_targets(
    tmp_path: Path,
) -> None:
    engine, run_id = queued_engine(tmp_path)
    worker = Worker(
        engine,
        RegistryBoundRunner(make_runner(), example_registry()),
        execution_targets=("different-target",),
        worker_id="target-filtered-worker",
    )

    assert not worker.run_once()
    assert engine.get_run(run_id)["state"] == "queued"


class FakeTargetRunner:
    def __init__(self) -> None:
        self.submissions: list[tuple[str, str]] = []
        self.polls: list[str] = []
        self.cancellations: list[str] = []
        self.finalizations: list[tuple[str, bool]] = []

    def submit(self, request: TaskRequest) -> TargetSubmission:
        handle = f"job-{len(self.submissions) + 1}"
        self.submissions.append((request.node_id, handle))
        return TargetSubmission(
            handle,
            metadata={"stage_durations_ms": {"target.submit": 7}},
        )

    def poll(self, request: TaskRequest, handle: str) -> TargetStatus:
        self.polls.append(handle)
        return TargetStatus(
            "succeeded",
            {"stage_durations_ms": {"target.queue": 11}},
        )

    def collect(self, request: TaskRequest, handle: str) -> TaskResult:
        if request.node_id == "generate":
            output = request.work_directory / "circuit.qasm"
            output.write_text("OPENQASM 2.0;\nqreg q[1];\n", encoding="utf-8")
            port = "circuit"
        else:
            output = request.work_directory / "results.json"
            output.write_text(json.dumps({"counts": {"0": 1}}), encoding="utf-8")
            port = "results"
        return TaskResult(
            {port: ArtifactResult.from_path(request.output_types[port], output)},
            f"collected {handle}",
        )

    def cancel(self, request: TaskRequest, handle: str) -> None:
        self.cancellations.append(handle)

    def finalize(self, request: TaskRequest, *, succeeded: bool) -> None:
        self.finalizations.append((request.node_id, succeeded))


def test_async_worker_adopts_persisted_handle_without_duplicate_submission(
    tmp_path: Path,
) -> None:
    engine, run_id = queued_engine(tmp_path)
    target = FakeTargetRunner()
    first = AsyncWorker(
        engine,
        RegistryBoundAsyncRunner(target, example_registry()),
        worker_id="target-worker-a",
    )

    assert first.run_once()
    submitted = engine.get_run(run_id)
    attempt = submitted["tasks"][0]["attempts"][0]
    assert attempt["state"] == "submitted"
    assert attempt["target_handle"] == "job-1"
    assert attempt["lease_token"] is None

    second = AsyncWorker(
        engine,
        RegistryBoundAsyncRunner(target, example_registry()),
        worker_id="target-worker-b",
    )
    assert second.run_once()
    recovered = engine.get_run(run_id)
    assert recovered["tasks"][0]["state"] == "succeeded"
    assert target.submissions == [("generate", "job-1")]
    assert target.polls == ["job-1"]
    assert target.finalizations == [("generate", True)]
    assert {worker["id"] for worker in engine.list_workers()} == {
        "target-worker-a",
        "target-worker-b",
    }
    stages = [
        event["stage"]
        for event in recovered["events"]
        if event["event_type"] == "stage.completed"
    ]
    assert stages == [
        "worker.submit",
        "target.submit",
        "worker.poll",
        "target.queue",
        "worker.collect",
    ]


def test_async_worker_propagates_run_cancellation_to_target(
    tmp_path: Path,
) -> None:
    engine, run_id = queued_engine(tmp_path)
    target = FakeTargetRunner()
    worker = AsyncWorker(
        engine,
        RegistryBoundAsyncRunner(target, example_registry()),
        worker_id="target-worker",
    )

    assert worker.run_once()
    assert engine.cancel_run(run_id)["state"] == "canceled"
    assert worker.run_once()

    canceled = engine.get_run(run_id)
    assert target.cancellations == ["job-1"]
    assert target.finalizations == [("generate", False)]
    assert canceled["tasks"][0]["attempts"][0]["state"] == "canceled"
    assert any(
        event["event_type"] == "target.cancel-requested" for event in canceled["events"]
    )
