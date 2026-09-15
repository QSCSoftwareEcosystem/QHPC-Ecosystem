from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import qhpc_ecosystem.container_engine as container_engine
from qhpc_ecosystem.local_images import (
    LocalImageError,
    ensure_public_images,
    load_public_images,
)


def write_manifest(tmp_path: Path, *, source: str | None = None) -> tuple[Path, str]:
    digest = "sha256:" + "a" * 64
    manifest = tmp_path / "public-images.json"
    manifest.write_text(
        json.dumps(
            {
                "api_version": "eqo.local-images/v1",
                "platform": "linux/amd64",
                "images": [
                    {
                        "id": "test-image",
                        "source": source
                        or f"ghcr.io/qscsoftwareecosystem/eqo-test@{digest}",
                        "local_reference": "qhpc/test:1.0",
                        "local_id": digest,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return manifest, digest


def docker_runner(images: dict[str, str], commands: list[list[str]]):
    def run(command, **_kwargs):
        commands.append(command)
        if command[1:3] == ["image", "inspect"]:
            image_id = images.get(command[-1])
            return subprocess.CompletedProcess(
                command,
                0 if image_id else 1,
                stdout=f"{image_id}\n" if image_id else "",
                stderr="" if image_id else "not found",
            )
        if command[1] == "pull":
            images[command[-1]] = "sha256:" + "a" * 64
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        if command[1] == "tag":
            images[command[-1]] = images[command[-2]]
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        raise AssertionError(f"unexpected Docker command: {command}")

    return run


def test_local_images_manifest_allows_only_immutable_qsc_ghcr_images(
    tmp_path: Path,
) -> None:
    manifest, _digest = write_manifest(
        tmp_path,
        source="ghcr.io/another-organization/eqo-test@sha256:" + "a" * 64,
    )

    with pytest.raises(LocalImageError, match="immutable QSC GHCR"):
        load_public_images(manifest)


def test_ensure_public_images_reuses_a_verified_local_image(tmp_path: Path) -> None:
    manifest, digest = write_manifest(tmp_path)
    images = {"qhpc/test:1.0": digest}
    commands: list[list[str]] = []

    result = ensure_public_images(
        manifest=manifest,
        runner=docker_runner(images, commands),
    )

    assert [(entry.id, entry.action) for entry in result] == [
        ("test-image", "reused")
    ]
    assert commands == [
        ["docker", "image", "inspect", "--format", "{{.Id}}", "qhpc/test:1.0"]
    ]


def test_ensure_public_images_pulls_and_tags_a_missing_image(tmp_path: Path) -> None:
    manifest, digest = write_manifest(tmp_path)
    images: dict[str, str] = {}
    commands: list[list[str]] = []

    result = ensure_public_images(
        manifest=manifest,
        runner=docker_runner(images, commands),
    )

    source = f"ghcr.io/qscsoftwareecosystem/eqo-test@{digest}"
    assert [(entry.id, entry.action) for entry in result] == [
        ("test-image", "installed")
    ]
    assert commands == [
        ["docker", "image", "inspect", "--format", "{{.Id}}", "qhpc/test:1.0"],
        ["docker", "pull", "--platform", "linux/amd64", source],
        ["docker", "tag", source, "qhpc/test:1.0"],
        ["docker", "image", "inspect", "--format", "{{.Id}}", "qhpc/test:1.0"],
    ]


def apptainer_runner(commands: list[list[str]]):
    def run(command, **_kwargs):
        commands.append(command)
        if command[1] == "pull":
            sif = Path(command[command.index("--arch") + 2])
            sif.parent.mkdir(parents=True, exist_ok=True)
            sif.write_bytes(b"pulled-sif-" + command[-1].encode())
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        raise AssertionError(f"unexpected Apptainer command: {command}")

    return run


def test_ensure_public_images_pulls_a_verified_sif_under_apptainer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("USE_APPTAINER", "1")
    monkeypatch.setattr(container_engine, "default_image_dir", lambda: tmp_path)
    manifest, digest = write_manifest(tmp_path)
    commands: list[list[str]] = []

    result = ensure_public_images(
        manifest=manifest, runner=apptainer_runner(commands)
    )

    assert [(entry.id, entry.action) for entry in result] == [
        ("test-image", "installed")
    ]
    source = f"ghcr.io/qscsoftwareecosystem/eqo-test@{digest}"
    sif = container_engine.sif_path_for("test-image")
    assert commands == [
        ["apptainer", "pull", "--force", "--arch", "amd64", str(sif), f"docker://{source}"]
    ]
    assert sif.is_file()

    lock = container_engine.read_locks()["qhpc/test:1.0"]
    assert lock["source_digest"] == digest
    assert lock["sif_sha256"] == container_engine.sha256_file(sif)

    # A second call with the recorded, unmodified SIF reuses it without pulling.
    reuse_commands: list[list[str]] = []
    reuse = ensure_public_images(
        manifest=manifest, runner=apptainer_runner(reuse_commands)
    )
    assert [(entry.id, entry.action) for entry in reuse] == [("test-image", "reused")]
    assert reuse_commands == []
