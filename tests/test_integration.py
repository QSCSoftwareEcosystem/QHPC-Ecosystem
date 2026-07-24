from __future__ import annotations

import copy
from pathlib import Path

import pytest

from qhpc_ecosystem import cli
from qhpc_ecosystem.contract import validate_contract
from qhpc_ecosystem.integration import (
    IntegrationError,
    IntegrationScaffold,
    find_integration_scaffold,
    load_integration_scaffolds,
    validate_scaffold_references,
    validate_scaffold_set,
)


ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "deployments" / "initial.yaml"


def test_initial_profile_has_an_aligned_scaffold_for_every_component() -> None:
    profile, scaffolds = load_integration_scaffolds(PROFILE)

    assert tuple(scaffold.component_id for scaffold in scaffolds) == tuple(
        component["id"] for component in profile["spec"]["components"]
    )
    assert len(scaffolds) == 10
    assert {
        scaffold.component_id
        for scaffold in scaffolds
        if scaffold.document["metadata"]["integration_status"] == "published"
    } == {"stabsim", "qasmtrans", "openqevo", "qappswiki"}


def test_initial_scaffolds_defer_production_containerization() -> None:
    _, scaffolds = load_integration_scaffolds(PROFILE)

    runtime_statuses = {
        scaffold.component_id: scaffold.document["spec"]["production_runtime"][
            "status"
        ]
        for scaffold in scaffolds
    }
    assert "verified" not in runtime_statuses.values()
    assert runtime_statuses["qappswiki"] == "not-applicable"
    assert runtime_statuses["openqse"] == "not-applicable"
    assert all(
        "runtime" not in scaffold.document["spec"] for scaffold in scaffolds
    )


def test_public_pending_components_have_pinned_interface_contracts() -> None:
    _, scaffolds = load_integration_scaffolds(PROFILE)

    for component_id in ("nwqec", "ftprimitivebench", "lightstim"):
        scaffold = find_integration_scaffold(scaffolds, component_id).document
        assert scaffold["spec"]["scope"]["status"] == "defined"
        assert scaffold["spec"]["deliverables"]["source_audit"] == "complete"
        assert scaffold["spec"]["deliverables"]["interface_contract"] == "complete"
        assert scaffold["spec"]["deliverables"]["adapter"] == "complete"
        assert scaffold["spec"]["deliverables"]["fixtures"] == "complete"
        assert scaffold["spec"]["deliverables"]["integration_tests"] == "complete"
        assert scaffold["spec"]["deliverables"]["registry_publication"] == "pending"
        assert scaffold["spec"]["production_runtime"]["status"] == "deferred"


def test_chatqec_source_and_service_scope_are_recorded_before_contract_work() -> None:
    _, scaffolds = load_integration_scaffolds(PROFILE)

    scaffold = find_integration_scaffold(scaffolds, "chatqec").document
    assert scaffold["spec"]["mirror"]["status"] == "verified"
    assert scaffold["spec"]["source"]["url"] == (
        "https://github.com/QSCSoftwareThrust/ChatQEC"
    )
    assert scaffold["spec"]["mirror"]["url"] == (
        "https://code.ornl.gov/qsc-as/chatqec"
    )
    assert scaffold["spec"]["scope"]["status"] == "defined"
    assert scaffold["spec"]["deliverables"]["source_audit"] == "complete"
    assert scaffold["spec"]["deliverables"]["interface_contract"] == "blocked"
    assert scaffold["spec"]["deliverables"]["adapter"] == "pending"
    assert scaffold["spec"]["contract_refs"] == []


def test_tn_sim_uses_public_upstream_without_a_qsc_mirror() -> None:
    _, scaffolds = load_integration_scaffolds(PROFILE)
    scaffold = find_integration_scaffold(scaffolds, "tn-sim").document

    assert scaffold["metadata"]["visibility"] == "public"
    assert scaffold["metadata"]["integration_status"] == "scaffolded"
    assert scaffold["spec"]["source"] == {
        "kind": "repository",
        "url": "https://github.com/pnnl/NWQ-Sim/tree/tn_sim",
        "catalog_repository": "NWQ-Sim",
    }
    assert scaffold["spec"]["mirror"] == {"status": "not-applicable"}
    assert scaffold["spec"]["deliverables"]["source_audit"] == "pending"


def test_draft_cross_project_artifact_types_are_valid() -> None:
    paths = sorted((ROOT / "artifact-types").glob("*.yaml"))
    assert {path.name for path in paths} == {
        "clifford-t-counts-v1.yaml",
        "logical-error-estimate-v1.yaml",
        "stim-circuit-v1.yaml",
    }
    for path in paths:
        validate_contract("artifact-type", path)


def test_scaffold_set_rejects_profile_metadata_drift() -> None:
    profile, scaffolds = load_integration_scaffolds(PROFILE)
    changed = copy.deepcopy(scaffolds[0].document)
    changed["metadata"]["name"] = "Different Name"
    records = (
        IntegrationScaffold(path=scaffolds[0].path, document=changed),
        *scaffolds[1:],
    )

    with pytest.raises(IntegrationError, match="scaffold name does not match"):
        validate_scaffold_set(profile, records)


def test_scaffold_reference_validation_rejects_missing_contract() -> None:
    _, scaffolds = load_integration_scaffolds(PROFILE)
    changed = copy.deepcopy(scaffolds[2].document)
    changed["spec"]["contract_refs"] = ["integrations/nwqec/missing.yaml"]
    records = (
        *scaffolds[:2],
        IntegrationScaffold(path=scaffolds[2].path, document=changed),
        *scaffolds[3:],
    )

    with pytest.raises(IntegrationError, match="referenced file not found"):
        validate_scaffold_references(records, ROOT)


def test_find_integration_scaffold_rejects_unknown_component() -> None:
    _, scaffolds = load_integration_scaffolds(PROFILE)

    with pytest.raises(IntegrationError, match="not found: missing"):
        find_integration_scaffold(scaffolds, "missing")


def test_integration_cli_validates_lists_and_inspects(capsys) -> None:
    assert cli.main(["integration", "validate", str(PROFILE)]) == 0
    assert "Integration scaffolds valid: initial@0.2.0 (10 components)" in (
        capsys.readouterr().out
    )

    assert cli.main(["integration", "list", str(PROFILE)]) == 0
    output = capsys.readouterr().out
    assert "COMPONENT" in output
    assert "nwqec" in output
    assert "deferred" in output

    assert cli.main(["integration", "info", str(PROFILE), "chatqec"]) == 0
    output = capsys.readouterr().out
    assert "Integration status:   scaffolded" in output
    assert "Production runtime:   deferred (oci)" in output
