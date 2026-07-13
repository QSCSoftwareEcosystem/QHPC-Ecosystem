"""Build and inspect deterministic registries of attributed capabilities."""

from __future__ import annotations

import os
import re
import tempfile
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable

import yaml

from .catalog import Catalog, Repository
from .contract import (
    ContractError,
    ContractIssue,
    document_digest,
    load_document,
    validate_contract_data,
)


DISCOVERY_FILENAMES = {"qhpc-capability.yaml", "qhpc-capability.yml"}
NESTED_DISCOVERY_FILENAMES = {"capability.yaml", "capability.yml"}
IGNORED_DIRECTORY_NAMES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
}
CATALOG_PROJECT_ALIASES = {
    "data-science": "data-schema",
    "hardware-tools": "hybrid-workflows",
}
PINNED_REVISION = re.compile(
    r"^(?:[0-9a-fA-F]{40,64}|v?(?:0|[1-9][0-9]*)\."
    r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"
    r"(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?)$"
)
SEMVER = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\."
    r"(0|[1-9][0-9]*)(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$"
)


class RegistryError(ContractError):
    """Raised when capability discovery or registry validation fails."""


def _file_digest(path: Path) -> str:
    return "sha256:" + sha256(path.read_bytes()).hexdigest()


def _repository_url(value: str) -> str:
    normalized = value.strip().rstrip("/")
    return normalized[:-4] if normalized.endswith(".git") else normalized


def _version_key(value: str) -> tuple[int, int, int, int, str]:
    match = SEMVER.fullmatch(value)
    if not match:
        return (0, 0, 0, 0, value)
    major, minor, patch, prerelease = match.groups()
    return (
        int(major),
        int(minor),
        int(patch),
        1 if prerelease is None else 0,
        prerelease or "",
    )


def _is_discovery_file(path: Path) -> bool:
    if path.name in DISCOVERY_FILENAMES:
        return True
    return path.parent.name == ".qhpc" and path.name in NESTED_DISCOVERY_FILENAMES


def discover_capability_files(sources: Iterable[str | Path]) -> tuple[Path, ...]:
    """Find descriptors using the project-root and .qhpc conventions."""
    discovered: set[Path] = set()
    for source_value in sources:
        source = Path(source_value).expanduser().resolve()
        if source.is_file():
            discovered.add(source)
            continue
        if not source.is_dir():
            raise RegistryError(f"capability source not found: {source}")
        for candidate in source.rglob("*.y*ml"):
            relative_parts = candidate.relative_to(source).parts
            if any(part in IGNORED_DIRECTORY_NAMES for part in relative_parts):
                continue
            if _is_discovery_file(candidate):
                discovered.add(candidate.resolve())
    if not discovered:
        raise RegistryError(
            "no capability descriptors found; use qhpc-capability.yaml or "
            ".qhpc/capability.yaml"
        )
    return tuple(sorted(discovered, key=str))


def _catalog_repository(
    capability: dict[str, Any], catalog: Catalog, descriptor_path: Path
) -> Repository:
    metadata = capability["metadata"]
    source_url = _repository_url(metadata["repository"]["url"])
    matches = [
        repository
        for repository in catalog.repositories
        if repository.source_url
        and _repository_url(repository.source_url) == source_url
    ]
    issues: list[ContractIssue] = []
    if not matches:
        issues.append(
            ContractIssue(
                "/metadata/repository/url",
                "does not match a repository in ecosystem.yaml",
            )
        )
    elif len(matches) > 1:
        issues.append(
            ContractIssue(
                "/metadata/repository/url",
                "matches more than one repository in ecosystem.yaml",
            )
        )
    if issues:
        raise RegistryError(f"registry ownership failed for {descriptor_path}", issues)

    repository = matches[0]
    expected_project = CATALOG_PROJECT_ALIASES.get(
        repository.qsc_project, repository.qsc_project
    )
    if metadata["project"] != expected_project:
        issues.append(
            ContractIssue(
                "/metadata/project",
                f"must be {expected_project} for catalog repository {repository.slug}",
            )
        )
    if repository.canonical_status != "canonical":
        issues.append(
            ContractIssue(
                "/metadata/repository/url",
                f"catalog repository {repository.slug} is {repository.canonical_status}",
            )
        )
    if repository.visibility == "unknown":
        issues.append(
            ContractIssue(
                "/metadata/visibility",
                f"catalog visibility is unresolved for {repository.slug}",
            )
        )
    if repository.visibility == "internal" and metadata["visibility"] == "public":
        issues.append(
            ContractIssue(
                "/metadata/visibility",
                "an internal repository cannot publish a public capability",
            )
        )
    revision = metadata["repository"]["revision"]
    if not PINNED_REVISION.fullmatch(revision):
        issues.append(
            ContractIssue(
                "/metadata/repository/revision",
                "must be a full commit hash or semantic release tag",
            )
        )
    qappswiki = capability["spec"].get("documentation", {}).get("qappswiki")
    if not qappswiki:
        issues.append(
            ContractIssue(
                "/spec/documentation/qappswiki",
                "is required for registry publication",
            )
        )
    if issues:
        raise RegistryError(f"registry ownership failed for {descriptor_path}", issues)
    return repository


