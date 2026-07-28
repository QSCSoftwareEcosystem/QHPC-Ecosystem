"""Development-only Slurm cluster transport backed by Docker Compose."""

from __future__ import annotations

import re
import shlex
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable, Sequence
from uuid import uuid4

from .contract import validate_contract
from .slurm import CommandResult, SlurmClient


CommandRunner = Callable[[Sequence[str]], CommandResult]
Sleeper = Callable[[float], None]
Clock = Callable[[], float]
TokenFactory = Callable[[], str]

READY_NODE_STATES = {"allocated", "completing", "idle", "mixed"}
TERMINAL_JOB_STATES = {"succeeded", "failed", "canceled"}


class SlurmTestClusterError(RuntimeError):
    """Raised when a development Slurm cluster cannot be managed or verified."""


@dataclass(frozen=True)
class ClusterStatus:
    compose: CommandResult
    controller: CommandResult
    nodes: CommandResult

    @property
    def ready(self) -> bool:
        states = _node_states(self.nodes.stdout)
        return (
            self.controller.returncode == 0
            and self.nodes.returncode == 0
            and bool(states & READY_NODE_STATES)
        )


@dataclass(frozen=True)
class SlurmSmokeResult:
    completed_job_id: str
    completed_state: str
    canceled_job_id: str | None
    canceled_state: str | None
    output: str
    duration_ms: int


def _execute(command: Sequence[str]) -> CommandResult:
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except OSError as exc:
        raise SlurmTestClusterError(
            f"cannot execute {command[0] if command else 'command'}: {exc}"
        ) from exc
    return CommandResult(result.returncode, result.stdout, result.stderr)


def _node_states(output: str) -> set[str]:
    states: set[str] = set()
    for line in output.splitlines():
        columns = line.strip().split("|")
        value = columns[1] if len(columns) > 1 else columns[0]
        state = value.lower().split("+", 1)[0].rstrip("*~#")
        if state:
            states.add(state)
    return states


def _repository_identity(value: str) -> str:
    normalized = value.strip().rstrip("/")
    return normalized[:-4] if normalized.endswith(".git") else normalized


