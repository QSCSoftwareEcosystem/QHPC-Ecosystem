"""Prepare and verify immutable Linux operation-container builds."""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import time
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Any

from .contract import load_document, validate_contract_data


_IMMUTABLE_IMAGE = re.compile(r"^(?:docker|oras)://.+@sha256:[0-9a-f]{64}$")


class OperationRuntimeError(RuntimeError):
    """Raised when an operation runtime cannot be prepared or verified."""


@dataclass(frozen=True)
class PreparedBuildContext:
    path: Path
    runtime_id: str
    platform: str
    source_revision: str
    source_archive_digest: str
    source_date_epoch: int


@dataclass(frozen=True)
class OCIImage:
    reference: str
    local_id: str


@dataclass(frozen=True)
class VerifiedOutput:
    container_path: str
    digest: str
    size: int


@dataclass(frozen=True)
class OCISmokeResult:
    image: str
    duration_ms: int
    outputs: tuple[VerifiedOutput, ...]
    stdout: str
    stderr: str


def _digest_bytes(payload: bytes) -> str:
    return "sha256:" + sha256(payload).hexdigest()


def file_digest(path: str | Path) -> str:
    return _digest_bytes(Path(path).read_bytes())


def _run_git(source: Path, *arguments: str, text: bool = True) -> str | bytes:
    try:
        completed = subprocess.run(
            ["git", "-C", str(source), *arguments],
            check=True,
            capture_output=True,
            text=text,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as error:
        detail = ""
        if isinstance(error, subprocess.CalledProcessError) and error.stderr:
            detail = (
                error.stderr.strip()
                if isinstance(error.stderr, str)
                else error.stderr.decode(errors="replace").strip()
            )
        suffix = f": {detail}" if detail else ""
        raise OperationRuntimeError(
            f"Git command failed for runtime source {source}{suffix}"
        ) from error
    return completed.stdout.strip() if text else completed.stdout


def source_archive_digest(source: str | Path, revision: str) -> str:
    source_path = Path(source).expanduser().resolve()
    if not source_path.is_dir():
        raise OperationRuntimeError(f"runtime source not found: {source_path}")
    _run_git(source_path, "rev-parse", "--verify", revision + "^{commit}")
    archive = _run_git(source_path, "archive", "--format=tar", revision, text=False)
    assert isinstance(archive, bytes)
    return _digest_bytes(archive)


def _workspace_root(manifest_path: Path, explicit: str | Path | None) -> Path:
    if explicit is not None:
        root = Path(explicit).expanduser().resolve()
        if not root.is_dir():
            raise OperationRuntimeError(f"workspace root not found: {root}")
        return root
    for candidate in (manifest_path.parent, *manifest_path.parents):
        if (candidate / "pyproject.toml").is_file() and (
            candidate / "src/qhpc_ecosystem"
        ).is_dir():
            return candidate
    raise OperationRuntimeError(
        f"cannot locate workspace root for runtime manifest: {manifest_path}"
    )


def _workspace_file(root: Path, relative: str, label: str) -> Path:
    path = (root / relative).resolve()
    if path != root and root not in path.parents:
        raise OperationRuntimeError(f"{label} escapes workspace root: {relative}")
    if not path.is_file():
        raise OperationRuntimeError(f"{label} not found: {path}")
    return path


def load_operation_runtime(path: str | Path) -> dict[str, Any]:
    document = load_document(path)
    validate_contract_data("operation-runtime", document)
    return document


def verify_runtime_definition(
    path: str | Path, workspace_root: str | Path | None = None
) -> dict[str, Any]:
    manifest_path = Path(path).expanduser().resolve()
    document = load_operation_runtime(manifest_path)
    root = _workspace_root(manifest_path, workspace_root)
    build = document["spec"]["build"]

    recipe = _workspace_file(root, build["recipe"]["path"], "runtime recipe")
    checks = [(recipe, build["recipe"]["digest"], "runtime recipe")]
    for item in build["context_files"]:
        checks.append(
            (
                _workspace_file(root, item["source"], "runtime context file"),
                item["digest"],
                f"runtime context file {item['source']}",
            )
        )
    fixture = document["spec"]["verification"].get("fixture")
    if fixture is not None:
        checks.append(
            (
                _workspace_file(root, fixture["path"], "runtime smoke fixture"),
                fixture["digest"],
                "runtime smoke fixture",
            )
        )
    for file_path, expected, label in checks:
        actual = file_digest(file_path)
        if actual != expected:
            raise OperationRuntimeError(
                f"{label} digest mismatch: expected {expected}, found {actual}"
            )

    references = re.findall(
        r"^FROM[ \t]+(\S+)",
        recipe.read_text(encoding="utf-8"),
        flags=re.IGNORECASE | re.MULTILINE,
    )
    expected_references = [
        build["builder"]["reference"],
        build["runtime_base"]["reference"],
    ]
    if references != expected_references:
        raise OperationRuntimeError(
            "runtime recipe FROM references do not match the pinned build contract"
        )
    return document


def _source_archive(source: Path, revision: str) -> tuple[bytes, int]:
    _run_git(source, "rev-parse", "--verify", revision + "^{commit}")
    archive = _run_git(source, "archive", "--format=tar", revision, text=False)
    timestamp = _run_git(source, "show", "-s", "--format=%ct", revision)
    assert isinstance(archive, bytes)
    assert isinstance(timestamp, str)
    return archive, int(timestamp)


def _write_context_file(path: Path, payload: bytes, mode: int, timestamp: int) -> None:
    path.write_bytes(payload)
    path.chmod(mode)
    os.utime(path, (timestamp, timestamp))


def _build_metadata(document: dict[str, Any]) -> dict[str, Any]:
    metadata = document["metadata"]
    build = document["spec"]["build"]
    metadata_document = {
        "runtime_id": metadata["id"],
        "runtime_version": metadata["version"],
        "source": metadata["source"],
        "source_archive_digest": build["source_archive"]["digest"],
        "source_date_epoch": build["source_archive"]["source_date_epoch"],
        "platform": document["spec"]["platform"],
    }
    dependencies = build.get("dependency_archives", [])
    if dependencies:
        metadata_document["dependency_archives"] = [
            {
                "filename": item["filename"],
                "url": item["url"],
                "digest": item["digest"],
            }
            for item in dependencies
        ]
    return metadata_document


def verify_build_context(
    document: dict[str, Any], context: str | Path
) -> dict[str, Any]:
    validate_contract_data("operation-runtime", document)
    context_path = Path(context).expanduser().resolve()
    if not context_path.is_dir():
        raise OperationRuntimeError(f"build context not found: {context_path}")
    build = document["spec"]["build"]
    expected_files = [
        ("Containerfile", build["recipe"]["digest"], 0o644),
        (
            build["source_archive"]["filename"],
            build["source_archive"]["digest"],
            0o644,
        ),
        *[
            (item["destination"], item["digest"], int(item["mode"], 8))
            for item in build["context_files"]
        ],
        *[
            (item["filename"], item["digest"], 0o644)
            for item in build.get("dependency_archives", [])
        ],
    ]
    expected_names = {name for name, _digest, _mode in expected_files}
    expected_names.add("qhpc-build.json")
    actual_names = {item.name for item in context_path.iterdir()}
    if actual_names != expected_names:
        raise OperationRuntimeError(
            "build context file set mismatch: "
            f"expected {sorted(expected_names)}, found {sorted(actual_names)}"
        )
    expected_mtime_ns = build["source_archive"]["source_date_epoch"] * 1_000_000_000
    for name, expected_digest, expected_mode in expected_files:
        path = context_path / name
        if path.is_symlink() or not path.is_file():
            raise OperationRuntimeError(f"build context file not found: {path}")
        actual_digest = file_digest(path)
        if actual_digest != expected_digest:
            raise OperationRuntimeError(
                f"build context file {name} digest mismatch: "
                f"expected {expected_digest}, found {actual_digest}"
            )
        actual_mode = stat.S_IMODE(path.stat().st_mode)
        if actual_mode != expected_mode:
            raise OperationRuntimeError(
                f"build context file {name} mode mismatch: "
                f"expected {expected_mode:04o}, found {actual_mode:04o}"
            )
        if path.stat().st_mtime_ns != expected_mtime_ns:
            raise OperationRuntimeError(
                f"build context file {name} timestamp does not match SOURCE_DATE_EPOCH"
            )

    metadata_path = context_path / "qhpc-build.json"
    if metadata_path.is_symlink() or not metadata_path.is_file():
        raise OperationRuntimeError(
            f"build context metadata not found: {metadata_path}"
        )
    try:
        context_metadata = json.loads(metadata_path.read_text(encoding="ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise OperationRuntimeError(
            f"invalid build context metadata: {metadata_path}"
        ) from error
    expected_metadata = _build_metadata(document)
    if context_metadata != expected_metadata:
        raise OperationRuntimeError(
            "build context metadata does not match the runtime contract"
        )
    if stat.S_IMODE(metadata_path.stat().st_mode) != 0o644:
        raise OperationRuntimeError("build context metadata mode must be 0644")
    if metadata_path.stat().st_mtime_ns != expected_mtime_ns:
        raise OperationRuntimeError(
            "build context metadata timestamp does not match SOURCE_DATE_EPOCH"
        )
    return context_metadata


def prepare_build_context(
    manifest: str | Path,
    source: str | Path,
    destination: str | Path,
    *,
    workspace_root: str | Path | None = None,
    dependency_cache: str | Path | None = None,
) -> PreparedBuildContext:
    manifest_path = Path(manifest).expanduser().resolve()
    document = verify_runtime_definition(manifest_path, workspace_root)
    root = _workspace_root(manifest_path, workspace_root)
    source_path = Path(source).expanduser().resolve()
    if not source_path.is_dir():
        raise OperationRuntimeError(f"runtime source not found: {source_path}")

    metadata = document["metadata"]
    build = document["spec"]["build"]
    revision = metadata["source"]["revision"]
    archive, timestamp = _source_archive(source_path, revision)
    actual_archive_digest = _digest_bytes(archive)
    expected_archive_digest = build["source_archive"]["digest"]
    if actual_archive_digest != expected_archive_digest:
        raise OperationRuntimeError(
            "source archive digest mismatch: "
            f"expected {expected_archive_digest}, found {actual_archive_digest}"
        )
    expected_timestamp = build["source_archive"]["source_date_epoch"]
    if timestamp != expected_timestamp:
        raise OperationRuntimeError(
            "source commit timestamp mismatch: "
            f"expected {expected_timestamp}, found {timestamp}"
        )

    output = Path(destination).expanduser().resolve()
    dependencies = build.get("dependency_archives", [])
    cache = (
        Path(dependency_cache).expanduser().resolve()
        if dependency_cache is not None
        else None
    )
    if dependencies and (cache is None or not cache.is_dir()):
        raise OperationRuntimeError(
            "runtime dependency cache is required and must be a directory"
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise OperationRuntimeError(f"build context already exists: {output}")
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{output.name}.", dir=str(output.parent))
    )
    try:
        recipe = _workspace_file(root, build["recipe"]["path"], "runtime recipe")
        _write_context_file(
            temporary / "Containerfile", recipe.read_bytes(), 0o644, timestamp
        )
        _write_context_file(
            temporary / build["source_archive"]["filename"],
            archive,
            0o644,
            timestamp,
        )
        for item in build["context_files"]:
            source_file = _workspace_file(root, item["source"], "runtime context file")
            _write_context_file(
                temporary / item["destination"],
                source_file.read_bytes(),
                int(item["mode"], 8),
                timestamp,
            )
        for item in dependencies:
            assert cache is not None
            dependency = (cache / item["filename"]).resolve()
            if dependency.parent != cache or not dependency.is_file():
                raise OperationRuntimeError(
                    f"runtime dependency not found: {item['filename']}"
                )
            actual = file_digest(dependency)
            if actual != item["digest"]:
                raise OperationRuntimeError(
                    f"runtime dependency {item['filename']} digest mismatch: "
                    f"expected {item['digest']}, found {actual}"
                )
            _write_context_file(
                temporary / item["filename"],
                dependency.read_bytes(),
                0o644,
                timestamp,
            )
        platform = document["spec"]["platform"]
        context_metadata = _build_metadata(document)
        _write_context_file(
            temporary / "qhpc-build.json",
            (
                json.dumps(context_metadata, sort_keys=True, separators=(",", ":"))
                + "\n"
            ).encode("ascii"),
            0o644,
            timestamp,
        )
        os.replace(temporary, output)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise

    return PreparedBuildContext(
        path=output,
        runtime_id=metadata["id"],
        platform=f"{platform['os']}/{platform['architecture']}",
        source_revision=revision,
        source_archive_digest=actual_archive_digest,
        source_date_epoch=timestamp,
    )


def _validate_image_tag(tag: str) -> None:
    if not tag or tag.startswith("-") or any(character.isspace() for character in tag):
        raise OperationRuntimeError(f"invalid local OCI image tag: {tag}")


def find_oci_builder(explicit: str | None = None) -> str:
    if explicit:
        executable = shutil.which(explicit)
        if executable is None:
            raise OperationRuntimeError(f"OCI builder not found: {explicit}")
        return executable
    for candidate in ("docker", "podman"):
        executable = shutil.which(candidate)
        if executable:
            return executable
    raise OperationRuntimeError("no OCI builder found; install Docker or Podman")


def oci_build_command(
    manifest: dict[str, Any],
    context: str | Path,
    tag: str,
    *,
    builder: str,
) -> list[str]:
    _validate_image_tag(tag)
    context_path = Path(context).expanduser().resolve()
    context_metadata = verify_build_context(manifest, context_path)
    platform = manifest["spec"]["platform"]
    expected_platform = f"{platform['os']}/{platform['architecture']}"
    actual_platform = (
        f"{context_metadata['platform']['os']}/"
        f"{context_metadata['platform']['architecture']}"
    )
    if actual_platform != expected_platform:
        raise OperationRuntimeError(
            f"build context platform mismatch: {actual_platform}"
        )
    command = [
        builder,
        "build",
        "--platform",
        expected_platform,
        "--network",
        "none",
    ]
    if Path(builder).name == "docker":
        command.append("--provenance=false")
    command.extend(
        [
            "--build-arg",
            f"SOURCE_DATE_EPOCH={context_metadata['source_date_epoch']}",
            "--file",
            str(context_path / "Containerfile"),
            "--tag",
            tag,
            str(context_path),
        ]
    )
    return command


def build_oci_image(
    manifest: dict[str, Any],
    context: str | Path,
    tag: str,
    *,
    builder: str | None = None,
) -> OCIImage:
    executable = find_oci_builder(builder)
    command = oci_build_command(manifest, context, tag, builder=executable)
    try:
        subprocess.run(command, check=True)
        completed = subprocess.run(
            [executable, "image", "inspect", "--format", "{{.Id}}", tag],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as error:
        raise OperationRuntimeError(
            f"OCI image build or inspection failed for {tag}"
        ) from error
    local_id = completed.stdout.strip()
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", local_id):
        raise OperationRuntimeError(
            f"OCI builder returned an invalid local image ID: {local_id}"
        )
    return OCIImage(reference=tag, local_id=local_id)


def _relative_mount_path(container_path: str, mount_path: str) -> Path:
    mount = PurePosixPath(mount_path)
    candidate = PurePosixPath(container_path)
    if (
        not mount.is_absolute()
        or not candidate.is_absolute()
        or ".." in mount.parts
        or ".." in candidate.parts
    ):
        raise OperationRuntimeError(
            f"unsafe verification or mount path: {container_path}"
        )
    try:
        relative = candidate.relative_to(mount)
    except ValueError as error:
        raise OperationRuntimeError(
            f"verification path {container_path} is outside mount {mount_path}"
        ) from error
    if not relative.parts:
        raise OperationRuntimeError(
            f"verification path must name a file inside mount {mount_path}"
        )
    return Path(*relative.parts)


def smoke_oci_image(
    manifest_path: str | Path,
    image: str,
    *,
    workspace_root: str | Path | None = None,
    builder: str | None = None,
) -> OCISmokeResult:
    _validate_image_tag(image)
    manifest_file = Path(manifest_path).expanduser().resolve()
    document = verify_runtime_definition(manifest_file, workspace_root)
    root = _workspace_root(manifest_file, workspace_root)
    executable = find_oci_builder(builder)
    execution = document["spec"]["execution"]
    verification = document["spec"]["verification"]
    platform = document["spec"]["platform"]
    mounts_by_kind = {item["kind"]: item for item in execution["mounts"]}
    if "output" not in mounts_by_kind:
        raise OperationRuntimeError("OCI smoke verification requires an output mount")

    with tempfile.TemporaryDirectory(prefix="qhpc-oci-smoke-") as temporary:
        temporary_path = Path(temporary)
        host_mounts: dict[str, Path] = {}
        for mount in execution["mounts"]:
            host_path = temporary_path / mount["name"]
            host_path.mkdir()
            if mount["mode"] == "rw":
                host_path.chmod(0o777)
            host_mounts[mount["kind"]] = host_path

        fixture = verification.get("fixture")
        if fixture is not None:
            input_mount = mounts_by_kind.get("input")
            if input_mount is None:
                raise OperationRuntimeError("OCI smoke fixture requires an input mount")
            fixture_relative = _relative_mount_path(
                fixture["mount_path"], input_mount["path"]
            )
            fixture_target = host_mounts["input"] / fixture_relative
            fixture_target.parent.mkdir(parents=True, exist_ok=True)
            fixture_source = _workspace_file(
                root, fixture["path"], "runtime smoke fixture"
            )
            fixture_target.write_bytes(fixture_source.read_bytes())
            fixture_target.chmod(0o444)

        command = [
            executable,
            "run",
            "--rm",
            "--platform",
            f"{platform['os']}/{platform['architecture']}",
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=16m",
        ]
        for mount in execution["mounts"]:
            value = f"type=bind,src={host_mounts[mount['kind']]},dst={mount['path']}"
            if mount["mode"] == "ro":
                value += ",readonly"
            command.extend(["--mount", value])
        command.extend([image, *verification["arguments"]])

        started = time.monotonic_ns()
        try:
            completed = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                timeout=verification["timeout_seconds"],
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
            raise OperationRuntimeError(
                f"OCI smoke verification failed for {image}"
            ) from error
        duration_ms = (time.monotonic_ns() - started) // 1_000_000

        output_mount = mounts_by_kind["output"]
        verified: list[VerifiedOutput] = []
        for expected in verification["expected_outputs"]:
            relative = _relative_mount_path(expected["path"], output_mount["path"])
            output = host_mounts["output"] / relative
            if not output.is_file():
                raise OperationRuntimeError(
                    f"OCI smoke output was not created: {expected['path']}"
                )
            size = output.stat().st_size
            if expected["nonempty"] and size == 0:
                raise OperationRuntimeError(
                    f"OCI smoke output is empty: {expected['path']}"
                )
            if expected.get("text_contains"):
                content = output.read_text(encoding="utf-8")
                for marker in expected["text_contains"]:
                    if marker not in content:
                        raise OperationRuntimeError(
                            f"OCI smoke output {expected['path']} "
                            f"does not contain {marker!r}"
                        )
            verified.append(
                VerifiedOutput(
                    container_path=expected["path"],
                    digest=file_digest(output),
                    size=size,
                )
            )
        return OCISmokeResult(
            image=image,
            duration_ms=duration_ms,
            outputs=tuple(verified),
            stdout=completed.stdout,
            stderr=completed.stderr,
        )


def apptainer_build_command(
    oci_reference: str,
    output: str | Path,
    *,
    executable: str = "apptainer",
    fakeroot: bool = False,
) -> list[str]:
    if not _IMMUTABLE_IMAGE.fullmatch(oci_reference):
        raise OperationRuntimeError(
            "Apptainer source must be an immutable docker:// or oras:// reference"
        )
    output_path = Path(output).expanduser().resolve()
    if output_path.suffix != ".sif":
        raise OperationRuntimeError("Apptainer output must use the .sif extension")
    command = [executable, "build"]
    if fakeroot:
        command.append("--fakeroot")
    command.extend([str(output_path), oci_reference])
    return command
