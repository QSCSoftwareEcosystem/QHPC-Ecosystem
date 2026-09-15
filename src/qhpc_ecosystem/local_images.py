"""Install and verify the immutable OCI image set used by EQO Local."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from .container_engine import (
    apptainer_requested,
    read_locks,
    sha256_file,
    sif_path_for,
    sif_store_dir,
    write_lock_entry,
)
from .local_assets import asset_path


_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_LOCAL_REFERENCE = re.compile(r"^[a-z0-9][a-z0-9._/-]*:[A-Za-z0-9_.-]+$")
_PUBLIC_GHCR_REFERENCE = re.compile(
    r"^ghcr\.io/qscsoftwareecosystem/[a-z0-9][a-z0-9._-]*@sha256:[0-9a-f]{64}$"
)


class LocalImageError(RuntimeError):
    """Raised when an admitted public image cannot be installed safely."""


@dataclass(frozen=True)
class PublicImage:
    """One exact public image and the local name EQO verifies."""

    id: str
    source: str
    local_reference: str
    local_id: str
    platform: str


@dataclass(frozen=True)
class ImageInstallResult:
    """One image result from a local image-set preflight."""

    id: str
    local_reference: str
    action: str


Runner = Callable[..., subprocess.CompletedProcess[str]]


def public_image_manifest_path() -> Path:
    """Return the release-owned manifest for the public EQO image set."""

    return asset_path("public-image-manifest")


def load_public_images(path: str | Path | None = None) -> tuple[PublicImage, ...]:
    """Load a tightly scoped, immutable public-image manifest."""

    manifest_path = Path(path) if path is not None else public_image_manifest_path()
    try:
        document = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise LocalImageError(
            f"cannot read EQO public image manifest: {manifest_path}"
        ) from error

    if not isinstance(document, dict):
        raise LocalImageError("EQO public image manifest must be an object")
    if document.get("api_version") != "eqo.local-images/v1":
        raise LocalImageError("unsupported EQO public image manifest version")
    if document.get("platform") != "linux/amd64":
        raise LocalImageError("EQO public image manifest must target linux/amd64")
    entries = document.get("images")
    if not isinstance(entries, list) or not entries:
        raise LocalImageError("EQO public image manifest must declare images")

    images: list[PublicImage] = []
    ids: set[str] = set()
    local_references: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise LocalImageError("EQO public image entries must be objects")
        try:
            image = PublicImage(
                id=entry["id"],
                source=entry["source"],
                local_reference=entry["local_reference"],
                local_id=entry["local_id"],
                platform=document["platform"],
            )
        except KeyError as error:
            raise LocalImageError(
                f"EQO public image entry is missing {error.args[0]!r}"
            ) from error
        if not isinstance(image.id, str) or not image.id:
            raise LocalImageError("EQO public image id must be a nonempty string")
        if not _PUBLIC_GHCR_REFERENCE.fullmatch(image.source):
            raise LocalImageError(
                f"EQO public image source is not an immutable QSC GHCR reference: {image.source}"
            )
        if not _LOCAL_REFERENCE.fullmatch(image.local_reference):
            raise LocalImageError(
                f"EQO public image has an invalid local reference: {image.local_reference}"
            )
        if not _SHA256.fullmatch(image.local_id):
            raise LocalImageError(
                f"EQO public image has an invalid local image ID: {image.local_id}"
            )
        if image.id in ids or image.local_reference in local_references:
            raise LocalImageError("EQO public image manifest contains duplicate entries")
        ids.add(image.id)
        local_references.add(image.local_reference)
        images.append(image)
    return tuple(images)


def _run(
    command: Sequence[str],
    *,
    runner: Runner,
    capture_output: bool,
) -> subprocess.CompletedProcess[str]:
    try:
        result = runner(
            list(command),
            check=False,
            text=True,
            capture_output=capture_output,
        )
    except OSError as error:
        raise LocalImageError(
            "Docker is required to install EQO Local images; start Docker Desktop first"
        ) from error
    if result.returncode:
        detail = (result.stderr or "").strip()
        suffix = f": {detail}" if detail else ""
        raise LocalImageError(f"Docker command failed: {' '.join(command)}{suffix}")
    return result


def _local_image_id(
    image: PublicImage,
    *,
    runner: Runner,
    docker: str,
) -> str | None:
    try:
        result = runner(
            [docker, "image", "inspect", "--format", "{{.Id}}", image.local_reference],
            check=False,
            text=True,
            capture_output=True,
        )
    except OSError as error:
        raise LocalImageError(
            "Docker is required to install EQO Local images; start Docker Desktop first"
        ) from error
    if result.returncode:
        return None
    value = (result.stdout or "").strip()
    if not _SHA256.fullmatch(value):
        raise LocalImageError(
            f"Docker returned an invalid image ID for {image.local_reference}"
        )
    return value


def _apptainer_arch(platform: str) -> str:
    """Map an OCI ``os/arch`` platform onto Apptainer's ``--arch`` value."""

    return platform.split("/", 1)[1] if "/" in platform else platform


