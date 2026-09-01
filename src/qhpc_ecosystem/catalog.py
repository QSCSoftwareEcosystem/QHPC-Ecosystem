"""Load and validate the QHPC ecosystem catalog."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


PACKAGE_ROLES = {
    "library",
    "framework",
    "simulator",
    "compiler",
    "workflow",
    "backend",
    "dataset",
    "other",
}
HARDWARE_TARGETS = {
    "local-cpu",
    "local-gpu",
    "hpc",
    "quantum-hardware",
    "simulator",
    "unknown",
}
INTERFACES = {
    "python-api",
    "registry",
    "adapter",
    "json-context",
    "markdown-source",
    "qasm",
    "qir",
    "stim",
    "mlir",
    "metadata-bundle",
    "mcp",
    "cli",
    "hybrid-agent-interface",
}
CONTAINER_STATUSES = {"ready", "planned", "blocked"}
CANONICAL_STATUSES = {"canonical", "ambiguous", "unresolved"}
VISIBILITIES = {"public", "internal", "unknown"}


class CatalogError(ValueError):
    """Raised when catalog data is missing or inconsistent."""


@dataclass(frozen=True)
class Environment:
    name: str
    recipe: Path
    description: str


@dataclass(frozen=True)
class Repository:
    slug: str
    display_name: str
    source_url: str | None
    notes: str
    qsc_project: str
    package_role: str
    capabilities: tuple[str, ...]
    hardware_targets: tuple[str, ...]
    interfaces: tuple[str, ...]
    environment: str
    container_status: str
    visibility: str
    canonical_status: str
    local_path: Path | None
    alternate_sources: tuple[str, ...]


@dataclass(frozen=True)
class Catalog:
    path: Path
    schema_version: int
    source_manifest: Path
    environments: dict[str, Environment]
    repositories: tuple[Repository, ...]

    def repository(self, slug: str) -> Repository:
        exact = next((repo for repo in self.repositories if repo.slug == slug), None)
        if exact:
            return exact
        matches = [
            repo for repo in self.repositories if repo.slug.lower() == slug.lower()
        ]
        if len(matches) == 1:
            return matches[0]
        raise CatalogError(f"unknown repository: {slug}")


REPOSITORY_REQUIRED_FIELDS = {
    "slug",
    "display_name",
    "source_url",
    "notes",
    "qsc_project",
    "package_role",
    "capabilities",
    "hardware_targets",
    "interfaces",
    "environment",
    "container_status",
    "visibility",
    "canonical_status",
}


def default_catalog_path() -> Path:
    """Return the catalog beside the source tree."""
    source_catalog = Path(__file__).resolve().parents[2] / "ecosystem.yaml"
    if source_catalog.is_file():
        return source_catalog
    from .local_assets import asset_path

    return asset_path("catalog")


def _resolve_path(base: Path, value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else (base / path).resolve()


def _string_list(item: dict[str, Any], field: str, slug: str) -> tuple[str, ...]:
    value = item[field]
    if not isinstance(value, list) or any(
        not isinstance(entry, str) for entry in value
    ):
        raise CatalogError(f"repository {slug}: {field} must be a list of strings")
    return tuple(value)


def _validate_vocab(
    slug: str, field: str, values: tuple[str, ...], allowed: set[str]
) -> None:
    invalid = sorted(set(values) - allowed)
    if invalid:
        raise CatalogError(f"repository {slug}: invalid {field}: {', '.join(invalid)}")


def load_catalog(path: str | Path | None = None) -> Catalog:
    """Load a catalog and reject incomplete or inconsistent metadata."""
    catalog_path = Path(path or default_catalog_path()).expanduser().resolve()
    try:
        raw = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CatalogError(f"catalog not found: {catalog_path}") from exc
    except yaml.YAMLError as exc:
        raise CatalogError(f"invalid YAML in {catalog_path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise CatalogError("catalog root must be a mapping")
    if raw.get("schema_version") != 1:
        raise CatalogError("catalog schema_version must be 1")

    base = catalog_path.parent
    manifest_value = raw.get("source_manifest")
    if not isinstance(manifest_value, str) or not manifest_value:
        raise CatalogError("source_manifest must be a non-empty path")

    raw_environments = raw.get("environments")
    if not isinstance(raw_environments, dict) or not raw_environments:
        raise CatalogError("environments must be a non-empty mapping")
    environments: dict[str, Environment] = {}
    for name, item in raw_environments.items():
        if not isinstance(name, str) or not isinstance(item, dict):
            raise CatalogError("each environment must be a named mapping")
        recipe = item.get("recipe")
        description = item.get("description")
        if not isinstance(recipe, str) or not isinstance(description, str):
            raise CatalogError(
                f"environment {name}: recipe and description are required"
            )
        environments[name] = Environment(name, _resolve_path(base, recipe), description)

    raw_repositories = raw.get("repositories")
    if not isinstance(raw_repositories, list):
        raise CatalogError("repositories must be a list")

    repositories: list[Repository] = []
    seen: set[str] = set()
    for item in raw_repositories:
        if not isinstance(item, dict):
            raise CatalogError("each repository must be a mapping")
        missing = sorted(REPOSITORY_REQUIRED_FIELDS - item.keys())
        slug = item.get("slug", "<unknown>")
        if missing:
            raise CatalogError(
                f"repository {slug}: missing fields: {', '.join(missing)}"
            )
        if not isinstance(slug, str) or not slug:
            raise CatalogError("repository slug must be a non-empty string")
        if slug in seen:
            raise CatalogError(f"duplicate repository slug: {slug}")
        seen.add(slug)

        strings = (
            "display_name",
            "notes",
            "qsc_project",
            "package_role",
            "environment",
            "container_status",
            "visibility",
            "canonical_status",
        )
        for field in strings:
            if not isinstance(item[field], str) or not item[field]:
                raise CatalogError(
                    f"repository {slug}: {field} must be a non-empty string"
                )
        if item["source_url"] is not None and not isinstance(item["source_url"], str):
            raise CatalogError(
                f"repository {slug}: source_url must be a string or null"
            )

        capabilities = _string_list(item, "capabilities", slug)
        hardware_targets = _string_list(item, "hardware_targets", slug)
        interfaces = _string_list(item, "interfaces", slug)
        raw_alternate_sources = item.get("alternate_sources", [])
        if not isinstance(raw_alternate_sources, list) or any(
            not isinstance(value, str) for value in raw_alternate_sources
        ):
            raise CatalogError(
                f"repository {slug}: alternate_sources must contain strings"
            )
        alternate_sources = tuple(raw_alternate_sources)

        if item["environment"] not in environments:
            raise CatalogError(
                f"repository {slug}: unknown environment {item['environment']}"
            )
        if item["package_role"] not in PACKAGE_ROLES:
            raise CatalogError(
                f"repository {slug}: invalid package_role {item['package_role']}"
            )
        if item["container_status"] not in CONTAINER_STATUSES:
            raise CatalogError(
                f"repository {slug}: invalid container_status {item['container_status']}"
            )
        if item["visibility"] not in VISIBILITIES:
            raise CatalogError(
                f"repository {slug}: invalid visibility {item['visibility']}"
            )
        if item["canonical_status"] not in CANONICAL_STATUSES:
            raise CatalogError(
                f"repository {slug}: invalid canonical_status {item['canonical_status']}"
            )
        _validate_vocab(slug, "hardware_targets", hardware_targets, HARDWARE_TARGETS)
        _validate_vocab(slug, "interfaces", interfaces, INTERFACES)
        if item["canonical_status"] == "unresolved" and item["source_url"] is not None:
            raise CatalogError(
                f"repository {slug}: unresolved sources must use a null source_url"
            )

        local_value = item.get("local_path")
        if local_value is not None and not isinstance(local_value, str):
            raise CatalogError(f"repository {slug}: local_path must be a string")
        repositories.append(
            Repository(
                slug=slug,
                display_name=item["display_name"],
                source_url=item["source_url"],
                notes=item["notes"],
                qsc_project=item["qsc_project"],
                package_role=item["package_role"],
                capabilities=capabilities,
                hardware_targets=hardware_targets,
                interfaces=interfaces,
                environment=item["environment"],
                container_status=item["container_status"],
                visibility=item["visibility"],
                canonical_status=item["canonical_status"],
                local_path=_resolve_path(base, local_value) if local_value else None,
                alternate_sources=alternate_sources,
            )
        )

    return Catalog(
        path=catalog_path,
        schema_version=raw["schema_version"],
        source_manifest=_resolve_path(base, manifest_value),
        environments=environments,
        repositories=tuple(repositories),
    )
