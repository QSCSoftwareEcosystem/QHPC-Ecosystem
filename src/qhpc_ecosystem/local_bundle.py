"""Versioned, checksum-verified export and import for EQO Local state."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from .contract import ContractError, validate_contract_data
from .engine import WorkflowEngine
from .local_release import (
    LocalPaths,
    LocalReleaseError,
    process_is_local_supervisor,
    read_local_state,
)


BUNDLE_API_VERSION = "eqo.local/v1"
BUNDLE_KIND = "PortableStateBundle"
BUNDLE_SCHEMA_VERSION = 1
MANIFEST_PATH = "manifest.json"
STATE_PATH = "state.json"
MAX_MANIFEST_BYTES = 4 * 1024 * 1024
MAX_STATE_BYTES = 256 * 1024 * 1024


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _json_bytes(document: dict[str, Any]) -> bytes:
    return (
        json.dumps(
            document,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _digest_bytes(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()


def _digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _safe_component(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or value in {".", ".."}:
        raise LocalReleaseError(f"invalid {label} in portable state")
    if len(value) > 255 or "/" in value or "\\" in value or Path(value).name != value:
        raise LocalReleaseError(f"unsafe {label} in portable state: {value!r}")
    return value


def _safe_member_path(value: Any) -> str:
    if not isinstance(value, str):
        raise LocalReleaseError("portable bundle member path must be a string")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise LocalReleaseError(f"unsafe portable bundle member path: {value!r}")
    return value


def _require_stopped(paths: LocalPaths, operation: str) -> None:
    state = read_local_state(paths)
    if state is None:
        return
    pid = state.get("supervisor_pid")
    if isinstance(pid, int) and process_is_local_supervisor(pid):
        raise LocalReleaseError(
            f"stop EQO Local before {operation}: eqo local down"
        )


def _counts(state: dict[str, Any]) -> dict[str, int]:
    return {
        "workflow_versions": len(state["workflow_versions"]),
        "workflow_drafts": len(state["workflow_drafts"]),
        "runs": len(state["runs"]),
        "tasks": len(state["tasks"]),
        "task_attempts": len(state["task_attempts"]),
        "execution_events": len(state["execution_events"]),
        "input_artifacts": len(state["input_artifacts"]),
        "output_artifacts": len(state["output_artifacts"]),
        "artifact_payloads": (
            len(state["input_artifacts"]) + len(state["output_artifacts"])
        ),
    }


def _default_destination(paths: LocalPaths) -> Path:
    return paths.export_root / f"eqo-local-{_timestamp()}.eqo"


def _copy_to_archive(
    archive: zipfile.ZipFile,
    source: Path,
    member: str,
    *,
    expected_checksum: str,
    expected_size: int,
) -> None:
    digest = hashlib.sha256()
    size_bytes = 0
    with source.open("rb") as input_stream, archive.open(member, "w") as output_stream:
        while chunk := input_stream.read(1024 * 1024):
            digest.update(chunk)
            size_bytes += len(chunk)
            output_stream.write(chunk)
    actual_checksum = "sha256:" + digest.hexdigest()
    if actual_checksum != expected_checksum:
        raise LocalReleaseError(f"artifact changed during export: {source}")
    if size_bytes != expected_size:
        raise LocalReleaseError(f"artifact size changed during export: {source}")


def export_local_state(
    paths: LocalPaths,
    *,
    release_version: str,
    destination: str | Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Create a portable archive containing logical records and payloads."""

    _require_stopped(paths, "exporting state")
    paths.ensure()
    engine = WorkflowEngine(paths.database, paths.artifact_root)
    try:
        state = engine.export_portable_state()
    except (ContractError, OSError, RuntimeError) as error:
        raise LocalReleaseError(f"cannot export EQO Local state: {error}") from error

    target = (
        Path(destination).expanduser().resolve()
        if destination is not None
        else _default_destination(paths)
    )
    if target.exists() and target.is_dir():
        target = target / _default_destination(paths).name
    elif not target.suffix:
        target = target.with_suffix(".eqo")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not overwrite:
        raise LocalReleaseError(
            f"export already exists: {target}; pass --force to replace it"
        )

    payloads: list[tuple[Path, dict[str, Any]]] = []
    manifest_artifacts: list[dict[str, Any]] = []
    for provenance, collection_name in (
        ("input", "input_artifacts"),
        ("task-output", "output_artifacts"),
    ):
        for record in state[collection_name]:
            artifact_id = _safe_component(record["id"], "artifact ID")
            try:
                metadata, source, name = engine.verified_artifact_path(artifact_id)
            except (ContractError, FileNotFoundError, OSError) as error:
                raise LocalReleaseError(
                    f"cannot export artifact {artifact_id}: {error}"
                ) from error
            safe_name = _safe_component(name, "artifact name")
            member = f"artifacts/{provenance}/{artifact_id}/{safe_name}"
            record["payload"] = member
            entry = {
                "id": artifact_id,
                "provenance": provenance,
                "path": member,
                "name": safe_name,
                "checksum": metadata["checksum"],
                "size_bytes": metadata["size_bytes"],
            }
            manifest_artifacts.append(entry)
            payloads.append((source, entry))

    manifest_artifacts.sort(key=lambda item: item["path"])
    payloads.sort(key=lambda item: item[1]["path"])
    state_bytes = _json_bytes(state)
    local_state = read_local_state(paths) or {}
    manifest = {
        "api_version": BUNDLE_API_VERSION,
        "kind": BUNDLE_KIND,
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "created_at": _now(),
        "release_version": release_version,
        "database_schema_version": state["database_schema_version"],
        "registry_digest": local_state.get("registry_digest"),
        "deployment_profile_digest": local_state.get("deployment_profile_digest"),
        "state": {
            "path": STATE_PATH,
            "checksum": _digest_bytes(state_bytes),
            "size_bytes": len(state_bytes),
        },
        "artifacts": manifest_artifacts,
        "counts": _counts(state),
    }
    validate_contract_data("local-state-bundle", manifest)
    manifest_bytes = _json_bytes(manifest)

    temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    try:
        with zipfile.ZipFile(
            temporary,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=6,
        ) as archive:
            for source, entry in payloads:
                _copy_to_archive(
                    archive,
                    source,
                    entry["path"],
                    expected_checksum=entry["checksum"],
                    expected_size=entry["size_bytes"],
                )
            archive.writestr(STATE_PATH, state_bytes)
            archive.writestr(MANIFEST_PATH, manifest_bytes)
        temporary.chmod(0o600)
        os.replace(temporary, target)
    except LocalReleaseError:
        temporary.unlink(missing_ok=True)
        raise
    except (OSError, zipfile.BadZipFile) as error:
        temporary.unlink(missing_ok=True)
        raise LocalReleaseError(
            f"cannot write portable bundle {target}: {error}"
        ) from error

    return {
        "path": str(target),
        "checksum": _digest_file(target),
        "size_bytes": target.stat().st_size,
        "counts": manifest["counts"],
    }


