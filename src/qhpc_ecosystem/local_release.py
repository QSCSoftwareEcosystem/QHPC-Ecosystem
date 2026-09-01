"""Portable single-user lifecycle support for EQO Local."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import time
import uuid
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Any, Mapping, Sequence
from urllib.error import URLError
from urllib.request import urlopen

from .local_assets import default_workflow_paths


LOCAL_SCHEMA_VERSION = 1
LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}


class LocalReleaseError(RuntimeError):
    """Raised when the portable local lifecycle cannot proceed safely."""


@dataclass(frozen=True)
class LocalPaths:
    """Operating-system appropriate locations owned by one EQO Local user."""

    config_root: Path
    data_root: Path
    cache_root: Path
    state_root: Path
    log_root: Path

    @classmethod
    def discover(
        cls,
        home: str | Path | None = None,
        *,
        environ: Mapping[str, str] | None = None,
        platform_name: str | None = None,
    ) -> LocalPaths:
        environment = os.environ if environ is None else environ
        explicit_home = home or environment.get("EQO_HOME")
        if explicit_home:
            root = Path(explicit_home).expanduser().resolve()
            return cls(
                config_root=root / "config",
                data_root=root / "data",
                cache_root=root / "cache",
                state_root=root / "state",
                log_root=root / "logs",
            )

        user_home = Path(environment.get("HOME", str(Path.home()))).expanduser()
        platform_value = platform_name or sys.platform
        if platform_value == "darwin":
            application_support = user_home / "Library" / "Application Support" / "EQO"
            return cls(
                config_root=application_support / "config",
                data_root=application_support / "data",
                cache_root=user_home / "Library" / "Caches" / "EQO",
                state_root=application_support / "state",
                log_root=user_home / "Library" / "Logs" / "EQO",
            )

        config_home = Path(
            environment.get("XDG_CONFIG_HOME", str(user_home / ".config"))
        )
        data_home = Path(
            environment.get("XDG_DATA_HOME", str(user_home / ".local" / "share"))
        )
        cache_home = Path(
            environment.get("XDG_CACHE_HOME", str(user_home / ".cache"))
        )
        state_home = Path(
            environment.get("XDG_STATE_HOME", str(user_home / ".local" / "state"))
        )
        return cls(
            config_root=(config_home / "eqo").resolve(),
            data_root=(data_home / "eqo").resolve(),
            cache_root=(cache_home / "eqo").resolve(),
            state_root=(state_home / "eqo").resolve(),
            log_root=(state_home / "eqo" / "logs").resolve(),
        )

    @property
    def config_file(self) -> Path:
        return self.config_root / "local-v1.json"

    @property
    def database(self) -> Path:
        return self.data_root / "workbench.sqlite"

    @property
    def artifact_root(self) -> Path:
        return self.data_root / "artifacts"

    @property
    def runtime_root(self) -> Path:
        return self.data_root / "runtimes"

    @property
    def service_root(self) -> Path:
        return self.data_root / "services"

    @property
    def export_root(self) -> Path:
        return self.data_root / "exports"

    @property
    def backup_root(self) -> Path:
        return self.data_root / "backups"

    @property
    def update_root(self) -> Path:
        return self.state_root / "updates"

    @property
    def state_file(self) -> Path:
        return self.state_root / "local-state-v1.json"

    @property
    def log_file(self) -> Path:
        return self.log_root / "local-supervisor.log"

    def ensure(self) -> None:
        for path in (
            self.config_root,
            self.data_root,
            self.cache_root,
            self.state_root,
            self.log_root,
            self.artifact_root,
            self.runtime_root,
            self.service_root,
            self.export_root,
            self.backup_root,
        ):
            path.mkdir(parents=True, exist_ok=True)

    def as_dict(self) -> dict[str, str]:
        return {
            "config": str(self.config_root),
            "data": str(self.data_root),
            "cache": str(self.cache_root),
            "state": str(self.state_root),
            "logs": str(self.log_root),
            "artifacts": str(self.artifact_root),
            "runtimes": str(self.runtime_root),
            "exports": str(self.export_root),
            "backups": str(self.backup_root),
        }

    def supervisor_arguments(self) -> tuple[str, ...]:
        return (
            "--config-root",
            str(self.config_root),
            "--data-root",
            str(self.data_root),
            "--cache-root",
            str(self.cache_root),
            "--state-root",
            str(self.state_root),
            "--log-root",
            str(self.log_root),
        )


@dataclass(frozen=True)
class LocalStackConfig:
    """Validated launch configuration persisted without credentials."""

    catalog: str
    registry: str
    deployment_profile: str
    workflows: tuple[str, ...]
    assistant_interface: str
    assistant_source_checkout: str | None
    host: str
    workbench_port: int
    api_port: int
    assistant_port: int
    assistant_enabled: bool = True
    poll_interval_seconds: float = 0.5
    lease_seconds: int = 300
    worker_stale_after_seconds: float = 15.0
    restart_delay_seconds: float = 1.0

    def validate(self) -> None:
        if self.host not in LOOPBACK_HOSTS:
            raise LocalReleaseError(
                "EQO Local must bind to a loopback host "
                f"({', '.join(sorted(LOOPBACK_HOSTS))})"
            )
        ports = [self.workbench_port, self.api_port]
        if self.assistant_enabled:
            ports.append(self.assistant_port)
        if any(port < 1 or port > 65535 for port in ports):
            raise LocalReleaseError("local service ports must be between 1 and 65535")
        if len(set(ports)) != len(ports):
            raise LocalReleaseError("local service ports must be different")
        if self.poll_interval_seconds <= 0:
            raise LocalReleaseError("worker poll interval must be greater than zero")
        if self.lease_seconds <= 0:
            raise LocalReleaseError("worker lease duration must be greater than zero")
        if self.worker_stale_after_seconds <= 0:
            raise LocalReleaseError("worker stale threshold must be greater than zero")
        if self.restart_delay_seconds <= 0:
            raise LocalReleaseError("service restart delay must be greater than zero")

    @property
    def browser_host(self) -> str:
        return "127.0.0.1" if self.host in {"::1", "localhost"} else self.host

    @property
    def workbench_url(self) -> str:
        return f"http://{self.browser_host}:{self.workbench_port}"

    @property
    def api_url(self) -> str:
        return f"http://{self.browser_host}:{self.api_port}"

    @property
    def assistant_url(self) -> str | None:
        if not self.assistant_enabled:
            return None
        return f"http://{self.browser_host}:{self.assistant_port}"

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": LOCAL_SCHEMA_VERSION,
            "catalog": self.catalog,
            "registry": self.registry,
            "deployment_profile": self.deployment_profile,
            "workflows": list(self.workflows),
            "assistant_interface": self.assistant_interface,
            "assistant_source_checkout": self.assistant_source_checkout,
            "assistant_enabled": self.assistant_enabled,
            "host": self.host,
            "workbench_port": self.workbench_port,
            "api_port": self.api_port,
            "assistant_port": self.assistant_port,
            "poll_interval_seconds": self.poll_interval_seconds,
            "lease_seconds": self.lease_seconds,
            "worker_stale_after_seconds": self.worker_stale_after_seconds,
            "restart_delay_seconds": self.restart_delay_seconds,
        }


def _write_json(path: Path, document: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.chmod(0o600)
    os.replace(temporary, path)


def write_local_config(paths: LocalPaths, config: LocalStackConfig) -> None:
    paths.ensure()
    _write_json(paths.config_file, config.as_dict())


def read_local_state(paths: LocalPaths) -> dict[str, Any] | None:
    try:
        document = json.loads(paths.state_file.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as error:
        raise LocalReleaseError(
            f"cannot read EQO Local state {paths.state_file}: {error}"
        ) from error
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        raise LocalReleaseError(f"unsupported EQO Local state: {paths.state_file}")
    return document


def write_local_state(paths: LocalPaths, document: Mapping[str, Any]) -> None:
    payload = dict(document)
    payload["schema_version"] = LOCAL_SCHEMA_VERSION
    payload["updated_at"] = time.time()
    _write_json(paths.state_file, payload)


def process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def process_is_local_supervisor(pid: int) -> bool:
    if not process_alive(pid):
        return False
    try:
        result = subprocess.run(
            ("ps", "-p", str(pid), "-o", "command="),
            capture_output=True,
            text=True,
            check=False,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    command = result.stdout
    return (
        result.returncode == 0
        and "qhpc_ecosystem.cli" in command
        and "local" in command
        and "_supervise" in command
    )


def _fetch_json(url: str, *, timeout_seconds: float = 0.75) -> Any:
    with urlopen(url, timeout=timeout_seconds) as response:
        if response.status != 200:
            raise LocalReleaseError(f"health endpoint returned {response.status}: {url}")
        return json.load(response)


def _endpoint_healthy(url: str) -> bool:
    try:
        payload = _fetch_json(url)
    except (OSError, URLError, ValueError, LocalReleaseError):
        return False
    return isinstance(payload, dict) and payload.get("status") == "ok"


def local_status(paths: LocalPaths) -> dict[str, Any]:
    state = read_local_state(paths)
    if state is None:
        return {
            "schema_version": LOCAL_SCHEMA_VERSION,
            "status": "stopped",
            "supervisor_running": False,
            "services": {},
            "workers": [],
            "paths": paths.as_dict(),
        }

    pid = state.get("supervisor_pid")
    supervisor_running = isinstance(pid, int) and process_is_local_supervisor(pid)
    endpoints = state.get("endpoints", {})
    services: dict[str, bool] = {}
    workers: list[str] = []
    if supervisor_running and isinstance(endpoints, dict):
        workbench = endpoints.get("workbench")
        api = endpoints.get("api")
        assistant = endpoints.get("assistant")
        if isinstance(workbench, str):
            services["workbench"] = _endpoint_healthy(f"{workbench}/health")
        if isinstance(api, str):
            services["api"] = _endpoint_healthy(f"{api}/api/v1/health")
            try:
                worker_payload = _fetch_json(f"{api}/api/v1/workers")
                if isinstance(worker_payload, list):
                    workers = sorted(
                        str(worker["id"])
                        for worker in worker_payload
                        if isinstance(worker, dict)
                        and worker.get("available")
                        and isinstance(worker.get("id"), str)
                    )
            except (OSError, URLError, ValueError, LocalReleaseError):
                workers = []
        if isinstance(assistant, str):
            services["assistant"] = _endpoint_healthy(f"{assistant}/v1/health")

    status = str(state.get("status", "unknown"))
    if not supervisor_running:
        if status not in {"stopped", "failed"}:
            status = "stale"
    elif status == "ready":
        expected_services = {"api", "workbench"}
        if endpoints.get("assistant"):
            expected_services.add("assistant")
        if not all(services.get(name, False) for name in expected_services):
            status = "unhealthy"
        elif "eqo-local-worker" not in workers:
            status = "unhealthy"

    report = dict(state)
    report.update(
        {
            "status": status,
            "supervisor_running": supervisor_running,
            "services": services,
            "workers": workers,
            "paths": paths.as_dict(),
        }
    )
    return report


def _port_available(host: str, port: int) -> bool:
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    value = socket.socket(family, socket.SOCK_STREAM)
    try:
        value.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        value.bind((host, port))
    except OSError:
        return False
    finally:
        value.close()
    return True


def require_available_ports(config: LocalStackConfig) -> None:
    ports = {
        "Workbench": config.workbench_port,
        "API": config.api_port,
    }
    if config.assistant_enabled:
        ports["Assistant"] = config.assistant_port
    unavailable = [
        f"{name} {config.host}:{port}"
        for name, port in ports.items()
        if not _port_available(config.host, port)
    ]
    if unavailable:
        raise LocalReleaseError(
            "local service port is already in use: " + ", ".join(unavailable)
        )


def require_local_dependencies() -> None:
    if importlib.util.find_spec("django") is None:
        raise LocalReleaseError(
            "EQO Local requires the Workbench dependency; install "
            "'qhpc-ecosystem[local]' and run the command again"
        )


def _file_digest(path: str) -> str:
    value = Path(path)
    try:
        digest = hashlib.sha256()
        with value.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
    except OSError as error:
        raise LocalReleaseError(f"cannot read local release input {value}: {error}") from error
    return f"sha256:{digest.hexdigest()}"


def _database_schema_version(database: Path) -> int:
    if not database.is_file():
        return 0
    try:
        with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as connection:
            table = connection.execute(
                "SELECT 1 FROM sqlite_master "
                "WHERE type='table' AND name='schema_migrations'"
            ).fetchone()
            if not table:
                return 0
            row = connection.execute(
                "SELECT MAX(version) FROM schema_migrations"
            ).fetchone()
    except sqlite3.DatabaseError as error:
        raise LocalReleaseError(
            f"cannot inspect EQO Local database {database}: {error}"
        ) from error
    return int(row[0] or 0)


def _database_integrity(database: Path) -> str:
    try:
        with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as connection:
            row = connection.execute("PRAGMA integrity_check").fetchone()
    except sqlite3.DatabaseError as error:
        raise LocalReleaseError(
            f"cannot verify EQO Local database {database}: {error}"
        ) from error
    return str(row[0]) if row else "no integrity result"


def _backup_database(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=False)
    try:
        with sqlite3.connect(source) as source_connection, sqlite3.connect(
            destination
        ) as destination_connection:
            source_connection.backup(destination_connection)
    except (OSError, sqlite3.DatabaseError) as error:
        raise LocalReleaseError(
            f"cannot create database upgrade backup {destination}: {error}"
        ) from error
    destination.chmod(0o600)


def _restore_database_backup(
    database: Path,
    backup: Path,
    failed_database: Path,
) -> None:
    for suffix in ("-wal", "-shm"):
        Path(str(database) + suffix).unlink(missing_ok=True)
    if database.exists():
        os.replace(database, failed_database)
    temporary = database.with_name(f".{database.name}.{os.getpid()}.restore")
    try:
        shutil.copy2(backup, temporary)
        temporary.chmod(0o600)
        os.replace(temporary, database)
    finally:
        temporary.unlink(missing_ok=True)


def prepare_local_database(paths: LocalPaths) -> dict[str, Any]:
    """Apply current migrations with a retained backup and automatic rollback."""

    from .engine import DATABASE_SCHEMA_VERSION, WorkflowEngine

    paths.ensure()
    existed = paths.database.is_file()
    source_version = _database_schema_version(paths.database) if existed else 0
    if source_version > DATABASE_SCHEMA_VERSION:
        raise LocalReleaseError(
            f"EQO Local database schema {source_version} is newer than supported "
            f"schema {DATABASE_SCHEMA_VERSION}; upgrade EQO before opening this data"
        )

    backup_directory: Path | None = None
    backup_database: Path | None = None
    metadata_file: Path | None = None
    if existed and source_version < DATABASE_SCHEMA_VERSION:
        backup_directory = (
            paths.backup_root
            / f"before-upgrade-{_timestamp_for_path()}-{uuid.uuid4().hex[:8]}"
        )
        backup_database = backup_directory / paths.database.name
        metadata_file = backup_directory / "upgrade.json"
        _backup_database(paths.database, backup_database)
        _write_json(
            metadata_file,
            {
                "schema_version": 1,
                "status": "backup-created",
                "from_database_schema": source_version,
                "to_database_schema": DATABASE_SCHEMA_VERSION,
                "database_checksum": _file_digest(str(backup_database)),
                "created_at": time.time(),
            },
        )

    try:
        engine = WorkflowEngine(paths.database, paths.artifact_root)
        current_version = engine.schema_version()
        if current_version != DATABASE_SCHEMA_VERSION:
            raise LocalReleaseError(
                f"database migration stopped at schema {current_version}; "
                f"expected {DATABASE_SCHEMA_VERSION}"
            )
        integrity = _database_integrity(paths.database)
        if integrity != "ok":
            raise LocalReleaseError(
                f"database integrity check failed after migration: {integrity}"
            )
    except Exception as error:
        if backup_database is None or backup_directory is None:
            if isinstance(error, LocalReleaseError):
                raise
            raise LocalReleaseError(
                f"cannot initialize EQO Local database: {error}"
            ) from error
        failed_database = backup_directory / "failed-workbench.sqlite"
        try:
            _restore_database_backup(paths.database, backup_database, failed_database)
            restored_integrity = _database_integrity(paths.database)
            if restored_integrity != "ok":
                raise LocalReleaseError(
                    f"restored database failed integrity check: {restored_integrity}"
                )
            _write_json(
                metadata_file,
                {
                    "schema_version": 1,
                    "status": "rolled-back",
                    "from_database_schema": source_version,
                    "to_database_schema": DATABASE_SCHEMA_VERSION,
                    "database_checksum": _file_digest(str(backup_database)),
                    "error": str(error),
                    "updated_at": time.time(),
                },
            )
        except (OSError, LocalReleaseError) as restore_error:
            raise LocalReleaseError(
                "EQO Local database migration failed and automatic rollback also "
                f"failed: {restore_error}; recovery backup: {backup_database}"
            ) from error
        raise LocalReleaseError(
            "EQO Local database migration failed and the previous database was "
            f"restored; recovery details: {backup_directory}; error: {error}"
        ) from error

    if metadata_file is not None and backup_database is not None:
        _write_json(
            metadata_file,
            {
                "schema_version": 1,
                "status": "upgraded",
                "from_database_schema": source_version,
                "to_database_schema": current_version,
                "database_checksum": _file_digest(str(backup_database)),
                "upgraded_database_checksum": _file_digest(str(paths.database)),
                "updated_at": time.time(),
            },
        )
    return {
        "database_schema_version": current_version,
        "upgraded": backup_directory is not None,
        "from_database_schema_version": source_version,
        "backup": str(backup_directory) if backup_directory is not None else None,
    }


def _timestamp_for_path() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def state_document(
    config: LocalStackConfig,
    paths: LocalPaths,
    *,
    release_version: str,
    supervisor_pid: int,
    status: str,
    services: Mapping[str, int] | None = None,
    error: str | None = None,
    database_schema_version: int | None = None,
    database_backup: str | None = None,
) -> dict[str, Any]:
    document: dict[str, Any] = {
        "release_version": release_version,
        "status": status,
        "supervisor_pid": supervisor_pid,
        "endpoints": {
            "workbench": config.workbench_url,
            "api": config.api_url,
            "assistant": config.assistant_url,
        },
        "services": dict(services or {}),
        "registry_digest": _file_digest(config.registry),
        "deployment_profile_digest": _file_digest(config.deployment_profile),
        "database": str(paths.database),
        "artifact_root": str(paths.artifact_root),
        "log_file": str(paths.log_file),
    }
    if database_schema_version is not None:
        document["database_schema_version"] = database_schema_version
    if database_backup:
        document["database_backup"] = database_backup
    if error:
        document["error"] = error
    return document


def supervisor_command(
    config: LocalStackConfig,
    paths: LocalPaths,
    *,
    python_executable: str = sys.executable,
) -> tuple[str, ...]:
    command = [
        python_executable,
        "-m",
        "qhpc_ecosystem.cli",
        "--catalog",
        config.catalog,
        "local",
        "_supervise",
        *paths.supervisor_arguments(),
        "--registry",
        config.registry,
        "--deployment-profile",
        config.deployment_profile,
        "--assistant-interface",
        config.assistant_interface,
        "--host",
        config.host,
        "--port",
        str(config.workbench_port),
        "--api-port",
        str(config.api_port),
        "--assistant-port",
        str(config.assistant_port),
        "--poll-interval",
        str(config.poll_interval_seconds),
        "--lease-seconds",
        str(config.lease_seconds),
        "--worker-stale-after",
        str(config.worker_stale_after_seconds),
        "--restart-delay",
        str(config.restart_delay_seconds),
    ]
    if config.assistant_source_checkout:
        command.extend(
            ("--assistant-source-checkout", config.assistant_source_checkout)
        )
    if not config.assistant_enabled:
        command.append("--no-assistant")
    for workflow in config.workflows:
        command.extend(("--workflow", workflow))
    return tuple(command)


def launch_local(
    config: LocalStackConfig,
    paths: LocalPaths,
    *,
    release_version: str,
    timeout_seconds: float = 30.0,
    open_browser: bool = False,
) -> dict[str, Any]:
    config.validate()
    if timeout_seconds <= 0:
        raise LocalReleaseError("local startup timeout must be greater than zero")
    require_local_dependencies()
    current = read_local_state(paths)
    if current is not None:
        current_pid = current.get("supervisor_pid")
        if isinstance(current_pid, int) and process_is_local_supervisor(current_pid):
            current_version = current.get("release_version", "unknown")
            raise LocalReleaseError(
                f"EQO Local {current_version} is already running (pid {current_pid})"
            )

    require_available_ports(config)
    paths.ensure()
    write_local_config(paths, config)
    with paths.log_file.open("ab") as log_stream:
        try:
            process = subprocess.Popen(
                supervisor_command(config, paths),
                stdin=subprocess.DEVNULL,
                stdout=log_stream,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        except OSError as error:
            raise LocalReleaseError(f"cannot start EQO Local: {error}") from error

    write_local_state(
        paths,
        state_document(
            config,
            paths,
            release_version=release_version,
            supervisor_pid=process.pid,
            status="starting",
        ),
    )
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            state = read_local_state(paths) or {}
            detail = state.get("error") or f"supervisor exited with status {process.returncode}"
            raise LocalReleaseError(f"EQO Local failed to start: {detail}; log: {paths.log_file}")
        state = read_local_state(paths)
        if state and state.get("status") == "ready":
            report = local_status(paths)
            if report["status"] == "ready":
                if open_browser:
                    webbrowser.open(config.workbench_url)
                return report
        if state and state.get("status") == "failed":
            raise LocalReleaseError(
                f"EQO Local failed to start: {state.get('error', 'unknown error')}; "
                f"log: {paths.log_file}"
            )
        time.sleep(0.1)

    process.terminate()
    raise LocalReleaseError(
        f"EQO Local did not become ready within {timeout_seconds:g} seconds; "
        f"log: {paths.log_file}"
    )


def stop_local(paths: LocalPaths, *, timeout_seconds: float = 15.0) -> bool:
    if timeout_seconds <= 0:
        raise LocalReleaseError("local shutdown timeout must be greater than zero")
    state = read_local_state(paths)
    if state is None:
        return False
    pid = state.get("supervisor_pid")
    if not isinstance(pid, int) or not process_is_local_supervisor(pid):
        if state.get("status") != "stopped":
            state["status"] = "stopped"
            write_local_state(paths, state)
        return False

    os.kill(pid, signal.SIGTERM)
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if not process_alive(pid):
            state["status"] = "stopped"
            write_local_state(paths, state)
            return True
        time.sleep(0.1)
    raise LocalReleaseError(
        f"EQO Local supervisor {pid} did not stop within {timeout_seconds:g} seconds"
    )


def open_local(paths: LocalPaths) -> str:
    report = local_status(paths)
    if report["status"] not in {"ready", "unhealthy"}:
        raise LocalReleaseError("EQO Local is not running; start it with 'eqo local up'")
    endpoints = report.get("endpoints", {})
    url = endpoints.get("workbench") if isinstance(endpoints, dict) else None
    if not isinstance(url, str):
        raise LocalReleaseError("EQO Local state does not contain a Workbench URL")
    webbrowser.open(url)
    return url


def supervise_local(
    config: LocalStackConfig,
    paths: LocalPaths,
    *,
    release_version: str,
) -> int:
    """Run the release supervisor in the detached child process."""

    from .chatqec_service import ChatQECSource
    from .dev_stack import DevStackConfig, DevStackSupervisor, build_service_specs

    config.validate()
    paths.ensure()
    stop_event = Event()

    def request_stop(_signum: int, _frame: object) -> None:
        stop_event.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    assistant_source_root = ""
    assistant_identity_token = ""
    if config.assistant_enabled:
        checkout = config.assistant_source_checkout
        source_probe = ChatQECSource.from_contract(config.assistant_interface, checkout)
        if checkout is None:
            source_probe = ChatQECSource(
                source_probe.repository,
                source_probe.revision,
                paths.service_root / f"chatqec-{source_probe.revision[:12]}",
            )
        assistant_source_root = str(source_probe.prepare())
        import secrets

        assistant_identity_token = secrets.token_urlsafe(32)

    stack_config = DevStackConfig(
        catalog=config.catalog,
        registry=config.registry,
        deployment_profile=config.deployment_profile,
        cluster_manifest="",
        database=str(paths.database),
        artifact_root=str(paths.artifact_root),
        runtime_root=str(paths.runtime_root),
        update_state_root=str(paths.update_root),
        workspace_root=str(Path(config.catalog).resolve().parent),
        workflows=config.workflows,
        host=config.host,
        port=config.workbench_port,
        api_port=config.api_port,
        chatqec_service_interface=config.assistant_interface,
        chatqec_source_root=assistant_source_root,
        chatqec_port=config.assistant_port,
        chatqec_identity_token=assistant_identity_token,
        poll_interval_seconds=config.poll_interval_seconds,
        lease_seconds=config.lease_seconds,
        worker_stale_after_seconds=config.worker_stale_after_seconds,
        start_local_worker=True,
        start_target_worker=False,
        start_workbench=True,
        start_chatqec=config.assistant_enabled,
        start_repository_updates=False,
        local_worker_id="eqo-local-worker",
    )
    supervisor = DevStackSupervisor(
        build_service_specs(stack_config),
        restart_delay_seconds=config.restart_delay_seconds,
        service_label="EQO Local",
    )
    base_state = state_document(
        config,
        paths,
        release_version=release_version,
        supervisor_pid=os.getpid(),
        status="starting",
    )
    database_report: dict[str, Any] = {}
    try:
        write_local_state(paths, base_state)
        database_report = prepare_local_database(paths)
        write_local_state(
            paths,
            state_document(
                config,
                paths,
                release_version=release_version,
                supervisor_pid=os.getpid(),
                status="starting",
                database_schema_version=database_report[
                    "database_schema_version"
                ],
                database_backup=database_report["backup"],
            ),
        )
        supervisor.start_api()
        supervisor.wait_for_api(f"{config.api_url}/api/v1/health")
        supervisor.start_services()
        if config.assistant_enabled and config.assistant_url:
            supervisor.wait_for_service(
                "chatqec",
                f"{config.assistant_url}/v1/health",
            )
        supervisor.wait_for_service("workbench", f"{config.workbench_url}/health")
        supervisor.wait_for_workers(
            f"{config.api_url}/api/v1/workers",
            {"eqo-local-worker"},
        )
        services = {
            name: process.pid for name, process in supervisor.processes.items()
        }
        write_local_state(
            paths,
            state_document(
                config,
                paths,
                release_version=release_version,
                supervisor_pid=os.getpid(),
                status="ready",
                services=services,
                database_schema_version=database_report[
                    "database_schema_version"
                ],
                database_backup=database_report["backup"],
            ),
        )
        supervisor.run(stop_event)
    except Exception as error:
        write_local_state(
            paths,
            state_document(
                config,
                paths,
                release_version=release_version,
                supervisor_pid=os.getpid(),
                status="failed",
                error=str(error),
                database_schema_version=database_report.get(
                    "database_schema_version"
                ),
                database_backup=database_report.get("backup"),
            ),
        )
        raise LocalReleaseError(str(error)) from error
    finally:
        supervisor.stop()

    write_local_state(
        paths,
        state_document(
            config,
            paths,
            release_version=release_version,
            supervisor_pid=os.getpid(),
            status="stopped",
            database_schema_version=database_report["database_schema_version"],
            database_backup=database_report["backup"],
        ),
    )
    return 0


def format_status(report: Mapping[str, Any]) -> str:
    lines = [f"EQO Local: {report.get('status', 'unknown')}"]
    if report.get("error"):
        lines.append(f"Error: {report['error']}")
    version = report.get("release_version")
    if version:
        lines.append(f"Release: {version}")
    endpoints = report.get("endpoints")
    if isinstance(endpoints, dict) and endpoints.get("workbench"):
        lines.append(f"Workbench: {endpoints['workbench']}")
        lines.append(f"API: {endpoints.get('api', 'unavailable')}")
        lines.append(f"Assistant: {endpoints.get('assistant') or 'disabled'}")
    services = report.get("services")
    if isinstance(services, dict) and services:
        health = ", ".join(
            f"{name}={'ready' if ready else 'unavailable'}"
            for name, ready in sorted(services.items())
        )
        lines.append(f"Services: {health}")
    workers = report.get("workers")
    if isinstance(workers, list):
        lines.append(f"Workers: {', '.join(workers) if workers else 'none'}")
    if report.get("registry_digest"):
        lines.append(f"Registry: {report['registry_digest']}")
    if report.get("database"):
        lines.append(f"Database: {report['database']}")
    if report.get("database_schema_version") is not None:
        lines.append(f"Database schema: {report['database_schema_version']}")
    if report.get("database_backup"):
        lines.append(f"Database backup: {report['database_backup']}")
    if report.get("artifact_root"):
        lines.append(f"Artifacts: {report['artifact_root']}")
    if report.get("log_file"):
        lines.append(f"Log: {report['log_file']}")
    return "\n".join(lines)


def resolve_paths(values: Sequence[str]) -> tuple[str, ...]:
    """Normalize release input files before detaching from the caller."""

    return tuple(str(Path(value).expanduser().resolve()) for value in values)


def default_local_workflows() -> tuple[str, ...]:
    return default_workflow_paths()
