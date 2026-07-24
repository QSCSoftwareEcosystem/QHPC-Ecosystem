"""Load pre-runtime integration scaffolds for a deployment profile."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

from .contract import (
    ContractError,
    ContractIssue,
    load_document,
    validate_contract,
    validate_contract_data,
)
from .deployment import load_deployment_profile


class IntegrationError(ContractError):
    """Raised when integration scaffolds and deployment scope disagree."""


@dataclass(frozen=True)
class IntegrationScaffold:
    path: Path
    document: dict[str, Any]

    @property
    def component_id(self) -> str:
        return self.document["metadata"]["id"]


def _normalized_url(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().rstrip("/")
    return normalized[:-4] if normalized.endswith(".git") else normalized


def validate_scaffold_set(
    profile: dict[str, Any], scaffolds: Iterable[IntegrationScaffold]
) -> None:
    """Require one aligned scaffold for every deployment component."""
    by_id: dict[str, IntegrationScaffold] = {}
    issues: list[ContractIssue] = []
    for scaffold in scaffolds:
        component_id = scaffold.component_id
        if component_id in by_id:
            issues.append(
                ContractIssue(
                    "/integrations",
                    f"duplicate integration scaffold ID: {component_id}",
                )
            )
        else:
            by_id[component_id] = scaffold

    expected_ids = {
        component["id"] for component in profile["spec"]["components"]
    }
    missing = sorted(expected_ids - set(by_id))
    if missing:
        issues.append(
            ContractIssue(
                "/integrations",
                "missing integration scaffolds: " + ", ".join(missing),
            )
        )

    for index, component in enumerate(profile["spec"]["components"]):
        scaffold = by_id.get(component["id"])
        if scaffold is None:
            continue
        metadata = scaffold.document["metadata"]
        spec = scaffold.document["spec"]
        path = f"/spec/components/{index}/integration_scaffold"

        for field in ("name", "role"):
            if metadata[field] != component[field]:
                issues.append(
                    ContractIssue(
                        path,
                        f"scaffold {field} does not match component {component['id']}",
                    )
                )

        profile_source = component["source"]
        scaffold_source = spec["source"]
        if scaffold_source["kind"] != profile_source["kind"]:
            issues.append(
                ContractIssue(path, "scaffold source kind does not match the profile")
            )
        elif _normalized_url(scaffold_source.get("url")) != _normalized_url(
            profile_source.get("url")
        ):
            issues.append(
                ContractIssue(path, "scaffold source URL does not match the profile")
            )

        catalog_repository = component.get("catalog_repository")
        if catalog_repository != scaffold_source.get("catalog_repository"):
            issues.append(
                ContractIssue(
                    path,
                    "scaffold catalog repository does not match the profile",
                )
            )

        onboarding_status = component["onboarding_status"]
        integration_status = metadata["integration_status"]
        if onboarding_status == "registry-published" and integration_status != "published":
            issues.append(
                ContractIssue(
                    path,
                    "registry-published components require a published scaffold",
                )
            )
        if onboarding_status == "blocked" and integration_status != "blocked":
            issues.append(
                ContractIssue(path, "blocked components require a blocked scaffold")
            )

    if issues:
        raise IntegrationError(
            "integration scaffolds do not match the deployment profile", issues
        )


def _local_reference(root: Path, reference: str) -> Path | None:
    parsed = urlparse(reference)
    if parsed.scheme or parsed.netloc:
        return None
    path = (root / parsed.path).resolve()
    if not path.is_relative_to(root):
        raise IntegrationError(f"integration reference escapes the workspace: {reference}")
    return path


def validate_scaffold_references(
    scaffolds: Iterable[IntegrationScaffold], workspace_root: str | Path
) -> None:
    """Validate local evidence and contract references declared by scaffolds."""
    root = Path(workspace_root).expanduser().resolve()
    issues: list[ContractIssue] = []
    kind_map = {
        "Capability": "capability",
        "OperationInterface": "operation-interface",
        "ServiceInterface": "service-interface",
    }
    for scaffold in scaffolds:
        spec = scaffold.document["spec"]
        component_id = scaffold.component_id
        for field in ("contract_refs", "evidence"):
            for index, reference in enumerate(spec[field]):
                issue_path = f"/integrations/{component_id}/{field}/{index}"
                try:
                    path = _local_reference(root, reference)
                except IntegrationError as error:
                    issues.append(ContractIssue(issue_path, str(error)))
                    continue
                if path is None:
                    continue
                if not path.is_file():
                    issues.append(
                        ContractIssue(issue_path, f"referenced file not found: {reference}")
                    )
                    continue
                if field == "evidence":
                    continue
                try:
                    document = load_document(path)
                    contract_kind = kind_map.get(document.get("kind"))
                    if contract_kind is None:
                        issues.append(
                            ContractIssue(
                                issue_path,
                                f"unsupported referenced contract kind: {document.get('kind')}",
                            )
                        )
                        continue
                    validate_contract_data(contract_kind, document)
                    if contract_kind in {
                        "operation-interface",
                        "service-interface",
                    } and document["metadata"]["component"] != component_id:
                        issues.append(
                            ContractIssue(
                                issue_path,
                                "interface component does not match its scaffold",
                            )
                        )
                except ContractError as error:
                    issues.append(ContractIssue(issue_path, str(error)))
    if issues:
        raise IntegrationError("invalid integration scaffold references", issues)


def load_integration_scaffolds(
    profile_path: str | Path, workspace_root: str | Path | None = None
) -> tuple[dict[str, Any], tuple[IntegrationScaffold, ...]]:
    """Load and align the scaffold paths declared by a deployment profile."""
    resolved_profile = Path(profile_path).expanduser().resolve()
    profile = load_deployment_profile(resolved_profile)
    root = (
        Path(workspace_root).expanduser().resolve()
        if workspace_root is not None
        else resolved_profile.parent.parent
    )
    records: list[IntegrationScaffold] = []
    for component in profile["spec"]["components"]:
        relative_path = Path(component["integration_scaffold"])
        path = (root / relative_path).resolve()
        if not path.is_relative_to(root):
            raise IntegrationError(
                f"integration scaffold escapes the workspace root: {relative_path}"
            )
        records.append(
            IntegrationScaffold(
                path=path,
                document=validate_contract("integration-scaffold", path),
            )
        )
    validate_scaffold_set(profile, records)
    validate_scaffold_references(records, root)
    return profile, tuple(records)


def find_integration_scaffold(
    scaffolds: Iterable[IntegrationScaffold], component_id: str
) -> IntegrationScaffold:
    for scaffold in scaffolds:
        if scaffold.component_id == component_id:
            return scaffold
    raise IntegrationError(f"integration scaffold not found: {component_id}")
