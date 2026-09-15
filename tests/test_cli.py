from __future__ import annotations

import json
from pathlib import Path

from qhpc_ecosystem import cli, runtime


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "ecosystem.yaml"


def invoke(*args: str) -> int:
    return cli.main(["--catalog", str(CATALOG), *args])


def test_eqo_is_the_primary_cli_name() -> None:
    parser = cli.build_parser()

    assert parser.prog == "eqo"
    assert parser.format_help().startswith("usage: eqo ")


def test_iqm_base_url_defaults_to_the_isolated_worker_endpoint(monkeypatch) -> None:
    monkeypatch.setenv("IQM_BASE_URL", "https://qccsw.ccs.ornl.gov")
    parser = cli.build_parser()

    direct = parser.parse_args(
        [
            "iqm-worker",
            "--registry",
            "examples/registry.yaml",
            "--deployment-profile",
            "deployments/initial.yaml",
            "--device-alias",
            "approved-device",
        ]
    )
    supervised = parser.parse_args(
        [
            "dev",
            "up",
            "--start-iqm-worker",
            "--iqm-device-alias",
            "approved-device",
        ]
    )

    assert direct.endpoint == "https://qccsw.ccs.ornl.gov"
    assert supervised.iqm_endpoint == "https://qccsw.ccs.ornl.gov"


def test_iqm_token_prompt_is_no_echo_and_rejects_an_empty_value(monkeypatch) -> None:
    prompts: list[str] = []
    monkeypatch.setattr(
        cli.getpass,
        "getpass",
        lambda prompt: prompts.append(prompt) or "worker-only-token",
    )

    assert cli._prompt_iqm_token("IQM_TOKEN") == "worker-only-token"
    assert prompts == ["Enter IQM_TOKEN for the isolated IQM worker: "]

    monkeypatch.setattr(cli.getpass, "getpass", lambda _prompt: "")
    try:
        cli._prompt_iqm_token("IQM_TOKEN")
    except cli.ContractError as error:
        assert "required" in str(error)
    else:  # pragma: no cover - protects the security boundary assertion above
        raise AssertionError("the token prompt accepted an empty value")


def test_iqm_simulation_worker_is_credential_free(tmp_path: Path, capsys) -> None:
    assert invoke(
        "iqm-simulation-worker",
        "--registry",
        str(ROOT / "examples" / "registry.yaml"),
        "--deployment-profile",
        str(ROOT / "deployments" / "initial.yaml"),
        "--database",
        str(tmp_path / "workbench.sqlite"),
        "--artifact-root",
        str(tmp_path / "artifacts"),
        "--once",
    ) == 0

    output = capsys.readouterr().out
    assert "no network; no credential; not hardware evidence" in output
    assert "IQM_TOKEN" not in output


def test_list_and_info_do_not_require_apptainer(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        runtime, "find_runtime", lambda *_: (_ for _ in ()).throw(AssertionError)
    )

    assert invoke("list") == 0
    assert "OpenQEvo" in capsys.readouterr().out
    assert invoke("info", "ftqc") == 0
    output = capsys.readouterr().out
    assert "Canonical status:  canonical" in output
    assert "Source:            https://github.com/QSCSoftwareEcosystem/FTQC" in output


def test_validate_checks_catalog_and_recipes(capsys) -> None:
    assert invoke("validate") == 0
    assert "26 repositories, 5 environments" in capsys.readouterr().out


def test_engagement_resources_are_listed_without_runtime_or_network(capsys) -> None:
    assert invoke("engagement", "list", "--json") == 0
    resources = json.loads(capsys.readouterr().out)
    assert resources["read_only"] is True
    assert [item["id"] for item in resources["resources"]] == [
        "hpc-ai-qc-crash-course",
        "quantum-computing-user-training",
        "fall-2026-qcup-hackathon",
    ]


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