def _safe_relative_path(root: Path, value: str, label: str) -> Path:
    relative = PurePosixPath(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise SlurmTestClusterError(f"{label} must be a safe relative path")
    destination = (root / Path(*relative.parts)).resolve()
    try:
        destination.relative_to(root.resolve())
    except ValueError as exc:
        raise SlurmTestClusterError(f"{label} escapes its allowed root") from exc
    return destination


class DockerComposeSlurmExecutor:
    """Run Slurm CLI tokens inside a Compose-managed controller service."""

    def __init__(
        self,
        compose_command: Sequence[str],
        service: str,
        working_directory: str,
        *,
        runner: CommandRunner = _execute,
    ) -> None:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", service):
            raise SlurmTestClusterError("invalid Compose controller service")
        directory = PurePosixPath(working_directory)
        if not directory.is_absolute() or ".." in directory.parts:
            raise SlurmTestClusterError(
                "Compose controller working directory must be absolute"
            )
        if not compose_command:
            raise SlurmTestClusterError("Compose command cannot be empty")
        self.compose_command = tuple(compose_command)
        self.service = service
        self.working_directory = str(directory)
        self.runner = runner

    def __call__(self, command: Sequence[str]) -> CommandResult:
        if not command or any(not token or "\x00" in token for token in command):
            raise SlurmTestClusterError("Slurm command contains an invalid token")
        return self.runner(
            [
                *self.compose_command,
                "exec",
                "-T",
                "--workdir",
                self.working_directory,
                self.service,
                *command,
            ]
        )


class SlurmDockerCluster:
    """Manage and smoke-test one pinned Slurm Docker cluster checkout."""

    def __init__(
        self,
        document: dict,
        manifest_path: Path,
        checkout: Path,
        *,
        runner: CommandRunner = _execute,
        sleeper: Sleeper = time.sleep,
        clock: Clock = time.monotonic,
        token_factory: TokenFactory = lambda: uuid4().hex[:12],
    ) -> None:
        self.document = document
        self.manifest_path = manifest_path.resolve()
        self.checkout = checkout.expanduser().resolve()
        self.runner = runner
        self.sleeper = sleeper
        self.clock = clock
        self.token_factory = token_factory

        compose = self.document["spec"]["compose"]
        services = set(compose["services"])
        if compose["controller_service"] not in services:
            raise SlurmTestClusterError(
                "controller service must be included in the started services"
            )
        missing_workers = set(compose["worker_services"]) - services
        if missing_workers:
            raise SlurmTestClusterError(
                "worker services are not started: "
                + ", ".join(sorted(missing_workers))
            )
        if (
            not self.document["spec"]["security"]["start_rest_api"]
            and "slurmrestd" in services
        ):
            raise SlurmTestClusterError(
                "slurmrestd cannot be started when REST exposure is disabled"
            )

    @classmethod
    def from_manifest(
        cls,
        manifest: str | Path,
        checkout: str | Path | None = None,
        **kwargs: object,
    ) -> SlurmDockerCluster:
        manifest_path = Path(manifest).expanduser().resolve()
        document = validate_contract("slurm-test-cluster", manifest_path)
        if checkout is None:
            metadata = document["metadata"]
            revision = document["spec"]["source"]["revision"][:12]
            checkout_path = (
                Path.cwd()
                / ".qhpc"
                / "test-clusters"
                / f"{metadata['id']}-{revision}"
            )
        else:
            checkout_path = Path(checkout)
        return cls(document, manifest_path, checkout_path, **kwargs)

    @property
    def source(self) -> dict:
        return self.document["spec"]["source"]

    @property
    def compose(self) -> dict:
        return self.document["spec"]["compose"]

    @property
    def compatibility(self) -> dict:
        return self.document["spec"]["compatibility"]

    @property
    def shared_host_directory(self) -> Path:
        return _safe_relative_path(
            self.checkout,
            self.compose["shared_directory"]["host"],
            "shared host directory",
        )

    @property
    def build_ca_path(self) -> Path:
        return _safe_relative_path(
            self.checkout,
            self.compatibility["build_ca_destination"],
            "build CA destination",
        )

    @property
    def shared_container_directory(self) -> PurePosixPath:
        return PurePosixPath(self.compose["shared_directory"]["container"])

    @property
    def compose_command(self) -> tuple[str, ...]:
        compose_file = _safe_relative_path(
            self.checkout, self.compose["compose_file"], "Compose file"
        )
        command = [
            "docker",
            "compose",
            "--project-name",
            self.compose["project_name"],
            "--project-directory",
            str(self.checkout),
            "--file",
            str(compose_file),
        ]
        for value in self.compose["overrides"]:
            override = _safe_relative_path(
                self.manifest_path.parent, value, "Compose override"
            )
            command.extend(["--file", str(override)])
        return tuple(command)

    @property
    def slurm_executor(self) -> DockerComposeSlurmExecutor:
        return DockerComposeSlurmExecutor(
            self.compose_command,
            self.compose["controller_service"],
            str(self.shared_container_directory),
            runner=self.runner,
        )

    def _checked(self, command: Sequence[str], action: str) -> CommandResult:
        result = self.runner(command)
        if result.returncode:
            detail = result.stderr.strip() or result.stdout.strip() or "no output"
            raise SlurmTestClusterError(f"{action} failed: {detail}")
        return result

    def _git(self, *arguments: str) -> list[str]:
        return ["git", "-C", str(self.checkout), *arguments]

    def prepare(self, build_ca: str | Path | None = None) -> Path:
        if self.checkout.exists() and not self.checkout.is_dir():
            raise SlurmTestClusterError(
                f"test-cluster checkout is not a directory: {self.checkout}"
            )
        if not (self.checkout / ".git").is_dir():
            if self.checkout.exists() and any(self.checkout.iterdir()):
                raise SlurmTestClusterError(
                    f"test-cluster checkout is non-empty and is not Git: {self.checkout}"
                )
            self.checkout.parent.mkdir(parents=True, exist_ok=True)
            self._checked(
                [
                    "git",
                    "clone",
                    "--branch",
                    self.source["branch"],
                    "--single-branch",
                    self.source["repository"],
                    str(self.checkout),
                ],
                "test-cluster clone",
            )

        origin = self._checked(
            self._git("remote", "get-url", "origin"), "test-cluster origin check"
        ).stdout.strip()
        if _repository_identity(origin) != _repository_identity(
            self.source["repository"]
        ):
            raise SlurmTestClusterError(
                f"unexpected test-cluster origin: {origin or 'missing'}"
            )

        revision = self.source["revision"]
        head = self._checked(
            self._git("rev-parse", "HEAD"), "test-cluster revision check"
        ).stdout.strip()
        if head != revision:
            dirty = self._checked(
                self._git("status", "--porcelain", "--untracked-files=no"),
                "test-cluster worktree check",
            ).stdout.strip()
            if dirty:
                raise SlurmTestClusterError(
                    "test-cluster checkout has tracked changes and cannot be repinned"
                )
            self._checked(
                self._git("cat-file", "-e", f"{revision}^{{commit}}"),
                "pinned test-cluster revision lookup",
            )
            self._checked(
                self._git("checkout", "--detach", revision),
                "test-cluster revision checkout",
            )

        self._install_compatibility_files()
        self._install_build_ca(build_ca)
        self._assert_prepared()
        return self.checkout

    def _compatibility_paths(self) -> list[tuple[Path, Path]]:
        paths: list[tuple[Path, Path]] = []
        for item in self.compatibility["files"]:
            source = _safe_relative_path(
                self.manifest_path.parent,
                item["source"],
                "compatibility source",
            )
            destination = _safe_relative_path(
                self.checkout,
                item["destination"],
                "compatibility destination",
            )
            paths.append((source, destination))
        return paths

    def _install_compatibility_files(self) -> None:
        for source, destination in self._compatibility_paths():
            if not source.is_file():
                raise SlurmTestClusterError(
                    f"compatibility source not found: {source}"
                )
            payload = source.read_bytes()
            if destination.is_file() and destination.read_bytes() == payload:
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(payload)

    def _install_build_ca(self, build_ca: str | Path | None) -> None:
        if build_ca is None:
            if not self.build_ca_path.exists():
                self.build_ca_path.write_bytes(b"")
            return
        source = Path(build_ca).expanduser().resolve()
        if not source.is_file():
            raise SlurmTestClusterError(f"build CA certificate not found: {source}")
        payload = source.read_bytes()
        if b"PRIVATE KEY" in payload:
            raise SlurmTestClusterError(
                "build CA input must not contain a private key"
            )
        if (
            payload.count(b"-----BEGIN CERTIFICATE-----") < 1
            or payload.count(b"-----BEGIN CERTIFICATE-----")
            != payload.count(b"-----END CERTIFICATE-----")
        ):
            raise SlurmTestClusterError(
                "build CA input must contain PEM certificates"
            )
        self.build_ca_path.write_bytes(payload)

    def _assert_prepared(self) -> None:
        if not (self.checkout / ".git").is_dir():
            raise SlurmTestClusterError(
                f"test-cluster checkout is not prepared: {self.checkout}"
            )
        head = self._checked(
            self._git("rev-parse", "HEAD"), "test-cluster revision check"
        ).stdout.strip()
        if head != self.source["revision"]:
            raise SlurmTestClusterError(
                f"test-cluster revision is {head}; expected {self.source['revision']}"
            )
        dirty = self._checked(
            self._git("status", "--porcelain", "--untracked-files=no"),
            "test-cluster worktree check",
        ).stdout.strip()
        if dirty:
            raise SlurmTestClusterError(
                "test-cluster checkout contains tracked modifications"
            )
        for source, destination in self._compatibility_paths():
            if not source.is_file():
                raise SlurmTestClusterError(
                    f"compatibility source not found: {source}"
                )
            if (
                not destination.is_file()
                or destination.read_bytes() != source.read_bytes()
            ):
                raise SlurmTestClusterError(
                    f"compatibility file is missing or modified: {destination}"
                )
        if not self.build_ca_path.is_file():
            raise SlurmTestClusterError(
                f"build CA compatibility file is missing: {self.build_ca_path}"
            )
        if b"PRIVATE KEY" in self.build_ca_path.read_bytes():
            raise SlurmTestClusterError(
                "build CA compatibility file contains a private key"
            )

        compose_file = _safe_relative_path(
            self.checkout, self.compose["compose_file"], "Compose file"
        )
        if not compose_file.is_file():
            raise SlurmTestClusterError(f"Compose file not found: {compose_file}")
        for value in self.compose["overrides"]:
            override = _safe_relative_path(
                self.manifest_path.parent, value, "Compose override"
            )
            if not override.is_file():
                raise SlurmTestClusterError(
                    f"Compose override not found: {override}"
                )
        if not (self.checkout / "LICENSE").is_file():
            raise SlurmTestClusterError("test-cluster source license file is missing")
        self.shared_host_directory.mkdir(parents=True, exist_ok=True)

    def map_shared_path(self, path: Path) -> str:
        resolved = path.expanduser().resolve()
        try:
            relative = resolved.relative_to(self.shared_host_directory.resolve())
        except ValueError as exc:
            raise SlurmTestClusterError(
                f"path is outside the test-cluster shared directory: {resolved}"
            ) from exc
        return str(
            self.shared_container_directory.joinpath(PurePosixPath(*relative.parts))
        )

    def _wait_for_controller(self, deadline: float) -> None:
        last = ""
        while self.clock() < deadline:
            result = self.slurm_executor(["scontrol", "ping"])
            last = result.stderr.strip() or result.stdout.strip()
            if result.returncode == 0:
                return
            self.sleeper(self.compose["poll_interval_seconds"])
        raise SlurmTestClusterError(
            f"Slurm controller did not become ready: {last or 'no response'}"
        )

    def _ensure_accounting_cluster(self, deadline: float) -> None:
        name = self.compose["cluster_name"]
        last = ""
        while self.clock() < deadline:
            result = self.slurm_executor(
                [
                    "sacctmgr",
                    "--noheader",
                    "--parsable2",
                    "show",
                    "cluster",
                    "where",
                    f"Cluster={name}",
                    "format=Cluster",
                ]
            )
            last = result.stderr.strip() or result.stdout.strip()
            clusters = {
                line.strip().split("|", 1)[0]
                for line in result.stdout.splitlines()
                if line.strip()
            }
            if result.returncode == 0 and name in clusters:
                return
            if result.returncode == 0:
                added = self.slurm_executor(
                    ["sacctmgr", "--immediate", "add", "cluster", f"Name={name}"]
                )
                if added.returncode == 0:
                    self._checked(
                        [
                            *self.compose_command,
                            "restart",
                            "slurmdbd",
                            self.compose["controller_service"],
                        ],
                        "Slurm accounting restart",
                    )
                    self._wait_for_controller(deadline)
                    return
                last = added.stderr.strip() or added.stdout.strip()
            self.sleeper(self.compose["poll_interval_seconds"])
        raise SlurmTestClusterError(
            f"Slurm accounting cluster was not registered: {last or 'no response'}"
        )

    def _wait_for_nodes(self, deadline: float) -> None:
        last = ""
        resumed = False
        while self.clock() < deadline:
            result = self.slurm_executor(
                [
                    "sinfo",
                    "--noheader",
                    "--format=%T",
                    "--partition",
                    self.compose["partition"],
                ]
            )
            states = _node_states(result.stdout)
            last = result.stderr.strip() or result.stdout.strip()
            if result.returncode == 0 and states & READY_NODE_STATES:
                return
            if (
                result.returncode == 0
                and states
                and not resumed
                and states <= {"down", "drained", "draining", "unknown"}
            ):
                self.slurm_executor(
                    ["scontrol", "update", "NodeName=ALL", "State=RESUME"]
                )
                resumed = True
            self.sleeper(self.compose["poll_interval_seconds"])
        raise SlurmTestClusterError(
            f"Slurm workers did not become ready: {last or 'no response'}"
        )

    def start(self, timeout_seconds: int | None = None) -> ClusterStatus:
        self._assert_prepared()
        timeout = timeout_seconds or self.compose["readiness_timeout_seconds"]
        if timeout < 1:
            raise SlurmTestClusterError("cluster readiness timeout must be positive")
        deadline = self.clock() + timeout
        self._checked(
            [
                *self.compose_command,
                "up",
                "--build",
                "--detach",
                "--remove-orphans",
                *self.compose["services"],
            ],
            "Slurm test-cluster start",
        )
        self._wait_for_controller(deadline)
        self._ensure_accounting_cluster(deadline)
        self._wait_for_nodes(deadline)
        return self.status()

    def status(self) -> ClusterStatus:
        self._assert_prepared()
        compose = self.runner([*self.compose_command, "ps"])
        controller = self.slurm_executor(["scontrol", "ping"])
        nodes = self.slurm_executor(
            [
                "sinfo",
                "--noheader",
                "--format=%N|%T|%C",
                "--partition",
                self.compose["partition"],
            ]
        )
        return ClusterStatus(compose=compose, controller=controller, nodes=nodes)

    def _wait_for_job(
        self,
        client: SlurmClient,
        job_id: str,
        expected: set[str],
        deadline: float,
    ) -> str:
        last_state = "unknown"
        last_error = ""
        while self.clock() < deadline:
            try:
                last_state = client.status(job_id)
                last_error = ""
            except RuntimeError as exc:
                last_error = str(exc)
            if last_state in expected:
                return last_state
            if last_state in TERMINAL_JOB_STATES:
                return last_state
            self.sleeper(self.compose["poll_interval_seconds"])
        detail = last_error or f"last state was {last_state}"
        raise SlurmTestClusterError(
            f"Slurm job {job_id} did not reach {sorted(expected)}: {detail}"
        )

    def smoke(
        self,
        *,
        timeout_seconds: int | None = None,
        verify_cancellation: bool = True,
        keep_artifacts: bool = False,
    ) -> SlurmSmokeResult:
        self._assert_prepared()
        timeout = timeout_seconds or self.compose["readiness_timeout_seconds"]
        if timeout < 1:
            raise SlurmTestClusterError("smoke timeout must be positive")
        token = self.token_factory()
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,31}", token):
            raise SlurmTestClusterError("smoke token is invalid")

        shared = self.shared_host_directory
        container = self.shared_container_directory
        partition = self.compose["partition"]
        marker = f"QHPC_SLURM_SMOKE_OK:{token}"
        completion_script = shared / f"qhpc-smoke-{token}.sbatch"
        completion_prefix = f"qhpc-smoke-{token}"
        cancellation_script = shared / f"qhpc-cancel-{token}.sbatch"
        cancellation_prefix = f"qhpc-cancel-{token}"
        completion_script.write_text(
            "\n".join(
                [
                    "#!/usr/bin/env bash",
                    f"#SBATCH --job-name=qhpc-smoke-{token}",
                    f"#SBATCH --partition={partition}",
                    "#SBATCH --time=00:02:00",
                    f"#SBATCH --output={container}/{completion_prefix}-%j.out",
                    f"#SBATCH --error={container}/{completion_prefix}-%j.err",
                    "set -euo pipefail",
                    f"printf '%s\\n' {shlex.quote(marker)}",
                    "hostname",
                    "",
                ]
            ),
            encoding="utf-8",
        )

        client = SlurmClient(
            executor=self.slurm_executor,
            script_path_mapper=self.map_shared_path,
        )
        started = self.clock()
        completed_job_id: str | None = None
        canceled_job_id: str | None = None
        completed_state = "unknown"
        canceled_state: str | None = None
        output = ""
        completion_terminal = False
        cancellation_terminal = False
        cleanup: list[Path] = [completion_script]
        try:
            completed_job_id = client.submit(completion_script)
            deadline = self.clock() + timeout
            completed_state = self._wait_for_job(
                client,
                completed_job_id,
                {"succeeded"},
                deadline,
            )
            if completed_state != "succeeded":
                raise SlurmTestClusterError(
                    f"Slurm smoke job {completed_job_id} ended as {completed_state}"
                )
            completion_terminal = True

            completion_output = shared / f"{completion_prefix}-{completed_job_id}.out"
            completion_error = shared / f"{completion_prefix}-{completed_job_id}.err"
            cleanup.extend([completion_output, completion_error])
            if not completion_output.is_file():
                raise SlurmTestClusterError(
                    f"Slurm smoke output was not collected: {completion_output}"
                )
            output = completion_output.read_text(encoding="utf-8")
            if marker not in output:
                raise SlurmTestClusterError(
                    "Slurm smoke output does not contain the expected marker"
                )

            if verify_cancellation:
                cancellation_script.write_text(
                    "\n".join(
                        [
                            "#!/usr/bin/env bash",
                            f"#SBATCH --job-name=qhpc-cancel-{token}",
                            f"#SBATCH --partition={partition}",
                            "#SBATCH --time=00:03:00",
                            f"#SBATCH --output={container}/{cancellation_prefix}-%j.out",
                            f"#SBATCH --error={container}/{cancellation_prefix}-%j.err",
                            "set -euo pipefail",
                            "sleep 120",
                            "",
                        ]
                    ),
                    encoding="utf-8",
                )
                cleanup.append(cancellation_script)
                canceled_job_id = client.submit(cancellation_script)
                active_state = self._wait_for_job(
                    client,
                    canceled_job_id,
                    {"queued", "running"},
                    self.clock() + timeout,
                )
                if active_state in TERMINAL_JOB_STATES:
                    raise SlurmTestClusterError(
                        f"cancellation smoke job ended before cancellation: {active_state}"
                    )
                client.cancel(canceled_job_id)
                canceled_state = self._wait_for_job(
                    client,
                    canceled_job_id,
                    {"canceled"},
                    self.clock() + timeout,
                )
                if canceled_state != "canceled":
                    raise SlurmTestClusterError(
                        f"Slurm cancellation job ended as {canceled_state}"
                    )
                cancellation_terminal = True
                cleanup.extend(
                    [
                        shared / f"{cancellation_prefix}-{canceled_job_id}.out",
                        shared / f"{cancellation_prefix}-{canceled_job_id}.err",
                    ]
                )
        except (OSError, RuntimeError, ValueError) as exc:
            if isinstance(exc, SlurmTestClusterError):
                raise
            raise SlurmTestClusterError(
                f"Slurm smoke verification failed: {exc}"
            ) from exc
        finally:
            if completed_job_id and not completion_terminal:
                try:
                    client.cancel(completed_job_id)
                except (RuntimeError, ValueError):
                    pass
            if canceled_job_id and not cancellation_terminal:
                try:
                    client.cancel(canceled_job_id)
                except (RuntimeError, ValueError):
                    pass
            if not keep_artifacts:
                for path in cleanup:
                    path.unlink(missing_ok=True)

        if completed_job_id is None:
            raise SlurmTestClusterError("Slurm smoke job was not submitted")
        return SlurmSmokeResult(
            completed_job_id=completed_job_id,
            completed_state=completed_state,
            canceled_job_id=canceled_job_id,
            canceled_state=canceled_state,
            output=output,
            duration_ms=max(0, round((self.clock() - started) * 1000)),
        )

    def stop(self) -> None:
        self._assert_prepared()
        self._checked(
            [*self.compose_command, "down", "--remove-orphans"],
            "Slurm test-cluster stop",
        )
