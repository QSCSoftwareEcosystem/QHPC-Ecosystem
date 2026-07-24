"""Load deployment scope and derive an executable registry view."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from .catalog import Catalog
from .contract import (
    ContractError,
    ContractIssue,
    load_document,
    validate_contract_data,
)


class DeploymentError(ContractError):
    """Raised when a deployment profile cannot be applied safely."""


def _normalized_url(value: str) -> str:
    normalized = value.strip().rstrip("/")
    return normalized[:-4] if normalized.endswith(".git") else normalized


def validate_deployment_catalog(
    profile: dict[str, Any], catalog: Catalog
) -> None:
    """Require profile repository references to match the current catalog."""
    repositories = {repository.slug: repository for repository in catalog.repositories}
    issues: list[ContractIssue] = []
    for index, component in enumerate(profile["spec"]["components"]):
        slug = component.get("catalog_repository")
        if slug is None:
            continue
        path = f"/spec/components/{index}/catalog_repository"
        repository = repositories.get(slug)
        if repository is None:
            issues.append(ContractIssue(path, f"unknown catalog repository: {slug}"))
            continue
        source = component["source"]
        if source["kind"] != "repository":
            issues.append(
                ContractIssue(path, "requires a repository source in the profile")
            )
            continue
        if repository.source_url is None:
            issues.append(ContractIssue(path, "catalog repository source is unresolved"))
        elif _normalized_url(repository.source_url) != _normalized_url(source["url"]):
            issues.append(
                ContractIssue(
                    f"/spec/components/{index}/source/url",
                    f"does not match catalog repository {slug}",
                )
            )
    if issues:
        raise DeploymentError("deployment profile does not match the catalog", issues)


def load_deployment_profile(
    path: str | Path, catalog: Catalog | None = None
) -> dict[str, Any]:
    profile = load_document(path)
    validate_contract_data("deployment-profile", profile)
    if catalog is not None:
        validate_deployment_catalog(profile, catalog)
    return profile


def deployment_catalog_repositories(profile: dict[str, Any]) -> frozenset[str]:
    """Return non-blocked catalog repositories selected by the allowlist."""
    validate_contract_data("deployment-profile", profile)
    return frozenset(
        component["catalog_repository"]
        for component in profile["spec"]["components"]
        if component["onboarding_status"] != "blocked"
        and "catalog_repository" in component
    )


def registry_for_deployment(
    registry: dict[str, Any], profile: dict[str, Any]
) -> dict[str, Any]:
    """Create a validated registry snapshot restricted to the profile allowlist."""
    validate_contract_data("registry", registry)
    allowed = deployment_catalog_repositories(profile)
    selected = [
        deepcopy(entry)
        for entry in registry["spec"]["entries"]
        if entry["catalog_repository"] in allowed
    ]
    if not selected:
        raise DeploymentError(
            "deployment profile selects no published registry capabilities"
        )
    filtered = deepcopy(registry)
    filtered["metadata"]["entry_count"] = len(selected)
    filtered["spec"]["entries"] = selected
    validate_contract_data("registry", filtered)
    return filtered
