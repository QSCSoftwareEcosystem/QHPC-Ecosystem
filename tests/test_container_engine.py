from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import qhpc_ecosystem.container_engine as container_engine
from qhpc_ecosystem.container_engine import (
    ContainerEngine,
    ContainerEngineError,
    apptainer_requested,
    require_network_isolation,
    run_command,
    select_engine,
    verified_sif,
    write_lock_entry,
)


DIGEST = "sha256:" + "a" * 64


def test_apptainer_requested_only_on_exact_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("USE_APPTAINER", raising=False)
    assert apptainer_requested() is False
    monkeypatch.setenv("USE_APPTAINER", "0")
    assert apptainer_requested() is False
    monkeypatch.setenv("USE_APPTAINER", "1")
    assert apptainer_requested() is True


def test_select_engine_defaults_to_docker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("USE_APPTAINER", raising=False)
    monkeypatch.setattr(
        container_engine.shutil,
        "which",
        lambda name: "/usr/bin/docker" if name == "docker" else None,
    )
    engine = select_engine()
    assert engine == ContainerEngine("docker", "/usr/bin/docker")
    assert engine.is_apptainer is False


def test_select_engine_uses_apptainer_when_requested(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("USE_APPTAINER", "1")
    monkeypatch.setattr(
        container_engine, "find_runtime", lambda name: "/usr/bin/apptainer"
    )
    engine = select_engine()
    assert engine == ContainerEngine("apptainer", "/usr/bin/apptainer")
    assert engine.is_apptainer is True


def test_select_engine_errors_when_apptainer_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from qhpc_ecosystem.catalog import CatalogError

    monkeypatch.setenv("USE_APPTAINER", "1")

    def missing(_name: str) -> str:
        raise CatalogError("Apptainer runtime not found: apptainer")

    monkeypatch.setattr(container_engine, "find_runtime", missing)
    with pytest.raises(ContainerEngineError, match="USE_APPTAINER=1"):
        select_engine()


def test_run_command_docker_argv_is_unchanged(tmp_path: Path) -> None:
    engine = ContainerEngine("docker", "/usr/bin/docker")
    inputs = tmp_path / "in"
    outputs = tmp_path / "out"
    command = run_command(
        engine,
        "qhpc/ftqc:tag",
        ("--preparation", "device"),
        input_bind=(inputs, "/inputs"),
        output_bind=(outputs, "/outputs"),
        platform="linux/amd64",
    )
    assert command == [
        "/usr/bin/docker",
        "run",
        "--rm",
        "--platform",
        "linux/amd64",
        "--network",
        "none",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,size=16m",
        "--mount",
        f"type=bind,src={inputs},dst=/inputs,readonly",
        "--mount",
        f"type=bind,src={outputs},dst=/outputs",
        "qhpc/ftqc:tag",
        "--preparation",
        "device",
    ]


def test_run_command_apptainer_argv(tmp_path: Path) -> None:
    engine = ContainerEngine("apptainer", "/usr/bin/apptainer")
    inputs = tmp_path / "in"
    outputs = tmp_path / "out"
    sif = tmp_path / "ftqc.sif"
    command = run_command(
        engine,
        str(sif),
        ("stim-simulate", "--shots", "4"),
        input_bind=(inputs, "/inputs"),
        output_bind=(outputs, "/outputs"),
        platform="linux/amd64",
    )
    assert command == [
        "/usr/bin/apptainer",
        "run",
        "--containall",
        "--cleanenv",
        "--writable-tmpfs",
        "--net",
        "--network",
        "none",
        "--bind",
        f"{inputs}:/inputs:ro",
        "--bind",
        f"{outputs}:/outputs",
        str(sif),
        "stim-simulate",
        "--shots",
        "4",
    ]


def test_run_command_apptainer_never_drops_network_isolation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An environment variable must never turn an admitted run into host networking."""

    monkeypatch.setenv("EQO_APPTAINER_SHARE_NETWORK", "1")
    command = run_command(
        ContainerEngine("apptainer", "/usr/bin/apptainer"),
        str(tmp_path / "x.sif"),
        (),
        network_none=True,
    )
    assert "--net" in command
    assert "--network" in command
    assert command[command.index("--network") + 1] == "none"


def test_require_network_isolation_rejects_a_host_that_cannot_create_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def denied(command, **_kwargs):
        return subprocess.CompletedProcess(
            command, 1, stdout="", stderr="network namespace is not permitted"
        )

    monkeypatch.setattr(container_engine.subprocess, "run", denied)
    with pytest.raises(ContainerEngineError, match="refuses to share the host network"):
        require_network_isolation(
            ContainerEngine("apptainer", "/usr/bin/apptainer"), str(tmp_path / "x.sif")
        )


def test_require_network_isolation_uses_an_isolated_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[list[str]] = []

    def allowed(command, **_kwargs):
        seen.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(container_engine.subprocess, "run", allowed)
    require_network_isolation(
        ContainerEngine("apptainer", "/usr/bin/apptainer"), str(tmp_path / "x.sif")
    )
    assert seen == [[
        "/usr/bin/apptainer", "exec", "--containall", "--cleanenv", "--net",
        "--network", "none", str(tmp_path / "x.sif"), "/bin/true",
    ]]


def _record_sif(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(container_engine, "default_image_dir", lambda: tmp_path)
    sif = container_engine.sif_path_for("stabsim")
    sif.parent.mkdir(parents=True, exist_ok=True)
    sif.write_bytes(b"immutable-sif-bytes")
    write_lock_entry(
        "qhpc/stabsim:tag",
        image_id="stabsim",
        source=f"ghcr.io/qscsoftwareecosystem/eqo-stabsim@{DIGEST}",
        source_digest=DIGEST,
        sif_path=sif,
        sif_sha256=container_engine.sha256_file(sif),
    )
    return sif


def test_verified_sif_accepts_a_matching_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sif = _record_sif(tmp_path, monkeypatch)
    assert verified_sif("qhpc/stabsim:tag", DIGEST) == sif


def test_verified_sif_rejects_wrong_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _record_sif(tmp_path, monkeypatch)
    with pytest.raises(ContainerEngineError, match="admitted digest"):
        verified_sif("qhpc/stabsim:tag", "sha256:" + "b" * 64)


def test_verified_sif_rejects_a_tampered_sif(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sif = _record_sif(tmp_path, monkeypatch)
    sif.write_bytes(b"tampered")
    with pytest.raises(ContainerEngineError, match="integrity check"):
        verified_sif("qhpc/stabsim:tag", DIGEST)


def test_verified_sif_requires_an_installed_image(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(container_engine, "default_image_dir", lambda: tmp_path)
    with pytest.raises(ContainerEngineError, match="no Apptainer SIF is installed"):
        verified_sif("qhpc/absent:tag", DIGEST)
