from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from qhpc_ecosystem import cli
from qhpc_ecosystem import dev_stack
from qhpc_ecosystem import engine as engine_module
from qhpc_ecosystem import local_release
from qhpc_ecosystem.catalog import load_catalog
from qhpc_ecosystem.engine import WorkflowEngine
from qhpc_ecosystem.local_release import (
    LocalPaths,
    LocalReleaseError,
    LocalStackConfig,
    _chatqec_agent_input_digest,
    default_slurm_test_cluster_inputs,
    default_ftqc_build_inputs,
    diagnostic_report,
    ensure_ftqc_oci_runtime,
    local_status,
    prepare_local_database,
    remove_stale_chatqec_agent_container,
    require_storage_capacity,
    state_document,
    stop_local,
    supervisor_command,
    write_local_config,
    write_local_state,
    write_diagnostic_report,
)
from qhpc_ecosystem.registry import load_registry


ROOT = Path(__file__).resolve().parents[1]


def config(**overrides) -> LocalStackConfig:
    values = {
        "catalog": str(ROOT / "ecosystem.yaml"),
        "registry": str(ROOT / "examples" / "registry.yaml"),
        "deployment_profile": str(ROOT / "deployments" / "initial.yaml"),
        "workflows": (),
        "assistant_interface": str(ROOT / "integrations" / "chatqec" / "service.yaml"),
        "assistant_source_checkout": None,
        "qappswiki_graph": str(
            ROOT
            / "src"
            / "qhpc_ecosystem"
            / "local_assets"
            / "knowledge"
            / "qappswiki-graph-v1.json"
        ),
        "host": "127.0.0.1",
        "workbench_port": 18080,
        "api_port": 18081,
        "assistant_port": 18082,
        "ecosystem_execution_enabled": False,
    }
    values.update(overrides)
    return LocalStackConfig(**values)


def test_explicit_home_keeps_all_local_state_under_one_root(tmp_path: Path) -> None:
    paths = LocalPaths.discover(tmp_path)

    assert paths.config_root == tmp_path / "config"
    assert paths.database == tmp_path / "data" / "workbench.sqlite"
    assert paths.artifact_root == tmp_path / "data" / "artifacts"
    assert paths.runtime_root == tmp_path / "data" / "runtimes"
    assert paths.backup_root == tmp_path / "data" / "backups"
    assert paths.log_file == tmp_path / "logs" / "local-supervisor.log"


def test_linux_paths_follow_xdg_locations(tmp_path: Path) -> None:
    paths = LocalPaths.discover(
        environ={
            "HOME": str(tmp_path / "home"),
            "XDG_CONFIG_HOME": str(tmp_path / "config"),
            "XDG_DATA_HOME": str(tmp_path / "data"),
            "XDG_CACHE_HOME": str(tmp_path / "cache"),
            "XDG_STATE_HOME": str(tmp_path / "state"),
        },
        platform_name="linux",
    )

    assert paths.config_root == tmp_path / "config" / "eqo"
    assert paths.data_root == tmp_path / "data" / "eqo"
    assert paths.cache_root == tmp_path / "cache" / "eqo"
    assert paths.state_root == tmp_path / "state" / "eqo"
    assert paths.log_root == tmp_path / "state" / "eqo" / "logs"


def test_packaged_installation_uses_the_bundled_slurm_fixture(
    tmp_path: Path,
) -> None:
    catalog = tmp_path / "catalog.yaml"
    catalog.write_text("api_version: qhpc/v1\n", encoding="utf-8")
    paths = LocalPaths.discover(tmp_path / "local-home")

    manifest, checkout = default_slurm_test_cluster_inputs(catalog, paths)

    assert Path(manifest).name == "cluster.yaml"
    assert "local_assets/test-clusters/slurm-docker-cluster" in manifest
    assert checkout == str(paths.data_root / "test-clusters" / "thomas-slurm-docker")


def test_local_config_rejects_non_loopback_and_port_collisions(
    tmp_path: Path,
) -> None:
    with pytest.raises(LocalReleaseError, match="loopback"):
        config(host="0.0.0.0").validate()
    with pytest.raises(LocalReleaseError, match="must be different"):
        config(api_port=18080).validate()
    with pytest.raises(LocalReleaseError, match="allowed hosts"):
        config(workbench_allowed_hosts=("*",)).validate()
    with pytest.raises(LocalReleaseError, match="QAppsWiki graph"):
        config(qappswiki_graph=str(tmp_path / "missing-graph.json")).validate()