def _read_member(
    archive: zipfile.ZipFile,
    path: str,
    *,
    maximum_bytes: int,
) -> bytes:
    try:
        info = archive.getinfo(path)
    except KeyError as error:
        raise LocalReleaseError(f"portable bundle is missing {path}") from error
    if info.flag_bits & 0x1:
        raise LocalReleaseError(f"encrypted portable bundle member is not supported: {path}")
    if info.is_dir() or info.file_size > maximum_bytes:
        raise LocalReleaseError(f"portable bundle member has an invalid size: {path}")
    try:
        content = archive.read(info)
    except (OSError, RuntimeError, zipfile.BadZipFile) as error:
        raise LocalReleaseError(f"cannot read portable bundle member {path}: {error}") from error
    if len(content) != info.file_size:
        raise LocalReleaseError(f"portable bundle member is truncated: {path}")
    return content


def _load_bundle(
    archive: zipfile.ZipFile,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, zipfile.ZipInfo]]:
    infos = archive.infolist()
    names = [info.filename for info in infos]
    if len(names) != len(set(names)):
        raise LocalReleaseError("portable bundle contains duplicate member names")
    info_by_name = {info.filename: info for info in infos}
    manifest_content = _read_member(
        archive,
        MANIFEST_PATH,
        maximum_bytes=MAX_MANIFEST_BYTES,
    )
    try:
        manifest = json.loads(manifest_content)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise LocalReleaseError(f"invalid portable bundle manifest: {error}") from error
    if not isinstance(manifest, dict):
        raise LocalReleaseError("portable bundle manifest must be an object")
    validate_contract_data("local-state-bundle", manifest)

    state_info = manifest["state"]
    state_path = _safe_member_path(state_info["path"])
    state_content = _read_member(
        archive,
        state_path,
        maximum_bytes=MAX_STATE_BYTES,
    )
    if len(state_content) != state_info["size_bytes"]:
        raise LocalReleaseError("portable state size does not match the manifest")
    if _digest_bytes(state_content) != state_info["checksum"]:
        raise LocalReleaseError("portable state checksum does not match the manifest")
    try:
        state = json.loads(state_content)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise LocalReleaseError(f"invalid portable state document: {error}") from error
    if not isinstance(state, dict):
        raise LocalReleaseError("portable state document must be an object")

    artifact_paths = {
        _safe_member_path(entry["path"]) for entry in manifest["artifacts"]
    }
    expected_names = {MANIFEST_PATH, state_path, *artifact_paths}
    if set(names) != expected_names:
        raise LocalReleaseError("portable bundle contains undeclared members")
    for path in artifact_paths:
        info = info_by_name[path]
        if info.is_dir() or info.flag_bits & 0x1:
            raise LocalReleaseError(f"invalid portable artifact member: {path}")
    return manifest, state, info_by_name


