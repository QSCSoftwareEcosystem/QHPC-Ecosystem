from __future__ import annotations

import threading
import time

from qhpc_ecosystem.dev_stack import (
    DevStackConfig,
    DevStackSupervisor,
    ServiceSpec,
    build_service_specs,
)


def config() -> DevStackConfig:
    return DevStackConfig(
        catalog="ecosystem.yaml",
        registry="examples/registry.yaml",
        deployment_profile="deployments/initial.yaml",
        cluster_manifest="infrastructure/test-clusters/cluster.yaml",
        database=".qhpc/live/workbench.sqlite",
        artifact_root=".qhpc/live/artifacts",
        runtime_root=".qhpc/runtimes",
        workflows=("examples/workflows/example.yaml",),
        host="127.0.0.1",
        port=8094,
        api_port=8095,
        chatqec_service_interface="integrations/chatqec/service.yaml",
        chatqec_source_root=".qhpc/services/chatqec-4c017510511f",
        chatqec_port=8096,
        chatqec_identity_token="test-workload-identity-token-000001",
        poll_interval_seconds=0.5,
        lease_seconds=300,
        worker_stale_after_seconds=15,
    )


def test_dev_stack_builds_separate_api_and_worker_processes() -> None:
    services = build_service_specs(config(), python_executable="/usr/bin/python3")

    assert [service.name for service in services] == [
        "api",
        "chatqec",
        "workbench",
        "local-worker",
        "virtual-slurm-worker",
    ]
    assert services[0].command[:5] == (
        "/usr/bin/python3",
        "-m",
        "qhpc_ecosystem.cli",
        "--catalog",
        "ecosystem.yaml",
    )
    assert "serve" in services[0].command
    assert "--enable-repository-updates" in services[0].command
    assert ".qhpc/live/updates" in services[0].command
    assert "chatqec-service" in services[1].command
    assert "qhpc_workbench" in services[2].command
    assert "worker" in services[3].command
    assert "target-worker" in services[4].command
    assert all(
        ".qhpc/live/workbench.sqlite" in service.command
        for service in (services[0], services[3], services[4])
    )
    assert "http://127.0.0.1:8095" in services[2].command
    token = ("QHPC_CHATQEC_IDENTITY_TOKEN", "test-workload-identity-token-000001")
    assert token in services[0].environment
    assert token in services[1].environment
    assert all(
        token not in service.environment
        for service in services[2:]
    )


def test_dev_stack_injects_databucket_credentials_into_api_only() -> None:
    databucket_config = DevStackConfig(
        **{
            **config().__dict__,
            "databucket_s3_endpoint": "http://127.0.0.1:3900",
            "databucket_bucket": "proj-materials-db",
            "databucket_access_key_id": "GKtest",
            "databucket_secret_access_key": "test-secret",
        }
    )
    services = build_service_specs(databucket_config, python_executable="/usr/bin/python3")

    endpoint = ("QHPC_DATABUCKET_S3_ENDPOINT", "http://127.0.0.1:3900")
    bucket = ("QHPC_DATABUCKET_BUCKET", "proj-materials-db")
    access_key = ("QHPC_DATABUCKET_ACCESS_KEY_ID", "GKtest")
    secret_key = ("QHPC_DATABUCKET_SECRET_ACCESS_KEY", "test-secret")
    assert endpoint in services[0].environment
    assert bucket in services[0].environment
    assert access_key in services[0].environment
    assert secret_key in services[0].environment
    assert all(
        access_key not in service.environment and secret_key not in service.environment
        for service in services[1:]
    )


def test_dev_stack_omits_databucket_credentials_when_disabled() -> None:
    disabled_config = DevStackConfig(**{**config().__dict__, "start_databucket": False})
    services = build_service_specs(disabled_config, python_executable="/usr/bin/python3")

    assert not any(name.startswith("QHPC_DATABUCKET_") for name, _ in services[0].environment)


class FakeProcess:
    next_pid = 1000

    def __init__(self, command, **kwargs) -> None:
        self.command = tuple(command)
        self.environment = kwargs.get("env", {})
        self.pid = FakeProcess.next_pid
        FakeProcess.next_pid += 1
        self.returncode = None

    def poll(self):
        return self.returncode

    def terminate(self) -> None:
        self.returncode = 0

    def wait(self, timeout=None):
        del timeout
        return self.returncode

    def kill(self) -> None:
        self.returncode = -9


def test_dev_stack_supervisor_restarts_exited_service(monkeypatch) -> None:
    created: list[FakeProcess] = []
    monkeypatch.setenv(
        "QHPC_CHATQEC_IDENTITY_TOKEN",
        "parent-token-must-not-reach-workers",
    )

    def factory(command, **kwargs):
        process = FakeProcess(command, **kwargs)
        created.append(process)
        return process

    services = (
        ServiceSpec(
            "api",
            ("python", "serve"),
            (("QHPC_CHATQEC_IDENTITY_TOKEN", "scoped-api-token"),),
        ),
        ServiceSpec("worker", ("python", "worker")),
    )
    supervisor = DevStackSupervisor(
        services,
        restart_delay_seconds=0.01,
        process_factory=factory,
    )
    supervisor.start_api()
    supervisor.start_workers()
    created[1].returncode = 7
    stop = threading.Event()
    thread = threading.Thread(target=supervisor.run, args=(stop,))
    thread.start()
    deadline = time.monotonic() + 2
    while len(created) < 3 and time.monotonic() < deadline:
        time.sleep(0.01)
    stop.set()
    thread.join(timeout=2)

    assert len(created) == 3
    assert created[2].command == ("python", "worker")
    assert (
        created[0].environment["QHPC_CHATQEC_IDENTITY_TOKEN"]
        == "scoped-api-token"
    )
    assert "QHPC_CHATQEC_IDENTITY_TOKEN" not in created[1].environment
    assert "QHPC_CHATQEC_IDENTITY_TOKEN" not in created[2].environment
    supervisor.stop()
