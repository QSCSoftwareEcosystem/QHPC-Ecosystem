from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SHIM_PATH = (
    ROOT
    / "infrastructure"
    / "test-clusters"
    / "slurm-docker-cluster"
    / "qhpc-oci-shim.py"
)
SPEC = importlib.util.spec_from_file_location("qhpc_oci_shim", SHIM_PATH)
assert SPEC is not None and SPEC.loader is not None
SHIM = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SHIM)


def test_oci_shim_accepts_only_the_reviewed_apptainer_argument_subset() -> None:
    descriptor, binds, working_directory, command = SHIM._parse_command(
        [
            "exec",
            "--containall",
            "--cleanenv",
            "--net",
            "--network",
            "none",
            "--no-home",
            "--pwd",
            "/work",
            "--bind",
            "/mnt/input:/inputs:ro",
            "/mnt/image.oci.json",
            "/opt/qhpc/bin/operation",
            "--shots",
            "100",
        ]
    )

    assert descriptor == "/mnt/image.oci.json"
    assert binds == ["/mnt/input:/inputs:ro"]
    assert working_directory == "/work"
    assert command == ["/opt/qhpc/bin/operation", "--shots", "100"]

    with pytest.raises(SHIM.ShimError, match="unsupported"):
        SHIM._parse_command(
            ["exec", "--privileged", "/mnt/image", "/bin/operation"]
        )


def test_oci_shim_maps_only_shared_scheduler_paths_to_host_paths(
    tmp_path: Path,
) -> None:
    shared = tmp_path / "shared"
    source = shared / "tasks" / "input"
    source.mkdir(parents=True)
    descriptor = {
        "host_shared_root": str(shared),
        "scheduler_shared_root": str(shared),
    }

    assert SHIM._docker_binds(
        [f"{source}:/inputs:ro"], descriptor
    ) == [f"{source.resolve()}:/inputs:ro"]
    with pytest.raises(SHIM.ShimError, match="outside shared storage"):
        SHIM._docker_binds(["/tmp/input:/inputs:ro"], descriptor)
