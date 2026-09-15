"""Packaged, versioned inputs for the portable EQO Local profile."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path


ASSETS = {
    "catalog": "ecosystem.yaml",
    "registry": "registry.yaml",
    "deployment-profile": "deployment.yaml",
    "assistant-interface": "assistant-service.yaml",
    "public-image-manifest": "images/public-ghcr-v1.json",
    "workflow-chatqec-code-parameters": "workflows/chatqec-code-parameters.yaml",
    "workflow-chatqec-qec-toolchain": "workflows/chatqec-qec-toolchain.yaml",
    "workflow-chatqec-threshold-sweep": "workflows/chatqec-threshold-sweep.yaml",
    "workflow-chatqec-tsim-simulation": "workflows/chatqec-tsim-simulation.yaml",
    "workflow-chatqec-glcb-link": "workflows/chatqec-glcb-link.yaml",
    "workflow-openqevo-catalog": "workflows/openqevo-method-catalog.yaml",
    "workflow-openqevo-method-context": "workflows/openqevo-method-context.yaml",
    "workflow-openqevo-dense-reference": "workflows/openqevo-dense-reference.yaml",
    "workflow-openqevo-synthesis": "workflows/openqevo-trotter-synthesis.yaml",
    "workflow-showcase-evolution-readiness": "workflows/showcase-evolution-readiness.yaml",
    "workflow-qasm-analysis": "workflows/ct-hw-qasm-analysis.yaml",
    "workflow-qec-memory": "workflows/qec-memory-estimation.yaml",
    "workflow-showcase-qec-distance-study": "workflows/showcase-qec-distance-study.yaml",
    "workflow-nwqec-counts": "workflows/nwqec-counts.yaml",
    "workflow-ftqc-iqm-bell": "workflows/ftqc-iqm-bell-preparation.yaml",
    "workflow-ftqc-iqm-steane": "workflows/ftqc-iqm-steane-preparation.yaml",
    "workflow-ftqc-iqm-bell-execution": "workflows/ftqc-iqm-bell-execution.yaml",
    "workflow-ftqc-iqm-steane-execution": "workflows/ftqc-iqm-steane-execution.yaml",
}

ASSISTANT_SOURCE = "chatqec"

DEFAULT_WORKFLOW_ASSETS = (
    "workflow-chatqec-code-parameters",
    "workflow-chatqec-qec-toolchain",
    "workflow-chatqec-threshold-sweep",
    "workflow-chatqec-tsim-simulation",
    "workflow-chatqec-glcb-link",
    "workflow-openqevo-catalog",
    "workflow-openqevo-method-context",
    "workflow-openqevo-dense-reference",
    "workflow-openqevo-synthesis",
    "workflow-showcase-evolution-readiness",
    "workflow-qasm-analysis",
    "workflow-qec-memory",
    "workflow-showcase-qec-distance-study",
    "workflow-nwqec-counts",
    "workflow-ftqc-iqm-bell",
    "workflow-ftqc-iqm-steane",
    "workflow-ftqc-iqm-bell-execution",
    "workflow-ftqc-iqm-steane-execution",
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


def assistant_source_path() -> Path:
    """Return the immutable ChatQEC corpus bundled with EQO Local."""

    value = files(__package__).joinpath(ASSISTANT_SOURCE)
    path = Path(str(value))
    if not path.is_dir():
        raise FileNotFoundError("packaged EQO Local Assistant corpus is missing")
    return path


def default_workflow_paths() -> tuple[str, ...]:
    return tuple(str(asset_path(name)) for name in DEFAULT_WORKFLOW_ASSETS)
