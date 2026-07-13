from __future__ import annotations

from pathlib import Path

import yaml

from qhpc_ecosystem import cli
from test_workflow import ROOT, example_registry


def test_cli_publishes_submits_inspects_and_cancels_run(tmp_path: Path, capsys) -> None:
    registry_path = tmp_path / "registry.yaml"
    registry_path.write_text(
        yaml.safe_dump(example_registry(), sort_keys=False), encoding="utf-8"
    )
    workflow_path = ROOT / "examples/contracts/valid/workflow.yaml"
    database = tmp_path / "engine.sqlite"
    artifacts = tmp_path / "artifacts"
    engine_args = ["--database", str(database), "--artifact-root", str(artifacts)]

    assert (
        cli.main(
            [
                "workflow",
                "validate",
                str(workflow_path),
                "--registry",
                str(registry_path),
            ]
        )
        == 0
    )
    assert "Workflow valid:" in capsys.readouterr().out

    assert (
        cli.main(
            [
                "workflow",
                "publish",
                str(workflow_path),
                "--registry",
                str(registry_path),
                *engine_args,
            ]
        )
        == 0
    )
    assert "Workflow published:" in capsys.readouterr().out

    assert (
        cli.main(
            [
                "run-record",
                "submit",
                "example-generate-and-simulate",
                "0.1.0",
                *engine_args,
            ]
        )
        == 0
    )
    output = capsys.readouterr().out
    run_id = output.split("Run submitted: ", 1)[1].split(" ", 1)[0]

    assert cli.main(["run-record", "info", run_id, *engine_args]) == 0
    assert '"state": "queued"' in capsys.readouterr().out

    assert cli.main(["run-record", "cancel", run_id, *engine_args]) == 0
    assert "(canceled)" in capsys.readouterr().out


def test_cli_registers_and_lists_input_artifact(tmp_path: Path, capsys) -> None:
    source = tmp_path / "input.qasm"
    source.write_text("OPENQASM 2.0;\nqreg q[1];\n", encoding="utf-8")
    database = tmp_path / "engine.sqlite"
    artifacts = tmp_path / "artifacts"
    common = ["--database", str(database), "--artifact-root", str(artifacts)]

    assert (
        cli.main(
            [
                "artifact",
                "register",
                str(source),
                "--type",
                "qhpc.quantum-circuit@1",
                *common,
            ]
        )
        == 0
    )
    output = capsys.readouterr().out
    artifact_id = output.split("Artifact registered: ", 1)[1].split(" ", 1)[0]
    assert cli.main(["artifact", "info", artifact_id, *common]) == 0
    assert '"artifact_type": "qhpc.quantum-circuit@1"' in capsys.readouterr().out