def _validate_payload_records(
    manifest: dict[str, Any],
    state: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    if manifest["database_schema_version"] != state.get("database_schema_version"):
        raise LocalReleaseError(
            "portable state database schema does not match the manifest"
        )
    try:
        actual_counts = _counts(state)
    except (KeyError, TypeError) as error:
        raise LocalReleaseError("portable state collections are incomplete") from error
    if actual_counts != manifest["counts"]:
        raise LocalReleaseError("portable state counts do not match the manifest")

    entries = {entry["id"]: entry for entry in manifest["artifacts"]}
    records: dict[str, dict[str, Any]] = {}
    for provenance, collection_name in (
        ("input", "input_artifacts"),
        ("task-output", "output_artifacts"),
    ):
        for record in state[collection_name]:
            if not isinstance(record, dict):
                raise LocalReleaseError("portable artifact record must be an object")
            artifact_id = _safe_component(record.get("id"), "artifact ID")
            if artifact_id in records:
                raise LocalReleaseError(
                    f"duplicate portable artifact identity: {artifact_id}"
                )
            entry = entries.get(artifact_id)
            if entry is None or entry["provenance"] != provenance:
                raise LocalReleaseError(
                    f"portable artifact manifest is missing {artifact_id}"
                )
            if (
                record.get("payload") != entry["path"]
                or record.get("checksum") != entry["checksum"]
                or record.get("size_bytes") != entry["size_bytes"]
            ):
                raise LocalReleaseError(
                    f"portable artifact metadata mismatch: {artifact_id}"
                )
            records[artifact_id] = record
    if set(records) != set(entries):
        raise LocalReleaseError("portable artifact identities do not match the manifest")
    return entries


def _restore_payload(
    archive: zipfile.ZipFile,
    entry: dict[str, Any],
    artifact_root: Path,
    final_artifact_root: Path,
) -> str:
    artifact_id = _safe_component(entry["id"], "artifact ID")
    name = _safe_component(entry["name"], "artifact name")
    directory = "inputs" if entry["provenance"] == "input" else "outputs"
    destination = artifact_root / directory / artifact_id / name
    destination.parent.mkdir(parents=True, exist_ok=False)
    digest = hashlib.sha256()
    size_bytes = 0
    try:
        with archive.open(entry["path"], "r") as source, destination.open("xb") as target:
            while chunk := source.read(1024 * 1024):
                digest.update(chunk)
                size_bytes += len(chunk)
                target.write(chunk)
    except (OSError, RuntimeError, zipfile.BadZipFile) as error:
        raise LocalReleaseError(
            f"cannot restore portable artifact {artifact_id}: {error}"
        ) from error
    if size_bytes != entry["size_bytes"]:
        raise LocalReleaseError(f"portable artifact size mismatch: {artifact_id}")
    if "sha256:" + digest.hexdigest() != entry["checksum"]:
        raise LocalReleaseError(f"portable artifact checksum mismatch: {artifact_id}")
    destination.chmod(0o600)
    return (final_artifact_root / directory / artifact_id / name).resolve().as_uri()


def _has_existing_state(paths: LocalPaths) -> bool:
    if paths.database.exists():
        return True
    return paths.artifact_root.exists() and any(paths.artifact_root.iterdir())


def _install_staged_state(
    paths: LocalPaths,
    stage_database: Path,
    stage_artifacts: Path,
    *,
    replace: bool,
) -> Path | None:
    existing = _has_existing_state(paths)
    if existing and not replace:
        raise LocalReleaseError(
            "EQO Local already contains state; pass --replace to import with an automatic backup"
        )

    backup_root: Path | None = None
    moved_database = False
    moved_artifacts = False
    installed_database = False
    installed_artifacts = False
    if existing:
        backup_root = (
            paths.backup_root
            / f"before-import-{_timestamp()}-{uuid.uuid4().hex[:8]}"
        )
        backup_root.mkdir(parents=True, exist_ok=False)

    try:
        if paths.database.exists():
            if backup_root is None:
                raise LocalReleaseError("destination database unexpectedly exists")
            os.replace(paths.database, backup_root / paths.database.name)
            moved_database = True
        for suffix in ("-wal", "-shm"):
            sidecar = Path(str(paths.database) + suffix)
            if sidecar.exists():
                if backup_root is None:
                    raise LocalReleaseError("destination database sidecar unexpectedly exists")
                os.replace(sidecar, backup_root / sidecar.name)
        if paths.artifact_root.exists():
            if any(paths.artifact_root.iterdir()):
                if backup_root is None:
                    raise LocalReleaseError("destination artifacts unexpectedly exist")
                os.replace(paths.artifact_root, backup_root / "artifacts")
                moved_artifacts = True
            else:
                paths.artifact_root.rmdir()
        os.replace(stage_database, paths.database)
        installed_database = True
        os.replace(stage_artifacts, paths.artifact_root)
        installed_artifacts = True
    except Exception:
        if installed_database and paths.database.exists():
            paths.database.unlink(missing_ok=True)
        if installed_artifacts and paths.artifact_root.exists():
            shutil.rmtree(paths.artifact_root)
        if backup_root is not None:
            backup_database = backup_root / paths.database.name
            if moved_database and backup_database.exists() and not paths.database.exists():
                os.replace(backup_database, paths.database)
            for suffix in ("-wal", "-shm"):
                backup_sidecar = backup_root / f"{paths.database.name}{suffix}"
                destination_sidecar = Path(str(paths.database) + suffix)
                if backup_sidecar.exists() and not destination_sidecar.exists():
                    os.replace(backup_sidecar, destination_sidecar)
            backup_artifacts = backup_root / "artifacts"
            if (
                moved_artifacts
                and backup_artifacts.exists()
                and not paths.artifact_root.exists()
            ):
                os.replace(backup_artifacts, paths.artifact_root)
        raise
    return backup_root


def import_local_state(
    paths: LocalPaths,
    bundle: str | Path,
    *,
    replace: bool = False,
) -> dict[str, Any]:
    """Validate a portable archive and atomically install rebuilt local state."""

    _require_stopped(paths, "importing state")
    source = Path(bundle).expanduser().resolve()
    if not source.is_file():
        raise LocalReleaseError(f"portable bundle not found: {source}")
    try:
        paths.ensure()
    except OSError as error:
        raise LocalReleaseError(
            f"cannot prepare EQO Local storage for import: {error}"
        ) from error
    if _has_existing_state(paths) and not replace:
        raise LocalReleaseError(
            "EQO Local already contains state; pass --replace to import with an automatic backup"
        )

    stage_root = paths.data_root.parent / f".{paths.data_root.name}.import-{uuid.uuid4().hex}"
    stage_database = stage_root / "workbench.sqlite"
    stage_artifacts = stage_root / "artifacts"
    try:
        stage_root.mkdir(parents=True, exist_ok=False)
        stage_artifacts.mkdir()
    except OSError as error:
        raise LocalReleaseError(f"cannot stage EQO Local import: {error}") from error
    try:
        try:
            archive_context = zipfile.ZipFile(source, "r")
        except (OSError, zipfile.BadZipFile) as error:
            raise LocalReleaseError(f"cannot open portable bundle {source}: {error}") from error
        with archive_context as archive:
            manifest, state, _infos = _load_bundle(archive)
            entries = _validate_payload_records(manifest, state)
            artifact_uris = {
                artifact_id: _restore_payload(
                    archive,
                    entry,
                    stage_artifacts,
                    paths.artifact_root,
                )
                for artifact_id, entry in sorted(entries.items())
            }

        engine = WorkflowEngine(stage_database, stage_artifacts)
        try:
            engine.import_portable_state(state, artifact_uris=artifact_uris)
        except (ContractError, OSError, RuntimeError) as error:
            raise LocalReleaseError(f"cannot import EQO Local state: {error}") from error
        with engine._connect() as connection:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise LocalReleaseError(
                f"imported EQO Local database failed integrity check: {integrity}"
            )

        try:
            backup_root = _install_staged_state(
                paths,
                stage_database,
                stage_artifacts,
                replace=replace,
            )
        except LocalReleaseError:
            raise
        except OSError as error:
            raise LocalReleaseError(
                f"cannot install imported EQO Local state: {error}"
            ) from error
        return {
            "path": str(source),
            "checksum": _digest_file(source),
            "release_version": manifest["release_version"],
            "counts": manifest["counts"],
            "backup": str(backup_root) if backup_root is not None else None,
        }
    finally:
        shutil.rmtree(stage_root, ignore_errors=True)
