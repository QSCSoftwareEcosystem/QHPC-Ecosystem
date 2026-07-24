from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from qhpc_ecosystem.contract import ContractError, load_document
from qhpc_ecosystem.engine import (
    ArtifactResult,
    FunctionRunner,
    TaskRequest,
    TaskResult,
    WorkflowEngine,
)
from test_workflow import example_registry


ROOT = Path(__file__).resolve().parents[1]


def make_runner() -> FunctionRunner:
    runner = FunctionRunner()

    def generate(request: TaskRequest) -> TaskResult:
        output = request.work_directory / "circuit.qasm"
        output.write_text(
            f"OPENQASM 2.0;\nqreg q[{request.parameters['qubits']}];\n",
            encoding="utf-8",
        )
        return TaskResult(
            {
                "circuit": ArtifactResult.from_path(
                    request.output_types["circuit"], output
                )
            },
            "generated circuit",
        )

    def simulate(request: TaskRequest) -> TaskResult:
        assert request.inputs["circuit"]["checksum"].startswith("sha256:")
        output = request.work_directory / "results.json"
        output.write_text(
            json.dumps({"shots": request.parameters["shots"], "counts": {"0": 1024}}),
            encoding="utf-8",
        )
        return TaskResult(
            {
                "results": ArtifactResult.from_path(
                    request.output_types["results"], output
                )
            },
            "simulated circuit",
        )

    runner.register("example-toolkit", "generate", generate)
    runner.register("example-toolkit", "simulate", simulate)
    return runner


def test_engine_executes_persistent_workflow_and_exports_bundle(tmp_path: Path) -> None:
    engine = WorkflowEngine(tmp_path / "engine.sqlite", tmp_path / "artifacts")
    workflow = load_document(ROOT / "examples/contracts/valid/workflow.yaml")
    registered = engine.register_workflow(
        workflow, example_registry(), created_by="test-user"
    )
    run = engine.submit_run(
        registered["id"],
        registered["version"],
        inputs={},
        execution_target="local-development",
        created_by="test-user",
    )

    assert run["state"] == "queued"
    assert engine.run_until_idle(make_runner()) == 2
    completed = engine.get_run(run["id"])
    assert completed["state"] == "succeeded"
    assert [task["state"] for task in completed["tasks"]] == [
        "succeeded",
        "succeeded",
    ]
    assert completed["outputs"]["results"].startswith("artifact-")

    bundle = engine.export_run(run["id"])
    assert bundle["workflow"]["digest"] == completed["workflow_digest"]
    assert len(bundle["artifacts"]) == 2
    assert bundle["digest"].startswith("sha256:")


def test_workflow_versions_are_immutable(tmp_path: Path) -> None:
    engine = WorkflowEngine(tmp_path / "engine.sqlite", tmp_path / "artifacts")
    workflow = load_document(ROOT / "examples/contracts/valid/workflow.yaml")
    engine.register_workflow(workflow, example_registry(), created_by="test-user")
    changed = copy.deepcopy(workflow)
    changed["metadata"]["name"] = "Changed without a version bump"

    with pytest.raises(ContractError, match="immutable"):
        engine.register_workflow(changed, example_registry(), created_by="test-user")


def test_failed_task_can_be_retried_without_repeating_parent(tmp_path: Path) -> None:
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
    runner = make_runner()
    attempts = {"simulate": 0}

    def flaky(request: TaskRequest) -> TaskResult:
        attempts["simulate"] += 1
        if attempts["simulate"] == 1:
            raise RuntimeError("temporary failure")
        output = request.work_directory / "results.json"
        output.write_text("{}", encoding="utf-8")
        return TaskResult(
            {
                "results": ArtifactResult.from_path(
                    request.output_types["results"], output
                )
            }
        )

    runner.register("example-toolkit", "simulate", flaky)
    assert engine.run_until_idle(runner) == 2
    failed = engine.get_run(run["id"])
    assert failed["state"] == "failed"
    assert failed["tasks"][0]["attempt"] == 1

    engine.retry_task(run["id"], "simulate")
    assert engine.run_until_idle(runner) == 1
    completed = engine.get_run(run["id"])
    assert completed["state"] == "succeeded"
    assert completed["tasks"][0]["attempt"] == 1
    assert completed["tasks"][1]["attempt"] == 2


def test_external_input_artifact_is_typed_persisted_and_exported(
    tmp_path: Path,
) -> None:
    engine = WorkflowEngine(tmp_path / "engine.sqlite", tmp_path / "artifacts")
    workflow = load_document(ROOT / "examples/contracts/valid/workflow.yaml")
    workflow["metadata"].update(
        {"id": "simulate-external-circuit", "name": "Simulate external circuit"}
    )
    workflow["spec"]["nodes"] = [workflow["spec"]["nodes"][1]]
    workflow["spec"]["edges"] = []
    workflow["spec"]["inputs"] = {
        "circuit": {
            "artifact_type": "qhpc.quantum-circuit@1",
            "to": {"node": "simulate", "port": "circuit"},
        }
    }
    artifact = engine.register_input_artifact(
        artifact_type="qhpc.quantum-circuit@1",
        content=b"OPENQASM 2.0;\nqreg q[1];\n",
        name="input.qasm",
        created_by="test-user",
    )
    engine.register_workflow(workflow, example_registry(), created_by="test-user")
    run = engine.submit_run(
        workflow["metadata"]["id"],
        workflow["metadata"]["version"],
        inputs={"circuit": artifact["id"]},
        execution_target="local-development",
        created_by="test-user",
    )

    assert engine.run_until_idle(make_runner()) == 1
    assert engine.get_run(run["id"])["state"] == "succeeded"
    bundle = engine.export_run(run["id"])
    assert bundle["artifacts"][0]["id"] == artifact["id"]
    assert bundle["artifacts"][0]["provenance"] == "input"

    wrong = engine.register_input_artifact(
        artifact_type="qhpc.measurement-results@1",
        content=b"{}",
        name="wrong.json",
        created_by="test-user",
    )
    with pytest.raises(ContractError, match="requires qhpc.quantum-circuit@1"):
        engine.submit_run(
            workflow["metadata"]["id"],
            workflow["metadata"]["version"],
            inputs={"circuit": wrong["id"]},
            execution_target="local-development",
            created_by="test-user",
        )


def test_run_submission_rechecks_a_stored_workflow_against_active_registry(
    tmp_path: Path,
) -> None:
    engine = WorkflowEngine(tmp_path / "engine.sqlite", tmp_path / "artifacts")
    workflow = load_document(ROOT / "examples/contracts/valid/workflow.yaml")
    engine.register_workflow(workflow, example_registry(), created_by="test-user")
    restricted_registry = copy.deepcopy(example_registry())
    restricted_registry["spec"]["entries"][0]["capability"]["metadata"]["id"] = (
        "allowed-toolkit"
    )

    with pytest.raises(ContractError, match="capability not found: example-toolkit"):
        engine.submit_run(
            workflow["metadata"]["id"],
            workflow["metadata"]["version"],
            registry=restricted_registry,
            inputs={},
            execution_target="local-development",
            created_by="test-user",
        )

    assert engine.list_runs() == []
