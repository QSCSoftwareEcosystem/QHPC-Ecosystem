"""Controlled Slurm and Apptainer submission primitives."""

from __future__ import annotations

import re
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence


JOB_ID = re.compile(r"^[0-9]+(?:_[0-9]+)?$")


@dataclass(frozen=True)
class SlurmResources:
    cpu: int = 1
    memory_mb: int = 1024
    walltime_seconds: int = 600
    gpu: int = 0
    partition: str | None = None


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str = ""


Executor = Callable[[Sequence[str]], CommandResult]


def _execute(command: Sequence[str]) -> CommandResult:
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    return CommandResult(result.returncode, result.stdout, result.stderr)


def classify_state(value: str) -> str:
    state = value.strip().upper().split("+", 1)[0].split(" ", 1)[0]
    if state in {"PENDING", "CONFIGURING", "REQUEUED", "RESIZING"}:
        return "queued"
    if state in {"RUNNING", "COMPLETING", "STAGE_OUT"}:
        return "running"
    if state == "COMPLETED":
        return "succeeded"
    if state in {"CANCELLED", "PREEMPTED"}:
        return "canceled"
    if state in {
        "BOOT_FAIL",
        "DEADLINE",
        "FAILED",
        "NODE_FAIL",
        "OUT_OF_MEMORY",
        "REVOKED",
        "TIMEOUT",
    }:
        return "failed"
    return "unknown"


def render_apptainer_job(
    *,
    image: str,
    entrypoint: Sequence[str],
    arguments: Sequence[str],
    resources: SlurmResources,
    job_name: str,
) -> str:
    """Render a batch script from validated tokens without accepting shell text."""
    if not entrypoint or any(not token for token in entrypoint):
        raise ValueError("entrypoint must contain non-empty tokens")
    if not (
        image.startswith("/")
        or image.startswith("file://")
        or image.startswith("oras://")
    ):
        raise ValueError("Apptainer image must be absolute, file://, or oras://")
    if resources.cpu < 1 or resources.memory_mb < 1 or resources.walltime_seconds < 1:
        raise ValueError("Slurm resources must be positive")
    if resources.gpu < 0:
        raise ValueError("GPU count cannot be negative")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", job_name):
        raise ValueError("invalid Slurm job name")
    if resources.partition and not re.fullmatch(
        r"[A-Za-z0-9_.-]+", resources.partition
    ):
        raise ValueError("invalid Slurm partition")

    minutes, seconds = divmod(resources.walltime_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    directives = [
        "#!/usr/bin/env bash",
        f"#SBATCH --job-name={job_name}",
        f"#SBATCH --cpus-per-task={resources.cpu}",
        f"#SBATCH --mem={resources.memory_mb}M",
        f"#SBATCH --time={hours:02d}:{minutes:02d}:{seconds:02d}",
    ]
    if resources.gpu:
        directives.append(f"#SBATCH --gpus={resources.gpu}")
    if resources.partition:
        directives.append(f"#SBATCH --partition={resources.partition}")
    command = [
        "apptainer",
        "exec",
        "--containall",
        "--cleanenv",
        image,
        *entrypoint,
        *arguments,
    ]
    return "\n".join(
        [*directives, "", "set -euo pipefail", "exec " + shlex.join(command), ""]
    )


class SlurmClient:
    def __init__(
        self,
        *,
        sbatch: str = "sbatch",
        squeue: str = "squeue",
        sacct: str = "sacct",
        scancel: str = "scancel",
        executor: Executor = _execute,
    ) -> None:
        self.sbatch = sbatch
        self.squeue = squeue
        self.sacct = sacct
        self.scancel = scancel
        self.executor = executor

    @staticmethod
    def _job_id(value: str) -> str:
        if not JOB_ID.fullmatch(value):
            raise ValueError(f"invalid Slurm job ID: {value}")
        return value

    def submit(self, script: str | Path) -> str:
        path = Path(script).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Slurm script not found: {path}")
        result = self.executor([self.sbatch, "--parsable", str(path)])
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or "sbatch failed")
        job_id = result.stdout.strip().split(";", 1)[0]
        return self._job_id(job_id)

    def status(self, job_id: str) -> str:
        checked = self._job_id(job_id)
        queued = self.executor(
            [self.squeue, "--noheader", "--format=%T", "--jobs", checked]
        )
        if queued.returncode:
            raise RuntimeError(queued.stderr.strip() or "squeue failed")
        if queued.stdout.strip():
            return classify_state(queued.stdout)
        history = self.executor(
            [
                self.sacct,
                "--noheader",
                "--parsable2",
                "--jobs",
                checked,
                "--format=State",
            ]
        )
        if history.returncode:
            raise RuntimeError(history.stderr.strip() or "sacct failed")
        first = next((line for line in history.stdout.splitlines() if line.strip()), "")
        return classify_state(first.split("|", 1)[0])

    def cancel(self, job_id: str) -> None:
        checked = self._job_id(job_id)
        result = self.executor([self.scancel, checked])
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or "scancel failed")
