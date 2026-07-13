from __future__ import annotations

from pathlib import Path

import yaml

from qhpc_ecosystem.sync import synchronize


ROOT = Path(__file__).resolve().parents[1]


def test_sync_preserves_curated_fields_and_adds_new_rows(tmp_path: Path) -> None:
    catalog_path = tmp_path / "ecosystem.yaml"
    catalog_path.write_text(
        (ROOT / "ecosystem.yaml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    manifest_path = tmp_path / "repositories.tsv"
    manifest_path.write_text(
        "slug\tdisplay_name\tsource_url\tnotes\n"
        "OpenQEvo\tOpenQEvo Renamed\thttps://example.test/openqevo\tUpdated note.\n"
        "new-repo\tNew Repo\thttps://example.test/new\tNew source.\n",
        encoding="utf-8",
    )

    assert synchronize(catalog_path, manifest_path)
    raw = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    repositories = {item["slug"]: item for item in raw["repositories"]}
    assert repositories["OpenQEvo"]["display_name"] == "OpenQEvo Renamed"
    assert repositories["OpenQEvo"]["environment"] == "python-lib"
    assert repositories["new-repo"]["container_status"] == "planned"
    assert "HeteQSys" in repositories


def test_sync_is_idempotent_for_current_manifest(tmp_path: Path) -> None:
    catalog_path = tmp_path / "ecosystem.yaml"
    catalog_path.write_text(
        (ROOT / "ecosystem.yaml").read_text(encoding="utf-8"), encoding="utf-8"
    )

    assert not synchronize(
        catalog_path,
        ROOT.parent / "ProjectManagement" / "gitlab-mirror" / "repositories.tsv",
    )


def test_check_mode_reports_drift_without_writing(tmp_path: Path) -> None:
    catalog_path = tmp_path / "ecosystem.yaml"
    original = (ROOT / "ecosystem.yaml").read_text(encoding="utf-8")
    catalog_path.write_text(original, encoding="utf-8")
    manifest_path = tmp_path / "repositories.tsv"
    manifest_path.write_text(
        "slug\tdisplay_name\tsource_url\tnotes\n"
        "OpenQEvo\tChanged\thttps://example.test/changed\tChanged.\n",
        encoding="utf-8",
    )

    assert synchronize(catalog_path, manifest_path, write=False)
    assert catalog_path.read_text(encoding="utf-8") == original
