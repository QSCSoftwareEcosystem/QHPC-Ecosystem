"""Development-only databucket/Garage object-storage transport backed by Docker Compose."""

from __future__ import annotations

import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from .slurm import CommandResult


CommandRunner = Callable[[Sequence[str]], CommandResult]
Sleeper = Callable[[float], None]
Clock = Callable[[], float]

_PROJECT_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,48}$")


class DatabucketStackError(RuntimeError):
    """Raised when the development databucket/Garage stack cannot be managed."""


@dataclass(frozen=True)
class DatabucketCredentials:
    endpoint: str
    region: str
    bucket: str
    access_key_id: str
    secret_access_key: str


def _execute(command: Sequence[str]) -> CommandResult:
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except OSError as exc:
        raise DatabucketStackError(
            f"cannot execute {command[0] if command else 'command'}: {exc}"
        ) from exc
    return CommandResult(result.returncode, result.stdout, result.stderr)


def _field(output: str, label: str) -> str:
    prefix = f"{label}:"
    for line in output.splitlines():
        if line.strip().startswith(prefix):
            return line.split(":", 1)[1].strip()
    return ""


def _healthy_node_id(status_output: str) -> str | None:
    # Mirrors databucket/scripts/seed-demo.sh's awk parse of `garage status`:
    # skip to the "==== HEALTHY NODES ====" section, skip its column header,
    # then take the first column of the first data row.
    state = 0
    for line in status_output.splitlines():
        if state == 0:
            if line.strip().startswith("==== HEALTHY NODES"):
                state = 1
            continue
        if state == 1:
            state = 2
            continue
        if state == 2 and line.strip():
            return line.split()[0]
    return None


