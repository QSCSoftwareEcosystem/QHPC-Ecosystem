from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
import yaml

from qhpc_ecosystem import cli
from qhpc_ecosystem.contract import (
    CONTRACT_SCHEMAS,
    ContractError,
    contract_kinds,
    load_document,
    load_schema,
    validate_contract,
    validate_contract_data,
)


ROOT = Path(__file__).resolve().parents[1]
VALID = ROOT / "examples" / "contracts" / "valid"
INVALID = ROOT / "tests" / "fixtures" / "contracts" / "invalid"
VALID_EXAMPLES = {
    "artifact": VALID / "artifact.yaml",
    "artifact-type": VALID / "artifact-type.yaml",
    "capability": VALID / "capability.yaml",
    "deployment-profile": ROOT / "deployments" / "initial.yaml",
    "execution-target": VALID / "execution-target.yaml",
    "hpc-acceptance": ROOT / "infrastructure/hpc-acceptance/initial.yaml",
    "integration-scaffold": ROOT / "integrations" / "nwqec" / "integration.yaml",
    "operation-interface": ROOT / "integrations" / "nwqec" / "interface.yaml",
    "operation-runtime": (
        ROOT / "containers" / "operations" / "qasmtrans" / "runtime.yaml"
    ),
    "pilot-profile": (
        ROOT / "infrastructure/pilot-profiles/doe-short-interactive.yaml"
    ),
    "run": VALID / "run.yaml",
    "service-interface": ROOT / "integrations" / "chatqec" / "service.yaml",
    "slurm-test-cluster": (
        ROOT
        / "infrastructure"
        / "test-clusters"
        / "slurm-docker-cluster"
        / "cluster.yaml"
    ),
    "storage-profile": VALID / "storage-profile.yaml",
    "workflow": VALID / "workflow.yaml",
    "workflow-draft": VALID / "workflow-draft.yaml",
}


def test_every_packaged_schema_is_valid_and_has_an_example() -> None:
    assert set(contract_kinds()) == set(CONTRACT_SCHEMAS)
    assert set(VALID_EXAMPLES) == set(CONTRACT_SCHEMAS) - {"registry"}

    for kind in contract_kinds():
        schema = load_schema(kind)
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["$id"].endswith(CONTRACT_SCHEMAS[kind])

    for kind, example in VALID_EXAMPLES.items():
        validate_contract(kind, example)


def test_mutable_runtime_fixture_is_rejected() -> None:
    with pytest.raises(ContractError) as error:
        validate_contract("capability", INVALID / "capability-mutable-runtime.yaml")

    message = str(error.value)
    assert "OCI references must end with the declared digest" in message
    assert "mutable ':latest' references are forbidden" in message


def test_cyclic_workflow_fixture_is_rejected() -> None:
    with pytest.raises(ContractError, match="workflow graph must be acyclic"):
        validate_contract("workflow", INVALID / "workflow-cycle.yaml")


def test_workflow_rejects_mismatched_edge_types_and_unknown_nodes() -> None:
    workflow = copy.deepcopy(load_document(VALID_EXAMPLES["workflow"]))
    workflow["spec"]["edges"][0]["to"]["artifact_type"] = "qhpc.measurement-results@1"
    workflow["spec"]["outputs"]["results"]["from"]["node"] = "missing"

    with pytest.raises(ContractError) as error:
        validate_contract_data("workflow", workflow)

    message = str(error.value)
    assert "edge artifact types must match exactly" in message
    assert "references unknown node missing" in message


def test_capability_rejects_default_with_wrong_parameter_type() -> None:
    capability = copy.deepcopy(load_document(VALID_EXAMPLES["capability"]))
    capability["spec"]["operations"][0]["parameters"]["qubits"]["default"] = "four"

    with pytest.raises(ContractError, match="does not match parameter type"):
        validate_contract_data("capability", capability)


def test_capability_guidance_requires_use_case_and_quick_start() -> None:
    capability = copy.deepcopy(load_document(VALID_EXAMPLES["capability"]))
    capability["spec"]["guidance"].pop("quick_start")

    with pytest.raises(ContractError, match="quick_start"):
        validate_contract_data("capability", capability)


def test_capability_component_can_name_the_upstream_tool() -> None:
    capability = copy.deepcopy(load_document(VALID_EXAMPLES["capability"]))

    assert capability["spec"]["component"]["name"] == "Example Quantum Toolkit"
    validate_contract_data("capability", capability)


def test_operation_interface_rejects_default_with_wrong_parameter_type() -> None:
    interface = copy.deepcopy(load_document(VALID_EXAMPLES["operation-interface"]))
    interface["spec"]["operations"][0]["parameters"]["epsilon"]["default"] = "small"

    with pytest.raises(ContractError, match="does not match parameter type"):
        validate_contract_data("operation-interface", interface)


def test_service_interface_rejects_unknown_or_invalid_nested_schemas() -> None:
    interface = copy.deepcopy(load_document(VALID_EXAMPLES["service-interface"]))
    interface["spec"]["endpoints"][0]["request_schema"] = "missing"
    interface["spec"]["schemas"]["answer-response"] = {"type": "unknown"}

    with pytest.raises(ContractError) as error:
        validate_contract_data("service-interface", interface)

    message = str(error.value)
    assert "references unknown schema missing" in message
    assert "is not a valid JSON Schema" in message


def test_storage_profile_rejects_unreviewed_or_inert_node_local_staging() -> None:
    profile = copy.deepcopy(load_document(VALID_EXAMPLES["storage-profile"]))
    profile["metadata"]["evidence"] = []
    profile["spec"]["node_local"]["mode"] = "disabled"

    with pytest.raises(ContractError) as error:
        validate_contract_data("storage-profile", profile)

    message = str(error.value)
    assert "required for an active storage profile" in message
    assert "flags require slurm-tmpdir mode" in message


def test_planned_slurm_target_cannot_be_activated_without_site_decisions() -> None:
    target = load_document(
        ROOT / "infrastructure/execution-targets/doe-slurm-apptainer.yaml"
    )
    validate_contract_data("execution-target", target)
    target["metadata"]["status"] = "active"

    with pytest.raises(ContractError) as error:
        validate_contract_data("execution-target", target)

    message = str(error.value)
    assert "scheduler/account" in message
    assert "resource_limits/max_cpu" in message
    assert "metadata/evidence" in message


def test_contract_cli_does_not_load_repository_catalog(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        cli,
        "load_catalog",
        lambda *_: (_ for _ in ()).throw(AssertionError("catalog loaded")),
    )

    assert cli.main(["contract", "list"]) == 0
    assert "capability\tcapability-v1.schema.json" in capsys.readouterr().out

    assert (
        cli.main(["contract", "validate", "workflow", str(VALID_EXAMPLES["workflow"])])
        == 0
    )
    assert "Contract valid: workflow" in capsys.readouterr().out


def test_contract_schema_cli_prints_json(capsys) -> None:
    assert cli.main(["contract", "schema", "artifact-type"]) == 0
    schema = json.loads(capsys.readouterr().out)
    assert schema["title"] == "QHPC Artifact Type v1"


def test_example_files_remain_yaml_serializable() -> None:
    for path in VALID_EXAMPLES.values():
        document = load_document(path)
        assert yaml.safe_load(yaml.safe_dump(document)) == document
