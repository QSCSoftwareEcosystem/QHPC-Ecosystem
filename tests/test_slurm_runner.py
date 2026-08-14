from __future__ import annotations

import copy
from pathlib import Path

import pytest

from qhpc_ecosystem.contract import document_digest, load_document
from qhpc_ecosystem.engine import ArtifactResult, TaskRequest, WorkflowEngine
from qhpc_ecosystem.operation_runtime import file_digest
from qhpc_ecosystem.slurm_runner import (
    SlurmApptainerRunner,
    SlurmDockerClusterRunner,
)
from qhpc_ecosystem.slurm_test_cluster import SlurmDockerCluster
from qhpc_ecosystem.worker import AsyncWorker, RegistryBoundAsyncRunner


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "containers/operations/qasmtrans/runtime.yaml"
WORKFLOW = ROOT / "examples/workflows/qasmtrans-transpile.yaml"
REGISTRY = ROOT / "examples/registry.yaml"
CLUSTER_MANIFEST = (
    ROOT
    / "infrastructure"
    / "test-clusters"
    / "slurm-docker-cluster"
    / "cluster.yaml"
)
INITIAL_RUNTIMES = (
    ROOT / "containers/operations/stabsim/runtime.yaml",
    ROOT / "containers/operations/nwqec/runtime.yaml",
    ROOT / "containers/operations/ftprimitivebench/runtime.yaml",
    ROOT / "containers/operations/lightstim/runtime.yaml",
    ROOT / "containers/operations/qasmtrans/runtime.yaml",
)


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


def _contracts(tmp_path: Path, runtime_path: Path = RUNTIME):
    runtime = copy.deepcopy(load_document(runtime_path))
    component_id = runtime["metadata"]["component"]
    image_cache = tmp_path / "images"
    image_cache.mkdir()
    image = image_cache / f"{component_id}.sif"
    image.write_bytes(b"simulated accepted SIF\n")
    image_digest = file_digest(image)

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
                "allowed_projects": [runtime["metadata"]["project"]],
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

    def scheduler_path(path: Path) -> str:
        relative = path.resolve().relative_to(tmp_path.resolve())
        return "/mnt/" + relative.as_posix()

    runner = SlurmApptainerRunner(
        target,
        storage,
        [runtime],
        client=scheduler,
        scheduler_path_mapper=scheduler_path,
    )
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
    assert str(tmp_path) not in script
    assert "/mnt/images/qasmtrans.sif" in script
    assert "/mnt/staging/" in script

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


def test_virtual_slurm_runner_uses_normal_worker_and_verified_oci_identity(
    tmp_path: Path,
) -> None:
    checkout = tmp_path / "cluster"
    (checkout / "shared-dir").mkdir(parents=True)
    cluster = SlurmDockerCluster.from_manifest(CLUSTER_MANIFEST, checkout)
    target = cluster.development_execution_target()
    storage = cluster.development_storage_profile()
    runtimes = cluster.development_runtimes()
    registry = load_document(REGISTRY)
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
        execution_target="development-slurm-docker",
        created_by="test-user",
    )
    scheduler = FakeSlurm()
    runner = SlurmDockerClusterRunner(
        target,
        storage,
        runtimes,
        cluster.runtime_images,
        host_shared_root=cluster.shared_host_directory,
        scheduler_shared_root=str(cluster.shared_container_directory),
        client=scheduler,
        scheduler_path_mapper=cluster.map_shared_path,
    )
    worker = AsyncWorker(
        engine,
        RegistryBoundAsyncRunner(runner, registry),
        worker_id="virtual-slurm-worker",
    )

    assert worker.run_once()
    submitted = engine.get_run(run["id"])
    attempt = submitted["tasks"][0]["attempts"][0]
    script = scheduler.submissions[0].read_text(encoding="utf-8")
    assert attempt["target_handle"] == "41001"
    assert "#SBATCH --account=development" in script
    assert "#SBATCH --partition=normal" in script
    assert "/usr/local/bin/qhpc-oci-shim exec" in script
    assert "/mnt/qhpc/images/qasmtrans-transpile-linux-amd64.oci.json" in script
    assert ":/inputs:ro" in script
    assert ":/outputs:rw" in script

    attempt_root = (
        Path(storage["spec"]["roots"]["task_staging"])
        / run["id"]
        / "transpile"
        / attempt["id"]
    )
    assert (attempt_root / "inputs/circuit.qasm").is_file()
    (attempt_root / "outputs/circuit.qasm").write_text(
        "OPENQASM 2.0;\nqreg q[2];\n",
        encoding="utf-8",
    )
    (attempt_root / "stage-timing.tsv").write_text(
        "application\t100\t125\n",
        encoding="ascii",
    )
    scheduler.state = "succeeded"

    restarted = AsyncWorker(
        engine,
        RegistryBoundAsyncRunner(runner, registry),
        worker_id="virtual-slurm-worker-restarted",
    )
    assert restarted.run_once()
    completed = engine.get_run(run["id"])
    assert completed["state"] == "succeeded"
    assert completed["tasks"][0]["outputs"]["circuit"].startswith("artifact-")
    assert any(
        event["stage"] == "target.application" and event["duration_ms"] == 25
        for event in completed["events"]
    )