class GarageStack:
    """Manage one databucket/Garage Docker Compose checkout for development.

    Talks only to the interface databucket already documents (docs/usage.md):
    its own docker-compose.yml and the `garage` container's `/garage` CLI —
    never databucket's shell scripts, so this has no dependency on their
    exact wording or exit-code conventions.
    """

    def __init__(
        self,
        checkout: str | Path,
        *,
        compose_file: str = "docker-compose.yml",
        project_name: str = "databucket",
        garage_service: str = "garage",
        garage_webui_service: str = "garage-webui",
        s3_port: int = 3900,
        readiness_timeout_seconds: int = 60,
        poll_interval_seconds: float = 1.0,
        runner: CommandRunner = _execute,
        sleeper: Sleeper = time.sleep,
        clock: Clock = time.monotonic,
    ) -> None:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", garage_service):
            raise DatabucketStackError("invalid Compose garage service")
        self.checkout = Path(checkout).expanduser().resolve()
        self.compose_file = compose_file
        self.project_name = project_name
        self.garage_service = garage_service
        self.garage_webui_service = garage_webui_service
        self.s3_port = s3_port
        self.readiness_timeout_seconds = readiness_timeout_seconds
        self.poll_interval_seconds = poll_interval_seconds
        self.runner = runner
        self.sleeper = sleeper
        self.clock = clock

    @property
    def endpoint(self) -> str:
        return f"http://127.0.0.1:{self.s3_port}"

    @property
    def compose_command(self) -> tuple[str, ...]:
        return (
            "docker",
            "compose",
            "--project-name",
            self.project_name,
            "--project-directory",
            str(self.checkout),
            "--file",
            str(self.checkout / self.compose_file),
        )

    def _garage_command(self, *args: str) -> list[str]:
        return [
            *self.compose_command,
            "exec",
            "-T",
            self.garage_service,
            "/garage",
            *args,
        ]

    def _garage(self, *args: str) -> CommandResult:
        return self.runner(self._garage_command(*args))

    def _checked(self, command: Sequence[str], action: str) -> CommandResult:
        result = self.runner(command)
        if result.returncode:
            detail = result.stderr.strip() or result.stdout.strip() or "no output"
            raise DatabucketStackError(f"{action} failed: {detail}")
        return result

    def prepare(self) -> None:
        if not self.checkout.is_dir():
            raise DatabucketStackError(
                f"databucket checkout not found: {self.checkout}"
            )
        if not (self.checkout / self.compose_file).is_file():
            raise DatabucketStackError(
                f"Compose file not found: {self.checkout / self.compose_file}"
            )
        if not (self.checkout / ".env").is_file():
            raise DatabucketStackError(
                "databucket checkout has no .env — run ./scripts/setup.sh in "
                f"{self.checkout} first"
            )

    def status(self) -> bool:
        """Return True if the Garage node is up and answering admin commands."""
        return self._garage("status").returncode == 0

    def start(self, timeout_seconds: int | None = None) -> None:
        self.prepare()
        timeout = timeout_seconds or self.readiness_timeout_seconds
        if timeout < 1:
            raise DatabucketStackError(
                "databucket readiness timeout must be positive"
            )
        deadline = self.clock() + timeout
        self._checked(
            [
                *self.compose_command,
                "up",
                "-d",
                self.garage_service,
                self.garage_webui_service,
            ],
            "databucket stack start",
        )
        last = ""
        while self.clock() < deadline:
            result = self._garage("status")
            last = result.stderr.strip() or result.stdout.strip()
            if result.returncode == 0:
                return
            self.sleeper(self.poll_interval_seconds)
        raise DatabucketStackError(
            f"Garage did not become ready: {last or 'no response'}"
        )

    def stop(self) -> None:
        self._checked(
            [*self.compose_command, "down", "--remove-orphans"],
            "databucket stack stop",
        )

    def ensure_layout(self) -> None:
        status = self._garage("status")
        if status.returncode != 0:
            raise DatabucketStackError(
                f"Garage is not reachable: {status.stderr.strip() or status.stdout.strip()}"
            )
        if "NO ROLE ASSIGNED" not in status.stdout:
            return
        node_id = _healthy_node_id(status.stdout)
        if not node_id:
            raise DatabucketStackError(
                "could not determine a healthy Garage node ID for layout assignment"
            )
        self._checked(
            self._garage_command("layout", "assign", "-z", "dc1", "-c", "1G", node_id),
            "Garage layout assign",
        )
        self._checked(
            self._garage_command("layout", "apply", "--version", "1"),
            "Garage layout apply",
        )

    def ensure_project(self, project: str) -> DatabucketCredentials:
        """Idempotently provision a project's bucket + scoped key, and return
        the credentials to reach it — reimplements the same idiom as
        databucket/scripts/seed-demo.sh (bucket create/key create/bucket
        allow, skipped when the bucket already exists)."""
        if not _PROJECT_NAME.fullmatch(project):
            raise DatabucketStackError(f"invalid databucket project name: {project}")
        self.ensure_layout()
        bucket = f"proj-{project}"
        key_name = f"proj-{project}-key"
        if self._garage("bucket", "info", bucket).returncode != 0:
            self._checked(
                self._garage_command("bucket", "create", bucket),
                "Garage bucket create",
            )
            self._checked(
                self._garage_command("key", "create", key_name),
                "Garage key create",
            )
            self._checked(
                self._garage_command(
                    "bucket",
                    "allow",
                    "--read",
                    "--write",
                    "--owner",
                    bucket,
                    "--key",
                    key_name,
                ),
                "Garage bucket allow",
            )
        info = self._checked(
            self._garage_command("key", "info", key_name, "--show-secret"),
            "Garage key info",
        )
        access_key_id = _field(info.stdout, "Key ID")
        secret_access_key = _field(info.stdout, "Secret key")
        if not access_key_id or not secret_access_key:
            raise DatabucketStackError(
                f"could not parse Garage key credentials for {key_name}"
            )
        return DatabucketCredentials(
            endpoint=self.endpoint,
            region="garage",
            bucket=bucket,
            access_key_id=access_key_id,
            secret_access_key=secret_access_key,
        )