def test_dependency_preflight_explains_how_to_install_workbench(monkeypatch) -> None:
    monkeypatch.setattr(local_release.importlib.util, "find_spec", lambda _name: None)

    with pytest.raises(LocalReleaseError, match=r"qhpc-ecosystem\[local\]"):
        local_release.require_local_dependencies()


def test_storage_preflight_rejects_unknown_or_insufficient_capacity(
    tmp_path: Path, monkeypatch
) -> None:
    paths = LocalPaths.discover(tmp_path / "local-home")
    monkeypatch.setattr(
        local_release,
        "_available_storage",
        lambda _path: {"available": False, "free_bytes": 0},
    )
    with pytest.raises(LocalReleaseError, match="cannot determine free storage"):
        require_storage_capacity(paths)

    monkeypatch.setattr(
        local_release,
        "_available_storage",
        lambda _path: {"available": True, "free_bytes": 1024},
    )
    with pytest.raises(LocalReleaseError, match="insufficient storage"):
        require_storage_capacity(paths)


def test_config_and_state_files_contain_no_runtime_identity_token(tmp_path: Path) -> None:
    paths = LocalPaths.discover(tmp_path)
    value = config(assistant_enabled=False)
    write_local_config(paths, value)
    write_local_state(
        paths,
        state_document(
            value,
            paths,
            release_version="0.1.0",
            supervisor_pid=1234,
            status="starting",
        ),
    )

    config_text = paths.config_file.read_text(encoding="utf-8")
    state_text = paths.state_file.read_text(encoding="utf-8")
    assert "token" not in config_text.lower()
    assert "token" not in state_text.lower()
    assert json.loads(state_text)["registry_digest"].startswith("sha256:")


