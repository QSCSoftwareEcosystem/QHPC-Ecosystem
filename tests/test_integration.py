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
    assert len(scaffolds) == 14
    assert {
        scaffold.component_id
        for scaffold in scaffolds
        if scaffold.document["metadata"]["integration_status"] == "published"
    } == {
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
    }
    assert {
        scaffold.component_id
        for scaffold in scaffolds
        if scaffold.document["metadata"]["integration_status"] == "scaffolded"
    } == {
        "exachem-qflow",
        "iris-qiris",
        "nwqsim-qflow",
    }


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


def test_pre_runtime_components_have_pinned_interface_contracts() -> None:
    _, scaffolds = load_integration_scaffolds(PROFILE)

    for component_id in (
        "tn-sim",
        "nwqec",
        "ftprimitivebench",
        "lightstim",
        "ftqc",
    ):
        scaffold = find_integration_scaffold(scaffolds, component_id).document
        assert scaffold["spec"]["scope"]["status"] == "defined"
        assert scaffold["spec"]["deliverables"]["source_audit"] == "complete"
        assert scaffold["spec"]["deliverables"]["interface_contract"] == "complete"
        assert scaffold["spec"]["deliverables"]["adapter"] == "complete"
        assert scaffold["spec"]["deliverables"]["fixtures"] == "complete"
        assert scaffold["spec"]["deliverables"]["integration_tests"] == "complete"
        assert scaffold["spec"]["deliverables"]["registry_publication"] == "complete"
        assert scaffold["spec"]["production_runtime"]["status"] == "deferred"


def test_chatqec_source_and_service_contract_are_complete_before_runtime() -> None:
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
    assert scaffold["spec"]["deliverables"]["interface_contract"] == "complete"
    assert scaffold["spec"]["deliverables"]["adapter"] == "complete"
    assert scaffold["spec"]["deliverables"]["fixtures"] == "complete"
    assert scaffold["spec"]["deliverables"]["integration_tests"] == "complete"
    assert scaffold["spec"]["deliverables"]["registry_publication"] == "complete"
    assert scaffold["spec"]["contract_refs"] == [
        "capabilities/ChatQEC/service/qhpc-capability.yaml",
        "integrations/chatqec/service.yaml"
    ]


def test_initial_pre_container_integration_scope_is_closed() -> None:
    _, scaffolds = load_integration_scaffolds(PROFILE)

    for scaffold_record in scaffolds:
        scaffold = scaffold_record.document
        if scaffold["metadata"]["integration_status"] != "published":
            continue
        deliverables = scaffold["spec"]["deliverables"]
        assert scaffold["spec"]["scope"]["status"] == "defined"
        assert deliverables["source_audit"] == "complete"
        assert deliverables["interface_contract"] == "complete"
        assert deliverables["adapter"] in {"complete", "not-applicable"}
        assert deliverables["fixtures"] in {"complete", "not-applicable"}
        assert deliverables["integration_tests"] == "complete"


def test_qflow_qiris_incubation_is_visible_but_not_executable() -> None:
    _, scaffolds = load_integration_scaffolds(PROFILE)

    for component_id in ("exachem-qflow", "iris-qiris", "nwqsim-qflow"):
        scaffold = find_integration_scaffold(scaffolds, component_id).document
        capability = validate_contract(
            "capability",
            ROOT / scaffold["spec"]["contract_refs"][0],
        )
        assert scaffold["metadata"]["integration_status"] == "scaffolded"
        assert scaffold["spec"]["production_runtime"]["status"] == "deferred"
        assert scaffold["spec"]["deliverables"]["adapter"] == "pending"
        assert not capability["spec"].get("operations")
        assert capability["metadata"]["maturity"] == "prototype"
        assert capability["spec"]["guidance"]["example_workflows"] == []


def test_openqse_and_qappswiki_publish_only_pinned_resources() -> None:
    _, scaffolds = load_integration_scaffolds(PROFILE)

    openqse = find_integration_scaffold(scaffolds, "openqse").document
    openqse_capability = validate_contract(
        "capability",
        ROOT / openqse["spec"]["contract_refs"][0],
    )
    openqse_revision = openqse_capability["metadata"]["repository"]["revision"]

    assert openqse["metadata"]["integration_status"] == "published"
    assert openqse["spec"]["deliverables"]["adapter"] == "not-applicable"
    assert openqse["spec"]["deliverables"]["integration_tests"] == "complete"
    assert openqse["spec"]["production_runtime"]["status"] == "not-applicable"
    assert not openqse_capability["spec"].get("operations")
    assert all(
        openqse_revision in resource["uri"]
        for resource in openqse_capability["spec"]["resources"]
        if resource["id"] != "developer-attribution"
    )
    assert any(
        resource["id"] == "developer-attribution"
        and resource["uri"] == "docs/tool-attribution.md#openqse"
        for resource in openqse_capability["spec"]["resources"]
    )

    qappswiki = find_integration_scaffold(scaffolds, "qappswiki").document
    qappswiki_capability = validate_contract(
        "capability",
        ROOT / qappswiki["spec"]["contract_refs"][0],
    )
    qappswiki_revision = qappswiki_capability["metadata"]["repository"][
        "revision"
    ]
    resources = {
        resource["id"]: resource
        for resource in qappswiki_capability["spec"]["resources"]
    }

    assert qappswiki["metadata"]["integration_status"] == "published"
    assert qappswiki["spec"]["deliverables"]["adapter"] == "complete"
    assert qappswiki["spec"]["deliverables"]["integration_tests"] == "complete"
    assert qappswiki["spec"]["production_runtime"]["status"] == "not-applicable"
    assert not qappswiki_capability["spec"].get("operations")
    assert resources["qappswiki-knowledge-adapter"]["uri"] == (
        "integrations/qappswiki/knowledge-interface.md"
    )
    assert all(
        qappswiki_revision in resources[resource_id]["uri"]
        for resource_id in ("qappswiki-cli", "qappswiki-corpus")
    )


