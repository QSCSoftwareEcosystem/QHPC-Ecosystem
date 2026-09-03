"""Build and verify immutable local development runtime artifacts."""

from __future__ import annotations

import io
import os
import json
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path


@dataclass(frozen=True)
class WheelRuntime:
    path: Path
    reference: str
    digest: str


@dataclass(frozen=True)
class NativeRuntime:
    path: Path
    reference: str
    digest: str


def _runtime_destination(
    runtime_root: str | Path,
    reference: str,
) -> tuple[str, Path]:
    root = Path(runtime_root).expanduser().resolve()
    options = (
        ("python-wheel", "qhpc-runtime://wheels/", "wheels", ".whl"),
        ("native", "qhpc-runtime://native/", "native", ".zip"),
    )
    for kind, prefix, directory, suffix in options:
        if not reference.startswith(prefix):
            continue
        name = reference[len(prefix) :]
        if not name or Path(name).name != name or not name.endswith(suffix):
            raise RuntimeError(f"invalid {kind} runtime reference: {reference}")
        return kind, root / directory / name
    raise RuntimeError(f"unsupported local runtime reference: {reference}")


def _artifact_digest(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def install_local_runtime(
    runtime_root: str | Path,
    artifact: str | Path,
    *,
    reference: str,
    digest: str,
    replace: bool = False,
) -> dict[str, object]:
    """Install one checksum-pinned wheel or native bundle atomically."""

    source = Path(artifact).expanduser().resolve()
    if not source.is_file():
        raise RuntimeError(f"runtime artifact not found: {source}")
    if (
        not digest.startswith("sha256:")
        or len(digest) != 71
        or any(character not in "0123456789abcdef" for character in digest[7:])
    ):
        raise RuntimeError("runtime digest must be a sha256 value")
    actual = _artifact_digest(source)
    if actual != digest:
        raise RuntimeError(
            f"runtime artifact digest mismatch: expected {digest}, found {actual}"
        )
    kind, destination = _runtime_destination(runtime_root, reference)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        installed_digest = _artifact_digest(destination)
        if installed_digest == digest:
            return {
                "kind": kind,
                "reference": reference,
                "digest": digest,
                "size": destination.stat().st_size,
                "installed": False,
            }
        if not replace:
            raise RuntimeError(
                "a different runtime artifact is already installed; use --replace"
            )
    with tempfile.NamedTemporaryFile(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
        delete=False,
    ) as temporary:
        temporary_path = Path(temporary.name)
        with source.open("rb") as stream:
            shutil.copyfileobj(stream, temporary)
        temporary.flush()
        os.fsync(temporary.fileno())
    try:
        if _artifact_digest(temporary_path) != digest:
            raise RuntimeError("runtime artifact changed while it was being installed")
        os.replace(temporary_path, destination)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()
    return {
        "kind": kind,
        "reference": reference,
        "digest": digest,
        "size": destination.stat().st_size,
        "installed": True,
    }


def remove_local_runtime(runtime_root: str | Path, reference: str) -> bool:
    """Remove one explicitly named local runtime and its verified extraction."""

    kind, destination = _runtime_destination(runtime_root, reference)
    if not destination.exists():
        return False
    digest = _artifact_digest(destination)
    destination.unlink()
    if kind == "native":
        extracted = (
            Path(runtime_root).expanduser().resolve()
            / "extracted"
            / digest.removeprefix("sha256:")
        )
        if extracted.is_dir():
            shutil.rmtree(extracted)
    return True


def list_local_runtimes(runtime_root: str | Path) -> list[dict[str, object]]:
    """Inventory installed optional runtimes without executing them."""

    root = Path(runtime_root).expanduser().resolve()
    result: list[dict[str, object]] = []
    for kind, directory, suffix, prefix in (
        ("python-wheel", "wheels", ".whl", "qhpc-runtime://wheels/"),
        ("native", "native", ".zip", "qhpc-runtime://native/"),
    ):
        runtime_directory = root / directory
        if not runtime_directory.is_dir():
            continue
        for path in sorted(runtime_directory.glob(f"*{suffix}")):
            if not path.is_file():
                continue
            result.append(
                {
                    "kind": kind,
                    "reference": prefix + path.name,
                    "digest": _artifact_digest(path),
                    "size": path.stat().st_size,
                }
            )
    return result


def _git(source: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(source), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _archive_revision(source: Path, revision: str, destination: Path) -> None:
    archive = subprocess.run(
        ["git", "-C", str(source), "archive", "--format=tar", revision],
        check=True,
        capture_output=True,
    ).stdout
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as bundle:
        root = destination.resolve()
        for member in bundle.getmembers():
            target = (destination / member.name).resolve()
            if target != root and root not in target.parents:
                raise RuntimeError("git archive contains an unsafe path")
        bundle.extractall(destination)


def build_wheel_runtime(
    source: str | Path,
    destination: str | Path,
    *,
    revision: str,
) -> WheelRuntime:
    """Build a reproducible wheel from an exact Git revision in isolation."""
    source_path = Path(source).expanduser().resolve()
    if not source_path.is_dir():
        raise FileNotFoundError(f"runtime source not found: {source_path}")
    _git(source_path, "rev-parse", "--verify", revision + "^{commit}")
    source_date_epoch = _git(source_path, "show", "-s", "--format=%ct", revision)
    destination_path = Path(destination).expanduser().resolve()
    destination_path.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="qhpc-wheel-") as temporary:
        temporary_path = Path(temporary)
        checkout = temporary_path / "source"
        wheelhouse = temporary_path / "wheelhouse"
        checkout.mkdir()
        wheelhouse.mkdir()
        _archive_revision(source_path, revision, checkout)
        environment = os.environ.copy()
        environment["SOURCE_DATE_EPOCH"] = source_date_epoch
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "wheel",
                "--no-deps",
                "--no-build-isolation",
                ".",
                "--wheel-dir",
                str(wheelhouse),
            ],
            cwd=checkout,
            env=environment,
            check=True,
        )
        wheels = list(wheelhouse.glob("*.whl"))
        if len(wheels) != 1:
            raise RuntimeError(f"expected one wheel, found {len(wheels)}")
        output = destination_path / wheels[0].name
        shutil.copyfile(wheels[0], output)

    digest = "sha256:" + sha256(output.read_bytes()).hexdigest()
    return WheelRuntime(
        path=output,
        reference=f"qhpc-runtime://wheels/{output.name}",
        digest=digest,
    )