def _verification_parameters(runtime: dict) -> dict:
    values = {
        name: binding["fixed"]
        for name, binding in runtime["spec"]["execution"]["parameters"].items()
        if "fixed" in binding
    }
    by_argument = {
        binding["argument"]: (name, binding["type"])
        for name, binding in runtime["spec"]["execution"]["parameters"].items()
        if "argument" in binding
    }
    arguments = iter(runtime["spec"]["verification"]["arguments"])
    for argument in arguments:
        name, value_type = by_argument[argument]
        raw = next(arguments)
        if value_type == "integer":
            value = int(raw)
        elif value_type == "number":
            value = float(raw)
        elif value_type == "boolean":
            value = raw.lower() == "true"
        else:
            value = raw
        values[name] = value
    return values


@pytest.mark.parametrize("runtime_path", INITIAL_RUNTIMES)
def test_initial_operation_runtimes_conform_to_slurm_apptainer_runner(
    tmp_path: Path,
    runtime_path: Path,
) -> None:
    case_root = tmp_path / runtime_path.parent.name
    case_root.mkdir()
    runtime, target, storage = _contracts(case_root, runtime_path)
    execution = runtime["spec"]["execution"]
    verification = runtime["spec"]["verification"]
    inputs: dict[str, dict] = {}
    fixture = verification.get("fixture")
    if fixture is not None:
        source = ROOT / fixture["path"]
        port = next(
            name
            for name, path in execution["ports"]["inputs"].items()
            if path == fixture["mount_path"]
        )
        artifact = ArtifactResult.from_path("qhpc.test-input@1", source)
        inputs[port] = {
            "uri": artifact.uri,
            "checksum": artifact.checksum,
            "size_bytes": artifact.size_bytes,
        }

    work = case_root / "work"
    work.mkdir()
    metadata = runtime["metadata"]
    release = runtime["spec"]["release"]
    request = TaskRequest(
        run_id=f"run-{metadata['component']}",
        node_id="operation",
        attempt_id=f"attempt-{metadata['component']}",
        capability_id=metadata["capability"],
        capability_version=metadata["version"],
        operation_id=metadata["operation"],
        runtime_reference=release["apptainer_reference"],
        runtime_digest=release["apptainer_digest"],
        parameters=_verification_parameters(runtime),
        inputs=inputs,
        output_types={
            name: "qhpc.test-output@1"
            for name in execution["ports"]["outputs"]
        },
        work_directory=work,
        project=metadata["project"],
        execution_target=target["metadata"]["id"],
        execution_class="batch-hpc",
        runtime_type="apptainer",
        resources={
            "cpu": 1,
            "memory_mb": 1024,
            "gpu": 0,
            "walltime_seconds": verification["timeout_seconds"],
        },
    )
    scheduler = FakeSlurm()
    runner = SlurmApptainerRunner(target, storage, [runtime], client=scheduler)

    submission = runner.submit(request)
    script = scheduler.submissions[0].read_text(encoding="utf-8")
    assert submission.handle == "41001"
    assert execution["entrypoint"][0] in script
    assert "--network none" in script

    attempt_root = (
        Path(storage["spec"]["roots"]["task_staging"])
        / request.run_id
        / request.node_id
        / request.attempt_id
    )
    output_mount = next(
        mount["path"]
        for mount in execution["mounts"]
        if mount["kind"] == "output"
    )
    for container_path in execution["ports"]["outputs"].values():
        relative = Path(container_path).relative_to(output_mount)
        output = attempt_root / "outputs" / relative
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("accepted fixture output\n", encoding="utf-8")
    scheduler.state = "succeeded"

    assert runner.poll(request, submission.handle).state == "succeeded"
    result = runner.collect(request, submission.handle)
    assert set(result.outputs) == set(execution["ports"]["outputs"])
    runner.finalize(request, succeeded=True)
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
