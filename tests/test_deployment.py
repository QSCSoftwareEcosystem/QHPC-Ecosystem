from __future__ import annotations

import copy
from pathlib import Path

import pytest

from qhpc_ecosystem import api, cli
from qhpc_ecosystem.catalog import load_catalog
from qhpc_ecosystem.contract import ContractError, validate_contract_data
from qhpc_ecosystem.deployment import (
    DeploymentError,
    deployment_catalog_repositories,
    load_deployment_profile,
    registry_for_deployment,
    validate_deployment_catalog,
)
from qhpc_ecosystem.registry import (
    RegistryError,
    find_registry_entry,
    load_registry,
    registry_entries,
)


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "ecosystem.yaml"
PROFILE = ROOT / "deployments" / "initial.yaml"
REGISTRY = ROOT / "examples" / "registry.yaml"


def test_initial_deployment_profile_is_the_authoritative_component_allowlist() -> None:
    profile = load_deployment_profile(PROFILE, load_catalog(CATALOG))

    assert tuple(
        component["name"] for component in profile["spec"]["components"]
    ) == (
        "STABSim",
        "TN-Sim",
        "NWQEC",
        "FTPrimitiveBench",
        "LightStim",
        "QASMTrans",
        "FTQC",
        "OpenQEvo",
        "OpenQSE",
        "QAppsWiki",
        "ChatQEC",
        "ExaChem QFlow",
        "QIRIS Runtime (IRIS/QIR-EE)",
        "NWQSim QFlow VQE Plugin",
    )
    assert profile["spec"]["selection_mode"] == "allowlist"
    assert profile["metadata"]["version"] == "0.7.0"
    stabsim = next(
        component
        for component in profile["spec"]["components"]
        if component["name"] == "STABSim"
    )
    assert stabsim["source"]["url"] == (
        "https://github.com/QSCSoftwareThrust/STABSim"
    )
    lightstim = next(
        component
        for component in profile["spec"]["components"]
        if component["name"] == "LightStim"
    )
    assert lightstim["source"]["url"] == (
        "https://github.com/QSCSoftwareThrust/LightStim"
    )
    ftqc = next(
        component
        for component in profile["spec"]["components"]
        if component["name"] == "FTQC"
    )
    assert ftqc["source"] == {
        "kind": "repository",
        "url": "https://github.com/QSCSoftwareEcosystem/FTQC",
    }
    tn_sim = next(
        component
        for component in profile["spec"]["components"]
        if component["name"] == "TN-Sim"
    )
    assert tn_sim["onboarding_status"] == "registry-published"
    assert tn_sim["catalog_repository"] == "NWQ-Sim"
    assert tn_sim["source"] == {
        "kind": "repository",
        "url": "https://github.com/pnnl/NWQ-Sim/tree/tn_sim",
    }
    chatqec = next(
        component
        for component in profile["spec"]["components"]
        if component["name"] == "ChatQEC"
    )
    assert chatqec["source"] == {
        "kind": "repository",
        "url": "https://github.com/QSCSoftwareThrust/ChatQEC",
    }
    exachem = next(
        component
        for component in profile["spec"]["components"]
        if component["id"] == "exachem-qflow"
    )
    assert exachem["onboarding_status"] == "onboarding"
    assert exachem["source"]["url"] == "https://github.com/ExaChem/exachem"
    qiris = next(
        component
        for component in profile["spec"]["components"]
        if component["id"] == "iris-qiris"
    )
    assert qiris["onboarding_status"] == "onboarding"
    assert qiris["source"]["url"] == "https://github.com/ORNL/iris"
    nwqsim_qflow = next(
        component
        for component in profile["spec"]["components"]
        if component["id"] == "nwqsim-qflow"
    )
    assert nwqsim_qflow["onboarding_status"] == "onboarding"
    assert nwqsim_qflow["source"]["url"] == "https://github.com/pnnl/nwq-sim"
    openqse = next(
        component
        for component in profile["spec"]["components"]
        if component["name"] == "OpenQSE"
    )
    assert openqse["onboarding_status"] == "registry-published"
    assert openqse["catalog_repository"] == "openqse-spec"
    assert openqse["source"] == {
        "kind": "repository",
        "url": "https://github.com/openQSE/openqse-spec",
    }


