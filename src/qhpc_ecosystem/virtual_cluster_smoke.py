"""End-to-end initial-operation smoke suite for the virtual Slurm target."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .contract import load_document
from .engine import WorkflowEngine
from .slurm_runner import SlurmDockerClusterRunner
from .slurm_test_cluster import SlurmDockerCluster
from .worker import AsyncWorker, RegistryBoundAsyncRunner


@dataclass(frozen=True)
class VirtualWorkflowResult:
    workflow_id: str
    run_id: str
    duration_ms: int
    artifact_ids: tuple[str, ...]
    stage_durations_ms: dict[str, int]


def _workflow_cases(root: Path) -> tuple[tuple[Path, dict[str, tuple[str, Path]]], ...]:
    workflows = root / "examples" / "workflows"
    return (
        (
            workflows / "ct-hw-qasm-analysis.yaml",
            {
                "circuit": (
                    "qhpc.quantum-circuit@1",
                    root / "containers/operations/qasmtrans/fixtures/bell.qasm",
                )
            },
        ),
        (workflows / "qec-memory-estimation.yaml", {}),
        (
            workflows / "nwqec-counts.yaml",
            {
                "circuit": (
                    "qhpc.quantum-circuit@1",
                    root / "containers/operations/nwqec/fixtures/clifford.qasm",
                )
            },
        ),
    )


def run_virtual_cluster_smoke(
    cluster: SlurmDockerCluster,
    registry: dict[str, Any],
    state_root: str | Path,
    *,
    timeout_seconds: int = 300,
) -> tuple[VirtualWorkflowResult, ...]:
    if timeout_seconds < 1:
        raise ValueError("virtual cluster smoke timeout must be positive")
    status = cluster.status()
    if not status.ready:
        raise RuntimeError("development Slurm cluster is not ready")
    cluster.verify_runtime_images()

    root = Path(state_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    engine = WorkflowEngine(root / "workbench.sqlite", root / "artifacts")
    target = cluster.development_execution_target()
    storage = cluster.development_storage_profile()
    runner = SlurmDockerClusterRunner(
        target,
        storage,
        cluster.development_runtimes(),
        cluster.runtime_images,
        host_shared_root=cluster.shared_host_directory,
        scheduler_shared_root=str(cluster.shared_container_directory),
        client=cluster.slurm_client,
        scheduler_path_mapper=cluster.map_shared_path,
    )
    worker = AsyncWorker(
        engine,
        RegistryBoundAsyncRunner(runner, registry),
        worker_id="virtual-slurm-smoke",
        poll_interval_seconds=0.2,
    )

    results: list[VirtualWorkflowResult] = []
    for workflow_path, input_files in _workflow_cases(cluster.workspace_root):
        workflow = load_document(workflow_path)
        engine.register_workflow(
            workflow,
            registry,
            created_by="virtual-slurm-smoke",
        )
        inputs = {
            name: engine.register_input_file(
                path,
                artifact_type=artifact_type,
                created_by="virtual-slurm-smoke",
            )["id"]
            for name, (artifact_type, path) in input_files.items()
        }
        started = time.monotonic()
        run = engine.submit_run(
            workflow["metadata"]["id"],
            workflow["metadata"]["version"],
            registry=registry,
            inputs=inputs,
            execution_target=target["metadata"]["id"],
            created_by="virtual-slurm-smoke",
        )
        deadline = started + timeout_seconds
        while run["state"] not in {"succeeded", "failed", "canceled"}:
            if time.monotonic() >= deadline:
                engine.cancel_run(run["id"])
                raise TimeoutError(
                    f"virtual Slurm workflow timed out: {workflow['metadata']['id']}"
                )
            worker.run_once()
            run = engine.get_run(run["id"])
            if run["state"] not in {"succeeded", "failed", "canceled"}:
                time.sleep(0.2)
        if run["state"] != "succeeded":
            failures = [
                attempt.get("failure") or {}
                for task in run["tasks"]
                for attempt in task["attempts"]
                if attempt["state"] == "failed"
            ]
            detail = next(
                (
                    failure.get("message")
                    for failure in failures
                    if failure.get("message")
                ),
                "no failure detail",
            )
            raise RuntimeError(
                f"virtual Slurm workflow failed "
                f"({workflow['metadata']['id']}): {detail}"
            )
        stage_durations = {
            event["stage"]: event["duration_ms"]
            for event in run["events"]
            if event["event_type"] == "stage.completed"
            and event["duration_ms"] is not None
        }
        results.append(
            VirtualWorkflowResult(
                workflow_id=workflow["metadata"]["id"],
                run_id=run["id"],
                duration_ms=max(0, round((time.monotonic() - started) * 1000)),
                artifact_ids=tuple(sorted(run["outputs"].values())),
                stage_durations_ms=stage_durations,
            )
        )
    return tuple(results)