def test_tn_sim_uses_public_upstream_and_pins_its_interface() -> None:
    _, scaffolds = load_integration_scaffolds(PROFILE)
    scaffold = find_integration_scaffold(scaffolds, "tn-sim").document

    assert scaffold["metadata"]["visibility"] == "public"
    assert scaffold["metadata"]["integration_status"] == "published"
    assert scaffold["spec"]["source"] == {
        "kind": "repository",
        "url": "https://github.com/pnnl/NWQ-Sim/tree/tn_sim",
        "catalog_repository": "NWQ-Sim",
    }
    assert scaffold["spec"]["mirror"] == {"status": "not-applicable"}
    assert scaffold["spec"]["scope"]["status"] == "defined"
    assert scaffold["spec"]["interfaces"] == ["qasm", "cli"]
    assert scaffold["spec"]["deliverables"]["source_audit"] == "complete"
    assert scaffold["spec"]["deliverables"]["interface_contract"] == "complete"
    assert scaffold["spec"]["deliverables"]["adapter"] == "complete"
    assert scaffold["spec"]["deliverables"]["fixtures"] == "complete"
    assert scaffold["spec"]["deliverables"]["integration_tests"] == "complete"
    assert scaffold["spec"]["deliverables"]["registry_publication"] == "complete"
    assert scaffold["spec"]["contract_refs"] == [
        "capabilities/NWQ-Sim/tn-sim/qhpc-capability.yaml",
        "integrations/tn-sim/interface.yaml"
    ]
    assert scaffold["spec"]["production_runtime"]["status"] == "deferred"


def test_ftqc_uses_synchronized_private_github_mirror_and_pins_interface() -> None:
    _, scaffolds = load_integration_scaffolds(PROFILE)
    scaffold = find_integration_scaffold(scaffolds, "ftqc").document
    capability = validate_contract(
        "capability",
        ROOT / scaffold["spec"]["contract_refs"][0],
    )

    assert scaffold["metadata"]["visibility"] == "internal"
    assert scaffold["metadata"]["integration_status"] == "published"
    assert scaffold["spec"]["source"] == {
        "kind": "repository",
        "url": "https://github.com/QSCSoftwareThrust/FTQC",
        "catalog_repository": "ftqc",
    }
    assert scaffold["spec"]["mirror"] == {
        "status": "verified",
        "url": "https://code.ornl.gov/qsc-ct/ftqc",
    }
    assert scaffold["spec"]["interfaces"] == ["qasm", "mlir", "qir", "cli"]
    assert scaffold["spec"]["contract_refs"] == [
        "capabilities/FTQC/compiler/qhpc-capability.yaml",
        "integrations/ftqc/interface.yaml",
        "artifact-types/ftqc-mlir-v1.yaml",
    ]
    assert scaffold["spec"]["production_runtime"]["status"] == "deferred"
    resources = {
        resource["id"]: resource
        for resource in capability["spec"]["resources"]
    }
    assert resources["ftqc-iqm-logical-qubit-candidate"] == {
        "id": "ftqc-iqm-logical-qubit-candidate",
        "kind": "documentation",
        "version": "0.1.0",
        "uri": (
            "docs/evidence/"
            "ftqc-iqm-logical-qubit-candidate-2026-07-29.md"
        ),
        "description": (
            "Developer-reported and source-supported one-logical-qubit ORNL "
            "IQM demonstration candidate, with the exact promotion evidence "
            "still required."
        ),
    }
    assert capability["metadata"]["integration"]["evidence"] == [
        "docs/evidence/ftqc-source-mirror-and-import-smoke-2026-07-29.md"
    ]
    assert not capability["spec"].get("operations")
    assert any(
        "One logical qubit on IQM" in step
        for step in capability["spec"]["guidance"]["quick_start"]
    )
    assert any(
        "not verified hardware evidence" in limitation
        for limitation in capability["spec"]["guidance"]["limitations"]
    )


def test_draft_cross_project_artifact_types_are_valid() -> None:
    paths = sorted((ROOT / "artifact-types").glob("*.yaml"))
    assert {path.name for path in paths} == {
        "clifford-t-counts-v1.yaml",
        "evolution-method-context-v1.yaml",
        "evolution-synthesis-report-v1.yaml",
        "ftqc-mlir-v1.yaml",
        "logical-error-estimate-v1.yaml",
        "measurement-counts-v1.yaml",
        "pauli-hamiltonian-v1.yaml",
        "qflow-cycle-checkpoint-v1.yaml",
        "qflow-taskset-result-v1.yaml",
        "qflow-taskset-v1.yaml",
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
    assert "Integration scaffolds valid: initial@0.7.0 (14 components)" in (
        capsys.readouterr().out
    )

    assert cli.main(["integration", "list", str(PROFILE)]) == 0
    output = capsys.readouterr().out
    assert "COMPONENT" in output
    assert "nwqec" in output
    assert "deferred" in output

    assert cli.main(["integration", "info", str(PROFILE), "chatqec"]) == 0
    output = capsys.readouterr().out
    assert "Integration status:   published" in output
    assert "Production runtime:   deferred (oci)" in output
