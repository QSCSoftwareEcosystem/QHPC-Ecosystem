from __future__ import annotations

import copy
from pathlib import Path

import pytest

from qhpc_ecosystem.contract import ContractError, document_digest, load_document
from qhpc_ecosystem.registry import load_registry
from qhpc_ecosystem.workflow import resolve_workflow, topological_nodes


ROOT = Path(__file__).resolve().parents[1]


def example_registry() -> dict:
    capability = load_document(ROOT / "examples/contracts/valid/capability.yaml")
    return {
        "api_version": "qhpc/v1",
        "kind": "Registry",
        "metadata": {
            "entry_count": 1,
            "catalog_digest": "sha256:" + "a" * 64,
        },
        "spec": {
            "entries": [
                {
                    "descriptor_digest": document_digest(capability),
                    "catalog_repository": "example",
                    "validation": {
                        "contract": "valid",
                        "attribution": "valid",
                        "authority": "ecosystem",
                        "curated_by": ["qhpc-ecosystem"],
                        "project_reviewed": False,
                        "runtime": "declared",
                        "documentation": "linked",
                        "status": "contract-valid",
                        "evidence": ["tests/test_contract.py"],
                    },
                    "capability": capability,
                }
            ]
        },
    }


def test_workflow_resolves_operations_ports_and_order() -> None:
    workflow = load_document(ROOT / "examples/contracts/valid/workflow.yaml")
    resolved = resolve_workflow(workflow, example_registry())

    assert set(resolved.operations) == {"generate", "simulate"}
    assert resolved.operations["simulate"].operation["id"] == "simulate"
    assert topological_nodes(workflow) == ("generate", "simulate")


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda workflow: workflow["spec"]["edges"][0]["to"].update(
                {"port": "missing"}
            ),
            "input port not found",
        ),
        (
            lambda workflow: workflow["spec"]["nodes"][0]["parameters"].update(
                {"qubits": 0}
            ),
            "below minimum",
        ),
        (
            lambda workflow: workflow["spec"]["nodes"][1]["operation"].update(
                {"operation": "missing"}
            ),
            "operation not found",
        ),
    ],
)
def test_workflow_rejects_registry_incompatibilities(mutation, message: str) -> None:
    workflow = copy.deepcopy(
        load_document(ROOT / "examples/contracts/valid/workflow.yaml")
    )
    mutation(workflow)

    with pytest.raises(ContractError, match=message):
        resolve_workflow(workflow, example_registry())


def test_ct_hw_workflow_resolves_pinned_cross_project_operations() -> None:
    workflow = load_document(ROOT / "examples/workflows/ct-hw-qasm-analysis.yaml")
    registry = load_registry(ROOT / "examples/registry.yaml")

    resolved = resolve_workflow(workflow, registry)

    assert topological_nodes(workflow) == ("transpile", "analyze")
    assert resolved.operations["transpile"].project == "compilation-tools"
    assert resolved.operations["analyze"].project == "hybrid-workflows"
