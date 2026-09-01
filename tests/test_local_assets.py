from __future__ import annotations

from pathlib import Path

import pytest

from qhpc_ecosystem.catalog import load_catalog
from qhpc_ecosystem.contract import validate_contract
from qhpc_ecosystem.local_assets import ASSETS, asset_path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ASSETS = {
    "catalog": ROOT / "ecosystem.yaml",
    "registry": ROOT / "examples" / "registry.yaml",
    "deployment-profile": ROOT / "deployments" / "initial.yaml",
    "assistant-interface": ROOT / "integrations" / "chatqec" / "service.yaml",
    "workflow-openqevo-catalog": ROOT
    / "examples"
    / "workflows"
    / "openqevo-method-catalog.yaml",
    "workflow-openqevo-synthesis": ROOT
    / "examples"
    / "workflows"
    / "openqevo-trotter-synthesis.yaml",
    "workflow-qasm-analysis": ROOT
    / "examples"
    / "workflows"
    / "ct-hw-qasm-analysis.yaml",
    "workflow-qec-memory": ROOT
    / "examples"
    / "workflows"
    / "qec-memory-estimation.yaml",
    "workflow-nwqec-counts": ROOT
    / "examples"
    / "workflows"
    / "nwqec-counts.yaml",
}


@pytest.mark.parametrize("name", sorted(SOURCE_ASSETS))
def test_packaged_local_asset_matches_reviewed_source(name: str) -> None:
    assert name in ASSETS
    assert asset_path(name).read_bytes() == SOURCE_ASSETS[name].read_bytes()


def test_packaged_local_assets_are_valid_release_inputs() -> None:
    catalog = load_catalog(asset_path("catalog"))
    registry = validate_contract("registry", asset_path("registry"))
    profile = validate_contract(
        "deployment-profile", asset_path("deployment-profile")
    )
    service = validate_contract(
        "service-interface", asset_path("assistant-interface")
    )
    workflows = [
        validate_contract("workflow", asset_path(name))
        for name in SOURCE_ASSETS
        if name.startswith("workflow-")
    ]

    assert catalog.repositories
    assert registry["metadata"]["entry_count"] == len(registry["spec"]["entries"])
    assert profile["metadata"]["id"] == "initial"
    assert service["metadata"]["id"] == "chatqec-internal-api"
    assert len(workflows) == 5
