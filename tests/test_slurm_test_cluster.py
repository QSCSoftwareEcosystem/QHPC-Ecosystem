from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from qhpc_ecosystem import cli
from qhpc_ecosystem.contract import (
    ContractError,
    load_document,
    validate_contract_data,
)
from qhpc_ecosystem.slurm import CommandResult
from qhpc_ecosystem.slurm_test_cluster import (
    ClusterStatus,
    SlurmDockerCluster,
    SlurmTestClusterError,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = (
    ROOT
    / "infrastructure"
    / "test-clusters"
    / "slurm-docker-cluster"
    / "cluster.yaml"
)
REVISION = "8c8065cbebb475a512a66cabff9aceda5f2c57b0"


def _prepared_checkout(path: Path) -> None:
    (path / ".git").mkdir(parents=True)
    (path / "shared-dir").mkdir()
    (path / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
    (path / "LICENSE").write_text("MIT\n", encoding="utf-8")
    manifest = load_document(MANIFEST)
    for item in manifest["spec"]["compatibility"]["files"]:
        destination = path / item["destination"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((MANIFEST.parent / item["source"]).read_bytes())
    (path / "qhpc-build-ca.pem").write_bytes(b"")


def test_manifest_rejects_rest_service_and_unsafe_source_paths() -> None:
    document = copy.deepcopy(load_document(MANIFEST))
    document["spec"]["compose"]["services"].append("slurmrestd")
    document["spec"]["compose"]["compose_file"] = "config/../docker-compose.yml"

    with pytest.raises(ContractError) as error:
        validate_contract_data("slurm-test-cluster", document)

    message = str(error.value)
    assert "cannot include slurmrestd" in message
    assert "must be a safe relative path" in message


def test_compose_override_isolates_names_and_persists_controller_state() -> None:
    override = yaml.safe_load((MANIFEST.parent / "compose.qhpc.yaml").read_text())

    services = override["services"]
    assert services["mysql"]["container_name"] == "qhpc-slurm-test-mysql"
    for name in ("slurmdbd", "slurmctld", "c1", "c2"):
        assert services[name]["container_name"] == f"qhpc-slurm-test-{name}"
        assert services[name]["image"] == (
            "qhpc/slurm-docker-cluster:25.05.0-qhpc"
        )
    assert "qhpc_slurm_state:/var/lib/slurmd" in services["slurmctld"]["volumes"]
    assert services["slurmctld"]["pull_policy"] == "never"
    assert services["c1"]["pull_policy"] == "never"
    assert services["c2"]["pull_policy"] == "never"
    assert "/var/run/docker.sock:/var/run/docker.sock" in services["c1"]["volumes"]
    assert "/var/run/docker.sock:/var/run/docker.sock" in services["c2"]["volumes"]


def test_prepare_rejects_private_key_as_build_ca(tmp_path: Path) -> None:
    checkout = tmp_path / "cluster"
    _prepared_checkout(checkout)
    private_key = tmp_path / "private.pem"
    private_key.write_text(
        "-----BEGIN PRIVATE KEY-----\nnot-a-ca\n-----END PRIVATE KEY-----\n",
        encoding="utf-8",
    )

    def run(command):
        command = list(command)
        if "remote" in command:
            return CommandResult(
                0, "https://github.com/naughtont3/slurm-docker-cluster.git\n"
            )
        if "rev-parse" in command:
            return CommandResult(0, REVISION + "\n")
        if "status" in command:
            return CommandResult(0, "")
        raise AssertionError(command)

    cluster = SlurmDockerCluster.from_manifest(MANIFEST, checkout, runner=run)

    with pytest.raises(SlurmTestClusterError, match="private key"):
        cluster.prepare(private_key)


def test_compose_executor_preserves_tokens_and_maps_shared_paths(
    tmp_path: Path,
) -> None:
    commands: list[list[str]] = []

    def run(command):
        commands.append(list(command))
        return CommandResult(0, "123\n")

    checkout = tmp_path / "cluster"
    (checkout / "shared-dir").mkdir(parents=True)
    script = checkout / "shared-dir" / "job with space.sbatch"
    script.write_text("#!/bin/sh\n", encoding="utf-8")
    cluster = SlurmDockerCluster.from_manifest(
        MANIFEST,
        checkout,
        runner=run,
    )

    result = cluster.slurm_executor(
        ["sbatch", "--parsable", cluster.map_shared_path(script)]
    )

    assert result.stdout == "123\n"
    assert commands[0][-8:] == [
        "exec",
        "-T",
        "--workdir",
        "/mnt",
        "slurmctld",
        "sbatch",
        "--parsable",
        "/mnt/job with space.sbatch",
    ]
    with pytest.raises(SlurmTestClusterError, match="outside"):
        cluster.map_shared_path(tmp_path / "outside.sbatch")


def test_development_target_loads_all_verified_oci_runtime_bindings(
    tmp_path: Path,
) -> None:
    checkout = tmp_path / "cluster"
    (checkout / "shared-dir").mkdir(parents=True)
    cluster = SlurmDockerCluster.from_manifest(MANIFEST, checkout)

    target = cluster.development_execution_target()
    storage = cluster.development_storage_profile()
    runtimes = cluster.development_runtimes()

    assert target["metadata"]["id"] == "development-slurm-docker"
    assert target["spec"]["scheduler"]["apptainer_executable"] == (
        "/usr/local/bin/qhpc-oci-shim"
    )
    assert storage["metadata"]["status"] == "active"
    assert Path(storage["spec"]["roots"]["task_staging"]).is_relative_to(
        cluster.shared_host_directory
    )
    assert {runtime["metadata"]["id"] for runtime in runtimes} == {
        image["runtime_id"] for image in cluster.runtime_images
    }
    assert len(runtimes) == 5


def test_development_target_verifies_local_image_ids(tmp_path: Path) -> None:
    checkout = tmp_path / "cluster"
    (checkout / "shared-dir").mkdir(parents=True)
    expected = {
        image["local_reference"]: image["digest"]
        for image in load_document(MANIFEST)["spec"]["runtime_images"]
    }
    commands: list[list[str]] = []

    def run(command):
        command = list(command)
        commands.append(command)
        return CommandResult(0, expected[command[-1]] + "\n")

    cluster = SlurmDockerCluster.from_manifest(MANIFEST, checkout, runner=run)
    cluster.verify_runtime_images()

    assert len(commands) == 5
    assert all(command[:3] == ["docker", "image", "inspect"] for command in commands)


def test_smoke_exercises_completion_accounting_and_cancellation(
    tmp_path: Path,
) -> None:
    checkout = tmp_path / "cluster"
    _prepared_checkout(checkout)
    canceled = False
    submissions = 0
    slurm_commands: list[list[str]] = []

    def run(command):
        nonlocal canceled, submissions
        command = list(command)
        if command[:3] == ["git", "-C", str(checkout)]:
            if "rev-parse" in command:
                return CommandResult(0, REVISION + "\n")
            if "status" in command:
                return CommandResult(0, "")
            raise AssertionError(command)

        service_index = command.index("slurmctld")
        slurm = command[service_index + 1 :]
        slurm_commands.append(slurm)
        if slurm[0] == "sbatch":
            submissions += 1
            return CommandResult(0, f"{100 + submissions};linux\n")
        if slurm[0] == "squeue":
            job_id = slurm[slurm.index("--jobs") + 1]
            if job_id == "101":
                return CommandResult(0, "")
            return CommandResult(0, "" if canceled else "RUNNING\n")
        if slurm[0] == "sacct":
            job_id = slurm[slurm.index("--jobs") + 1]
            if job_id == "101":
                output = checkout / "shared-dir" / "qhpc-smoke-fixed-101.out"
                output.write_text(
                    "QHPC_SLURM_SMOKE_OK:fixed\nworker-1\n",
                    encoding="utf-8",
                )
                return CommandResult(0, "COMPLETED|\n")
            return CommandResult(0, "CANCELLED by 0|\n")
        if slurm[0] == "scancel":
            canceled = True
            return CommandResult(0, "")
        raise AssertionError(slurm)

    cluster = SlurmDockerCluster.from_manifest(
        MANIFEST,
        checkout,
        runner=run,
        sleeper=lambda _: None,
        token_factory=lambda: "fixed",
    )

    result = cluster.smoke(timeout_seconds=10)

    assert result.completed_job_id == "101"
    assert result.completed_state == "succeeded"
    assert result.canceled_job_id == "102"
    assert result.canceled_state == "canceled"
    assert "QHPC_SLURM_SMOKE_OK:fixed" in result.output
    assert [command[0] for command in slurm_commands] == [
        "sbatch",
        "squeue",
        "sacct",
        "sbatch",
        "squeue",
        "scancel",
        "squeue",
        "sacct",
    ]
    assert not list((checkout / "shared-dir").glob("qhpc-*"))


def test_cli_reports_cluster_status_without_loading_catalog(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class FakeCluster:
        def status(self) -> ClusterStatus:
            return ClusterStatus(
                compose=CommandResult(0, "slurmctld running\n"),
                controller=CommandResult(0, "Slurmctld is UP\n"),
                nodes=CommandResult(0, "c1|idle|0/8/0/8\n"),
            )

    monkeypatch.setattr(
        SlurmDockerCluster,
        "from_manifest",
        staticmethod(lambda *_: FakeCluster()),
    )

    assert cli.main(["slurm-test-cluster", "status", str(MANIFEST)]) == 0
    output = capsys.readouterr().out
    assert "Ready: true" in output
    assert "c1|idle|0/8/0/8" in output
