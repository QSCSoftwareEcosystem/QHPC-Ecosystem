"""Foreground supervisor for the complete local QHPC development stack."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from threading import Event
from typing import Callable, Sequence
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener

from .container_engine import apptainer_requested
from .operation_runtime import find_oci_builder


_DIRECT_OPENER = build_opener(ProxyHandler({}))


@dataclass(frozen=True)
class DevStackConfig:
    catalog: str
    registry: str
    deployment_profile: str
    cluster_manifest: str
    database: str
    artifact_root: str
    runtime_root: str
    workflows: tuple[str, ...]
    host: str
    port: int
    api_port: int
    chatqec_service_interface: str
    chatqec_source_root: str
    chatqec_port: int
    chatqec_identity_token: str
    poll_interval_seconds: float
    lease_seconds: int
    worker_stale_after_seconds: float
    workbench_allowed_hosts: tuple[str, ...] = ()
    qappswiki_graph: str = ""
    cluster_checkout: str = ""
    chatqec_container_image: str = ""
    update_state_root: str = ".qhpc/live/updates"
    workspace_root: str = "."
    start_local_worker: bool = True
    start_target_worker: bool = True
    local_worker_serves_batch: bool = False
    start_workbench: bool = True
    start_chatqec: bool = True
    start_repository_updates: bool = True
    start_databucket: bool = True
    start_iqm_worker: bool = False
    start_iqm_simulation_worker: bool = False
    databucket_s3_endpoint: str = ""
    databucket_bucket: str = ""
    databucket_access_key_id: str = ""
    databucket_secret_access_key: str = ""
    iqm_endpoint: str = ""
    iqm_device_alias: str = ""
    iqm_token: str = ""
    local_worker_id: str = "dev-local-worker"
    target_worker_id: str = "dev-virtual-slurm-worker"
    iqm_worker_id: str = "dev-iqm-worker"
    iqm_simulation_worker_id: str = "dev-iqm-simulation-worker"


@dataclass(frozen=True)
class ServiceSpec:
    name: str
    command: tuple[str, ...]
    environment: tuple[tuple[str, str], ...] = ()
    secret_environment_names: tuple[str, ...] = ()
    cleanup_command: tuple[str, ...] = ()


def build_service_specs(
    config: DevStackConfig,
    *,
    python_executable: str = sys.executable,
) -> tuple[ServiceSpec, ...]:
    base = (
        python_executable,
        "-m",
        "qhpc_ecosystem.cli",
        "--catalog",
        config.catalog,
    )
    shared = (
        "--registry",
        config.registry,
        "--deployment-profile",
        config.deployment_profile,
        "--database",
        config.database,
        "--artifact-root",
        config.artifact_root,
    )
    api_command = [
        *base,
        "serve",
        *shared,
        "--host",
        config.host,
        "--port",
        str(config.api_port),
        "--worker-stale-after",
        str(config.worker_stale_after_seconds),
    ]
    api_environment: tuple[tuple[str, str], ...] = ()
    if config.start_repository_updates:
        api_command.extend(
            (
                "--enable-repository-updates",
                "--workspace-root",
                config.workspace_root,
                "--update-state-root",
                config.update_state_root,
            )
        )
    if config.qappswiki_graph:
        api_command.extend(("--qappswiki-graph", config.qappswiki_graph))
    if config.start_chatqec:
        api_command.extend(
            (
                "--chatqec-service-url",
                f"http://127.0.0.1:{config.chatqec_port}",
            )
        )
        api_environment = (
            ("QHPC_CHATQEC_IDENTITY_TOKEN", config.chatqec_identity_token),
        )
    if config.start_databucket:
        api_environment = api_environment + (
            ("QHPC_DATABUCKET_S3_ENDPOINT", config.databucket_s3_endpoint),
            ("QHPC_DATABUCKET_BUCKET", config.databucket_bucket),
            ("QHPC_DATABUCKET_ACCESS_KEY_ID", config.databucket_access_key_id),
            (
                "QHPC_DATABUCKET_SECRET_ACCESS_KEY",
                config.databucket_secret_access_key,
            ),
        )
    for workflow in config.workflows:
        api_command.extend(("--workflow", workflow))
    services = [ServiceSpec("api", tuple(api_command), api_environment)]
    if config.start_chatqec:
        # Under USE_APPTAINER=1 there is no daemon to publish a service container;
        # run the same citation-backed assistant in-process instead.
        if config.chatqec_container_image and not apptainer_requested():
            try:
                container_engine = find_oci_builder()
            except Exception as error:
                raise RuntimeError(
                    "EQO Local ChatQEC agent requires Docker or Podman"
                ) from error
            services.append(
                ServiceSpec(
                    "chatqec",
                    (
                        container_engine,
                        "run",
                        "--rm",
                        "--name",
                        f"eqo-chatqec-{config.chatqec_port}",
                        "--platform",
                        "linux/amd64",
                        "--read-only",
                        "--cap-drop",
                        "ALL",
                        "--security-opt",
                        "no-new-privileges",
                        "--tmpfs",
                        "/tmp:rw,noexec,nosuid,size=128m",
                        "--publish",
                        f"127.0.0.1:{config.chatqec_port}:8096",
                        "--env",
                        "QHPC_CHATQEC_IDENTITY_TOKEN",
                        "--env",
                        "QHPC_CHATQEC_LISTEN_HOST=0.0.0.0",
                        "--env",
                        "QHPC_CHATQEC_LISTEN_PORT=8096",
                        config.chatqec_container_image,
                    ),
                    (
                        (
                            "QHPC_CHATQEC_IDENTITY_TOKEN",
                            config.chatqec_identity_token,
                        ),
                    ),
                    ("QHPC_CHATQEC_IDENTITY_TOKEN",),
                    (
                        container_engine,
                        "rm",
                        "--force",
                        f"eqo-chatqec-{config.chatqec_port}",
                    ),
                )
            )
        else:
            services.append(
                ServiceSpec(
                    "chatqec",
                    (
                        *base,
                        "chatqec-service",
                        "serve",
                        config.chatqec_service_interface,
                        "--checkout",
                        config.chatqec_source_root,
                        "--host",
                        "127.0.0.1",
                        "--port",
                        str(config.chatqec_port),
                    ),
                    (
                        (
                            "QHPC_CHATQEC_IDENTITY_TOKEN",
                            config.chatqec_identity_token,
                        ),
                    ),
                )
            )
    if config.start_workbench:
        workbench_environment = (
            (
                "QHPC_WORKBENCH_ALLOWED_HOSTS",
                ",".join(config.workbench_allowed_hosts),
            ),
        ) if config.workbench_allowed_hosts else ()
        services.append(
            ServiceSpec(
                "workbench",
                (
                    python_executable,
                    "-m",
                    "qhpc_workbench",
                    "--host",
                    config.host,
                    "--port",
                    str(config.port),
                    "--api-base",
                    f"http://{config.host}:{config.api_port}",
                ),
                workbench_environment,
            )
        )
    if config.start_local_worker:
        services.append(
            ServiceSpec(
                "local-worker",
                (
                    *base,
                    "worker",
                    *shared,
                    "--runtime-root",
                    config.runtime_root,
                    "--poll-interval",
                    str(config.poll_interval_seconds),
                    "--lease-seconds",
                    str(config.lease_seconds),
                    "--worker-id",
                    config.local_worker_id,
                    "--execution-target",
                    "local-development",
                    "--execution-target",
                    "local-container",
                    *(
                        (
                            "--execution-target",
                            "development-slurm-docker",
                            "--execution-class",
                            "interactive-local",
                            "--execution-class",
                            "batch-hpc",
                        )
                        if config.local_worker_serves_batch
                        else ()
                    ),
                ),
            )
        )
    if config.start_target_worker:
        target_command = [
            *base,
            "target-worker",
            *shared,
            "--slurm-test-cluster",
            config.cluster_manifest,
            "--poll-interval",
            str(config.poll_interval_seconds),
            "--lease-seconds",
            str(config.lease_seconds),
            "--worker-id",
            config.target_worker_id,
        ]
        if config.cluster_checkout:
            target_command.extend(("--slurm-test-checkout", config.cluster_checkout))
        services.append(
            ServiceSpec(
                "virtual-slurm-worker",
                tuple(target_command),
            )
        )
    if config.start_iqm_worker:
        services.append(
            ServiceSpec(
                "iqm-worker",
                (
                    *base,
                    "iqm-worker",
                    *shared,
                    "--endpoint",
                    config.iqm_endpoint,
                    "--device-alias",
                    config.iqm_device_alias,
                    "--poll-interval",
                    str(config.poll_interval_seconds),
                    "--lease-seconds",
                    str(config.lease_seconds),
                    "--worker-id",
                    config.iqm_worker_id,
                ),
                (("IQM_TOKEN", config.iqm_token),) if config.iqm_token else (),
                ("IQM_TOKEN",),
            )
        )
    if config.start_iqm_simulation_worker:
        services.append(
            ServiceSpec(
                "iqm-simulation-worker",
                (
                    *base,
                    "iqm-simulation-worker",
                    *shared,
                    "--poll-interval",
                    str(config.poll_interval_seconds),
                    "--lease-seconds",
                    str(config.lease_seconds),
                    "--worker-id",
                    config.iqm_simulation_worker_id,
                ),
            )
        )
    return tuple(services)


ProcessFactory = Callable[..., subprocess.Popen[bytes]]
CommandRunner = Callable[..., object]


class DevStackSupervisor:
    """Keep the API and workers alive as independently restartable processes."""

    def __init__(
        self,
        services: Sequence[ServiceSpec],
        *,
        restart_delay_seconds: float = 1.0,
        process_factory: ProcessFactory = subprocess.Popen,
        cleanup_runner: CommandRunner = subprocess.run,
        service_label: str = "QHPC dev",
    ) -> None:
        if not services:
            raise ValueError("development stack requires at least one service")
        if restart_delay_seconds <= 0:
            raise ValueError("service restart delay must be greater than zero")
        self.services = tuple(services)
        self.restart_delay_seconds = restart_delay_seconds
        self.process_factory = process_factory
        self.cleanup_runner = cleanup_runner
        self.service_label = service_label
        self.processes: dict[str, subprocess.Popen[bytes]] = {}

    def _cleanup(self, service: ServiceSpec) -> None:
        """Remove a bounded external service left by an interrupted client.

        A ``docker run`` client can receive SIGTERM before Docker has stopped
        its named container. Only services that explicitly opt in get a
        cleanup command; the local ChatQEC name is derived from its loopback
        port, so this cannot target an arbitrary user container.
        """

        if not service.cleanup_command:
            return
        try:
            self.cleanup_runner(
                service.cleanup_command,
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=20,
            )
        except (OSError, subprocess.SubprocessError) as error:
            print(
                f"{self.service_label} could not clean external service "
                f"{service.name}: {error}"
            )

    def _start(self, service: ServiceSpec) -> subprocess.Popen[bytes]:
        self._cleanup(service)
        environment = os.environ.copy()
        environment.pop("QHPC_CHATQEC_IDENTITY_TOKEN", None)
        environment.pop("QHPC_DATABUCKET_ACCESS_KEY_ID", None)
        environment.pop("QHPC_DATABUCKET_SECRET_ACCESS_KEY", None)
        environment.pop("IQM_BASE_URL", None)
        environment.pop("IQM_TOKEN", None)
        environment.pop("EQO_LOCAL_IQM_TOKEN", None)
        for name in service.secret_environment_names:
            environment.pop(name, None)
        environment.update(dict(service.environment))
        # Start each service as its own session/process-group leader so that on
        # shutdown the whole tree can be signalled — a worker plus any container
        # process it launched (notably `apptainer run`, which runs the tool as a
        # descendant rather than in a separate daemon).
        process = self.process_factory(
            service.command,
            env=environment,
            start_new_session=True,
        )
        self.processes[service.name] = process
        print(f"{self.service_label} service started: {service.name} (pid {process.pid})")
        return process

    def start_api(self) -> None:
        self._start(self.services[0])

    def start_services(self) -> None:
        for service in self.services[1:]:
            self._start(service)

    def start_workers(self) -> None:
        self.start_services()

    def wait_for_api(
        self,
        url: str,
        *,
        timeout_seconds: float = 15.0,
    ) -> None:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            api = self.processes.get("api")
            if api is None or api.poll() is not None:
                raise RuntimeError("QHPC API exited before becoming ready")
            try:
                with _DIRECT_OPENER.open(url, timeout=1) as response:
                    if response.status == 200:
                        return
            except (OSError, URLError):
                pass
            time.sleep(0.1)
        raise TimeoutError(f"QHPC API did not become ready: {url}")

    def wait_for_workers(
        self,
        url: str,
        worker_ids: set[str],
        *,
        timeout_seconds: float = 15.0,
    ) -> None:
        if not worker_ids:
            return
        deadline = time.monotonic() + timeout_seconds
        available: set[str] = set()
        while time.monotonic() < deadline:
            try:
                with _DIRECT_OPENER.open(url, timeout=1) as response:
                    workers = json.load(response)
                available = {
                    worker["id"] for worker in workers if worker.get("available")
                }
                if worker_ids <= available:
                    return
            except (OSError, URLError, ValueError):
                pass
            time.sleep(0.1)
        missing = ", ".join(sorted(worker_ids - available))
        raise TimeoutError(f"QHPC workers did not become ready: {missing}")

    def wait_for_service(
        self,
        name: str,
        url: str,
        *,
        timeout_seconds: float = 15.0,
    ) -> None:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            process = self.processes.get(name)
            if process is None or process.poll() is not None:
                raise RuntimeError(f"QHPC {name} exited before becoming ready")
            try:
                with _DIRECT_OPENER.open(url, timeout=1) as response:
                    if response.status == 200:
                        return
            except (OSError, URLError):
                pass
            time.sleep(0.1)
        raise TimeoutError(f"QHPC {name} did not become ready: {url}")

    def run(self, stop_event: Event) -> None:
        while not stop_event.wait(0.25):
            for service in self.services:
                process = self.processes.get(service.name)
                if process is None or process.poll() is None:
                    continue
                return_code = process.returncode
                print(
                    f"{self.service_label} service exited: {service.name} "
                    f"(status {return_code}); restarting"
                )
                if stop_event.wait(self.restart_delay_seconds):
                    return
                self._start(service)

    def _signal_tree(self, process: "subprocess.Popen[bytes]", sig: int) -> bool:
        """Signal a service's whole process group; report whether that worked.

        Real services lead their own group (``start_new_session=True``), so this
        also reaps descendants such as a worker's ``apptainer run`` container.
        Only real ``subprocess.Popen`` handles are group-signalled; test doubles
        are not, so their pids can never collide with a live system process. When
        this returns ``False`` the caller falls back to ``terminate``/``kill``.
        """

        if not isinstance(process, subprocess.Popen):
            return False
        try:
            os.killpg(os.getpgid(process.pid), sig)
        except (ProcessLookupError, PermissionError, OSError):
            return False
        return True

    def stop(self, *, timeout_seconds: float = 10.0) -> None:
        processes = list(reversed(tuple(self.processes.items())))
        for _name, process in processes:
            if process.poll() is None:
                if not self._signal_tree(process, signal.SIGTERM):
                    process.terminate()
        deadline = time.monotonic() + timeout_seconds
        for name, process in processes:
            remaining = max(0.0, deadline - time.monotonic())
            try:
                process.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                print(
                    f"{self.service_label} service did not stop cleanly: "
                    f"{name}; killing"
                )
                if not self._signal_tree(process, signal.SIGKILL):
                    process.kill()
                process.wait()
        for service in reversed(self.services):
            self._cleanup(service)
        self.processes.clear()