def _run_apptainer(
    command: Sequence[str],
    *,
    runner: Runner,
    capture_output: bool,
) -> subprocess.CompletedProcess[str]:
    try:
        result = runner(
            list(command),
            check=False,
            text=True,
            capture_output=capture_output,
        )
    except OSError as error:
        raise LocalImageError(
            "Apptainer is required to install EQO Local SIF images "
            "(requested via USE_APPTAINER=1); install Apptainer first"
        ) from error
    if result.returncode:
        detail = (result.stderr or "").strip()
        suffix = f": {detail}" if detail else ""
        raise LocalImageError(f"Apptainer command failed: {' '.join(command)}{suffix}")
    return result


def _ensure_public_sifs(
    *,
    manifest: str | Path | None,
    runner: Runner,
    apptainer: str,
) -> tuple[ImageInstallResult, ...]:
    """Pull each admitted image into a verified SIF by its immutable digest.

    Identity is guaranteed by pulling ``docker://…@sha256:`` by digest. The
    resulting SIF hash is recorded in the cache-side lock so a reuse can detect
    local tampering (a SIF is not byte-reproducible, so no fixed hash is pinned
    in the committed manifest).
    """

    store = sif_store_dir()
    store.mkdir(parents=True, exist_ok=True)
    locks = read_locks()
    results: list[ImageInstallResult] = []
    for image in load_public_images(manifest):
        source_digest = image.source.split("@", 1)[1]
        sif = sif_path_for(image.id)
        entry = locks.get(image.local_reference)
        if (
            sif.is_file()
            and entry is not None
            and entry.get("source_digest") == source_digest
            and entry.get("sif_sha256") == sha256_file(sif)
        ):
            results.append(
                ImageInstallResult(
                    id=image.id,
                    local_reference=image.local_reference,
                    action="reused",
                )
            )
            continue

        _run_apptainer(
            [
                apptainer,
                "pull",
                "--force",
                "--arch",
                _apptainer_arch(image.platform),
                str(sif),
                f"docker://{image.source}",
            ],
            runner=runner,
            capture_output=False,
        )
        if not sif.is_file():
            raise LocalImageError(
                f"Apptainer pull did not produce a SIF for {image.local_reference}"
            )
        digest = sha256_file(sif)
        write_lock_entry(
            image.local_reference,
            image_id=image.id,
            source=image.source,
            source_digest=source_digest,
            sif_path=sif,
            sif_sha256=digest,
        )
        results.append(
            ImageInstallResult(
                id=image.id,
                local_reference=image.local_reference,
                action="installed",
            )
        )
    return tuple(results)


def ensure_public_images(
    *,
    manifest: str | Path | None = None,
    runner: Runner = subprocess.run,
    docker: str = "docker",
    apptainer: str = "apptainer",
) -> tuple[ImageInstallResult, ...]:
    """Install only absent or mismatched admitted images, then verify all IDs.

    Every network request names a GHCR digest recorded in the reviewed release
    manifest. Under Docker (the default) a tag is applied locally only after that
    immutable payload has been downloaded. Under ``USE_APPTAINER=1`` each image is
    pulled by digest into a verified SIF. No mutable tag or host-native fallback
    is used by either path.
    """

    if apptainer_requested():
        return _ensure_public_sifs(
            manifest=manifest, runner=runner, apptainer=apptainer
        )

    results: list[ImageInstallResult] = []
    for image in load_public_images(manifest):
        actual = _local_image_id(image, runner=runner, docker=docker)
        if actual == image.local_id:
            results.append(
                ImageInstallResult(
                    id=image.id,
                    local_reference=image.local_reference,
                    action="reused",
                )
            )
            continue

        _run(
            [docker, "pull", "--platform", image.platform, image.source],
            runner=runner,
            capture_output=False,
        )
        _run(
            [docker, "tag", image.source, image.local_reference],
            runner=runner,
            capture_output=True,
        )
        actual = _local_image_id(image, runner=runner, docker=docker)
        if actual != image.local_id:
            raise LocalImageError(
                f"downloaded EQO image identity mismatch for {image.local_reference}: "
                f"expected {image.local_id}, found {actual or 'missing'}"
            )
        results.append(
            ImageInstallResult(
                id=image.id,
                local_reference=image.local_reference,
                action="installed",
            )
        )
    return tuple(results)
