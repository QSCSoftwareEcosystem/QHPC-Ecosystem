"""Packaged, versioned inputs for the portable EQO Local profile."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path


ASSETS = {
    "catalog": "ecosystem.yaml",
    "registry": "registry.yaml",
    "deployment-profile": "deployment.yaml",
    "assistant-interface": "assistant-service.yaml",
    "workflow-openqevo-catalog": "workflows/openqevo-method-catalog.yaml",
    "workflow-openqevo-synthesis": "workflows/openqevo-trotter-synthesis.yaml",
    "workflow-qasm-analysis": "workflows/ct-hw-qasm-analysis.yaml",
    "workflow-qec-memory": "workflows/qec-memory-estimation.yaml",
    "workflow-nwqec-counts": "workflows/nwqec-counts.yaml",
}

DEFAULT_WORKFLOW_ASSETS = (
    "workflow-openqevo-catalog",
    "workflow-openqevo-synthesis",
    "workflow-qasm-analysis",
    "workflow-qec-memory",
    "workflow-nwqec-counts",
)


def asset_path(name: str) -> Path:
    try:
        relative_path = ASSETS[name]
    except KeyError as error:
        raise ValueError(f"unknown EQO Local asset: {name}") from error
    value = files(__package__).joinpath(relative_path)
    path = Path(str(value))
    if not path.is_file():
        raise FileNotFoundError(f"packaged EQO Local asset is missing: {relative_path}")
    return path


def default_workflow_paths() -> tuple[str, ...]:
    return tuple(str(asset_path(name)) for name in DEFAULT_WORKFLOW_ASSETS)
