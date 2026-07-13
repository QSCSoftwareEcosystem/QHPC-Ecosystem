from __future__ import annotations

import csv
from pathlib import Path

import pytest
import yaml

from qhpc_ecosystem.catalog import CatalogError, load_catalog


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "ecosystem.yaml"


def test_catalog_covers_mirror_manifest_and_pending_repository() -> None:
    catalog = load_catalog(CATALOG)
    with catalog.source_manifest.open(encoding="utf-8", newline="") as stream:
        manifest_slugs = {row["slug"] for row in csv.DictReader(stream, delimiter="\t")}
    catalog_slugs = {repository.slug for repository in catalog.repositories}

    assert manifest_slugs <= catalog_slugs
    assert len(catalog.repositories) == len(manifest_slugs) + 1
    assert catalog.repository("HeteQSys").container_status == "blocked"
    assert catalog.repository("ftqc").canonical_status == "ambiguous"
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
