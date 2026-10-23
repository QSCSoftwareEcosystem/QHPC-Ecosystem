from __future__ import annotations

from pathlib import Path

import pytest

from qhpc_ecosystem.catalog import load_catalog


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def mirror_manifest() -> Path:
    """Return the sibling GitLab mirror manifest, skipping when it is absent.

    The manifest lives in the separate ProjectManagement repository, so a
    standalone QHPC-Ecosystem checkout cannot check catalog coverage against it.
    """
    path = load_catalog(ROOT / "ecosystem.yaml").source_manifest
    if not path.is_file():
        pytest.skip(f"mirror manifest not checked out: {path}")
    return path
