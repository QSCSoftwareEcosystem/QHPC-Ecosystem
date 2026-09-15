"""Portable single-user lifecycle support for EQO Local."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import platform
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import uuid
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Any, Mapping, Sequence
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import ProxyHandler, build_opener

from .local_assets import asset_path, assistant_source_path, default_workflow_paths
from .local_adapters import FTQC_OCI_DIGEST, FTQC_OCI_IMAGE
from .local_runtime import list_local_runtimes
from .operation_runtime import (
    OperationRuntimeError,
    build_oci_image,
    find_oci_builder,
    prepare_build_context,
    verify_runtime_definition,
)


LOCAL_SCHEMA_VERSION = 1
LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}
MINIMUM_FREE_BYTES = 512 * 1024 * 1024
_DIRECT_OPENER = build_opener(ProxyHandler({}))
CHATQEC_AGENT_OCI_IMAGE = "qhpc/chatqec-agent:a1ddc2e-dd19a85-linux-amd64-v1"
CHATQEC_AGENT_TSIM_IMAGE = "qhpc/chatqec-tsim:dd19a85-linux-amd64"
CHATQEC_AGENT_TSIM_DIGEST = "sha256:05524a6a1cb04618fc0797c46f071ac5447cd2f89aa7fe36598c2fa550538db0"
CHATQEC_AGENT_INPUT_LABEL = "org.qscsoftware.build-inputs-sha256"
_CHATQEC_AGENT_INPUTS = (
    "containers/services/chatqec-agent/Containerfile",
    "src/qhpc_ecosystem/__init__.py",
    "src/qhpc_ecosystem/service_adapters.py",
    "src/qhpc_ecosystem/chatqec_readiness.py",
    "src/qhpc_ecosystem/chatqec_agent_service.py",
)


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
    iqm_simulation_enabled: bool = False
    iqm_worker_enabled: bool = False
    iqm_endpoint: str | None = None
    iqm_device_alias: str | None = None
    iqm_token: str = ""
    ftqc_source_checkout: str | None = None
    ftqc_runtime_manifest: str | None = None
    ftqc_dependency_cache: str | None = None
    ecosystem_execution_enabled: bool = True
    slurm_test_cluster: str | None = None
    slurm_test_checkout: str | None = None
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
        if self.iqm_simulation_enabled and self.iqm_worker_enabled:
            raise LocalReleaseError(
                "select either the safe IQM simulation worker or the IQM worker"
            )
        if self.iqm_worker_enabled:
            if not (self.iqm_endpoint and self.iqm_device_alias):
                raise LocalReleaseError(
                    "the IQM worker requires an endpoint and device alias"
                )
            endpoint = urlparse(self.iqm_endpoint)
            if (
                endpoint.scheme != "https"
                or not endpoint.netloc
                or endpoint.username
                or endpoint.password
                or endpoint.query
                or endpoint.fragment
            ):
                raise LocalReleaseError(
                    "the IQM endpoint must be a credential-free HTTPS URL"
                )

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
            "iqm_simulation_enabled": self.iqm_simulation_enabled,
            "iqm_worker_enabled": self.iqm_worker_enabled,
            "iqm_endpoint": self.iqm_endpoint,
            "iqm_device_alias": self.iqm_device_alias,
            "ftqc_source_checkout": self.ftqc_source_checkout,
            "ftqc_runtime_manifest": self.ftqc_runtime_manifest,
            "ftqc_dependency_cache": self.ftqc_dependency_cache,
            "ecosystem_execution_enabled": self.ecosystem_execution_enabled,
            "slurm_test_cluster": self.slurm_test_cluster,
            "slurm_test_checkout": self.slurm_test_checkout,
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


def default_ftqc_build_inputs(
    catalog: str | Path,
) -> tuple[str | None, str | None]:
    """Find the FTQC checkout and runtime contract in an EQO source workspace.

    A packaged release deliberately carries neither the private FTQC source nor
    an unpinned compiler bundle.  A source checkout, however, has both the
    checked-in runtime contract and the conventional sibling FTQC checkout.
    The subsequent contract verification still rejects any revision or archive
    that differs from the admitted source.
    """

    catalog_path = Path(catalog).expanduser().resolve()
    for root in (catalog_path.parent, *catalog_path.parents):
        manifest = root / "containers" / "operations" / "ftqc" / "runtime.yaml"
        source = root.parent / "FTQC"
        if manifest.is_file() and source.is_dir():
            return str(source), str(manifest)
    return None, None


def default_slurm_test_cluster_inputs(
    catalog: str | Path,
    paths: LocalPaths,
) -> tuple[str, str]:
    """Locate the reviewed fixture used for complete Local execution.

    The fixture receives only isolated development data and runs the admitted
    OCI operation images.  Its checkout belongs to EQO Local, not to the
    caller's source tree.
    """

    catalog_path = Path(catalog).expanduser().resolve()
    for root in (catalog_path.parent, *catalog_path.parents):
        manifest = (
            root
            / "infrastructure"
            / "test-clusters"
            / "slurm-docker-cluster"
            / "cluster.yaml"
        )
        if manifest.is_file():
            checkout = paths.data_root / "test-clusters" / "thomas-slurm-docker"
            return str(manifest), str(checkout)
    raise LocalReleaseError(
        "the complete EQO Local execution fixture is missing from this installation; "
        "use the reviewed EQO source release containing infrastructure/test-clusters"
    )


def _ftqc_image_id(builder: str) -> str | None:
    """Return the local FTQC image identity, without treating a miss as fatal."""

    try:
        completed = subprocess.run(
            [builder, "image", "inspect", "--format", "{{.Id}}", FTQC_OCI_IMAGE],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as error:
        raise LocalReleaseError("FTQC OCI runtime inspection failed") from error
    image_id = completed.stdout.strip()
    if completed.returncode != 0:
        return None
    if not image_id.startswith("sha256:") or len(image_id) != 71:
        raise LocalReleaseError("FTQC OCI builder returned an invalid image identity")
    return image_id


def ensure_ftqc_oci_runtime(config: LocalStackConfig, paths: LocalPaths) -> str:
    """Require the exact FTQC OCI image, building it from its pinned contract if needed."""

    try:
        builder = find_oci_builder()
    except OperationRuntimeError as error:
        raise LocalReleaseError(
            "FTQC preparation requires Docker or Podman; install one before starting EQO Local"
        ) from error

    current_id = _ftqc_image_id(builder)
    if current_id == FTQC_OCI_DIGEST:
        return "available"

    if not (config.ftqc_source_checkout and config.ftqc_runtime_manifest):
        detail = (
            "missing" if current_id is None else f"has unexpected identity {current_id}"
        )
        raise LocalReleaseError(
            "the admitted FTQC OCI runtime is "
            f"{detail}; provide --ftqc-source-checkout and --ftqc-runtime-manifest "
            "so EQO Local can build the checksum-pinned image"
        )

    manifest = Path(config.ftqc_runtime_manifest).expanduser().resolve()
    source = Path(config.ftqc_source_checkout).expanduser().resolve()
    try:
        document = verify_runtime_definition(manifest)
        with tempfile.TemporaryDirectory(
            prefix="ftqc-oci-", dir=str(paths.cache_root)
        ) as temporary:
            context = Path(temporary) / "context"
            prepared = prepare_build_context(
                manifest,
                source,
                context,
                dependency_cache=config.ftqc_dependency_cache,
            )
            image = build_oci_image(document, prepared.path, FTQC_OCI_IMAGE, builder=builder)
    except OperationRuntimeError as error:
        hint = ""
        if "dependency cache" in str(error):
            hint = " Provide --ftqc-dependency-cache with the approved LLVM archive."
        raise LocalReleaseError(
            f"cannot build the admitted FTQC OCI runtime: {error}{hint}"
        ) from error

    if image.local_id != FTQC_OCI_DIGEST:
        raise LocalReleaseError(
            "the newly built FTQC OCI runtime does not match the admitted image identity"
        )
    return "built"


def _local_image_id(builder: str, image: str) -> str | None:
    try:
        completed = subprocess.run(
            [builder, "image", "inspect", "--format", "{{.Id}}", image],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as error:
        raise LocalReleaseError("OCI image inspection failed") from error
    identifier = completed.stdout.strip()
    if completed.returncode:
        return None
    if not identifier.startswith("sha256:") or len(identifier) != 71:
        raise LocalReleaseError(f"OCI builder returned an invalid image identity for {image}")
    return identifier


def _chatqec_agent_input_digest(workspace: Path) -> str:
    """Fingerprint every source file copied into the local agent image."""

    inputs = [workspace / relative for relative in _CHATQEC_AGENT_INPUTS]
    asset_root = workspace / "src/qhpc_ecosystem/local_assets/chatqec"
    inputs.extend(sorted(path for path in asset_root.rglob("*") if path.is_file()))
    if not inputs or any(not path.is_file() for path in inputs):
        raise LocalReleaseError("ChatQEC agent image inputs are incomplete")
    digest = hashlib.sha256()
    for path in inputs:
        digest.update(path.relative_to(workspace).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
        digest.update(b"\0")
    return digest.hexdigest()


def _local_image_label(builder: str, image: str, label: str) -> str | None:
    try:
        completed = subprocess.run(
            [
                builder,
                "image",
                "inspect",
                "--format",
                f'{{{{index .Config.Labels "{label}"}}}}',
                image,
            ],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as error:
        raise LocalReleaseError("OCI image label inspection failed") from error
    if completed.returncode:
        return None
    value = completed.stdout.strip()
    return value or None


def ensure_chatqec_agent_oci_runtime() -> str:
    """Build the local ChatQEC service image from admitted parent images only."""

    try:
        builder = find_oci_builder()
    except OperationRuntimeError as error:
        raise LocalReleaseError(
            "ChatQEC agent preparation requires Docker or Podman"
        ) from error
    for image, expected in ((CHATQEC_AGENT_TSIM_IMAGE, CHATQEC_AGENT_TSIM_DIGEST),):
        actual = _local_image_id(builder, image)
        if actual != expected:
            detail = "missing" if actual is None else f"has unexpected identity {actual}"
            raise LocalReleaseError(
                f"ChatQEC agent parent image {image} is {detail}; build its admitted runtime first"
            )
    workspace = Path(__file__).resolve().parents[2]
    recipe = workspace / "containers" / "services" / "chatqec-agent" / "Containerfile"
    if not recipe.is_file():
        raise LocalReleaseError("ChatQEC agent container recipe is missing from this EQO installation")
    input_digest = _chatqec_agent_input_digest(workspace)
    if (
        _local_image_id(builder, CHATQEC_AGENT_OCI_IMAGE) is not None
        and _local_image_label(builder, CHATQEC_AGENT_OCI_IMAGE, CHATQEC_AGENT_INPUT_LABEL)
        == input_digest
    ):
        return "available"
    try:
        subprocess.run(
            [
                builder,
                "build",
                "--network=none",
                "--platform",
                "linux/amd64",
                "--file",
                str(recipe),
                "--tag",
                CHATQEC_AGENT_OCI_IMAGE,
                "--label",
                f"{CHATQEC_AGENT_INPUT_LABEL}={input_digest}",
                str(workspace),
            ],
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise LocalReleaseError("cannot build the ChatQEC agent OCI image offline") from error
    if _local_image_id(builder, CHATQEC_AGENT_OCI_IMAGE) is None:
        raise LocalReleaseError("ChatQEC agent OCI image build did not produce the expected tag")
    if (
        _local_image_label(builder, CHATQEC_AGENT_OCI_IMAGE, CHATQEC_AGENT_INPUT_LABEL)
        != input_digest
    ):
        raise LocalReleaseError("ChatQEC agent OCI image is missing its input fingerprint")
    return "built"


def remove_stale_chatqec_agent_container(config: LocalStackConfig) -> bool:
    """Remove only the named local ChatQEC container left by a prior supervisor.

    Docker can retain the detached container when its ``docker run`` client is
    interrupted. The name is derived exclusively from EQO Local's configured
    loopback assistant port, so this cannot remove an arbitrary container.
    A missing engine or absent container is left for the normal prerequisite
    checks to explain.
    """

    if not config.assistant_enabled:
        return False
    try:
        builder = find_oci_builder()
        completed = subprocess.run(
            [builder, "rm", "--force", f"eqo-chatqec-{config.assistant_port}"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError, OperationRuntimeError):
        return False
    return completed.returncode == 0


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
            ("ps", "-ww", "-p", str(pid), "-o", "command="),
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
    with _DIRECT_OPENER.open(url, timeout=timeout_seconds) as response:
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
        elif (
            isinstance(state.get("services"), dict)
            and "virtual-slurm-worker" in state["services"]
            and "eqo-local-virtual-slurm-worker" not in workers
        ):
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


def _available_storage(path: Path) -> dict[str, int | bool]:
    candidate = path
    while not candidate.exists() and candidate != candidate.parent:
        candidate = candidate.parent
    try:
        usage = shutil.disk_usage(candidate)
    except OSError:
        return {"available": False, "free_bytes": 0}
    return {"available": True, "free_bytes": usage.free}


def require_storage_capacity(
    paths: LocalPaths,
    *,
    minimum_free_bytes: int = MINIMUM_FREE_BYTES,
) -> None:
    """Refuse startup when the local data volume cannot safely hold state."""

    storage = _available_storage(paths.data_root)
    if not storage["available"]:
        raise LocalReleaseError(
            "cannot determine free storage for EQO Local application data"
        )
    free_bytes = int(storage["free_bytes"])
    if free_bytes < minimum_free_bytes:
        required_mib = minimum_free_bytes // (1024 * 1024)
        available_mib = free_bytes // (1024 * 1024)
        raise LocalReleaseError(
            "insufficient storage for EQO Local: "
            f"at least {required_mib} MiB is required, {available_mib} MiB is free"
        )


def diagnostic_report(paths: LocalPaths, *, release_version: str) -> dict[str, Any]:
    """Collect a secret-free support report without reading logs or credentials."""

    try:
        status = local_status(paths)
        service_status: dict[str, Any] = {
            "status": status.get("status", "unknown"),
            "supervisor_running": bool(status.get("supervisor_running")),
            "services": status.get("services", {}),
            "workers": status.get("workers", []),
        }
    except Exception as error:
        service_status = {
            "status": "unavailable",
            "supervisor_running": False,
            "services": {},
            "workers": [],
            "error_type": type(error).__name__,
        }

    database: dict[str, Any] = {
        "present": paths.database.is_file(),
        "size": paths.database.stat().st_size if paths.database.is_file() else 0,
    }
    if database["present"]:
        try:
            database["integrity"] = _database_integrity(paths.database)
            database["schema_version"] = _database_schema_version(paths.database)
        except Exception as error:
            database["integrity"] = "unavailable"
            database["error_type"] = type(error).__name__

    assistant: dict[str, Any]
    try:
        from .chatqec_service import CanonicalChatQEC, ChatQECSource

        source = ChatQECSource.from_contract(
            asset_path("assistant-interface"),
            assistant_source_path(),
        )
        source.verify()
        responder = CanonicalChatQEC(
            source.checkout,
            source_url=source.repository,
            source_revision=source.revision,
        )
        assistant = {
            "available": True,
            "mode": "canonical-corpus-extractive-fallback",
            "source_revision": source.revision,
            "corpus_revision": responder.corpus_revision,
            "canonical_pages": len(responder.pages),
            "tool_execution": False,
        }
    except Exception as error:
        assistant = {
            "available": False,
            "error_type": type(error).__name__,
        }

    return {
        "schema_version": 1,
        "release_version": release_version,
        "platform": {
            "system": platform.system(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "dependencies": {
            "django": importlib.util.find_spec("django") is not None,
        },
        "service": service_status,
        "state": {
            "config_present": paths.config_file.is_file(),
            "state_present": paths.state_file.is_file(),
            "log_present": paths.log_file.is_file(),
        },
        "database": database,
        "storage": {
            **_available_storage(paths.data_root),
            "minimum_free_bytes": MINIMUM_FREE_BYTES,
        },
        "assistant": assistant,
        "runtimes": list_local_runtimes(paths.runtime_root),
    }


def write_diagnostic_report(
    report: Mapping[str, Any],
    destination: str | Path,
    *,
    overwrite: bool = False,
) -> Path:
    path = Path(destination).expanduser().resolve()
    if path.exists() and not overwrite:
        raise LocalReleaseError(
            f"diagnostic report already exists: {path}; use --force to replace it"
        )
    _write_json(path, report)
    return path


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
    startup_timeout_seconds: float = 60.0,
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
        "--startup-timeout",
        str(startup_timeout_seconds),
    ]
    if config.assistant_source_checkout:
        command.extend(
            ("--assistant-source-checkout", config.assistant_source_checkout)
        )
    if not config.assistant_enabled:
        command.append("--no-assistant")
    if config.iqm_simulation_enabled:
        command.append("--iqm-simulation")
    if config.iqm_worker_enabled:
        command.extend(
            (
                "--start-iqm-worker",
                "--iqm-endpoint",
                config.iqm_endpoint or "",
                "--iqm-device-alias",
                config.iqm_device_alias or "",
            )
        )
    if config.ftqc_source_checkout:
        command.extend(("--ftqc-source-checkout", config.ftqc_source_checkout))
    if config.ftqc_runtime_manifest:
        command.extend(("--ftqc-runtime-manifest", config.ftqc_runtime_manifest))
    if config.ftqc_dependency_cache:
        command.extend(("--ftqc-dependency-cache", config.ftqc_dependency_cache))
    for workflow in config.workflows:
        command.extend(("--workflow", workflow))
    return tuple(command)


def launch_local(
    config: LocalStackConfig,
    paths: LocalPaths,
    *,
    release_version: str,
    timeout_seconds: float = 60.0,
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

    # Clear only an orphaned EQO-owned ChatQEC container before the generic
    # port check. This makes a previous interrupted `eqo local down` recover
    # without touching unrelated services or containers.
    remove_stale_chatqec_agent_container(config)
    require_available_ports(config)
    require_storage_capacity(paths)
    paths.ensure()
    ensure_ftqc_oci_runtime(config, paths)
    if config.assistant_enabled:
        ensure_chatqec_agent_oci_runtime()
    write_local_config(paths, config)
    child_environment = {**os.environ, "PYTHONUNBUFFERED": "1"}
    child_environment.pop("IQM_TOKEN", None)
    child_environment.pop("EQO_LOCAL_IQM_TOKEN", None)
    if config.iqm_token:
        child_environment["EQO_LOCAL_IQM_TOKEN"] = config.iqm_token
    with paths.log_file.open("ab") as log_stream:
        try:
            process = subprocess.Popen(
                supervisor_command(
                    config,
                    paths,
                    startup_timeout_seconds=timeout_seconds,
                ),
                stdin=subprocess.DEVNULL,
                stdout=log_stream,
                stderr=subprocess.STDOUT,
                env=child_environment,
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
    startup_timeout_seconds: float = 60.0,
) -> int:
    """Run the release supervisor in the detached child process."""

    from .chatqec_service import ChatQECSource
    from .dev_stack import DevStackConfig, DevStackSupervisor, build_service_specs

    config.validate()
    if startup_timeout_seconds <= 0:
        raise LocalReleaseError("local startup timeout must be greater than zero")
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
        if checkout is None:
            source_probe = ChatQECSource.from_contract(
                config.assistant_interface,
                assistant_source_path(),
            )
            source_probe.verify()
            assistant_source_root = str(source_probe.checkout)
        else:
            source_probe = ChatQECSource.from_contract(
                config.assistant_interface,
                checkout,
            )
            assistant_source_root = str(source_probe.prepare())
        import secrets

        assistant_identity_token = secrets.token_urlsafe(32)

    cluster = None
    cluster_started_by_local = False
    cluster_manifest = ""
    cluster_checkout = ""
    if config.ecosystem_execution_enabled:
        from .slurm_test_cluster import SlurmDockerCluster

        default_manifest, default_checkout = default_slurm_test_cluster_inputs(
            config.catalog, paths
        )
        cluster_manifest = config.slurm_test_cluster or default_manifest
        cluster_checkout = config.slurm_test_checkout or default_checkout
        cluster = SlurmDockerCluster.from_manifest(cluster_manifest, cluster_checkout)
        cluster.prepare()
        cluster_status = cluster.status()
        if not cluster_status.ready:
            cluster_status = cluster.start()
            cluster_started_by_local = True
        if not cluster_status.ready:
            raise LocalReleaseError(
                "the EQO Local virtual Slurm execution fixture did not become ready"
            )
        cluster.verify_runtime_images(required_on_start_only=True)

    stack_config = DevStackConfig(
        catalog=config.catalog,
        registry=config.registry,
        deployment_profile=config.deployment_profile,
        cluster_manifest=cluster_manifest,
        cluster_checkout=cluster_checkout,
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
        chatqec_container_image=(
            CHATQEC_AGENT_OCI_IMAGE if config.assistant_enabled else ""
        ),
        poll_interval_seconds=config.poll_interval_seconds,
        lease_seconds=config.lease_seconds,
        worker_stale_after_seconds=config.worker_stale_after_seconds,
        start_local_worker=True,
        start_target_worker=config.ecosystem_execution_enabled,
        start_workbench=True,
        start_chatqec=config.assistant_enabled,
        start_repository_updates=False,
        start_iqm_worker=config.iqm_worker_enabled,
        start_iqm_simulation_worker=config.iqm_simulation_enabled,
        iqm_endpoint=config.iqm_endpoint or "",
        iqm_device_alias=config.iqm_device_alias or "",
        iqm_token=config.iqm_token,
        local_worker_id="eqo-local-worker",
        target_worker_id="eqo-local-virtual-slurm-worker",
        iqm_worker_id="eqo-local-iqm-worker",
        iqm_simulation_worker_id="eqo-local-iqm-simulation-worker",
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
    startup_deadline = time.monotonic() + startup_timeout_seconds

    def remaining_startup_time() -> float:
        remaining = startup_deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(
                "EQO Local exceeded its startup timeout before all services became ready"
            )
        return remaining

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
        # Start independent services together so a slow first import on one
        # host does not consume the entire bounded startup window before the
        # other services have even been launched. Workers already retry while
        # the API is becoming available.
        supervisor.start_api()
        supervisor.start_services()
        supervisor.wait_for_api(
            f"{config.api_url}/api/v1/health",
            timeout_seconds=remaining_startup_time(),
        )
        if config.assistant_enabled and config.assistant_url:
            supervisor.wait_for_service(
                "chatqec",
                f"{config.assistant_url}/v1/health",
                timeout_seconds=remaining_startup_time(),
            )
        supervisor.wait_for_service(
            "workbench",
            f"{config.workbench_url}/health",
            timeout_seconds=remaining_startup_time(),
        )
        expected_workers = {"eqo-local-worker"}
        if config.ecosystem_execution_enabled:
            expected_workers.add("eqo-local-virtual-slurm-worker")
        if config.iqm_worker_enabled:
            expected_workers.add("eqo-local-iqm-worker")
        if config.iqm_simulation_enabled:
            expected_workers.add("eqo-local-iqm-simulation-worker")
        supervisor.wait_for_workers(
            f"{config.api_url}/api/v1/workers",
            expected_workers,
            timeout_seconds=remaining_startup_time(),
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
        if cluster is not None and cluster_started_by_local:
            cluster.stop()

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
