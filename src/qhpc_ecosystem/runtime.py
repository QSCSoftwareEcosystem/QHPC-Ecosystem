"""Apptainer runtime command construction."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Sequence

from .catalog import CatalogError, Environment, Repository


def find_runtime(explicit: str | None = None) -> str:
    """Find Apptainer while explaining common workstation-only setups."""
    if explicit:
        resolved = shutil.which(explicit)
        if resolved:
            return resolved
        candidate = Path(explicit).expanduser()
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate.resolve())
        raise CatalogError(f"Apptainer runtime not found: {explicit}")

    apptainer = shutil.which("apptainer")
    if apptainer:
        return apptainer
    if shutil.which("docker") or shutil.which("podman"):
        raise CatalogError(
            "Apptainer is required for build, shell, and run commands. "
            "Docker or Podman is installed, but it is not a supported runtime in v1."
        )
    raise CatalogError(
        "Apptainer is required for build, shell, and run commands; install it on the target HPC system."
    )


def default_image_dir() -> Path:
    cache = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return cache / "qhpc-ecosystem" / "images"


def image_path(environment: Environment, image_dir: Path) -> Path:
    return image_dir.expanduser().resolve() / f"{environment.name}.sif"


def resolve_workspace(repository: Repository, requested: str | Path | None) -> Path:
    if requested:
        workspace = Path(requested).expanduser().resolve()
    elif repository.local_path and repository.local_path.is_dir():
        workspace = repository.local_path
    else:
        workspace = Path.cwd().resolve()
    if not workspace.is_dir():
        raise CatalogError(f"workspace directory not found: {workspace}")
    return workspace


def build_command(
    runtime: str,
    environment: Environment,
    destination: Path,
    *,
    force: bool = False,
    fakeroot: bool = False,
) -> list[str]:
    command = [runtime, "build"]
    if force:
        command.append("--force")
    if fakeroot:
        command.append("--fakeroot")
    command.extend([str(destination), str(environment.recipe)])
    return command


def workspace_command(
    runtime: str,
    action: str,
    image: Path,
    workspace: Path,
    command: Sequence[str] = (),
) -> list[str]:
    if action not in {"shell", "exec"}:
        raise ValueError(f"unsupported runtime action: {action}")
    result = [
        runtime,
        action,
        "--bind",
        f"{workspace}:/workspace",
        "--pwd",
        "/workspace",
        str(image),
    ]
    result.extend(command)
    return result


def execute(command: Sequence[str]) -> int:
    return subprocess.run(list(command), check=False).returncode
