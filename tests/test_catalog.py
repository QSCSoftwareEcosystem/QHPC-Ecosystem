from __future__ import annotations

import csv
from pathlib import Path

import pytest
import yaml

from qhpc_ecosystem.catalog import CatalogError, load_catalog


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "ecosystem.yaml"


def test_catalog_covers_mirror_manifest_and_non_mirrored_repositories() -> None:
    catalog = load_catalog(CATALOG)
    with catalog.source_manifest.open(encoding="utf-8", newline="") as stream:
        manifest_slugs = {row["slug"] for row in csv.DictReader(stream, delimiter="\t")}
    catalog_slugs = {repository.slug for repository in catalog.repositories}

    assert manifest_slugs <= catalog_slugs
    assert catalog_slugs - manifest_slugs == {
        "ExaChem",
        "HeteQSys",
        "IRIS-QIRIS",
        "NWQ-Sim",
        "NWQSim-QFlow",
        "openqse-spec",
    }
    assert catalog.repository("HeteQSys").container_status == "blocked"
    assert catalog.repository("NWQ-Sim").source_url == (
        "https://github.com/pnnl/NWQ-Sim/tree/tn_sim"
    )
    assert catalog.repository("ExaChem").source_url == (
        "https://github.com/ExaChem/exachem"
    )
    assert catalog.repository("IRIS-QIRIS").source_url == (
        "https://github.com/ORNL/iris"
    )
    assert catalog.repository("NWQSim-QFlow").source_url == (
        "https://github.com/pnnl/nwq-sim"
    )
    assert catalog.repository("chatqec").source_url == (
        "https://github.com/QSCSoftwareThrust/ChatQEC"
    )
    assert catalog.repository("FTPrimitiveBench").source_url == (
        "https://github.com/QSCSoftwareThrust/FTPrimitiveBench"
    )
    assert catalog.repository("FTPrimitiveBench").alternate_sources == (
        "https://github.com/ShuwenKan/FTPrimitiveBench",
    )
    assert catalog.repository("STABSim").source_url == (
        "https://github.com/QSCSoftwareThrust/STABSim"
    )
    assert catalog.repository("STABSim").alternate_sources == (
        "https://github.com/seangarn32/STABSim",
    )
    assert catalog.repository("LightStim").source_url == (
        "https://github.com/QSCSoftwareThrust/LightStim"
    )
    assert catalog.repository("LightStim").alternate_sources == (
        "https://github.com/QuTone/LightStim",
    )
    assert catalog.repository("openqse-spec").source_url == (
        "https://github.com/openQSE/openqse-spec"
    )
    assert catalog.repository("ftqc").source_url == (
        "https://github.com/QSCSoftwareEcosystem/FTQC"
    )
    assert catalog.repository("ftqc").alternate_sources == (
        "https://code.ornl.gov/qsc-ct/ftqc",
    )
    assert catalog.repository("ftqc").canonical_status == "canonical"
    assert len(catalog.environments) == 5


def test_catalog_rejects_unknown_environment(tmp_path: Path) -> None:
    raw = yaml.safe_load(CATALOG.read_text(encoding="utf-8"))
    raw["repositories"][0]["environment"] = "missing"
    path = tmp_path / "ecosystem.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    with pytest.raises(CatalogError, match="unknown environment"):
        load_catalog(path)


def test_repository_lookup_is_case_insensitive() -> None:
    catalog = load_catalog(CATALOG)
    assert catalog.repository("openqevo").slug == "OpenQEvo"
