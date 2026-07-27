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
    account: str | None = None
    qos: str | None = None


@dataclass(frozen=True)
class ApptainerBind:
    source: str
    destination: str
    read_only: bool


@dataclass(frozen=True)
class NodeLocalStaging:
    namespace: str
    stage_image: bool = True
    stage_read_only_binds: bool = True
    minimum_free_mb: int | None = None


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
    binds: Sequence[ApptainerBind] = (),
    working_directory: str = "/work",
    stdout_path: str | None = None,
    stderr_path: str | None = None,
    telemetry_path: str | None = None,
    apptainer_executable: str = "apptainer",
    node_local: NodeLocalStaging | None = None,
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
    for label, value in (
        ("account", resources.account),
        ("QoS", resources.qos),
    ):
        if value and not re.fullmatch(r"[A-Za-z0-9_.-]+", value):
            raise ValueError(f"invalid Slurm {label}")
    if not (
        re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", apptainer_executable)
        or (
            apptainer_executable.startswith("/")
            and not any(character.isspace() for character in apptainer_executable)
        )
    ):
        raise ValueError("invalid Apptainer executable")
    if not working_directory.startswith("/") or any(
        character.isspace() for character in working_directory
    ):
        raise ValueError("container working directory must be absolute")
    for path, label in (
        (stdout_path, "stdout"),
        (stderr_path, "stderr"),
        (telemetry_path, "telemetry"),
    ):
        if path is not None and (
            not path.startswith("/") or "\n" in path or "\r" in path
        ):
            raise ValueError(f"{label} path must be absolute")
    for bind in binds:
        if not bind.source.startswith("/") or "\n" in bind.source:
            raise ValueError("Apptainer bind source must be absolute")
        if (
            not bind.destination.startswith("/")
            or any(character.isspace() for character in bind.destination)
            or ":" in bind.destination
        ):
            raise ValueError("Apptainer bind destination must be absolute")
    if node_local:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", node_local.namespace):
            raise ValueError("invalid node-local staging namespace")
        if node_local.minimum_free_mb is not None and node_local.minimum_free_mb < 1:
            raise ValueError("node-local minimum free space must be positive")
        if node_local.stage_image and image.startswith(("file://", "oras://")):
            raise ValueError("node-local image staging requires an absolute image path")

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
    if resources.account:
        directives.append(f"#SBATCH --account={resources.account}")
    if resources.qos:
        directives.append(f"#SBATCH --qos={resources.qos}")
    if stdout_path:
        directives.append(f"#SBATCH --output={stdout_path}")
    if stderr_path:
        directives.append(f"#SBATCH --error={stderr_path}")

    setup = ["", "set -euo pipefail", "umask 077"]
    image_token = shlex.quote(image)
    bind_tokens = [
        shlex.quote(
            f"{bind.source}:{bind.destination}:{'ro' if bind.read_only else 'rw'}"
        )
        for bind in binds
    ]
    if node_local:
        setup.extend(
            [
                (
                    'QHPC_NODE_ROOT="${SLURM_TMPDIR:'
                    "?SLURM_TMPDIR is required"
                    f'}}/qhpc-{node_local.namespace}"'
                ),
                'mkdir -p -- "$QHPC_NODE_ROOT"',
            ]
        )
        if node_local.minimum_free_mb is not None:
            setup.extend(
                [
                    (
                        'QHPC_FREE_MB=$(df -Pm -- "$SLURM_TMPDIR" '
                        "| awk 'NR==2 {print $4}')"
                    ),
                    (f'if [ "$QHPC_FREE_MB" -lt {node_local.minimum_free_mb} ]; then'),
                    '  printf "%s\\n" "insufficient SLURM_TMPDIR space" >&2',
                    "  exit 74",
                    "fi",
                ]
            )
        stage_start = "QHPC_STAGE_START=$(date +%s%3N)"
        if telemetry_path:
            setup.append(stage_start)
        if node_local.stage_image:
            setup.append(f'cp -- {shlex.quote(image)} "$QHPC_NODE_ROOT/runtime.sif"')
            image_token = '"$QHPC_NODE_ROOT/runtime.sif"'
        if node_local.stage_read_only_binds:
            updated_binds: list[str] = []
            for index, bind in enumerate(binds):
                if not bind.read_only:
                    updated_binds.append(bind_tokens[index])
                    continue
                local = f"$QHPC_NODE_ROOT/bind-{index}"
                setup.extend(
                    [
                        f'mkdir -p -- "{local}"',
                        (f'cp -a -- {shlex.quote(bind.source)}/. "{local}/"'),
                    ]
                )
                updated_binds.append(f'"{local}:{bind.destination}:ro"')
            bind_tokens = updated_binds
        if telemetry_path:
            setup.extend(
                [
                    "QHPC_STAGE_END=$(date +%s%3N)",
                    (
                        "printf '%s\\t%s\\t%s\\n' node-local-stage "
                        '"$QHPC_STAGE_START" "$QHPC_STAGE_END" >> '
                        f"{shlex.quote(telemetry_path)}"
                    ),
                ]
            )

    command_tokens = [
        shlex.quote(apptainer_executable),
        "exec",
        "--containall",
        "--cleanenv",
        "--net",
        "--network",
        "none",
        "--no-home",
        "--pwd",
        shlex.quote(working_directory),
    ]
    for bind in bind_tokens:
        command_tokens.extend(["--bind", bind])
    command_tokens.extend([image_token, *(shlex.quote(token) for token in entrypoint)])
    command_tokens.extend(shlex.quote(token) for token in arguments)
    command = " ".join(command_tokens)
    if telemetry_path:
        setup.extend(
            [
                "QHPC_STAGE_START=$(date +%s%3N)",
                "set +e",
                command,
                "QHPC_EXIT_CODE=$?",
                "set -e",
                "QHPC_STAGE_END=$(date +%s%3N)",
                (
                    "printf '%s\\t%s\\t%s\\n' application "
                    '"$QHPC_STAGE_START" "$QHPC_STAGE_END" >> '
                    f"{shlex.quote(telemetry_path)}"
                ),
                'exit "$QHPC_EXIT_CODE"',
            ]
        )
    else:
        setup.append("exec " + command)
    return "\n".join([*directives, *setup, ""])


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

    def find_by_name(self, job_name: str) -> str | None:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", job_name):
            raise ValueError("invalid Slurm job name")
        queued = self.executor(
            [self.squeue, "--noheader", "--name", job_name, "--format=%A"]
        )
        if queued.returncode:
            raise RuntimeError(queued.stderr.strip() or "squeue failed")
        for line in queued.stdout.splitlines():
            candidate = line.strip()
            if JOB_ID.fullmatch(candidate):
                return candidate
        history = self.executor(
            [
                self.sacct,
                "--noheader",
                "--parsable2",
                "--name",
                job_name,
                "--format=JobIDRaw,JobName",
            ]
        )
        if history.returncode:
            raise RuntimeError(history.stderr.strip() or "sacct failed")
        for line in history.stdout.splitlines():
            job_id, separator, name = line.strip().partition("|")
            if separator and name == job_name and JOB_ID.fullmatch(job_id):
                return job_id
        return None

    def cancel(self, job_id: str) -> None:
        checked = self._job_id(job_id)
        result = self.executor([self.scancel, checked])
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or "scancel failed")
