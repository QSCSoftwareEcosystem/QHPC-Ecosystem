from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from qhpc_ecosystem import cli
from qhpc_ecosystem import engine as engine_module
from qhpc_ecosystem import local_release
from qhpc_ecosystem.engine import WorkflowEngine
from qhpc_ecosystem.local_release import (
    LocalPaths,
    LocalReleaseError,
    LocalStackConfig,
    diagnostic_report,
    local_status,
    prepare_local_database,
    require_storage_capacity,
    state_document,
    stop_local,
    supervisor_command,
    write_local_config,
    write_local_state,
    write_diagnostic_report,
)


ROOT = Path(__file__).resolve().parents[1]


def config(**overrides) -> LocalStackConfig:
    values = {
        "catalog": str(ROOT / "ecosystem.yaml"),
        "registry": str(ROOT / "examples" / "registry.yaml"),
        "deployment_profile": str(ROOT / "deployments" / "initial.yaml"),
        "workflows": (),
        "assistant_interface": str(ROOT / "integrations" / "chatqec" / "service.yaml"),
        "assistant_source_checkout": None,
        "host": "127.0.0.1",
        "workbench_port": 18080,
        "api_port": 18081,
        "assistant_port": 18082,
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


def test_local_config_rejects_non_loopback_and_port_collisions() -> None:
    with pytest.raises(LocalReleaseError, match="loopback"):
        config(host="0.0.0.0").validate()
    with pytest.raises(LocalReleaseError, match="must be different"):
        config(api_port=18080).validate()


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


def test_cli_local_status_uses_portable_home(tmp_path: Path, capsys) -> None:
    assert cli.main(["local", "status", "--home", str(tmp_path)]) == 0
    assert "EQO Local: stopped" in capsys.readouterr().out


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