def build_registry(sources: Iterable[str | Path], catalog: Catalog) -> dict[str, Any]:
    """Build a deterministic registry from local project release directories."""
    entries: list[dict[str, Any]] = []
    for descriptor_path in discover_capability_files(sources):
        capability = load_document(descriptor_path)
        try:
            validate_contract_data("capability", capability)
        except ContractError as exc:
            raise RegistryError(
                f"invalid capability descriptor: {descriptor_path}", exc.issues
            ) from exc
        repository = _catalog_repository(capability, catalog, descriptor_path)
        integration = capability["metadata"]["integration"]
        entries.append(
            {
                "descriptor_digest": document_digest(capability),
                "catalog_repository": repository.slug,
                "validation": {
                    "contract": "valid",
                    "attribution": "valid",
                    "authority": integration["authority"],
                    "curated_by": integration["maintainers"],
                    "project_reviewed": integration["project_reviewed"],
                    "runtime": integration["runtime_status"],
                    "documentation": "linked",
                    "status": integration["validation_status"],
                    "evidence": integration.get("evidence", []),
                },
                "capability": capability,
            }
        )

    entries.sort(
        key=lambda entry: (
            entry["capability"]["metadata"]["id"],
            _version_key(entry["capability"]["metadata"]["version"]),
        )
    )
    registry = {
        "api_version": "qhpc/v1",
        "kind": "Registry",
        "metadata": {
            "entry_count": len(entries),
            "catalog_digest": _file_digest(catalog.path),
        },
        "spec": {"entries": entries},
    }
    try:
        validate_contract_data("registry", registry)
    except ContractError as exc:
        raise RegistryError("generated registry is invalid", exc.issues) from exc
    return registry


def validate_registry_catalog(registry: dict[str, Any], catalog: Catalog) -> None:
    issues: list[ContractIssue] = []
    if registry["metadata"]["catalog_digest"] != _file_digest(catalog.path):
        issues.append(
            ContractIssue(
                "/metadata/catalog_digest",
                "does not match the current ecosystem catalog",
            )
        )
    for index, entry in enumerate(registry["spec"]["entries"]):
        try:
            repository = _catalog_repository(
                entry["capability"], catalog, Path(f"registry-entry-{index}")
            )
        except RegistryError as error:
            for issue in error.issues:
                issues.append(
                    ContractIssue(
                        f"/spec/entries/{index}/capability{issue.path}", issue.message
                    )
                )
            continue
        if entry["catalog_repository"] != repository.slug:
            issues.append(
                ContractIssue(
                    f"/spec/entries/{index}/catalog_repository",
                    f"must be {repository.slug}",
                )
            )
    if issues:
        raise RegistryError("registry does not match the current catalog", issues)


def load_registry(path: str | Path, catalog: Catalog | None = None) -> dict[str, Any]:
    registry = load_document(path)
    validate_contract_data("registry", registry)
    if catalog:
        validate_registry_catalog(registry, catalog)
    return registry


def write_registry(path: str | Path, registry: dict[str, Any]) -> Path:
    """Write a registry atomically using stable YAML field ordering."""
    destination = Path(path).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    serialized = yaml.safe_dump(
        registry,
        allow_unicode=False,
        sort_keys=False,
        width=100,
    )
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=destination.parent,
        prefix=destination.name + ".",
        suffix=".tmp",
        delete=False,
    ) as stream:
        stream.write(serialized)
        temporary = Path(stream.name)
    try:
        os.replace(temporary, destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return destination


def registry_digest(registry: dict[str, Any]) -> str:
    return document_digest(registry)


def registry_entries(registry: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    return tuple(registry["spec"]["entries"])


def find_registry_entry(
    registry: dict[str, Any], capability_id: str, version: str | None = None
) -> dict[str, Any]:
    matches = [
        entry
        for entry in registry_entries(registry)
        if entry["capability"]["metadata"]["id"] == capability_id
        and (version is None or entry["capability"]["metadata"]["version"] == version)
    ]
    if not matches:
        suffix = f" version {version}" if version else ""
        raise RegistryError(f"capability not found: {capability_id}{suffix}")
    return max(
        matches,
        key=lambda entry: _version_key(entry["capability"]["metadata"]["version"]),
    )
