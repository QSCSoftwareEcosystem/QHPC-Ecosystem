from __future__ import annotations

import copy
from pathlib import Path

from qhpc_ecosystem.contract import document_digest, load_document
from qhpc_ecosystem.engine import WorkflowEngine
from qhpc_ecosystem.operation_runtime import file_digest
from qhpc_ecosystem.slurm_runner import SlurmApptainerRunner
from qhpc_ecosystem.worker import AsyncWorker, RegistryBoundAsyncRunner


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "containers/operations/qasmtrans/runtime.yaml"
WORKFLOW = ROOT / "examples/workflows/qasmtrans-transpile.yaml"
REGISTRY = ROOT / "examples/registry.yaml"


class FakeSlurm:
    def __init__(self) -> None:
        self.state = "queued"
        self.submissions: list[Path] = []
        self.cancellations: list[str] = []

    def submit(self, script: str | Path) -> str:
        self.submissions.append(Path(script))
        return "41001"

    def status(self, job_id: str) -> str:
        assert job_id == "41001"
        return self.state

    def cancel(self, job_id: str) -> None:
        assert job_id == "41001"
        self.cancellations.append(job_id)

    def find_by_name(self, job_name: str) -> str | None:
        assert job_name.startswith("qhpc-")
        return None


def _contracts(tmp_path: Path):
    image_cache = tmp_path / "images"
    image_cache.mkdir()
    image = image_cache / "qasmtrans.sif"
    image.write_bytes(b"simulated accepted SIF\n")
    image_digest = file_digest(image)

    runtime = copy.deepcopy(load_document(RUNTIME))
    runtime["metadata"]["status"] = "target-accepted"
    runtime["metadata"]["evidence"].append("docs/evidence/simulated-target.md")
    runtime["spec"]["release"] = {
        "status": "target-accepted",
        "oci_reference": "registry.example/qasmtrans@sha256:" + "1" * 64,
        "oci_digest": "sha256:" + "1" * 64,
        "apptainer_reference": str(image),
        "apptainer_digest": image_digest,
        "sbom": "evidence/qasmtrans.spdx.json",
        "signature": "evidence/qasmtrans.sig",
        "attestation": "evidence/qasmtrans.intoto.jsonl",
    }
    target = {
        "api_version": "qhpc/v1",
        "kind": "ExecutionTarget",
        "metadata": {
            "id": "test-slurm",
            "name": "Simulated Slurm target",
            "owners": ["software-engineering"],
            "visibility": "internal",
            "status": "active",
            "evidence": ["docs/evidence/simulated-target.md"],
        },
        "spec": {
            "runner": "slurm",
            "execution_classes": ["interactive-hpc-pilot", "batch-hpc"],
            "container_runtimes": ["apptainer"],
            "resource_limits": {
                "max_cpu": 4,
                "max_memory_mb": 4096,
                "max_gpu": 0,
                "max_walltime_seconds": 600,
            },
            "policies": {
                "approved_images_only": True,
                "network_access": "none",
                "allowed_projects": ["compilation-tools"],
            },
            "storage_profile": "test-storage",
            "scheduler": {
                "system": "slurm",
                "account": "qsc",
                "partition": "batch",
                "qos": "normal",
                "apptainer_executable": "/usr/bin/apptainer",
                "max_active_jobs": 8,
            },
        },
    }
    storage = {
        "api_version": "qhpc/v1",
        "kind": "StorageProfile",
        "metadata": {
            "id": "test-storage",
            "name": "Simulated storage",
            "version": "0.1.0",
            "owners": ["software-engineering"],
            "status": "active",
            "evidence": ["docs/evidence/simulated-storage.md"],
        },
        "spec": {
            "execution_target": "test-slurm",
            "shared_filesystem": "project",
            "roots": {
                "image_cache": str(image_cache),
                "task_staging": str(tmp_path / "staging"),
            },
            "mounts": {
                "input": "/inputs",
                "output": "/outputs",
                "scratch": "/scratch",
            },
            "node_local": {
                "mode": "slurm-tmpdir",
                "stage_image": True,
                "stage_inputs": True,
                "minimum_free_mb": 128,
            },
            "policies": {
                "verify_image_digest": True,
                "verify_input_checksums": True,
                "cleanup": "on-success",
                "max_task_input_bytes": 1000000,
            },
        },
    }
    return runtime, target, storage


def _target_registry(runtime: dict) -> dict:
    registry = copy.deepcopy(load_document(REGISTRY))
    for entry in registry["spec"]["entries"]:
        capability = entry["capability"]
        if capability["metadata"]["id"] != "qasmtrans-transpiler":
            continue
        operation = capability["spec"]["operations"][0]
        operation["runtime"] = {
            "type": "apptainer",
            "reference": runtime["spec"]["release"]["apptainer_reference"],
            "digest": runtime["spec"]["release"]["apptainer_digest"],
        }
        operation["execution_targets"] = ["test-slurm"]
        entry["descriptor_digest"] = document_digest(capability)
        break
    return registry


