from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
import yaml

from qhpc_ecosystem import cli
from qhpc_ecosystem.contract import validate_contract
from qhpc_ecosystem.hpc_acceptance import (
    HpcAcceptanceError,
    inspect_hpc_acceptance,
)


ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "infrastructure/hpc-acceptance/initial.yaml"


def _write_profile(tmp_path: Path, document: dict) -> Path:
    path = tmp_path / "hpc-acceptance.yaml"
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    return path


def test_initial_hpc_acceptance_profile_covers_only_initial_components() -> None:
    validate_contract("hpc-acceptance", PROFILE)
    report = inspect_hpc_acceptance(PROFILE)

    assert len(report.cases) == 14
    assert [case.component_id for case in report.cases] == [
        "stabsim",
        "tn-sim",
        "nwqec",
        "ftprimitivebench",
        "lightstim",
        "qasmtrans",
        "ftqc",
        "openqevo",
        "openqse",
        "qappswiki",
        "chatqec",
        "exachem-qflow",
        "iris-qiris",
        "nwqsim-qflow",
    ]
    assert {
        case.component_id
        for case in report.cases
        if case.status == "oci-verified"
    } == {
        "stabsim",
        "nwqec",
        "ftprimitivebench",
        "lightstim",
        "qasmtrans",
    }
    assert {
        case.component_id
        for case in report.cases
        if case.status == "runtime-pending"
    } == {"tn-sim", "ftqc"}
    assert {
        case.component_id
        for case in report.cases
        if case.status == "not-applicable"
    } == {
        "openqevo",
        "openqse",
        "qappswiki",
        "chatqec",
        "exachem-qflow",
        "iris-qiris",
        "nwqsim-qflow",
    }
    assert len(report.batch_cases) == 7
    assert report.scheduler_fixture_status == "validated"
    assert report.execution_target_status == "planned"
    assert report.storage_profile_status == "planned"
    assert report.ready is False
    assert "QFw" not in PROFILE.read_text(encoding="utf-8")


def test_hpc_acceptance_rejects_deployment_or_runtime_drift(
    tmp_path: Path,
) -> None:
    document = validate_contract("hpc-acceptance", PROFILE)
    missing = copy.deepcopy(document)
    missing["spec"]["cases"].pop()
    with pytest.raises(HpcAcceptanceError, match="component order and membership"):
        inspect_hpc_acceptance(
            _write_profile(tmp_path, missing),
            workspace_root=ROOT,
        )

    mismatched = copy.deepcopy(document)
    mismatched["spec"]["cases"][0]["runtime"] = (
        "containers/operations/qasmtrans/runtime.yaml"
    )
    with pytest.raises(
        HpcAcceptanceError,
        match="is not declared by the component integration scaffold",
    ):
        inspect_hpc_acceptance(
            _write_profile(tmp_path, mismatched),
            workspace_root=ROOT,
        )


def test_hpc_acceptance_cli_reports_status_and_enforces_gate(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert cli.main(["hpc-acceptance", "status", str(PROFILE)]) == 0
    output = capsys.readouterr().out
    assert "HPC acceptance: initial@0.3.0 (planned)" in output
    assert "Batch operations: 7 (oci-verified=5, runtime-pending=2)" in output
    assert "Ready: false" in output

    assert (
        cli.main(["hpc-acceptance", "gate", str(PROFILE), "--json"])
        == 1
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["ready"] is False
    assert payload["scheduler_fixture_status"] == "validated"
