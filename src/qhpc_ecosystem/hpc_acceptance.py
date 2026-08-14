"""Inspect HPC acceptance readiness for a deployment-scoped component set."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .contract import (
    ContractError,
    ContractIssue,
    load_document,
    validate_contract,
    validate_contract_data,
)
from .integration import load_integration_scaffolds
from .operation_runtime import verify_runtime_definition


class HpcAcceptanceError(ContractError):
    """Raised when an HPC acceptance profile disagrees with repository state."""


@dataclass(frozen=True)
class HpcAcceptanceCase:
    component_id: str
    component_name: str
    classification: str
    status: str
    runtime_id: str | None
    blockers: tuple[str, ...]

    @property
    def required(self) -> bool:
        return self.classification == "batch-operation"

    @property
    def ready(self) -> bool:
        return not self.required or self.status == "target-ready"


@dataclass(frozen=True)
class HpcAcceptanceReport:
    profile_id: str
    profile_version: str
    profile_status: str
    deployment_id: str
    deployment_version: str
    scheduler_fixture_id: str
    scheduler_fixture_status: str
    execution_target_id: str
    execution_target_status: str
    storage_profile_id: str
    storage_profile_status: str
    cases: tuple[HpcAcceptanceCase, ...]
    blockers: tuple[str, ...]

    @property
    def ready(self) -> bool:
        return not self.blockers and all(case.ready for case in self.cases)

    @property
    def batch_cases(self) -> tuple[HpcAcceptanceCase, ...]:
        return tuple(case for case in self.cases if case.required)

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["ready"] = self.ready
        return value


def _workspace_root(profile_path: Path, explicit: str | Path | None) -> Path:
    if explicit is not None:
        root = Path(explicit).expanduser().resolve()
        if not root.is_dir():
            raise HpcAcceptanceError(f"workspace root not found: {root}")
        return root
    for candidate in profile_path.parents:
        if (candidate / "pyproject.toml").is_file() and (
            candidate / "src/qhpc_ecosystem"
        ).is_dir():
            return candidate
    raise HpcAcceptanceError(
        f"cannot locate workspace root for HPC profile: {profile_path}"
    )


def _workspace_path(root: Path, value: str, label: str) -> Path:
    path = (root / value).resolve()
    if path != root and not path.is_relative_to(root):
        raise HpcAcceptanceError(f"{label} escapes workspace root: {value}")
    if not path.is_file():
        raise HpcAcceptanceError(f"{label} not found: {path}")
    return path


def _runtime_status(runtime: dict[str, Any]) -> tuple[str, tuple[str, ...]]:
    metadata_status = runtime["metadata"]["status"]
    release_status = runtime["spec"]["release"]["status"]
    if metadata_status == "target-accepted" and release_status == "target-accepted":
        return "target-ready", ()
    if release_status == "published":
        return (
            "sif-pending",
            (
                "convert and verify the OCI release as a SIF",
                "record target acceptance and execute the contracted fixture",
            ),
        )
    if metadata_status == "oci-smoke-tested":
        return (
            "oci-verified",
            (
                "publish an immutable OCI release with supply-chain evidence",
                "convert and verify an accepted SIF on the target",
                "execute the contracted fixture through the Slurm worker",
            ),
        )
    return (
        "build-ready",
        ("build and pass the contracted network-disabled OCI smoke test",),
    )


def inspect_hpc_acceptance(
    profile: str | Path,
    *,
    workspace_root: str | Path | None = None,
) -> HpcAcceptanceReport:
    profile_path = Path(profile).expanduser().resolve()
    document = load_document(profile_path)
    validate_contract_data("hpc-acceptance", document)
    root = _workspace_root(profile_path, workspace_root)
    spec = document["spec"]

    deployment_path = _workspace_path(
        root, spec["deployment_profile"], "deployment profile"
    )
    deployment, scaffolds = load_integration_scaffolds(deployment_path, root)
    scaffold_by_id = {scaffold.component_id: scaffold for scaffold in scaffolds}
    components = deployment["spec"]["components"]
    component_by_id = {component["id"]: component for component in components}
    cases = spec["cases"]
    issues: list[ContractIssue] = []

    expected_ids = tuple(component["id"] for component in components)
    actual_ids = tuple(case["component"] for case in cases)
    if actual_ids != expected_ids:
        issues.append(
            ContractIssue(
                "/spec/cases",
                "component order and membership must match the deployment profile: "
                + ", ".join(expected_ids),
            )
        )

    allowed_roles = {
        "batch-operation": {"operation-provider"},
        "library-resource": {"operation-provider"},
        "service": {"assistant-service"},
        "integration-standard": {"integration-standard"},
        "knowledge-resource": {"knowledge-resource"},
    }
    results: list[HpcAcceptanceCase] = []
    for index, case in enumerate(cases):
        component_id = case["component"]
        component = component_by_id.get(component_id)
        scaffold = scaffold_by_id.get(component_id)
        path = f"/spec/cases/{index}"
        if component is None or scaffold is None:
            continue
        if component["role"] not in allowed_roles[case["classification"]]:
            issues.append(
                ContractIssue(
                    path + "/classification",
                    f"does not match deployment role {component['role']}",
                )
            )
        if case["integration"] != component["integration_scaffold"]:
            issues.append(
                ContractIssue(
                    path + "/integration",
                    "does not match the deployment integration scaffold",
                )
            )

        runtime_id: str | None = None
        if case["classification"] != "batch-operation":
            results.append(
                HpcAcceptanceCase(
                    component_id=component_id,
                    component_name=component["name"],
                    classification=case["classification"],
                    status="not-applicable",
                    runtime_id=None,
                    blockers=(),
                )
            )
            continue

        runtime_reference = case.get("runtime")
        if runtime_reference is None:
            blockers = tuple(scaffold.document["spec"]["blockers"])
            if not blockers:
                blockers = (case.get("rationale", "operation runtime is pending"),)
            results.append(
                HpcAcceptanceCase(
                    component_id=component_id,
                    component_name=component["name"],
                    classification=case["classification"],
                    status="runtime-pending",
                    runtime_id=None,
                    blockers=blockers,
                )
            )
            continue

        if runtime_reference not in scaffold.document["spec"]["contract_refs"]:
            issues.append(
                ContractIssue(
                    path + "/runtime",
                    "is not declared by the component integration scaffold",
                )
            )
            continue
        runtime_path = _workspace_path(
            root, runtime_reference, f"runtime for {component_id}"
        )
        runtime = verify_runtime_definition(runtime_path, root)
        runtime_id = runtime["metadata"]["id"]
        if runtime["metadata"]["component"] != component_id:
            issues.append(
                ContractIssue(
                    path + "/runtime",
                    "operation runtime component does not match the acceptance case",
                )
            )
            continue
        status, blockers = _runtime_status(runtime)
        results.append(
            HpcAcceptanceCase(
                component_id=component_id,
                component_name=component["name"],
                classification=case["classification"],
                status=status,
                runtime_id=runtime_id,
                blockers=blockers,
            )
        )

    fixture = validate_contract(
        "slurm-test-cluster",
        _workspace_path(root, spec["scheduler_fixture"], "scheduler fixture"),
    )
    if (
        fixture["spec"]["scope"] != "development-only"
        or fixture["spec"]["production_evidence"]
    ):
        issues.append(
            ContractIssue(
                "/spec/scheduler_fixture",
                "must remain development-only and produce no production evidence",
            )
        )
    if fixture["metadata"]["status"] != "validated":
        issues.append(
            ContractIssue(
                "/spec/scheduler_fixture",
                "must reference a validated scheduler fixture",
            )
        )
    target = validate_contract(
        "execution-target",
        _workspace_path(
            root, spec["target"]["execution_target"], "execution target"
        ),
    )
    storage = validate_contract(
        "storage-profile",
        _workspace_path(root, spec["target"]["storage_profile"], "storage profile"),
    )
    requirements = spec["requirements"]
    target_spec = target["spec"]
    if target_spec["runner"] != requirements["scheduler"]:
        issues.append(
            ContractIssue(
                "/spec/target/execution_target",
                "does not provide the required scheduler",
            )
        )
    if requirements["container_runtime"] not in target_spec["container_runtimes"]:
        issues.append(
            ContractIssue(
                "/spec/target/execution_target",
                "does not provide the required container runtime",
            )
        )
    if target_spec["policies"]["network_access"] != requirements["network"]:
        issues.append(
            ContractIssue(
                "/spec/target/execution_target",
                "does not enforce the required network policy",
            )
        )
    if (
        requirements["immutable_images"]
        and not target_spec["policies"]["approved_images_only"]
    ):
        issues.append(
            ContractIssue(
                "/spec/target/execution_target",
                "does not require approved immutable images",
            )
        )
    if target_spec["storage_profile"] != storage["metadata"]["id"]:
        issues.append(
            ContractIssue(
                "/spec/target/storage_profile",
                "does not match the execution target storage reference",
            )
        )
    if storage["spec"]["execution_target"] != target["metadata"]["id"]:
        issues.append(
            ContractIssue(
                "/spec/target/execution_target",
                "does not match the storage profile target reference",
            )
        )

    if issues:
        raise HpcAcceptanceError(
            "HPC acceptance profile does not match repository state", issues
        )

    blockers: list[str] = []
    profile_status = document["metadata"]["status"]
    target_status = target["metadata"]["status"]
    storage_status = storage["metadata"]["status"]
    if profile_status not in {"active", "accepted"}:
        blockers.append(f"HPC acceptance profile is {profile_status}")
    if target_status != "active":
        blockers.append(f"execution target is {target_status}")
    if storage_status != "active":
        blockers.append(f"storage profile is {storage_status}")

    return HpcAcceptanceReport(
        profile_id=document["metadata"]["id"],
        profile_version=document["metadata"]["version"],
        profile_status=profile_status,
        deployment_id=deployment["metadata"]["id"],
        deployment_version=deployment["metadata"]["version"],
        scheduler_fixture_id=fixture["metadata"]["id"],
        scheduler_fixture_status=fixture["metadata"]["status"],
        execution_target_id=target["metadata"]["id"],
        execution_target_status=target_status,
        storage_profile_id=storage["metadata"]["id"],
        storage_profile_status=storage_status,
        cases=tuple(results),
        blockers=tuple(blockers),
    )
