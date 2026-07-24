from __future__ import annotations

from pathlib import Path

from qhpc_ecosystem import cli, runtime


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "ecosystem.yaml"


def invoke(*args: str) -> int:
    return cli.main(["--catalog", str(CATALOG), *args])


def test_list_and_info_do_not_require_apptainer(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        runtime, "find_runtime", lambda *_: (_ for _ in ()).throw(AssertionError)
    )

    assert invoke("list") == 0
    assert "OpenQEvo" in capsys.readouterr().out
    assert invoke("info", "ftqc") == 0
    output = capsys.readouterr().out
    assert "Canonical status:  ambiguous" in output
    assert "QSCSoftwareThrust/FTQC" in output


def test_validate_checks_catalog_and_recipes(capsys) -> None:
    assert invoke("validate") == 0
    assert "19 repositories, 5 environments" in capsys.readouterr().out


def test_build_explains_docker_only_host(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        runtime.shutil,
        "which",
        lambda command: "/usr/local/bin/docker" if command == "docker" else None,
    )

    assert invoke("--image-dir", str(tmp_path), "build", "OpenQEvo") == 2
    error = capsys.readouterr().err
    assert "Apptainer is required" in error
    assert "Docker or Podman is installed" in error


def test_run_constructs_bound_workspace_command(tmp_path: Path, monkeypatch) -> None:
    image_dir = tmp_path / "images"
    image_dir.mkdir()
    (image_dir / "python-lib.sif").touch()
    commands: list[list[str]] = []
    monkeypatch.setattr(runtime, "find_runtime", lambda *_: "/usr/bin/apptainer")
    monkeypatch.setattr(
        runtime, "execute", lambda command: commands.append(list(command)) or 0
    )

    result = cli.main(
        [
            "--catalog",
            str(CATALOG),
            "--image-dir",
            str(image_dir),
            "run",
            "OpenQEvo",
            "--workspace",
            str(tmp_path),
            "--",
            "python3",
            "-V",
        ]
    )

    assert result == 0
    assert commands == [
        [
            "/usr/bin/apptainer",
            "exec",
            "--bind",
            f"{tmp_path}:/workspace",
            "--pwd",
            "/workspace",
            str(image_dir / "python-lib.sif"),
            "python3",
            "-V",
        ]
    ]


def test_blocked_repository_stops_before_runtime(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        runtime, "find_runtime", lambda *_: (_ for _ in ()).throw(AssertionError)
    )
    assert invoke("build", "HeteQSys") == 2
    assert "is blocked" in capsys.readouterr().err