def test_slurm_apptainer_runner_executes_simulated_qasm_workflow(
    tmp_path: Path,
) -> None:
    runtime, target, storage = _contracts(tmp_path)
    registry = _target_registry(runtime)
    engine = WorkflowEngine(tmp_path / "engine.sqlite", tmp_path / "artifacts")
    workflow = load_document(WORKFLOW)
    engine.register_workflow(workflow, registry, created_by="test-user")
    uploaded = engine.register_input_artifact(
        artifact_type="qhpc.quantum-circuit@1",
        content=b"OPENQASM 2.0;\nqreg q[2];\n",
        name="bell.qasm",
        created_by="test-user",
    )
    run = engine.submit_run(
        workflow["metadata"]["id"],
        workflow["metadata"]["version"],
        registry=registry,
        inputs={"circuit": uploaded["id"]},
        execution_target="test-slurm",
        created_by="test-user",
    )
    scheduler = FakeSlurm()
    runner = SlurmApptainerRunner(target, storage, [runtime], client=scheduler)
    worker = AsyncWorker(
        engine,
        RegistryBoundAsyncRunner(runner, registry),
        worker_id="test-slurm-worker",
    )

    assert worker.run_once()
    submitted = engine.get_run(run["id"])
    attempt = submitted["tasks"][0]["attempts"][0]
    assert attempt["state"] == "submitted"
    assert attempt["target_handle"] == "41001"
    assert len(scheduler.submissions) == 1
    script = scheduler.submissions[0].read_text(encoding="utf-8")
    assert "#SBATCH --account=qsc" in script
    assert "#SBATCH --partition=batch" in script
    assert "--containall --cleanenv --net --network none --no-home" in script
    assert "SLURM_TMPDIR" in script
    assert ":/inputs:ro" in script
    assert ":/outputs:rw" in script

    attempt_root = (
        Path(storage["spec"]["roots"]["task_staging"])
        / run["id"]
        / "transpile"
        / attempt["id"]
    )
    assert (attempt_root / "inputs/circuit.qasm").read_bytes() == (
        b"OPENQASM 2.0;\nqreg q[2];\n"
    )
    (attempt_root / "outputs/circuit.qasm").write_text(
        "OPENQASM 2.0;\nqreg q[2];\n",
        encoding="utf-8",
    )
    (attempt_root / "stage-timing.tsv").write_text(
        "node-local-stage\t100\t106\napplication\t110\t132\n",
        encoding="ascii",
    )
    scheduler.state = "succeeded"

    restarted = AsyncWorker(
        engine,
        RegistryBoundAsyncRunner(runner, registry),
        worker_id="test-slurm-worker-restarted",
    )
    assert restarted.run_once()

    completed = engine.get_run(run["id"])
    assert completed["state"] == "succeeded"
    assert len(scheduler.submissions) == 1
    assert completed["tasks"][0]["outputs"]["circuit"].startswith("artifact-")
    stages = {
        event["stage"]: event["duration_ms"]
        for event in completed["events"]
        if event["event_type"] == "stage.completed"
    }
    assert stages["target.node-local-stage"] == 6
    assert stages["target.application"] == 22
    assert stages["target.output-stage"] >= 0
    assert not attempt_root.exists()


def test_slurm_submission_receipt_recovers_crash_without_resubmission(
    tmp_path: Path,
) -> None:
    runtime, target, storage = _contracts(tmp_path)
    registry = _target_registry(runtime)
    engine = WorkflowEngine(tmp_path / "engine.sqlite", tmp_path / "artifacts")
    workflow = load_document(WORKFLOW)
    engine.register_workflow(workflow, registry, created_by="test-user")
    uploaded = engine.register_input_artifact(
        artifact_type="qhpc.quantum-circuit@1",
        content=b"OPENQASM 2.0;\nqreg q[1];\n",
        name="input.qasm",
        created_by="test-user",
    )
    run = engine.submit_run(
        workflow["metadata"]["id"],
        workflow["metadata"]["version"],
        registry=registry,
        inputs={"circuit": uploaded["id"]},
        execution_target="test-slurm",
        created_by="test-user",
    )
    scheduler = FakeSlurm()
    runner = SlurmApptainerRunner(target, storage, [runtime], client=scheduler)
    engine.register_worker("crashed-worker", kind="target")
    lease = engine.claim_task("crashed-worker", lease_seconds=60)
    assert lease is not None
    request = engine.task_request(lease)
    engine.mark_submitting(lease)
    submitted = runner.submit(request)
    assert submitted.handle == "41001"
    assert len(scheduler.submissions) == 1

    with engine._connect() as connection:
        connection.execute(
            """
            UPDATE task_attempts SET lease_expires_at='2000-01-01T00:00:00Z'
            WHERE id=?
            """,
            (lease.attempt_id,),
        )
        connection.execute(
            """
            UPDATE tasks SET lease_expires_at='2000-01-01T00:00:00Z'
            WHERE run_id=? AND node_id=?
            """,
            (lease.run_id, lease.node_id),
        )

    restarted = AsyncWorker(
        engine,
        RegistryBoundAsyncRunner(runner, registry),
        worker_id="recovery-worker",
    )
    assert restarted.run_once()
    recovered = engine.get_run(run["id"])["tasks"][0]["attempts"][0]
    assert recovered["id"] == lease.attempt_id
    assert recovered["target_handle"] == "41001"
    assert recovered["state"] == "submitted"
    assert len(scheduler.submissions) == 1