def test_deployment_registry_exposes_only_selected_published_capabilities() -> None:
    catalog = load_catalog(CATALOG)
    profile = load_deployment_profile(PROFILE, catalog)
    registry = registry_for_deployment(load_registry(REGISTRY, catalog), profile)

    assert deployment_catalog_repositories(profile) == frozenset(
        {
            "STABSim",
            "NWQ-Sim",
            "nwqec",
            "FTPrimitiveBench",
            "LightStim",
            "qasmtrans",
            "ftqc",
            "OpenQEvo",
            "openqse-spec",
            "QAppsWiki",
            "chatqec",
            "ExaChem",
            "IRIS-QIRIS",
            "NWQSim-QFlow",
        }
    )
    assert {entry["catalog_repository"] for entry in registry_entries(registry)} == {
        "STABSim",
        "NWQ-Sim",
        "nwqec",
        "FTPrimitiveBench",
        "LightStim",
        "qasmtrans",
        "ftqc",
        "OpenQEvo",
        "openqse-spec",
        "QAppsWiki",
        "chatqec",
        "ExaChem",
        "IRIS-QIRIS",
        "NWQSim-QFlow",
    }
    assert registry["metadata"]["entry_count"] == 14
    validate_contract_data("registry", registry)
    with pytest.raises(RegistryError, match="capability not found"):
        find_registry_entry(registry, "qsc-hardware-survey")


def test_deployment_profile_rejects_duplicate_components() -> None:
    profile = load_deployment_profile(PROFILE)
    profile["spec"]["components"].append(
        copy.deepcopy(profile["spec"]["components"][0])
    )

    with pytest.raises(ContractError) as error:
        validate_contract_data("deployment-profile", profile)

    assert "duplicate component IDs: stabsim" in str(error.value)
    assert "duplicate catalog repositories: STABSim" in str(error.value)


def test_deployment_profile_rejects_catalog_source_drift() -> None:
    profile = load_deployment_profile(PROFILE)
    profile["spec"]["components"][0]["source"]["url"] = (
        "https://example.invalid/STABSim"
    )

    with pytest.raises(DeploymentError, match="does not match catalog repository"):
        validate_deployment_catalog(profile, load_catalog(CATALOG))


def test_serve_applies_the_deployment_profile_before_building_api_context(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    captured: dict = {}

    def capture(context, host: str, port: int) -> None:
        captured["registry"] = context.registry
        captured["host"] = host
        captured["port"] = port

    monkeypatch.setattr(api, "serve", capture)

    assert (
        cli.main(
            [
                "--catalog",
                str(CATALOG),
                "serve",
                "--registry",
                str(REGISTRY),
                "--deployment-profile",
                str(PROFILE),
                "--database",
                str(tmp_path / "workbench.sqlite"),
                "--artifact-root",
                str(tmp_path / "artifacts"),
            ]
        )
        == 0
    )

    assert {
        entry["catalog_repository"]
        for entry in registry_entries(captured["registry"])
    } == {
        "STABSim",
        "NWQ-Sim",
        "nwqec",
        "FTPrimitiveBench",
        "LightStim",
        "qasmtrans",
        "ftqc",
        "OpenQEvo",
        "openqse-spec",
        "QAppsWiki",
        "chatqec",
        "ExaChem",
        "IRIS-QIRIS",
        "NWQSim-QFlow",
    }
    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == 8080
    assert "Deployment profile: initial@0.7.0" in capsys.readouterr().out


def test_worker_command_uses_the_same_deployment_profile(
    tmp_path: Path, capsys
) -> None:
    assert (
        cli.main(
            [
                "--catalog",
                str(CATALOG),
                "worker",
                "--registry",
                str(REGISTRY),
                "--deployment-profile",
                str(PROFILE),
                "--database",
                str(tmp_path / "workbench.sqlite"),
                "--artifact-root",
                str(tmp_path / "artifacts"),
                "--runtime-root",
                str(tmp_path / "runtimes"),
                "--drain",
            ]
        )
        == 0
    )

    output = capsys.readouterr().out
    assert "QHPC Worker: initial@0.7.0 (14 published capabilities)" in output
    assert "Worker stopped: 0 tasks processed" in output