def resolve_wheel_runtime(
    runtime_root: str | Path, reference: str, digest: str
) -> Path:
    prefix = "qhpc-runtime://wheels/"
    if not reference.startswith(prefix):
        raise RuntimeError(f"unsupported local runtime reference: {reference}")
    name = reference[len(prefix) :]
    if not name or Path(name).name != name or not name.endswith(".whl"):
        raise RuntimeError("invalid wheel runtime name")
    path = Path(runtime_root).expanduser().resolve() / "wheels" / name
    if not path.is_file():
        raise RuntimeError(f"wheel runtime not installed: {path}")
    actual = "sha256:" + sha256(path.read_bytes()).hexdigest()
    if actual != digest:
        raise RuntimeError(
            f"wheel runtime digest mismatch: expected {digest}, found {actual}"
        )
    return path


def _zip_info(name: str, timestamp: int, executable: bool = False) -> zipfile.ZipInfo:
    date_time = datetime.fromtimestamp(timestamp, timezone.utc).timetuple()[:6]
    info = zipfile.ZipInfo(name, date_time=max(date_time, (1980, 1, 1, 0, 0, 0)))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = ((0o755 if executable else 0o644) & 0xFFFF) << 16
    return info


def build_cmake_runtime(
    source: str | Path,
    destination: str | Path,
    *,
    revision: str,
    name: str,
    target: str,
    executable: str,
    assets: tuple[str, ...] = (),
    source_subdirectory: str = ".",
) -> NativeRuntime:
    """Build a pinned CMake target and package it with selected source assets."""
    source_path = Path(source).expanduser().resolve()
    _git(source_path, "rev-parse", "--verify", revision + "^{commit}")
    timestamp = int(_git(source_path, "show", "-s", "--format=%ct", revision))
    destination_path = Path(destination).expanduser().resolve()
    destination_path.mkdir(parents=True, exist_ok=True)
    system = platform.system().lower()
    machine = platform.machine().lower()
    archive_name = f"{name}-{revision[:12]}-{system}-{machine}.zip"
    output = destination_path / archive_name

    with tempfile.TemporaryDirectory(prefix="qhpc-native-") as temporary:
        temporary_path = Path(temporary)
        checkout = temporary_path / "source"
        build = temporary_path / "build"
        checkout.mkdir()
        _archive_revision(source_path, revision, checkout)
        source_directory = (checkout / source_subdirectory).resolve()
        if (
            checkout.resolve() not in source_directory.parents
            and source_directory != checkout.resolve()
        ):
            raise RuntimeError("CMake source subdirectory escapes checkout")
        environment = os.environ.copy()
        environment["SOURCE_DATE_EPOCH"] = str(timestamp)
        prefix_map = f"-ffile-prefix-map={checkout}=. -fdebug-prefix-map={checkout}=."
        subprocess.run(
            [
                "cmake",
                "-S",
                str(source_directory),
                "-B",
                str(build),
                "-DCMAKE_BUILD_TYPE=Release",
                f"-DCMAKE_CXX_FLAGS={prefix_map}",
            ],
            env=environment,
            check=True,
        )
        subprocess.run(
            ["cmake", "--build", str(build), "--target", target, "--parallel", "2"],
            env=environment,
            check=True,
        )
        binary = (build / executable).resolve()
        if not binary.is_file():
            matches = list(build.rglob(executable))
            if len(matches) != 1:
                raise RuntimeError(f"native executable not found: {executable}")
            binary = matches[0]
        asset_paths: list[tuple[str, Path]] = []
        for asset in assets:
            path = (checkout / asset).resolve()
            if checkout.resolve() not in path.parents or not path.is_file():
                raise RuntimeError(f"invalid native runtime asset: {asset}")
            asset_paths.append((asset, path))
        manifest = {
            "name": name,
            "revision": revision,
            "platform": {"system": system, "machine": machine},
            "executable": f"bin/{Path(executable).name}",
            "assets": [asset for asset, _ in asset_paths],
        }
        with zipfile.ZipFile(output, "w") as archive:
            archive.writestr(
                _zip_info("manifest.json", timestamp),
                json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n",
            )
            archive.writestr(
                _zip_info(f"bin/{Path(executable).name}", timestamp, executable=True),
                binary.read_bytes(),
            )
            for asset, path in asset_paths:
                archive.writestr(_zip_info(asset, timestamp), path.read_bytes())

    digest = "sha256:" + sha256(output.read_bytes()).hexdigest()
    return NativeRuntime(
        path=output,
        reference=f"qhpc-runtime://native/{output.name}",
        digest=digest,
    )


