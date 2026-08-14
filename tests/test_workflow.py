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


def test_evolution_showcase_resolves_four_tools_and_five_outputs() -> None:
    workflow = load_document(
        ROOT / "examples/workflows/showcase-evolution-readiness.yaml"
    )
    registry = load_registry(ROOT / "examples/registry.yaml")

    resolved = resolve_workflow(workflow, registry)

    assert topological_nodes(workflow) == (
        "synthesize",
        "count",
        "transpile",
        "analyze",
    )
    assert {
        operation.capability_id
        for operation in resolved.operations.values()
    } == {
        "openqevo-library",
        "qasmtrans-transpiler",
        "stabsim-simulator",
        "nwqec-qec-transpilation",
    }
    assert {
        output["artifact_type"]
        for output in workflow["spec"]["outputs"].values()
    } == {
        "qhpc.quantum-circuit@1",
        "qhpc.evolution-synthesis-report@1",
        "qhpc.transpiled-circuit@1",
        "qhpc.circuit-metrics@1",
        "qhpc.clifford-t-counts@1",
    }
    nodes = {node["id"]: node for node in workflow["spec"]["nodes"]}
    assert nodes["synthesize"]["execution_target"] == "local-development"
    assert nodes["synthesize"]["execution_class"] == "interactive-local"
    for node_id in ("count", "transpile", "analyze"):
        assert nodes[node_id]["execution_target"] == "development-slurm-docker"
        assert nodes[node_id]["execution_class"] == "batch-hpc"


def test_qec_distance_showcase_resolves_two_parallel_experiments() -> None:
    workflow = load_document(
        ROOT / "examples/workflows/showcase-qec-distance-study.yaml"
    )
    registry = load_registry(ROOT / "examples/registry.yaml")

    resolved = resolve_workflow(workflow, registry)

    assert topological_nodes(workflow) == (
        "build-distance-3",
        "build-distance-5",
        "estimate-distance-3",
        "estimate-distance-5",
    )
    assert {
        operation.capability_id
        for operation in resolved.operations.values()
    } == {
        "ftprimitivebench-primitives",
        "lightstim-simulation",
    }
    assert set(workflow["spec"]["outputs"]) == {
        "distance_3_circuit",
        "distance_3_estimate",
        "distance_5_circuit",
        "distance_5_estimate",
    }
