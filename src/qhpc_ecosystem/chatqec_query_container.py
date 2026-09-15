"""Deterministic build-context preparation for the ChatQEC query image."""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import tempfile
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from .chatqec_query_service import PINNED_CHATQEC_REVISION
from .operation_runtime import OperationRuntimeError, find_oci_builder


SOURCE_DATE_EPOCH = 1787598244
SOURCE_ARCHIVE_DIGEST = "sha256:1af97636073b031a2e859bd56e544ea2064c3b7af1ebf6af827202177a472718"
UPSTREAM_LOCK_DIGEST = "sha256:214fff8b9ffc463ecea2667a15436b6beb8cb8a20173667941003b891508a511"
QUERY_BASE_IMAGE = (
    "docker.io/library/python:3.11.13-slim-bookworm"
    "@sha256:cec9aa7aa96eea4fa036e9b82be1e6b325f2e3707f462d885868df51ec0a4b47"
)
_ADAPTER_FILES = (
    "src/qhpc_ecosystem/__init__.py",
    "src/qhpc_ecosystem/chatqec_readiness.py",
    "src/qhpc_ecosystem/chatqec_query_service.py",
    "src/qhpc_ecosystem/service_adapters.py",
)
_RECIPE = "containers/services/chatqec-query/Containerfile"


class ChatQECQueryContainerError(RuntimeError):
    """Raised when a query image context is not reproducible or safe to build."""


@dataclass(frozen=True)
class PreparedQueryContext:
    path: Path
    source_revision: str
    source_archive_digest: str
    wheels: tuple[dict[str, str], ...]


def _digest(payload: bytes) -> str:
    return "sha256:" + sha256(payload).hexdigest()


def _workspace_root(explicit: str | Path | None = None) -> Path:
    if explicit is not None:
        root = Path(explicit).expanduser().resolve()
    else:
        root = Path(__file__).resolve().parents[2]
    if not (root / "pyproject.toml").is_file() or not (root / "src/qhpc_ecosystem").is_dir():
        raise ChatQECQueryContainerError(f"EQO workspace root is invalid: {root}")
    return root