def build_cpp_runtime(
    source: str | Path,
    destination: str | Path,
    *,
    revision: str,
    name: str,
    executable: str,
    source_files: tuple[str, ...],
    include_directories: tuple[str, ...] = (),
) -> NativeRuntime:
    """Build a pinned standalone C++ executable with an explicit source set."""
    if not source_files:
        raise RuntimeError("at least one C++ source file is required")
    source_path = Path(source).expanduser().resolve()
    _git(source_path, "rev-parse", "--verify", revision + "^{commit}")
    timestamp = int(_git(source_path, "show", "-s", "--format=%ct", revision))
    destination_path = Path(destination).expanduser().resolve()
    destination_path.mkdir(parents=True, exist_ok=True)
    system = platform.system().lower()
    machine = platform.machine().lower()
    output = destination_path / f"{name}-{revision[:12]}-{system}-{machine}.zip"

    with tempfile.TemporaryDirectory(prefix="qhpc-cpp-") as temporary:
        temporary_path = Path(temporary)
        checkout = temporary_path / "source"
        binary = temporary_path / executable
        checkout.mkdir()
        _archive_revision(source_path, revision, checkout)

        def checked_path(relative: str, *, directory: bool = False) -> Path:
            path = (checkout / relative).resolve()
            if checkout.resolve() not in path.parents:
                raise RuntimeError(f"native build path escapes checkout: {relative}")
            if directory and not path.is_dir():
                raise RuntimeError(f"include directory not found: {relative}")
            if not directory and not path.is_file():
                raise RuntimeError(f"source file not found: {relative}")
            return path

        sources = [checked_path(item) for item in source_files]
        includes = [checked_path(item, directory=True) for item in include_directories]
        prefix_map = f"-ffile-prefix-map={checkout}=."
        environment = os.environ.copy()
        environment["SOURCE_DATE_EPOCH"] = str(timestamp)
        subprocess.run(
            [
                os.environ.get("CXX", "c++"),
                "-std=c++17",
                "-O3",
                prefix_map,
                *(f"-I{path}" for path in includes),
                *(str(path) for path in sources),
                "-o",
                str(binary),
            ],
            env=environment,
            check=True,
        )
        manifest = {
            "name": name,
            "revision": revision,
            "platform": {"system": system, "machine": machine},
            "executable": f"bin/{executable}",
            "sources": list(source_files),
            "include_directories": list(include_directories),
            "assets": [],
        }
        with zipfile.ZipFile(output, "w") as archive:
            archive.writestr(
                _zip_info("manifest.json", timestamp),
                json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n",
            )
            archive.writestr(
                _zip_info(f"bin/{executable}", timestamp, executable=True),
                binary.read_bytes(),
            )

    digest = "sha256:" + sha256(output.read_bytes()).hexdigest()
    return NativeRuntime(
        path=output,
        reference=f"qhpc-runtime://native/{output.name}",
        digest=digest,
    )


def resolve_native_runtime(
    runtime_root: str | Path, reference: str, digest: str
) -> Path:
    prefix = "qhpc-runtime://native/"
    if not reference.startswith(prefix):
        raise RuntimeError(f"unsupported native runtime reference: {reference}")
    name = reference[len(prefix) :]
    if not name or Path(name).name != name or not name.endswith(".zip"):
        raise RuntimeError("invalid native runtime name")
    root = Path(runtime_root).expanduser().resolve()
    archive_path = root / "native" / name
    if not archive_path.is_file():
        raise RuntimeError(f"native runtime not installed: {archive_path}")
    actual = "sha256:" + sha256(archive_path.read_bytes()).hexdigest()
    if actual != digest:
        raise RuntimeError(
            f"native runtime digest mismatch: expected {digest}, found {actual}"
        )
    extracted = root / "extracted" / digest.removeprefix("sha256:")
    marker = extracted / ".verified"
    if not marker.is_file():
        extracted.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive_path) as bundle:
            for member in bundle.infolist():
                target = (extracted / member.filename).resolve()
                if extracted not in target.parents:
                    raise RuntimeError("native runtime contains an unsafe path")
            bundle.extractall(extracted)
        manifest = json.loads((extracted / "manifest.json").read_text(encoding="utf-8"))
        executable = extracted / manifest["executable"]
        executable.chmod(0o755)
        marker.write_text(digest + "\n", encoding="ascii")
    return extracted
