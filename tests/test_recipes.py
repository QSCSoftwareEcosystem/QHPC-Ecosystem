from __future__ import annotations

from pathlib import Path

from qhpc_ecosystem.catalog import load_catalog


ROOT = Path(__file__).resolve().parents[1]


def test_every_environment_has_a_labeled_apptainer_recipe() -> None:
    catalog = load_catalog(ROOT / "ecosystem.yaml")

    for name, environment in catalog.environments.items():
        recipe = environment.recipe.read_text(encoding="utf-8")
        assert "Bootstrap: docker" in recipe
        assert f'org.qscsoftware.environment "{name}"' in recipe
        assert f"QHPC_ENVIRONMENT_CLASS={name}" in recipe
        assert "%test" in recipe