def _git(source: Path, *arguments: str, text: bool = True) -> str | bytes:
    try:
        result = subprocess.run(
            ["git", "-C", str(source), *arguments],
            check=True,
            capture_output=True,
            text=text,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise ChatQECQueryContainerError("unable to verify the ChatQEC source checkout") from error
    return result.stdout.strip() if text else result.stdout


def _write(path: Path, payload: bytes, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    path.chmod(mode)
    os.utime(path, (SOURCE_DATE_EPOCH, SOURCE_DATE_EPOCH))


def _wheel_records(wheelhouse: Path) -> tuple[dict[str, str], ...]:
    if not wheelhouse.is_dir():
        raise ChatQECQueryContainerError("ChatQEC query build requires an approved wheelhouse directory")
    wheels = sorted(item for item in wheelhouse.iterdir() if item.is_file() and item.suffix == ".whl")
    if not wheels or any(item.is_symlink() for item in wheels):
        raise ChatQECQueryContainerError("ChatQEC query wheelhouse must contain regular wheel files")
    unexpected = [item.name for item in wheelhouse.iterdir() if item.name not in {wheel.name for wheel in wheels}]
    if unexpected:
        raise ChatQECQueryContainerError("ChatQEC query wheelhouse contains non-wheel entries")
    return tuple(
        {"filename": wheel.name, "digest": _digest(wheel.read_bytes())}
        for wheel in wheels
    )


def _metadata(root: Path, wheels: tuple[dict[str, str], ...]) -> dict[str, Any]:
    adapter = []
    for relative in _ADAPTER_FILES:
        path = root / relative
        if not path.is_file():
            raise ChatQECQueryContainerError(f"ChatQEC adapter file is missing: {relative}")
        adapter.append({"path": relative, "digest": _digest(path.read_bytes())})
    recipe = root / _RECIPE
    if not recipe.is_file():
        raise ChatQECQueryContainerError("ChatQEC query Containerfile is missing")
    return {
        "schema_version": 1,
        "source_revision": PINNED_CHATQEC_REVISION,
        "source_date_epoch": SOURCE_DATE_EPOCH,
        "source_archive_digest": SOURCE_ARCHIVE_DIGEST,
        "upstream_uv_lock_digest": UPSTREAM_LOCK_DIGEST,
        "base_image": QUERY_BASE_IMAGE,
        "recipe": {"path": _RECIPE, "digest": _digest(recipe.read_bytes())},
        "adapter": adapter,
        "wheels": list(wheels),
    }


def prepare_query_context(
    source: str | Path,
    wheelhouse: str | Path,
    destination: str | Path,
    *,
    workspace_root: str | Path | None = None,
) -> PreparedQueryContext:
    """Build an immutable, offline Docker context from a pinned Git archive."""

    root = _workspace_root(workspace_root)
    source_root = Path(source).expanduser().resolve()
    if not source_root.is_dir():
        raise ChatQECQueryContainerError("ChatQEC source checkout is not a directory")
    revision = _git(source_root, "rev-parse", "HEAD")
    if revision != PINNED_CHATQEC_REVISION:
        raise ChatQECQueryContainerError("ChatQEC checkout is not at the admitted revision")
    timestamp = _git(source_root, "show", "-s", "--format=%ct", PINNED_CHATQEC_REVISION)
    if timestamp != str(SOURCE_DATE_EPOCH):
        raise ChatQECQueryContainerError("ChatQEC source commit timestamp differs")
    archive = _git(source_root, "archive", "--format=tar", PINNED_CHATQEC_REVISION, text=False)
    assert isinstance(archive, bytes)
    if _digest(archive) != SOURCE_ARCHIVE_DIGEST:
        raise ChatQECQueryContainerError("ChatQEC source archive digest differs")
    lock = _git(source_root, "show", f"{PINNED_CHATQEC_REVISION}:uv.lock", text=False)
    assert isinstance(lock, bytes)
    if _digest(lock) != UPSTREAM_LOCK_DIGEST:
        raise ChatQECQueryContainerError("ChatQEC uv.lock digest differs")
    records = _wheel_records(Path(wheelhouse).expanduser().resolve())
    output = Path(destination).expanduser().resolve()
    if output.exists():
        raise ChatQECQueryContainerError(f"ChatQEC query build context already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=str(output.parent)))
    try:
        _write(temporary / "Containerfile", (root / _RECIPE).read_bytes(), 0o644)
        _write(temporary / "source.tar", archive, 0o644)
        for relative in _ADAPTER_FILES:
            source_file = root / relative
            destination_file = temporary / "qhpc_ecosystem" / source_file.name
            _write(destination_file, source_file.read_bytes(), 0o644)
        wheel_root = Path(wheelhouse).expanduser().resolve()
        for record in records:
            _write(
                temporary / "wheelhouse" / record["filename"],
                (wheel_root / record["filename"]).read_bytes(),
                0o644,
            )
        _write(
            temporary / "build-metadata.json",
            (json.dumps(_metadata(root, records), sort_keys=True, separators=(",", ":")) + "\n").encode("ascii"),
            0o644,
        )
        os.replace(temporary, output)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return PreparedQueryContext(
        path=output,
        source_revision=PINNED_CHATQEC_REVISION,
        source_archive_digest=SOURCE_ARCHIVE_DIGEST,
        wheels=records,
    )


def verify_query_context(
    context: str | Path,
    *,
    workspace_root: str | Path | None = None,
) -> dict[str, Any]:
    """Verify every context member before an offline image build."""

    root = _workspace_root(workspace_root)
    path = Path(context).expanduser().resolve()
    if not path.is_dir():
        raise ChatQECQueryContainerError("ChatQEC query build context is not a directory")
    metadata_path = path / "build-metadata.json"
    try:
        metadata = json.loads(metadata_path.read_text(encoding="ascii"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ChatQECQueryContainerError("ChatQEC query build metadata is invalid") from error
    wheels = metadata.get("wheels") if isinstance(metadata, dict) else None
    if not isinstance(wheels, list) or not all(isinstance(item, dict) for item in wheels):
        raise ChatQECQueryContainerError("ChatQEC query build wheel metadata is invalid")
    normalized_wheels = tuple(
        {"filename": str(item.get("filename", "")), "digest": str(item.get("digest", ""))}
        for item in wheels
    )
    if metadata != _metadata(root, normalized_wheels):
        raise ChatQECQueryContainerError("ChatQEC query build metadata differs from the recipe")
    expected = {"Containerfile", "source.tar", "build-metadata.json", "qhpc_ecosystem", "wheelhouse"}
    if {item.name for item in path.iterdir()} != expected:
        raise ChatQECQueryContainerError("ChatQEC query build context file set is invalid")
    required_adapter_names = {Path(item).name for item in _ADAPTER_FILES}
    if {item.name for item in (path / "qhpc_ecosystem").iterdir()} != required_adapter_names:
        raise ChatQECQueryContainerError("ChatQEC query adapter context is invalid")
    for item in metadata["adapter"]:
        adapter = path / "qhpc_ecosystem" / Path(item["path"]).name
        if not adapter.is_file() or _digest(adapter.read_bytes()) != item["digest"]:
            raise ChatQECQueryContainerError("ChatQEC query adapter file differs")
    if _digest((path / "source.tar").read_bytes()) != SOURCE_ARCHIVE_DIGEST:
        raise ChatQECQueryContainerError("ChatQEC query source archive differs")
    for item in normalized_wheels:
        wheel = path / "wheelhouse" / item["filename"]
        if not wheel.is_file() or _digest(wheel.read_bytes()) != item["digest"]:
            raise ChatQECQueryContainerError("ChatQEC query wheel differs")
    for item in path.rglob("*"):
        if item.is_symlink() or (item.is_file() and stat.S_IMODE(item.stat().st_mode) != 0o644):
            raise ChatQECQueryContainerError("ChatQEC query build context mode is invalid")
        if item.is_file() and item.stat().st_mtime_ns != SOURCE_DATE_EPOCH * 1_000_000_000:
            raise ChatQECQueryContainerError("ChatQEC query build context timestamp is invalid")
    return metadata


def build_query_image(
    context: str | Path,
    tag: str,
    *,
    builder: str | None = None,
    workspace_root: str | Path | None = None,
) -> str:
    """Build the context with networking disabled and return its local image ID."""

    verify_query_context(context, workspace_root=workspace_root)
    if not tag or tag.startswith("-") or any(character.isspace() for character in tag):
        raise ChatQECQueryContainerError("ChatQEC query image tag is invalid")
    try:
        executable = find_oci_builder(builder)
    except OperationRuntimeError as error:
        raise ChatQECQueryContainerError("Docker or Podman is required for the ChatQEC query image") from error
    try:
        subprocess.run(
            [executable, "build", "--network=none", "--file", str(Path(context) / "Containerfile"), "--tag", tag, str(context)],
            check=True,
        )
        result = subprocess.run(
            [executable, "image", "inspect", "--format", "{{.Id}}", tag],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise ChatQECQueryContainerError("ChatQEC query OCI build failed") from error
    image_id = result.stdout.strip()
    if not image_id.startswith("sha256:") or len(image_id) != 71:
        raise ChatQECQueryContainerError("ChatQEC query OCI builder returned an invalid image ID")
    return image_id
