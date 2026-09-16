from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from qhpc_ecosystem.catalog import load_catalog
from qhpc_ecosystem.chatqec_service import CanonicalChatQEC, ChatQECSource
from qhpc_ecosystem.contract import validate_contract
from qhpc_ecosystem.local_assets import ASSETS, assistant_source_path, asset_path
from qhpc_ecosystem.local_images import load_public_images
from qhpc_ecosystem.knowledge import QAppsWikiKnowledge


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ASSETS = {
    "catalog": ROOT / "ecosystem.yaml",
    "registry": ROOT / "examples" / "registry.yaml",
    "deployment-profile": ROOT / "deployments" / "initial.yaml",
    "assistant-interface": ROOT / "integrations" / "chatqec" / "service.yaml",
    "workflow-chatqec-code-parameters": ROOT
    / "examples"
    / "workflows"
    / "chatqec-code-parameters.yaml",
    "workflow-chatqec-qec-toolchain": ROOT
    / "examples"
    / "workflows"
    / "chatqec-qec-toolchain.yaml",
    "workflow-chatqec-threshold-sweep": ROOT
    / "examples"
    / "workflows"
    / "chatqec-threshold-sweep.yaml",
    "workflow-chatqec-tsim-simulation": ROOT
    / "examples"
    / "workflows"
    / "chatqec-tsim-simulation.yaml",
    "workflow-chatqec-glcb-link": ROOT
    / "examples"
    / "workflows"
    / "chatqec-glcb-link.yaml",
    "workflow-openqevo-catalog": ROOT
    / "examples"
    / "workflows"
    / "openqevo-method-catalog.yaml",
    "workflow-openqevo-method-context": ROOT
    / "examples"
    / "workflows"
    / "openqevo-method-context.yaml",
    "workflow-openqevo-dense-reference": ROOT
    / "examples"
    / "workflows"
    / "openqevo-dense-reference.yaml",
    "workflow-openqevo-synthesis": ROOT
    / "examples"
    / "workflows"
    / "openqevo-trotter-synthesis.yaml",
    "workflow-openqevo-nwqsim-tour": ROOT
    / "examples"
    / "workflows"
    / "openqevo-nwqsim-tour.yaml",
    "workflow-showcase-evolution-readiness": ROOT
    / "examples"
    / "workflows"
    / "showcase-evolution-readiness.yaml",
    "workflow-qasm-analysis": ROOT
    / "examples"
    / "workflows"
    / "ct-hw-qasm-analysis.yaml",
    "workflow-qec-memory": ROOT
    / "examples"
    / "workflows"
    / "qec-memory-estimation.yaml",
    "workflow-showcase-qec-distance-study": ROOT
    / "examples"
    / "workflows"
    / "showcase-qec-distance-study.yaml",
    "workflow-nwqec-counts": ROOT
    / "examples"
    / "workflows"
    / "nwqec-counts.yaml",
    "workflow-ftqc-iqm-bell": ROOT
    / "examples"
    / "workflows"
    / "ftqc-iqm-bell-preparation.yaml",
    "workflow-ftqc-iqm-steane": ROOT
    / "examples"
    / "workflows"
    / "ftqc-iqm-steane-preparation.yaml",
    "workflow-ftqc-iqm-bell-execution": ROOT
    / "examples"
    / "workflows"
    / "ftqc-iqm-bell-execution.yaml",
    "workflow-ftqc-iqm-steane-execution": ROOT
    / "examples"
    / "workflows"
    / "ftqc-iqm-steane-execution.yaml",
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
    assert catalog.source_manifest.read_bytes() == (
        ROOT / "catalog" / "repositories.tsv"
    ).read_bytes()
    assert registry["metadata"]["entry_count"] == len(registry["spec"]["entries"])
    assert profile["metadata"]["id"] == "initial"
    assert service["metadata"]["id"] == "chatqec-internal-api"
    assert len(workflows) == 19


def test_packaged_assistant_corpus_is_immutable_and_requires_no_checkout() -> None:
    interface = asset_path("assistant-interface")
    source = ChatQECSource.from_contract(interface, assistant_source_path())

    source.verify()
    responder = CanonicalChatQEC(
        source.checkout,
        source_url=source.repository,
        source_revision=source.revision,
    )

    assert source.revision == "a1ddc2e4916b1f4152fba4c94c9c7512eea0d977"
    assert len(responder.pages) == 60
    assert responder.corpus_revision == (
        "sha256:95e43b52660f4789457ef54b0b5c3ffc557b0610e24fc4780ed709c800928330"
    )


def test_packaged_qappswiki_graph_is_immutable_and_requires_no_checkout() -> None:
    graph = asset_path("qappswiki-graph")
    knowledge = QAppsWikiKnowledge(
        graph,
        source_revision="d5f0248945516a4198f92edd9764a2fe5b676549",
    )
    summary = knowledge.summary()

    assert summary["available"] is True
    assert summary["schema_version"] == "qappswiki-graph-0"
    assert summary["stats"]["content_nodes"] == 711
    assert summary["stats"]["all_nodes"] == 1413
    assert summary["stats"]["edges"] == 4660
    assert summary["stats"]["communities"] == 9
    assert hashlib.sha256(graph.read_bytes()).hexdigest() == (
        "ba8abcdf70dfecd1c041f39f5a4d84aaa5691189956e5ab959835c054809d05e"
    )
    assert graph.stat().st_size < 2 * 1024 * 1024


def test_packaged_public_image_manifest_declares_the_admitted_image_set() -> None:
    images = load_public_images()

    assert [image.id for image in images] == [
        "qasmtrans",
        "stabsim",
        "nwqec",
        "ftprimitivebench",
        "lightstim",
        "ftqc",
        "chatqec-qec-tools",
        "chatqec-lightstim",
        "chatqec-tsim",
        "stim",
            "tsim",
            "qfw-slurm-development",
            "nwqsim",
    ]
    assert all(image.source.startswith("ghcr.io/qscsoftwareecosystem/") for image in images)
    qfw = next(image for image in images if image.id == "qfw-slurm-development")
    assert qfw.source == (
        "ghcr.io/qscsoftwareecosystem/eqo-qfw-slurm@sha256:"
        "5d6a15ba9338e54c4eda135381cc74d1f65e582da9fc861abfb1c0b1dd359105"
    )
    assert qfw.local_reference == "qhpc/openqse-qfw-slurm:0.1.0-office"
    assert qfw.local_id == (
        "sha256:1ee74220fa86caec44abe12993e794e9e911abef7c4ef37fdbc1e3fa6d9cd95b"
    )
