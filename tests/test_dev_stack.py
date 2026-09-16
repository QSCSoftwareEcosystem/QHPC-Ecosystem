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
    assert "local-development" in services[3].command
    assert "local-container" in services[3].command
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


def test_dev_stack_allows_explicit_reverse_proxy_host_for_workbench_only() -> None:
    value = DevStackConfig(
        **{
            **config().__dict__,
            "workbench_allowed_hosts": ("128.219.7.192",),
        }
    )

    services = build_service_specs(value, python_executable="/usr/bin/python3")
    workbench = next(service for service in services if service.name == "workbench")

    assert workbench.environment == (
        ("QHPC_WORKBENCH_ALLOWED_HOSTS", "128.219.7.192"),
    )
    assert all(
        "QHPC_WORKBENCH_ALLOWED_HOSTS" not in dict(service.environment)
        for service in services
        if service is not workbench
    )


def test_dev_stack_passes_explicit_qappswiki_graph_to_api_only() -> None:
    value = DevStackConfig(
        **{
            **config().__dict__,
            "qappswiki_graph": "/opt/eqo/qappswiki-graph-v1.json",
        }
    )

    services = build_service_specs(value, python_executable="/usr/bin/python3")
    api = next(service for service in services if service.name == "api")

    assert api.command[api.command.index("--qappswiki-graph") + 1] == (
        "/opt/eqo/qappswiki-graph-v1.json"
    )
    assert all(
        "--qappswiki-graph" not in service.command
        for service in services
        if service is not api
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


def test_dev_stack_starts_iqm_worker_only_when_explicit_and_scopes_token(monkeypatch) -> None:
    value = DevStackConfig(
        **{
            **config().__dict__,
            "start_iqm_worker": True,
            "iqm_endpoint": "https://iqm.example.test/cocos",
            "iqm_device_alias": "approved-qpu",
            "iqm_token": "worker-only-iqm-token",
        }
    )
    services = build_service_specs(value, python_executable="/usr/bin/python3")
    iqm = next(service for service in services if service.name == "iqm-worker")

    assert "iqm-worker" in iqm.command
    assert "https://iqm.example.test/cocos" in iqm.command
    assert ("IQM_TOKEN", "worker-only-iqm-token") in iqm.environment

    created: list[FakeProcess] = []

    def factory(command, **kwargs):
        process = FakeProcess(command, **kwargs)
        created.append(process)
        return process

    monkeypatch.setenv("IQM_TOKEN", "parent-token-must-not-reach-other-services")
    monkeypatch.setenv("IQM_BASE_URL", "https://qccsw.ccs.ornl.gov")
    supervisor = DevStackSupervisor(
        services,
        process_factory=factory,
    )
    supervisor.start_api()
    supervisor.start_workers()
    processes = {process.command: process for process in created}
    iqm_process = next(
        process for process in created if "iqm-worker" in process.command
    )
    assert iqm_process.environment["IQM_TOKEN"] == "worker-only-iqm-token"
    assert all(
        "IQM_TOKEN" not in process.environment
        for process in created
        if process is not iqm_process
    )
    assert all("IQM_BASE_URL" not in process.environment for process in created)
    assert processes
    supervisor.stop()


def test_dev_stack_starts_simulation_worker_without_iqm_configuration() -> None:
    value = DevStackConfig(
        **{
            **config().__dict__,
            "start_iqm_simulation_worker": True,
        }
    )

    services = build_service_specs(value, python_executable="/usr/bin/python3")
    simulation = next(
        service for service in services if service.name == "iqm-simulation-worker"
    )

    assert "iqm-simulation-worker" in simulation.command
    assert simulation.environment == ()
    assert simulation.secret_environment_names == ()


def test_dev_stack_accepts_release_specific_worker_identity() -> None:
    value = config()
    value = DevStackConfig(
        **{
            **value.__dict__,
            "start_target_worker": False,
            "local_worker_id": "eqo-local-worker",
        }
    )

    services = build_service_specs(value, python_executable="/usr/bin/python3")

    assert [service.name for service in services][-1] == "local-worker"
    assert "eqo-local-worker" in services[-1].command


def test_containerized_chatqec_has_a_narrow_named_container_cleanup(monkeypatch) -> None:
    monkeypatch.setattr("qhpc_ecosystem.dev_stack.find_oci_builder", lambda: "docker")
    value = DevStackConfig(
        **{
            **config().__dict__,
            "chatqec_container_image": "qhpc/chatqec-agent:test",
        }
    )

    chatqec = next(
        service for service in build_service_specs(value) if service.name == "chatqec"
    )

    assert chatqec.cleanup_command == (
        "docker",
        "rm",
        "--force",
        "eqo-chatqec-8096",
    )


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


def test_supervisor_cleans_named_external_service_before_start_and_on_stop() -> None:
    created: list[FakeProcess] = []
    cleanup_commands: list[tuple[str, ...]] = []

    def factory(command, **kwargs):
        process = FakeProcess(command, **kwargs)
        created.append(process)
        return process

    def cleanup(command, **kwargs) -> None:
        del kwargs
        cleanup_commands.append(tuple(command))

    stale_cleanup = ("docker", "rm", "--force", "eqo-chatqec-8096")
    supervisor = DevStackSupervisor(
        (
            ServiceSpec("api", ("python", "serve")),
            ServiceSpec(
                "chatqec",
                ("docker", "run", "qhpc/chatqec-agent:test"),
                cleanup_command=stale_cleanup,
            ),
        ),
        process_factory=factory,
        cleanup_runner=cleanup,
    )

    supervisor.start_api()
    supervisor.start_workers()
    supervisor.stop()

    assert len(created) == 2
    assert cleanup_commands == [stale_cleanup, stale_cleanup]


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
