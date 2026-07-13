"""Synchronize source locations from the GitLab mirror manifest."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import yaml

from .catalog import CatalogError


MANIFEST_FIELDS = ("slug", "display_name", "source_url", "notes")


def read_manifest(path: str | Path) -> list[dict[str, str]]:
    manifest_path = Path(path).expanduser().resolve()
    try:
        with manifest_path.open(encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream, delimiter="\t")
            if reader.fieldnames != list(MANIFEST_FIELDS):
                raise CatalogError(
                    f"manifest columns must be, in order: {', '.join(MANIFEST_FIELDS)}"
                )
            rows = list(reader)
    except FileNotFoundError as exc:
        raise CatalogError(f"manifest not found: {manifest_path}") from exc

    slugs = [row["slug"] for row in rows]
    if any(not slug for slug in slugs):
        raise CatalogError("manifest contains an empty slug")
    if len(slugs) != len(set(slugs)):
        raise CatalogError("manifest contains duplicate slugs")
    return rows


def _new_repository(row: dict[str, str]) -> dict[str, Any]:
    return {
        **row,
        "qsc_project": "unknown",
        "package_role": "other",
        "capabilities": [],
        "hardware_targets": ["unknown"],
        "interfaces": [],
        "environment": "python-lib",
        "container_status": "planned",
        "visibility": "unknown",
        "canonical_status": "canonical",
    }


def synchronize(
    catalog_path: str | Path,
    manifest_path: str | Path,
    *,
    write: bool = True,
) -> bool:
    """Update manifest-owned fields and append new repositories.

    Returns True when the in-memory synchronized catalog differs from disk.
    """
    path = Path(catalog_path).expanduser().resolve()
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CatalogError(f"catalog not found: {path}") from exc
    except yaml.YAMLError as exc:
        raise CatalogError(f"invalid YAML in {path}: {exc}") from exc
    if not isinstance(raw, dict) or not isinstance(raw.get("repositories"), list):
        raise CatalogError("catalog must contain a repositories list")

    original = yaml.safe_dump(raw, sort_keys=False, allow_unicode=False)
    by_slug = {
        item.get("slug"): item
        for item in raw["repositories"]
        if isinstance(item, dict) and isinstance(item.get("slug"), str)
    }
    for row in read_manifest(manifest_path):
        item = by_slug.get(row["slug"])
        if item is None:
            item = _new_repository(row)
            raw["repositories"].append(item)
            by_slug[row["slug"]] = item
        else:
            for field in MANIFEST_FIELDS[1:]:
                item[field] = row[field]

    updated = yaml.safe_dump(raw, sort_keys=False, allow_unicode=False)
    changed = updated != original
    if changed and write:
        path.write_text(updated, encoding="utf-8")
    return changed
