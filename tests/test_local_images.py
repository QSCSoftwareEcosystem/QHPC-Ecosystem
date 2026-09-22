from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import qhpc_ecosystem.container_engine as container_engine
import qhpc_ecosystem.local_images as local_images
from qhpc_ecosystem.local_images import (
    LocalImageError,
    ensure_public_images,
    load_public_images,
)


@pytest.fixture(autouse=True)
def _amd64_host_without_ambient_opt_ins(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default to a Linux/AMD64 host so results do not depend on the runner.

    Tests that exercise Linux/ARM64 selection override these explicitly.
    """

    monkeypatch.delenv(local_images.UNSIGNED_ARM64_ALPHA_ENV, raising=False)
    monkeypatch.delenv("USE_APPTAINER", raising=False)
    monkeypatch.setattr(container_engine.platform, "machine", lambda: "x86_64")


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


def test_linux_arm64_refuses_an_amd64_only_admitted_release_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest, _digest = write_manifest(tmp_path)
    commands: list[list[str]] = []
    monkeypatch.setattr(local_images.sys, "platform", "linux")
    monkeypatch.setattr(container_engine.platform, "machine", lambda: "aarch64")

    with pytest.raises(LocalImageError, match="no admitted public EQO Linux/ARM64"):
        ensure_public_images(manifest=manifest, runner=docker_runner({}, commands))

    assert commands == []


def test_apptainer_on_native_arm64_selects_the_arm64_manifest_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(local_images.UNSIGNED_ARM64_ALPHA_ENV, raising=False)
    monkeypatch.setenv("USE_APPTAINER", "1")
    monkeypatch.setattr(local_images.sys, "platform", "linux")
    monkeypatch.setattr(container_engine.platform, "machine", lambda: "aarch64")

    images = load_public_images()

    assert {image.id for image in images} == {
        "stim-arm64-alpha",
        "nwqsim-arm64-alpha",
        "ftqc-arm64-alpha",
    }
    assert {image.platform for image in images} == {"linux/arm64"}
    assert all("linux-arm64-alpha" in image.local_reference for image in images)


def test_apptainer_on_amd64_keeps_the_amd64_manifest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(local_images.UNSIGNED_ARM64_ALPHA_ENV, raising=False)
    monkeypatch.setenv("USE_APPTAINER", "1")
    monkeypatch.setattr(local_images.sys, "platform", "linux")
    monkeypatch.setattr(container_engine.platform, "machine", lambda: "x86_64")

    assert not local_images.unsigned_arm64_alpha_enabled()
    assert {image.platform for image in load_public_images()} == {"linux/amd64"}


def test_arm64_images_are_not_selected_without_apptainer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(local_images.UNSIGNED_ARM64_ALPHA_ENV, raising=False)
    monkeypatch.delenv("USE_APPTAINER", raising=False)
    monkeypatch.setattr(local_images.sys, "platform", "linux")
    monkeypatch.setattr(container_engine.platform, "machine", lambda: "aarch64")

    assert not local_images.unsigned_arm64_alpha_enabled()


def test_unsigned_arm64_alpha_environment_rejects_other_hosts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(local_images.UNSIGNED_ARM64_ALPHA_ENV, "1")
    monkeypatch.setattr(local_images.sys, "platform", "darwin")

    with pytest.raises(LocalImageError, match="supported only on Linux/ARM64"):
        ensure_public_images(manifest=write_manifest(tmp_path)[0])


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


def _capturing_apptainer_runner(seen_envs: list[dict[str, str] | None]):
    def run(command, **kwargs):
        seen_envs.append(kwargs.get("env"))
        if command[1] == "pull":
            sif = Path(command[command.index("--arch") + 2])
            sif.parent.mkdir(parents=True, exist_ok=True)
            sif.write_bytes(b"pulled-sif")
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        raise AssertionError(f"unexpected Apptainer command: {command}")

    return run


def test_ensure_public_images_defaults_apptainer_tmpdir_to_var_tmp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Apptainer's OCI-to-SIF unpack must not depend on a small ``/tmp``.

    HPC login nodes and tmpfs-backed Linux VMs routinely cap ``/tmp`` well
    below the size of an unpacked container rootfs, which fails the pull with
    "no space left on device". EQO defaults ``APPTAINER_TMPDIR`` to
    ``/var/tmp`` instead, which conventionally holds larger, longer-lived
    scratch data than a tmpfs-backed ``/tmp`` — and, unlike a directory under
    the user's home, is never a network or virtiofs share that could reject
    the xattr operations a rootfs unpack performs.
    """

    monkeypatch.setenv("USE_APPTAINER", "1")
    monkeypatch.delenv("APPTAINER_TMPDIR", raising=False)
    monkeypatch.delenv("TMPDIR", raising=False)
    monkeypatch.setattr(container_engine, "default_image_dir", lambda: tmp_path)
    manifest, _digest = write_manifest(tmp_path)
    seen_envs: list[dict[str, str] | None] = []

    ensure_public_images(
        manifest=manifest, runner=_capturing_apptainer_runner(seen_envs)
    )

    assert len(seen_envs) == 1
    env = seen_envs[0]
    assert env is not None
    assert env["APPTAINER_TMPDIR"] == "/var/tmp"


def test_ensure_public_images_ignores_an_incidental_tmpdir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A merely-present ``TMPDIR`` must not suppress the ``/var/tmp`` default.

    macOS (and many shells) export a per-session ``TMPDIR`` on every process
    regardless of whether anyone configured Apptainer's scratch space. That
    was observed to reach Apptainer running inside a Linux VM through a shell
    wrapper, name a host-only path that does not exist in the guest, and
    silently fall back to the guest's small ``/tmp`` — reproducing the
    original "no space left on device" failure. Only the Apptainer-specific
    variable counts as deliberate configuration.
    """

    monkeypatch.setenv("USE_APPTAINER", "1")
    monkeypatch.delenv("APPTAINER_TMPDIR", raising=False)
    monkeypatch.setenv("TMPDIR", "/var/folders/incidental-macos-tmpdir/T")
    monkeypatch.setattr(container_engine, "default_image_dir", lambda: tmp_path)
    manifest, _digest = write_manifest(tmp_path)
    seen_envs: list[dict[str, str] | None] = []

    ensure_public_images(
        manifest=manifest, runner=_capturing_apptainer_runner(seen_envs)
    )

    assert len(seen_envs) == 1
    env = seen_envs[0]
    assert env is not None
    assert env["APPTAINER_TMPDIR"] == "/var/tmp"


def test_ensure_public_images_respects_an_existing_apptainer_tmpdir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An operator- or scheduler-supplied scratch directory is never overridden."""

    monkeypatch.setenv("USE_APPTAINER", "1")
    monkeypatch.setenv("APPTAINER_TMPDIR", "/scratch/site-scheduler-scratch")
    monkeypatch.setattr(container_engine, "default_image_dir", lambda: tmp_path)
    manifest, _digest = write_manifest(tmp_path)
    seen_envs: list[dict[str, str] | None] = []

    ensure_public_images(
        manifest=manifest, runner=_capturing_apptainer_runner(seen_envs)
    )

    assert len(seen_envs) == 1
    env = seen_envs[0]
    assert env is not None
    assert env["APPTAINER_TMPDIR"] == "/scratch/site-scheduler-scratch"


def test_ensure_public_images_warns_on_apptainer_arch_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("USE_APPTAINER", "1")
    monkeypatch.setattr(container_engine, "default_image_dir", lambda: tmp_path)
    monkeypatch.setattr(container_engine.platform, "machine", lambda: "ppc64le")
    manifest, _digest = write_manifest(tmp_path)
    commands: list[list[str]] = []

    result = ensure_public_images(manifest=manifest, runner=apptainer_runner(commands))

    assert [(entry.id, entry.action) for entry in result] == [
        ("test-image", "installed")
    ]
    assert commands, "the pull still proceeds despite the arch mismatch"
    warning = capsys.readouterr().err
    assert "ppc64le" in warning
    assert "amd64" in warning
    assert "exec format error" in warning


def test_ensure_public_images_refuses_unsigned_arm64_candidates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("USE_APPTAINER", "1")
    monkeypatch.setattr(container_engine.platform, "machine", lambda: "aarch64")
    monkeypatch.setattr(local_images.sys, "platform", "linux")
    manifest, _digest = write_manifest(tmp_path)

    with pytest.raises(LocalImageError, match="ARM64 internal-alpha candidates remain unsigned"):
        ensure_public_images(manifest=manifest, runner=apptainer_runner([]))