def test_arm64_alpha_registry_is_a_per_user_runtime_derivative(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = LocalPaths.discover(tmp_path / "local-home")
    paths.ensure()
    monkeypatch.setattr(local_release, "unsigned_arm64_alpha_enabled", lambda: True)
    monkeypatch.setattr(local_release, "apptainer_requested", lambda: True)

    selected = local_release._arm64_alpha_registry_config(config(), paths)

    assert selected.registry != str(ROOT / "examples" / "registry.yaml")
    generated = Path(selected.registry).read_text(encoding="utf-8")
    assert "eqo-stim@sha256:f0efb9d55beebb4a691553eceab064846159ee4056552f138ce1582a564daa75" in generated
    assert "eqo-nwqsim@sha256:1afbab53b85670d02053366fb3fd1c0e796d35f9353cc0a2b53da33d274cb8dd" in generated
    assert "eqo-ftqc@sha256:a97fb05603b1b8ee370ad04096798c1cbaa397135877b0bdf8428a7d08a70f37" in generated
    load_registry(selected.registry, load_catalog(ROOT / "ecosystem.yaml"))


def test_iqm_worker_configuration_requires_a_credential_free_https_endpoint() -> None:
    value = config(
        assistant_enabled=False,
        iqm_worker_enabled=True,
        iqm_endpoint="https://qccsw.ccs.ornl.gov",
        iqm_device_alias="iqm-qpu-1",
        iqm_token="not-persisted",
    )

    value.validate()
    persisted = value.as_dict()
    assert "token" not in json.dumps(persisted).lower()

    with pytest.raises(LocalReleaseError, match="credential-free HTTPS"):
        config(
            assistant_enabled=False,
            iqm_worker_enabled=True,
            iqm_endpoint="https://qccsw.ccs.ornl.gov/?credential=never",
            iqm_device_alias="iqm-qpu-1",
        ).validate()


def test_ftqc_runtime_preflight_accepts_only_the_admitted_image(
    tmp_path: Path, monkeypatch
) -> None:
    paths = LocalPaths.discover(tmp_path)
    monkeypatch.setattr(local_release, "find_oci_builder", lambda: "docker")
    monkeypatch.setattr(
        local_release,
        "_ftqc_image_id",
        lambda _builder: local_release.FTQC_OCI_DIGEST,
    )

    assert ensure_ftqc_oci_runtime(config(), paths) == "available"


def test_ftqc_runtime_build_inputs_are_discovered_from_a_source_workspace(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "QHPC-Ecosystem"
    catalog = workspace / "ecosystem.yaml"
    manifest = workspace / "containers" / "operations" / "ftqc" / "runtime.yaml"
    source = tmp_path / "FTQC"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("contract", encoding="utf-8")
    catalog.write_text("catalog", encoding="utf-8")
    source.mkdir()

    assert default_ftqc_build_inputs(catalog) == (str(source), str(manifest))


def test_ftqc_runtime_preflight_builds_from_the_pinned_contract(
    tmp_path: Path, monkeypatch
) -> None:
    paths = LocalPaths.discover(tmp_path)
    paths.ensure()
    source = tmp_path / "FTQC"
    source.mkdir()
    manifest = tmp_path / "runtime.yaml"
    manifest.write_text("contract", encoding="utf-8")
    dependency_cache = tmp_path / "llvm-source-cache"
    dependency_cache.mkdir()
    value = config(
        ftqc_source_checkout=str(source),
        ftqc_runtime_manifest=str(manifest),
        ftqc_dependency_cache=str(dependency_cache),
    )
    calls: list[str] = []
    requested_caches: list[str | None] = []
    monkeypatch.setattr(local_release, "find_oci_builder", lambda: "docker")
    monkeypatch.setattr(local_release, "_ftqc_image_id", lambda _builder: None)
    monkeypatch.setattr(
        local_release,
        "verify_runtime_definition",
        lambda _manifest: {"runtime": "pinned"},
    )
    monkeypatch.setattr(
        local_release,
        "prepare_build_context",
        lambda _manifest, _source, context, *, dependency_cache: (
            requested_caches.append(dependency_cache) or SimpleNamespace(path=context)
        ),
    )

    def build(document, context, tag, *, builder):
        calls.extend((str(document), str(context), tag, builder))
        return SimpleNamespace(local_id=local_release.FTQC_OCI_DIGEST)

    monkeypatch.setattr(local_release, "build_oci_image", build)

    assert ensure_ftqc_oci_runtime(value, paths) == "built"
    assert requested_caches == [str(dependency_cache)]
    assert calls[-2:] == ["qhpc/ftqc:779216de-linux-amd64", "docker"]


def test_ftqc_runtime_preflight_explains_how_to_build_a_missing_image(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(local_release, "find_oci_builder", lambda: "docker")
    monkeypatch.setattr(local_release, "_ftqc_image_id", lambda _builder: None)

    with pytest.raises(LocalReleaseError, match="--ftqc-source-checkout"):
        ensure_ftqc_oci_runtime(config(), LocalPaths.discover(tmp_path))


def test_chatqec_agent_input_digest_changes_when_a_copied_asset_changes(
    tmp_path: Path,
) -> None:
    for relative in local_release._CHATQEC_AGENT_INPUTS:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(relative, encoding="utf-8")
    canonical = tmp_path / "local_assets/chatqec/knowledge/canonical"
    canonical.mkdir(parents=True)
    page = canonical / "surface-code.md"
    page.write_text("first revision", encoding="utf-8")

    first = _chatqec_agent_input_digest(tmp_path)
    page.write_text("second revision", encoding="utf-8")

    assert _chatqec_agent_input_digest(tmp_path) != first


def test_stale_chatqec_cleanup_targets_only_the_configured_eqo_name(
    monkeypatch,
) -> None:
    commands: list[tuple[str, ...]] = []

    def runner(command, **kwargs):
        assert kwargs["check"] is False
        assert kwargs["timeout"] == 20
        commands.append(tuple(command))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(local_release, "find_oci_builder", lambda: "docker")
    monkeypatch.setattr(local_release.subprocess, "run", runner)

    assert remove_stale_chatqec_agent_container(config(assistant_port=18082)) is True
    assert commands == [("docker", "rm", "--force", "eqo-chatqec-18082")]
    assert remove_stale_chatqec_agent_container(config(assistant_enabled=False)) is False


def test_status_reports_health_and_compatible_worker(
    tmp_path: Path, monkeypatch
) -> None:
    paths = LocalPaths.discover(tmp_path)
    value = config(assistant_enabled=False)
    write_local_state(
        paths,
        state_document(
            value,
            paths,
            release_version="0.1.0",
            supervisor_pid=4321,
            status="ready",
            services={"api": 10, "workbench": 11, "local-worker": 12},
        ),
    )
    monkeypatch.setattr(local_release, "process_is_local_supervisor", lambda _pid: True)
    monkeypatch.setattr(local_release, "_endpoint_healthy", lambda _url: True)
    monkeypatch.setattr(
        local_release,
        "_fetch_json",
        lambda _url: [{"id": "eqo-local-worker", "available": True}],
    )

    report = local_status(paths)

    assert report["status"] == "ready"
    assert report["services"] == {"api": True, "workbench": True}
    assert report["workers"] == ["eqo-local-worker"]


def test_status_preserves_failed_startup_detail(tmp_path: Path, monkeypatch) -> None:
    paths = LocalPaths.discover(tmp_path)
    value = config(assistant_enabled=False)
    write_local_state(
        paths,
        state_document(
            value,
            paths,
            release_version="0.1.0",
            supervisor_pid=4321,
            status="failed",
            error="Workbench dependency unavailable",
        ),
    )
    monkeypatch.setattr(local_release, "process_is_local_supervisor", lambda _pid: False)

    report = local_status(paths)

    assert report["status"] == "failed"
    assert report["error"] == "Workbench dependency unavailable"
    assert "Error: Workbench dependency unavailable" in local_release.format_status(
        report
    )


def test_supervisor_command_preserves_distinct_os_paths(tmp_path: Path) -> None:
    paths = LocalPaths(
        config_root=tmp_path / "config",
        data_root=tmp_path / "data",
        cache_root=tmp_path / "cache",
        state_root=tmp_path / "state",
        log_root=tmp_path / "logs",
    )

    command = supervisor_command(
        config(assistant_enabled=False),
        paths,
        python_executable="/usr/bin/python3",
    )

    for option, value in zip(
        ("--config-root", "--data-root", "--cache-root", "--state-root", "--log-root"),
        (paths.config_root, paths.data_root, paths.cache_root, paths.state_root, paths.log_root),
    ):
        assert command[command.index(option) + 1] == str(value)
    assert "--no-assistant" in command
    assert "--no-ecosystem-execution" in command
    assert "slurm" not in " ".join(command).lower()
    assert command[command.index("--startup-timeout") + 1] == "60.0"


def test_supervisor_command_uses_the_requested_startup_timeout(tmp_path: Path) -> None:
    paths = LocalPaths.discover(tmp_path)

    command = supervisor_command(
        config(assistant_enabled=False),
        paths,
        startup_timeout_seconds=75.5,
    )

    assert command[command.index("--startup-timeout") + 1] == "75.5"


def test_supervisor_command_preserves_explicit_workbench_allowed_hosts(
    tmp_path: Path,
) -> None:
    command = supervisor_command(
        config(
            assistant_enabled=False,
            workbench_allowed_hosts=("128.219.7.192", "eqo.example.test"),
        ),
        LocalPaths.discover(tmp_path),
    )

    assert command.count("--workbench-allowed-host") == 2
    first = command.index("--workbench-allowed-host")
    second = command.index("--workbench-allowed-host", first + 1)
    assert command[first + 1] == "128.219.7.192"
    assert command[second + 1] == "eqo.example.test"


def test_supervisor_command_can_enable_the_safe_iqm_simulation(tmp_path: Path) -> None:
    command = supervisor_command(
        config(assistant_enabled=False, iqm_simulation_enabled=True),
        LocalPaths.discover(tmp_path),
    )

    assert "--iqm-simulation" in command


def test_supervisor_command_passes_nonsecret_iqm_configuration_only(
    tmp_path: Path,
) -> None:
    command = supervisor_command(
        config(
            assistant_enabled=False,
            iqm_worker_enabled=True,
            iqm_endpoint="https://qccsw.ccs.ornl.gov",
            iqm_device_alias="iqm-qpu-1",
            iqm_token="do-not-place-in-arguments",
        ),
        LocalPaths.discover(tmp_path),
    )

    assert "--start-iqm-worker" in command
    assert command[command.index("--iqm-device-alias") + 1] == "iqm-qpu-1"
    assert "do-not-place-in-arguments" not in command


def test_supervisor_launches_services_before_waiting_for_api(
    tmp_path: Path, monkeypatch
) -> None:
    events: list[str] = []

    class RecordingSupervisor:
        processes: dict[str, object] = {}

        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def start_api(self) -> None:
            events.append("start_api")

        def start_services(self) -> None:
            events.append("start_services")

        def wait_for_api(self, *_args, **_kwargs) -> None:
            events.append("wait_for_api")

        def wait_for_service(self, name, *_args, **_kwargs) -> None:
            events.append(f"wait_for_service:{name}")

        def wait_for_workers(self, *_args, **_kwargs) -> None:
            events.append("wait_for_workers")

        def run(self, _stop_event) -> None:
            events.append("run")

        def stop(self) -> None:
            events.append("stop")

    monkeypatch.setattr(dev_stack, "build_service_specs", lambda _config: ())
    monkeypatch.setattr(dev_stack, "DevStackSupervisor", RecordingSupervisor)
    monkeypatch.setattr(local_release.signal, "signal", lambda *_args: None)

    assert local_release.supervise_local(
        config(assistant_enabled=False),
        LocalPaths.discover(tmp_path / "local-home"),
        release_version="0.1.0",
    ) == 0
    assert events == [
        "start_api",
        "start_services",
        "wait_for_api",
        "wait_for_service:workbench",
        "wait_for_workers",
        "run",
        "stop",
    ]


def test_stop_does_not_signal_an_unverified_stale_pid(
    tmp_path: Path, monkeypatch
) -> None:
    paths = LocalPaths.discover(tmp_path)
    value = config(assistant_enabled=False)
    write_local_state(
        paths,
        state_document(
            value,
            paths,
            release_version="0.1.0",
            supervisor_pid=9876,
            status="ready",
        ),
    )
    monkeypatch.setattr(local_release, "process_is_local_supervisor", lambda _pid: False)
    monkeypatch.setattr(
        local_release.os,
        "kill",
        lambda *_args: (_ for _ in ()).throw(AssertionError("must not signal")),
    )

    assert not stop_local(paths)
    assert local_release.read_local_state(paths)["status"] == "stopped"


def test_supervisor_identity_uses_untruncated_process_command(monkeypatch) -> None:
    captured: list[tuple[str, ...]] = []

    def run(command, **_kwargs):
        captured.append(tuple(command))
        return SimpleNamespace(
            returncode=0,
            stdout="python -m qhpc_ecosystem.cli local _supervise",
        )

    monkeypatch.setattr(local_release, "process_alive", lambda _pid: True)
    monkeypatch.setattr(local_release.subprocess, "run", run)

    assert local_release.process_is_local_supervisor(4321)
    assert captured == [("ps", "-ww", "-p", "4321", "-o", "command=")]


def test_cli_local_status_uses_portable_home(tmp_path: Path, capsys) -> None:
    assert cli.main(["local", "status", "--home", str(tmp_path)]) == 0
    assert "EQO Local: stopped" in capsys.readouterr().out


def test_cli_local_iqm_configuration_scopes_terminal_credential(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    captured: list[LocalStackConfig] = []
    monkeypatch.setenv("IQM_TOKEN", "terminal-secret")
    monkeypatch.setattr(
        local_release,
        "launch_local",
        lambda value, *_args, **_kwargs: captured.append(value)
        or {"status": "ready"},
    )

    assert cli.main(
        [
            "local",
            "up",
            "--home",
            str(tmp_path),
            "--no-assistant",
            "--start-iqm-worker",
            "--iqm-endpoint",
            "https://qccsw.ccs.ornl.gov",
            "--iqm-device-alias",
            "iqm-qpu-1",
        ]
    ) == 0

    assert captured[0].iqm_token == "terminal-secret"
    assert "terminal-secret" not in capsys.readouterr().out


def test_diagnostic_report_is_portable_and_secret_free(tmp_path: Path) -> None:
    paths = LocalPaths.discover(tmp_path / "private-user-location")
    report = diagnostic_report(paths, release_version="0.1.0")

    payload = json.dumps(report)
    assert report["assistant"]["available"] is True
    assert report["assistant"]["canonical_pages"] == 60
    assert report["service"]["status"] == "stopped"
    assert report["runtimes"] == []
    assert str(tmp_path) not in payload
    assert "token" not in payload.lower()

    destination = tmp_path / "support" / "diagnostic.json"
    assert write_diagnostic_report(report, destination) == destination.resolve()
    assert destination.stat().st_mode & 0o077 == 0
    with pytest.raises(LocalReleaseError, match="already exists"):
        write_diagnostic_report(report, destination)


def test_cli_manages_optional_runtime_and_writes_diagnostics(
    tmp_path: Path, capsys
) -> None:
    home = tmp_path / "home"
    artifact = tmp_path / "runtime.whl"
    artifact.write_bytes(b"optional runtime")
    digest = "sha256:" + __import__("hashlib").sha256(artifact.read_bytes()).hexdigest()
    reference = "qhpc-runtime://wheels/runtime.whl"

    assert cli.main(
        [
            "local",
            "runtime",
            "install",
            str(artifact),
            "--reference",
            reference,
            "--digest",
            digest,
            "--home",
            str(home),
        ]
    ) == 0
    assert "runtime installed" in capsys.readouterr().out
    assert cli.main(
        ["local", "runtime", "list", "--json", "--home", str(home)]
    ) == 0
    assert json.loads(capsys.readouterr().out)[0]["reference"] == reference
    assert cli.main(
        ["local", "runtime", "remove", reference, "--home", str(home)]
    ) == 0
    assert "runtime removed" in capsys.readouterr().out

    report = tmp_path / "diagnostic.json"
    assert cli.main(
        ["local", "diagnose", str(report), "--home", str(home)]
    ) == 0
    assert "diagnostic report" in capsys.readouterr().out
    assert json.loads(report.read_text(encoding="utf-8"))["schema_version"] == 1


def test_database_upgrade_creates_retained_backup(tmp_path: Path) -> None:
    paths = LocalPaths.discover(tmp_path)
    WorkflowEngine(paths.database, paths.artifact_root)
    with sqlite3.connect(paths.database) as connection:
        connection.execute("DELETE FROM schema_migrations")
        connection.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (3, 'test')"
        )

    report = prepare_local_database(paths)
    backup_root = Path(report["backup"])

    assert report["upgraded"]
    assert report["from_database_schema_version"] == 3
    assert report["database_schema_version"] == 4
    assert (backup_root / "workbench.sqlite").is_file()
    assert json.loads((backup_root / "upgrade.json").read_text())["status"] == (
        "upgraded"
    )
    with sqlite3.connect(backup_root / "workbench.sqlite") as connection:
        assert connection.execute(
            "SELECT MAX(version) FROM schema_migrations"
        ).fetchone()[0] == 3


def test_failed_database_upgrade_restores_previous_database(
    tmp_path: Path, monkeypatch
) -> None:
    paths = LocalPaths.discover(tmp_path)
    WorkflowEngine(paths.database, paths.artifact_root)
    with sqlite3.connect(paths.database) as connection:
        connection.execute("DELETE FROM schema_migrations")
        connection.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (3, 'test')"
        )

    class FailingMigration:
        def __init__(self, database: str | Path, _artifact_root: str | Path) -> None:
            with sqlite3.connect(database) as connection:
                connection.execute("DELETE FROM schema_migrations")
                connection.execute(
                    "INSERT INTO schema_migrations(version, applied_at) "
                    "VALUES (4, 'failed')"
                )
            raise RuntimeError("simulated migration failure")

    monkeypatch.setattr(engine_module, "WorkflowEngine", FailingMigration)

    with pytest.raises(LocalReleaseError, match="previous database was restored"):
        prepare_local_database(paths)

    with sqlite3.connect(paths.database) as connection:
        assert connection.execute(
            "SELECT MAX(version) FROM schema_migrations"
        ).fetchone()[0] == 3
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    backup_roots = list(paths.backup_root.glob("before-upgrade-*"))
    assert len(backup_roots) == 1
    assert (backup_roots[0] / "failed-workbench.sqlite").is_file()
    assert json.loads((backup_roots[0] / "upgrade.json").read_text())["status"] == (
        "rolled-back"
    )
