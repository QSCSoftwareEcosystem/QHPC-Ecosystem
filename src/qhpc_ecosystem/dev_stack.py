"""Foreground supervisor for the complete local QHPC development stack."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from threading import Event
from typing import Callable, Sequence
from urllib.error import URLError
from urllib.request import urlopen


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
    update_state_root: str = ".qhpc/live/updates"
    workspace_root: str = "."
    start_local_worker: bool = True
    start_target_worker: bool = True
    start_workbench: bool = True
    start_chatqec: bool = True
    start_repository_updates: bool = True
    start_databucket: bool = True
    databucket_s3_endpoint: str = ""
    databucket_bucket: str = ""
    databucket_access_key_id: str = ""
    databucket_secret_access_key: str = ""


@dataclass(frozen=True)
class ServiceSpec:
    name: str
    command: tuple[str, ...]
    environment: tuple[tuple[str, str], ...] = ()


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
                    "dev-local-worker",
                ),
            )
        )
    if config.start_target_worker:
        services.append(
            ServiceSpec(
                "virtual-slurm-worker",
                (
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
                    "dev-virtual-slurm-worker",
                ),
            )
        )
    return tuple(services)


ProcessFactory = Callable[..., subprocess.Popen[bytes]]


class DevStackSupervisor:
    """Keep the API and workers alive as independently restartable processes."""

    def __init__(
        self,
        services: Sequence[ServiceSpec],
        *,
        restart_delay_seconds: float = 1.0,
        process_factory: ProcessFactory = subprocess.Popen,
    ) -> None:
        if not services:
            raise ValueError("development stack requires at least one service")
        if restart_delay_seconds <= 0:
            raise ValueError("service restart delay must be greater than zero")
        self.services = tuple(services)
        self.restart_delay_seconds = restart_delay_seconds
        self.process_factory = process_factory
        self.processes: dict[str, subprocess.Popen[bytes]] = {}

    def _start(self, service: ServiceSpec) -> subprocess.Popen[bytes]:
        environment = os.environ.copy()
        environment.pop("QHPC_CHATQEC_IDENTITY_TOKEN", None)
        environment.pop("QHPC_DATABUCKET_ACCESS_KEY_ID", None)
        environment.pop("QHPC_DATABUCKET_SECRET_ACCESS_KEY", None)
        environment.update(dict(service.environment))
        process = self.process_factory(
            service.command,
            env=environment,
        )
        self.processes[service.name] = process
        print(f"QHPC dev service started: {service.name} (pid {process.pid})")
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
                with urlopen(url, timeout=1) as response:
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
                with urlopen(url, timeout=1) as response:
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
                with urlopen(url, timeout=1) as response:
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
                    f"QHPC dev service exited: {service.name} "
                    f"(status {return_code}); restarting"
                )
                if stop_event.wait(self.restart_delay_seconds):
                    return
                self._start(service)

    def stop(self, *, timeout_seconds: float = 10.0) -> None:
        processes = list(reversed(tuple(self.processes.items())))
        for _name, process in processes:
            if process.poll() is None:
                process.terminate()
        deadline = time.monotonic() + timeout_seconds
        for name, process in processes:
            remaining = max(0.0, deadline - time.monotonic())
            try:
                process.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                print(f"QHPC dev service did not stop cleanly: {name}; killing")
                process.kill()
                process.wait()
        self.processes.clear()
