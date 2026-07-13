from __future__ import annotations

from pathlib import Path

import pytest

from qhpc_ecosystem.slurm import (
    CommandResult,
    SlurmClient,
    SlurmResources,
    classify_state,
    render_apptainer_job,
)


def test_apptainer_script_quotes_tokens_and_limits_resources() -> None:
    script = render_apptainer_job(
        image="oras://registry.internal/qasmtrans@sha256:abc",
        entrypoint=["/opt/qhpc/bin/qasmtrans"],
        arguments=["--input", "/work/input circuit.qasm"],
        resources=SlurmResources(
            cpu=4, memory_mb=8192, walltime_seconds=3661, gpu=1, partition="batch"
        ),
        job_name="qhpc-run-1",
    )

    assert "#SBATCH --time=01:01:01" in script
    assert "#SBATCH --gpus=1" in script
    assert "'/work/input circuit.qasm'" in script
    assert "--containall --cleanenv" in script


@pytest.mark.parametrize(
    ("slurm_state", "qhpc_state"),
    [
        ("PENDING", "queued"),
        ("RUNNING", "running"),
        ("COMPLETED", "succeeded"),
        ("OUT_OF_MEMORY", "failed"),
        ("CANCELLED by 123", "canceled"),
    ],
)
def test_slurm_state_classification(slurm_state: str, qhpc_state: str) -> None:
    assert classify_state(slurm_state) == qhpc_state


def test_slurm_client_submits_polls_history_and_cancels(tmp_path: Path) -> None:
    commands: list[list[str]] = []

    def execute(command):
        commands.append(list(command))
        if command[0] == "sbatch":
            return CommandResult(0, "12345;cluster\n")
        if command[0] == "squeue":
            return CommandResult(0, "")
        if command[0] == "sacct":
            return CommandResult(0, "COMPLETED|\n")
        return CommandResult(0, "")

    script = tmp_path / "job.sh"
    script.write_text("#!/bin/sh\n", encoding="utf-8")
    client = SlurmClient(executor=execute)

    assert client.submit(script) == "12345"
    assert client.status("12345") == "succeeded"
    client.cancel("12345")
    assert [command[0] for command in commands] == [
        "sbatch",
        "squeue",
        "sacct",
        "scancel",
    ]


def test_slurm_rejects_untrusted_identifiers() -> None:
    client = SlurmClient(executor=lambda command: CommandResult(0, ""))
    with pytest.raises(ValueError, match="invalid Slurm job ID"):
        client.cancel("123; touch /tmp/bad")
