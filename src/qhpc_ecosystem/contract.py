"""Load and validate versioned QHPC integration contracts."""

from __future__ import annotations

import json
from hashlib import sha256
from collections import Counter, deque
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

import yaml
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError


CONTRACT_SCHEMAS = {
    "artifact": "artifact-v1.schema.json",
    "artifact-type": "artifact-type-v1.schema.json",
    "capability": "capability-v1.schema.json",
    "deployment-profile": "deployment-profile-v1.schema.json",
    "execution-target": "execution-target-v1.schema.json",
    "hpc-acceptance": "hpc-acceptance-v1.schema.json",
    "integration-scaffold": "integration-scaffold-v1.schema.json",
    "operation-interface": "operation-interface-v1.schema.json",
    "operation-runtime": "operation-runtime-v1.schema.json",
    "pilot-profile": "pilot-profile-v1.schema.json",
    "registry": "registry-v1.schema.json",
    "run": "run-v1.schema.json",
    "service-interface": "service-interface-v1.schema.json",
    "slurm-test-cluster": "slurm-test-cluster-v1.schema.json",
    "storage-profile": "storage-profile-v1.schema.json",
    "workflow": "workflow-v1.schema.json",
    "workflow-draft": "workflow-draft-v1.schema.json",
}


@dataclass(frozen=True)
class ContractIssue:
    path: str
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"


class ContractError(ValueError):
    """Raised when a contract file or document is invalid."""

    def __init__(self, message: str, issues: Iterable[ContractIssue] = ()) -> None:
        self.issues = tuple(issues)
        detail = "\n".join(f"  - {issue}" for issue in self.issues)
        super().__init__(f"{message}\n{detail}" if detail else message)


def contract_kinds() -> tuple[str, ...]:
    return tuple(sorted(CONTRACT_SCHEMAS))


def normalize_kind(kind: str) -> str:
    normalized = kind.strip().lower().replace("_", "-")
    if normalized not in CONTRACT_SCHEMAS:
        choices = ", ".join(contract_kinds())
        raise ContractError(f"unknown contract kind: {kind}; choose one of: {choices}")
    return normalized


def load_schema(kind: str) -> dict[str, Any]:
    normalized = normalize_kind(kind)
    resource = files("qhpc_ecosystem").joinpath(
        "contracts", CONTRACT_SCHEMAS[normalized]
    )
    try:
        with resource.open("r", encoding="utf-8") as stream:
            schema = json.load(stream)
        Draft202012Validator.check_schema(schema)
    except (OSError, json.JSONDecodeError, SchemaError) as exc:
        raise ContractError(f"invalid packaged schema for {normalized}: {exc}") from exc
    return schema


def load_document(path: str | Path) -> dict[str, Any]:
    document_path = Path(path).expanduser().resolve()
    try:
        document = yaml.safe_load(document_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ContractError(f"contract document not found: {document_path}") from exc
    except yaml.YAMLError as exc:
        raise ContractError(f"invalid YAML in {document_path}: {exc}") from exc
    if not isinstance(document, dict):
        raise ContractError(f"contract document must be a mapping: {document_path}")
    return document


def document_digest(document: dict[str, Any]) -> str:
    payload = json.dumps(
        document,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return "sha256:" + sha256(payload).hexdigest()


def _json_path(parts: Iterable[object]) -> str:
    encoded = [str(part).replace("~", "~0").replace("/", "~1") for part in parts]
    return "/" + "/".join(encoded) if encoded else "/"


def _duplicate_issues(
    values: Iterable[str], path: str, description: str
) -> list[ContractIssue]:
    duplicates = sorted(value for value, count in Counter(values).items() if count > 1)
    if not duplicates:
        return []
    return [ContractIssue(path, f"duplicate {description}: {', '.join(duplicates)}")]


def _registry_key(value: str) -> tuple[str, int, int, int, int, str]:
    capability_id, version = value.rsplit("@", 1)
    core = version.split("+", 1)[0]
    numeric, separator, prerelease = core.partition("-")
    try:
        major, minor, patch = (int(part) for part in numeric.split("."))
    except (TypeError, ValueError):
        return (capability_id, 0, 0, 0, 0, version)
    return (
        capability_id,
        major,
        minor,
        patch,
        1 if not separator else 0,
        prerelease,
    )


def _validate_parameter_defaults(document: dict[str, Any]) -> list[ContractIssue]:
    issues: list[ContractIssue] = []
    python_types = {
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
    }
    operations = document["spec"].get("operations", [])
    for operation_index, operation in enumerate(operations):
        for name, parameter in operation.get("parameters", {}).items():
            path = f"/spec/operations/{operation_index}/parameters/{name}"
            if "default" in parameter:
                expected = python_types[parameter["type"]]
                value = parameter["default"]
                valid = isinstance(value, expected)
                if parameter["type"] in {"integer", "number"} and isinstance(
                    value, bool
                ):
                    valid = False
                if not valid:
                    issues.append(
                        ContractIssue(
                            path + "/default", "does not match parameter type"
                        )
                    )
                if "enum" in parameter and value not in parameter["enum"]:
                    issues.append(
                        ContractIssue(path + "/default", "is not present in enum")
                    )
            if (
                "minimum" in parameter
                and "maximum" in parameter
                and parameter["minimum"] > parameter["maximum"]
            ):
                issues.append(
                    ContractIssue(path, "minimum must not be greater than maximum")
                )
    return issues


def _validate_capability(document: dict[str, Any]) -> list[ContractIssue]:
    issues: list[ContractIssue] = []
    metadata = document["metadata"]
    integration = metadata["integration"]
    if integration["authority"] == "project" and not integration["project_reviewed"]:
        issues.append(
            ContractIssue(
                "/metadata/integration/project_reviewed",
                "must be true when integration authority is project",
            )
        )
    evidenced_statuses = {
        "smoke-tested",
        "integration-tested",
        "production-approved",
    }
    if integration["validation_status"] in evidenced_statuses and not integration.get(
        "evidence"
    ):
        issues.append(
            ContractIssue(
                "/metadata/integration/evidence",
                "is required for smoke-tested or higher validation status",
            )
        )
    if metadata.get("deprecated") and not metadata.get("replaced_by"):
        issues.append(
            ContractIssue(
                "/metadata/replaced_by",
                "is required when a capability is deprecated",
            )
        )

    operations = document["spec"].get("operations", [])
    runtime_status = integration["runtime_status"]
    if operations and runtime_status == "not-applicable":
        issues.append(
            ContractIssue(
                "/metadata/integration/runtime_status",
                "cannot be not-applicable when operations are published",
            )
        )
    if not operations and runtime_status != "not-applicable":
        issues.append(
            ContractIssue(
                "/metadata/integration/runtime_status",
                "must be not-applicable when no operations are published",
            )
        )
    if (
        integration["validation_status"] == "production-approved"
        and operations
        and runtime_status != "verified"
    ):
        issues.append(
            ContractIssue(
                "/metadata/integration/runtime_status",
                "must be verified for production-approved operations",
            )
        )
    issues.extend(
        _duplicate_issues(
            (operation["id"] for operation in operations),
            "/spec/operations",
            "operation IDs",
        )
    )
    resources = document["spec"].get("resources", [])
    issues.extend(
        _duplicate_issues(
            (resource["id"] for resource in resources),
            "/spec/resources",
            "resource IDs",
        )
    )

    for index, operation in enumerate(operations):
        runtime = operation["runtime"]
        reference = runtime["reference"]
        digest = runtime["digest"]
        path = f"/spec/operations/{index}/runtime/reference"
        if runtime["type"] == "oci" and not reference.endswith("@" + digest):
            issues.append(
                ContractIssue(path, "OCI references must end with the declared digest")
            )
        if runtime["type"] == "apptainer" and not (
            reference.startswith("/")
            or reference.startswith("file://")
            or reference.startswith("oras://")
        ):
            issues.append(
                ContractIssue(
                    path,
                    "Apptainer references must be absolute paths, file:// URIs, or oras:// URIs",
                )
            )
        if runtime["type"] == "python-wheel" and not reference.startswith(
            "qhpc-runtime://wheels/"
        ):
            issues.append(
                ContractIssue(
                    path,
                    "Python wheel references must use qhpc-runtime://wheels/",
                )
            )
        if runtime["type"] == "native-bundle" and not reference.startswith(
            "qhpc-runtime://native/"
        ):
            issues.append(
                ContractIssue(
                    path,
                    "Native bundle references must use qhpc-runtime://native/",
                )
            )
        if ":latest" in reference:
            issues.append(
                ContractIssue(path, "mutable ':latest' references are forbidden")
            )
    issues.extend(_validate_parameter_defaults(document))
    return issues


def _validate_workflow(document: dict[str, Any]) -> list[ContractIssue]:
    issues: list[ContractIssue] = []
    spec = document["spec"]
    node_ids = [node["id"] for node in spec["nodes"]]
    issues.extend(_duplicate_issues(node_ids, "/spec/nodes", "node IDs"))
    known = set(node_ids)

    adjacency = {node_id: set() for node_id in known}
    indegree = {node_id: 0 for node_id in known}
    for index, edge in enumerate(spec["edges"]):
        source = edge["from"]
        target = edge["to"]
        path = f"/spec/edges/{index}"
        for endpoint_name, endpoint in (("from", source), ("to", target)):
            if endpoint["node"] not in known:
                issues.append(
                    ContractIssue(
                        f"{path}/{endpoint_name}/node",
                        f"references unknown node {endpoint['node']}",
                    )
                )
        if source["artifact_type"] != target["artifact_type"]:
            issues.append(ContractIssue(path, "edge artifact types must match exactly"))
        if source["node"] == target["node"]:
            issues.append(ContractIssue(path, "self-edges are not allowed"))
        elif source["node"] in known and target["node"] in known:
            if target["node"] not in adjacency[source["node"]]:
                adjacency[source["node"]].add(target["node"])
                indegree[target["node"]] += 1

    for name, workflow_input in spec["inputs"].items():
        if workflow_input["to"]["node"] not in known:
            issues.append(
                ContractIssue(
                    f"/spec/inputs/{name}/to/node",
                    f"references unknown node {workflow_input['to']['node']}",
                )
            )
    for name, workflow_output in spec["outputs"].items():
        if workflow_output["from"]["node"] not in known:
            issues.append(
                ContractIssue(
                    f"/spec/outputs/{name}/from/node",
                    f"references unknown node {workflow_output['from']['node']}",
                )
            )

    if len(known) == len(node_ids):
        ready = deque(node_id for node_id, degree in indegree.items() if degree == 0)
        visited = 0
        while ready:
            node_id = ready.popleft()
            visited += 1
            for target in adjacency[node_id]:
                indegree[target] -= 1
                if indegree[target] == 0:
                    ready.append(target)
        if visited != len(known):
            issues.append(
                ContractIssue("/spec/edges", "workflow graph must be acyclic")
            )
    return issues


def _validate_workflow_draft(document: dict[str, Any]) -> list[ContractIssue]:
    layout_ids = [node["id"] for node in document["spec"]["layout"]["nodes"]]
    return _duplicate_issues(
        layout_ids,
        "/spec/layout/nodes",
        "canvas node IDs",
    )


def _validate_run(document: dict[str, Any]) -> list[ContractIssue]:
    return _duplicate_issues(
        (task["node_id"] for task in document["spec"]["tasks"]),
        "/spec/tasks",
        "task node IDs",
    )


def _validate_execution_target(document: dict[str, Any]) -> list[ContractIssue]:
    metadata = document["metadata"]
    spec = document["spec"]
    if spec["runner"] != "slurm" or metadata["status"] != "active":
        return []
    issues: list[ContractIssue] = []
    scheduler = spec["scheduler"]
    if "account" not in scheduler:
        issues.append(
            ContractIssue(
                "/spec/scheduler/account",
                "is required before a Slurm target can be active",
            )
        )
    required_limits = {
        "max_cpu",
        "max_memory_mb",
        "max_gpu",
        "max_walltime_seconds",
    }
    missing_limits = sorted(required_limits - set(spec["resource_limits"]))
    for field in missing_limits:
        issues.append(
            ContractIssue(
                f"/spec/resource_limits/{field}",
                "is required before a Slurm target can be active",
            )
        )
    if not metadata.get("evidence"):
        issues.append(
            ContractIssue(
                "/metadata/evidence",
                "is required before a Slurm target can be active",
            )
        )
    return issues


def _validate_registry(document: dict[str, Any]) -> list[ContractIssue]:
    issues: list[ContractIssue] = []
    entries = document["spec"]["entries"]
    if document["metadata"]["entry_count"] != len(entries):
        issues.append(
            ContractIssue(
                "/metadata/entry_count",
                "must equal the number of registry entries",
            )
        )

    keys: list[str] = []
    projects_by_id: dict[str, str] = {}
    for index, entry in enumerate(entries):
        capability = entry["capability"]
        path = f"/spec/entries/{index}"
        try:
            validate_contract_data("capability", capability)
        except ContractError as error:
            for issue in error.issues:
                suffix = "" if issue.path == "/" else issue.path
                issues.append(
                    ContractIssue(path + "/capability" + suffix, issue.message)
                )
        expected_digest = document_digest(capability)
        if entry["descriptor_digest"] != expected_digest:
            issues.append(
                ContractIssue(
                    path + "/descriptor_digest",
                    "does not match the embedded capability",
                )
            )

        metadata = capability.get("metadata", {})
        capability_id = metadata.get("id")
        version = metadata.get("version")
        project = metadata.get("project")
        if isinstance(capability_id, str) and isinstance(version, str):
            keys.append(f"{capability_id}@{version}")
        if isinstance(capability_id, str) and isinstance(project, str):
            previous = projects_by_id.setdefault(capability_id, project)
            if previous != project:
                issues.append(
                    ContractIssue(
                        path + "/capability/metadata/project",
                        f"capability {capability_id} changes ownership from {previous} to {project}",
                    )
                )

    issues.extend(_duplicate_issues(keys, "/spec/entries", "capability versions"))
    if keys != sorted(keys, key=_registry_key):
        issues.append(
            ContractIssue(
                "/spec/entries",
                "entries must be sorted by capability ID and version",
            )
        )
    return issues


def _validate_deployment_profile(document: dict[str, Any]) -> list[ContractIssue]:
    components = document["spec"]["components"]
    issues = _duplicate_issues(
        (component["id"] for component in components),
        "/spec/components",
        "component IDs",
    )
    issues.extend(
        _duplicate_issues(
            (
                component["catalog_repository"]
                for component in components
                if "catalog_repository" in component
            ),
            "/spec/components",
            "catalog repositories",
        )
    )
    issues.extend(
        _duplicate_issues(
            (component["integration_scaffold"] for component in components),
            "/spec/components",
            "integration scaffold paths",
        )
    )
    return issues


def _validate_integration_scaffold(
    document: dict[str, Any],
) -> list[ContractIssue]:
    issues: list[ContractIssue] = []
    metadata = document["metadata"]
    spec = document["spec"]
    source = spec["source"]
    mirror = spec["mirror"]
    environment = spec["development_environment"]
    scope = spec["scope"]
    deliverables = spec["deliverables"]
    runtime = spec["production_runtime"]
    blockers = spec["blockers"]

    if mirror["status"] in {"inventory-listed", "verified"} and not mirror.get("url"):
        issues.append(
            ContractIssue(
                "/spec/mirror/url",
                "is required when the mirror is inventory-listed or verified",
            )
        )
    if mirror["status"] not in {"inventory-listed", "verified"} and mirror.get("url"):
        issues.append(
            ContractIssue(
                "/spec/mirror/url",
                "is only allowed for an inventory-listed or verified mirror",
            )
        )

    if environment["status"] == "assigned" and not environment.get("class"):
        issues.append(
            ContractIssue(
                "/spec/development_environment/class",
                "is required when a development environment is assigned",
            )
        )
    if environment["status"] != "assigned" and environment.get("class"):
        issues.append(
            ContractIssue(
                "/spec/development_environment/class",
                "is only allowed for an assigned development environment",
            )
        )

    if runtime["status"] in {"deferred", "verified"} and not runtime.get("technology"):
        issues.append(
            ContractIssue(
                "/spec/production_runtime/technology",
                "is required for a deferred or verified production runtime",
            )
        )
    if runtime["status"] == "not-applicable" and runtime.get("technology"):
        issues.append(
            ContractIssue(
                "/spec/production_runtime/technology",
                "must be omitted when a production runtime is not applicable",
            )
        )

    if source["kind"] == "unresolved":
        if scope["status"] != "blocked":
            issues.append(
                ContractIssue(
                    "/spec/scope/status",
                    "must be blocked while the source is unresolved",
                )
            )
        if deliverables["source_audit"] != "blocked":
            issues.append(
                ContractIssue(
                    "/spec/deliverables/source_audit",
                    "must be blocked while the source is unresolved",
                )
            )

    if metadata["integration_status"] == "blocked" and not blockers:
        issues.append(
            ContractIssue(
                "/spec/blockers",
                "must identify at least one blocker for a blocked integration",
            )
        )
    if "blocked" in deliverables.values() and not blockers:
        issues.append(
            ContractIssue(
                "/spec/blockers",
                "must identify blockers when a deliverable is blocked",
            )
        )

    publication = deliverables["registry_publication"]
    if metadata["integration_status"] == "published" and publication != "complete":
        issues.append(
            ContractIssue(
                "/spec/deliverables/registry_publication",
                "must be complete for a published integration",
            )
        )
    if publication == "complete":
        for field in ("source_audit", "interface_contract"):
            if deliverables[field] != "complete":
                issues.append(
                    ContractIssue(
                        f"/spec/deliverables/{field}",
                        "must be complete before registry publication",
                    )
                )
    if deliverables["source_audit"] == "complete" and not spec["evidence"]:
        issues.append(
            ContractIssue(
                "/spec/evidence",
                "is required when the source audit is complete",
            )
        )
    if deliverables["interface_contract"] == "complete" and not spec["contract_refs"]:
        issues.append(
            ContractIssue(
                "/spec/contract_refs",
                "is required when the interface contract is complete",
            )
        )
    return issues


def _validate_operation_interface(document: dict[str, Any]) -> list[ContractIssue]:
    issues: list[ContractIssue] = []
    metadata = document["metadata"]
    if (
        metadata["status"] in {"contract-valid", "project-reviewed"}
        and not metadata["evidence"]
    ):
        issues.append(
            ContractIssue(
                "/metadata/evidence",
                "is required for a contract-valid or project-reviewed interface",
            )
        )
    operations = document["spec"]["operations"]
    issues.extend(
        _duplicate_issues(
            (operation["id"] for operation in operations),
            "/spec/operations",
            "operation IDs",
        )
    )
    issues.extend(_validate_parameter_defaults(document))
    return issues


def _validate_hpc_acceptance(document: dict[str, Any]) -> list[ContractIssue]:
    issues: list[ContractIssue] = []
    metadata = document["metadata"]
    spec = document["spec"]
    cases = spec["cases"]
    issues.extend(
        _duplicate_issues(
            (case["component"] for case in cases),
            "/spec/cases",
            "component IDs",
        )
    )

    relative_paths = [
        ("/spec/deployment_profile", spec["deployment_profile"]),
        ("/spec/scheduler_fixture", spec["scheduler_fixture"]),
        ("/spec/target/execution_target", spec["target"]["execution_target"]),
        ("/spec/target/storage_profile", spec["target"]["storage_profile"]),
        *[
            (f"/spec/cases/{index}/integration", case["integration"])
            for index, case in enumerate(cases)
        ],
        *[
            (f"/spec/cases/{index}/runtime", case["runtime"])
            for index, case in enumerate(cases)
            if "runtime" in case
        ],
    ]
    for path, value in relative_paths:
        parsed = PurePosixPath(value)
        if parsed.is_absolute() or ".." in parsed.parts:
            issues.append(
                ContractIssue(path, "must be a workspace-relative path without '..'")
            )

    for index, case in enumerate(cases):
        path = f"/spec/cases/{index}"
        is_batch = case["classification"] == "batch-operation"
        if is_batch and case["acceptance"] != "required":
            issues.append(
                ContractIssue(
                    path + "/acceptance",
                    "batch operations require HPC acceptance",
                )
            )
        if not is_batch and case["acceptance"] != "not-applicable":
            issues.append(
                ContractIssue(
                    path + "/acceptance",
                    "non-batch components cannot require Slurm acceptance",
                )
            )
        if not is_batch and "runtime" in case:
            issues.append(
                ContractIssue(
                    path + "/runtime",
                    "non-batch components cannot declare an operation runtime",
                )
            )
        if not is_batch and "rationale" not in case:
            issues.append(
                ContractIssue(
                    path + "/rationale",
                    "is required for a non-batch component",
                )
            )

    if metadata["status"] in {"active", "accepted"} and not metadata["evidence"]:
        issues.append(
            ContractIssue(
                "/metadata/evidence",
                "is required for an active or accepted HPC profile",
            )
        )
    if metadata["status"] == "accepted":
        missing = [
            case["component"]
            for case in cases
            if case["classification"] == "batch-operation"
            and "runtime" not in case
        ]
        if missing:
            issues.append(
                ContractIssue(
                    "/spec/cases",
                    "accepted profile has batch components without runtimes: "
                    + ", ".join(missing),
                )
            )
    return issues


def _validate_operation_runtime(document: dict[str, Any]) -> list[ContractIssue]:
    issues: list[ContractIssue] = []
    metadata = document["metadata"]
    build = document["spec"]["build"]
    execution = document["spec"]["execution"]
    release = document["spec"]["release"]

    for name in ("builder", "runtime_base"):
        image = build[name]
        reference = image["reference"]
        digest = image["digest"]
        path = f"/spec/build/{name}/reference"
        if not reference.endswith("@" + digest):
            issues.append(
                ContractIssue(path, "base image reference must end with its digest")
            )
        if ":latest" in reference:
            issues.append(
                ContractIssue(path, "mutable ':latest' references are forbidden")
            )

    file_paths = [
        ("/spec/build/recipe/path", build["recipe"]["path"]),
        *[
            (f"/spec/build/context_files/{index}/source", item["source"])
            for index, item in enumerate(build["context_files"])
        ],
    ]
    verification = document["spec"]["verification"]
    if "fixture" in verification:
        file_paths.append(
            (
                "/spec/verification/fixture/path",
                verification["fixture"]["path"],
            )
        )
    for path, value in file_paths:
        candidate = Path(value)
        if candidate.is_absolute() or ".." in candidate.parts:
            issues.append(
                ContractIssue(path, "must be a workspace-relative path without '..'")
            )

    destinations = [item["destination"] for item in build["context_files"]]
    dependency_names = [
        item["filename"] for item in build.get("dependency_archives", [])
    ]
    issues.extend(
        _duplicate_issues(
            destinations,
            "/spec/build/context_files",
            "context destinations",
        )
    )
    for index, destination in enumerate(destinations):
        generated_names = {
            "Containerfile",
            "qhpc-build.json",
            build["source_archive"]["filename"],
            *dependency_names,
        }
        if destination in generated_names:
            issues.append(
                ContractIssue(
                    f"/spec/build/context_files/{index}/destination",
                    "conflicts with a generated build-context file",
                )
            )
    issues.extend(
        _duplicate_issues(
            dependency_names,
            "/spec/build/dependency_archives",
            "dependency archive filenames",
        )
    )
    generated_names = {
        "Containerfile",
        "qhpc-build.json",
        build["source_archive"]["filename"],
    }
    for index, filename in enumerate(dependency_names):
        if filename in generated_names:
            issues.append(
                ContractIssue(
                    f"/spec/build/dependency_archives/{index}/filename",
                    "conflicts with a generated build-context file",
                )
            )
        if Path(filename).name != filename:
            issues.append(
                ContractIssue(
                    f"/spec/build/dependency_archives/{index}/filename",
                    "must be a top-level build-context filename",
                )
            )

    mounts = execution["mounts"]
    issues.extend(
        _duplicate_issues(
            (mount["name"] for mount in mounts),
            "/spec/execution/mounts",
            "mount names",
        )
    )
    issues.extend(
        _duplicate_issues(
            (mount["path"] for mount in mounts),
            "/spec/execution/mounts",
            "mount paths",
        )
    )
    issues.extend(
        _duplicate_issues(
            (mount["kind"] for mount in mounts),
            "/spec/execution/mounts",
            "mount kinds",
        )
    )
    for index, mount in enumerate(mounts):
        expected_mode = "ro" if mount["kind"] == "input" else "rw"
        if mount["mode"] != expected_mode:
            issues.append(
                ContractIssue(
                    f"/spec/execution/mounts/{index}/mode",
                    f"{mount['kind']} mounts must be {expected_mode}",
                )
            )

    container_paths = [
        ("/spec/execution/entrypoint/0", execution["entrypoint"][0]),
        ("/spec/execution/working_directory", execution["working_directory"]),
    ]
    if "fixture" in verification:
        container_paths.append(
            (
                "/spec/verification/fixture/mount_path",
                verification["fixture"]["mount_path"],
            )
        )
    container_paths.extend(
        (f"/spec/execution/mounts/{index}/path", mount["path"])
        for index, mount in enumerate(mounts)
    )
    for direction, ports in execution["ports"].items():
        container_paths.extend(
            (
                f"/spec/execution/ports/{direction}/{name}",
                value,
            )
            for name, value in ports.items()
        )
    container_paths.extend(
        (f"/spec/verification/expected_outputs/{index}/path", output["path"])
        for index, output in enumerate(
            document["spec"]["verification"]["expected_outputs"]
        )
    )
    for path, value in container_paths:
        candidate = PurePosixPath(value)
        if not candidate.is_absolute() or ".." in candidate.parts:
            issues.append(
                ContractIssue(path, "must be an absolute normalized container path")
            )

    mounts_by_kind = {mount["kind"]: mount for mount in mounts}
    mounted_files = [
        *[
            (
                f"/spec/verification/expected_outputs/{index}/path",
                output["path"],
                "output",
            )
            for index, output in enumerate(verification["expected_outputs"])
        ],
    ]
    if "fixture" in verification:
        mounted_files.append(
            (
                "/spec/verification/fixture/mount_path",
                verification["fixture"]["mount_path"],
                "input",
            )
        )
    mounted_files.extend(
        (
            f"/spec/execution/ports/{direction}/{name}",
            value,
            "input" if direction == "inputs" else "output",
        )
        for direction, ports in execution["ports"].items()
        for name, value in ports.items()
    )
    for path, value, kind in mounted_files:
        mount = mounts_by_kind.get(kind)
        if mount is None:
            issues.append(ContractIssue(path, f"requires a declared {kind} mount"))
            continue
        if ".." in PurePosixPath(value).parts:
            continue
        try:
            relative = PurePosixPath(value).relative_to(PurePosixPath(mount["path"]))
        except ValueError:
            relative = None
        if relative is None or not relative.parts:
            issues.append(
                ContractIssue(path, f"must name a file inside the {kind} mount")
            )

    if execution["ports"]["inputs"] and "fixture" not in verification:
        issues.append(
            ContractIssue(
                "/spec/verification/fixture",
                "is required when the runtime declares input ports",
            )
        )

    for direction, ports in execution["ports"].items():
        values = list(ports.values())
        issues.extend(
            _duplicate_issues(
                values,
                f"/spec/execution/ports/{direction}",
                f"{direction} port paths",
            )
        )
    dynamic_arguments = [
        binding["argument"]
        for binding in execution["parameters"].values()
        if "argument" in binding
    ]
    issues.extend(
        _duplicate_issues(
            dynamic_arguments,
            "/spec/execution/parameters",
            "parameter arguments",
        )
    )

    status = metadata["status"]
    release_status = release["status"]
    if status == "build-ready" and release_status != "unpublished":
        issues.append(
            ContractIssue(
                "/spec/release/status",
                "must be unpublished while the runtime is only build-ready",
            )
        )
    if status in {"oci-smoke-tested", "target-accepted"} and not metadata["evidence"]:
        issues.append(
            ContractIssue(
                "/metadata/evidence",
                "is required after an OCI smoke test or target acceptance",
            )
        )
    if status == "target-accepted" and release_status != "target-accepted":
        issues.append(
            ContractIssue(
                "/spec/release/status",
                "must be target-accepted when metadata status is target-accepted",
            )
        )
    if release_status == "target-accepted" and status != "target-accepted":
        issues.append(
            ContractIssue(
                "/metadata/status",
                "must be target-accepted when the release is target-accepted",
            )
        )

    if release_status in {"published", "target-accepted"}:
        for field in ("oci_reference", "oci_digest"):
            if field not in release:
                issues.append(
                    ContractIssue(
                        f"/spec/release/{field}",
                        "is required for a published runtime",
                    )
                )
        if "oci_reference" in release and "oci_digest" in release:
            if not release["oci_reference"].endswith("@" + release["oci_digest"]):
                issues.append(
                    ContractIssue(
                        "/spec/release/oci_reference",
                        "must end with the declared OCI digest",
                    )
                )

    if release_status == "target-accepted":
        for field in (
            "apptainer_reference",
            "apptainer_digest",
            "sbom",
            "signature",
            "attestation",
        ):
            if field not in release:
                issues.append(
                    ContractIssue(
                        f"/spec/release/{field}",
                        "is required for a target-accepted runtime",
                    )
                )
        reference = release.get("apptainer_reference")
        if reference and not (
            reference.startswith("/")
            or reference.startswith("file://")
            or reference.startswith("oras://")
        ):
            issues.append(
                ContractIssue(
                    "/spec/release/apptainer_reference",
                    "must be an absolute path, file:// URI, or oras:// URI",
                )
            )
        if (
            reference
            and reference.startswith("oras://")
            and "apptainer_digest" in release
            and not reference.endswith("@" + release["apptainer_digest"])
        ):
            issues.append(
                ContractIssue(
                    "/spec/release/apptainer_reference",
                    "ORAS references must end with the declared Apptainer digest",
                )
            )
    return issues


def _validate_service_interface(document: dict[str, Any]) -> list[ContractIssue]:
    issues: list[ContractIssue] = []
    metadata = document["metadata"]
    if (
        metadata["status"] in {"contract-valid", "project-reviewed"}
        and not metadata["evidence"]
    ):
        issues.append(
            ContractIssue(
                "/metadata/evidence",
                "is required for a contract-valid or project-reviewed interface",
            )
        )

    schemas = document["spec"]["schemas"]
    for name, schema in schemas.items():
        try:
            Draft202012Validator.check_schema(schema)
        except SchemaError as error:
            issues.append(
                ContractIssue(
                    f"/spec/schemas/{name}",
                    f"is not a valid JSON Schema: {error.message}",
                )
            )

    endpoints = document["spec"]["endpoints"]
    issues.extend(
        _duplicate_issues(
            (endpoint["id"] for endpoint in endpoints),
            "/spec/endpoints",
            "endpoint IDs",
        )
    )
    issues.extend(
        _duplicate_issues(
            (f"{endpoint['method']} {endpoint['path']}" for endpoint in endpoints),
            "/spec/endpoints",
            "endpoint method and path pairs",
        )
    )
    for index, endpoint in enumerate(endpoints):
        for field in ("request_schema", "response_schema"):
            reference = endpoint[field]
            if reference not in schemas:
                issues.append(
                    ContractIssue(
                        f"/spec/endpoints/{index}/{field}",
                        f"references unknown schema {reference}",
                    )
                )
    return issues


def _validate_storage_profile(document: dict[str, Any]) -> list[ContractIssue]:
    issues: list[ContractIssue] = []
    metadata = document["metadata"]
    spec = document["spec"]
    roots = spec["roots"]
    mounts = spec["mounts"]
    node_local = spec["node_local"]
    if metadata["status"] == "active" and not metadata["evidence"]:
        issues.append(
            ContractIssue(
                "/metadata/evidence",
                "is required for an active storage profile",
            )
        )
    values = [*roots.values(), *mounts.values()]
    if len(values) != len(set(values)):
        issues.append(
            ContractIssue(
                "/spec",
                "storage roots and container mount paths must be distinct",
            )
        )
    if node_local["mode"] == "disabled" and (
        node_local["stage_image"] or node_local["stage_inputs"]
    ):
        issues.append(
            ContractIssue(
                "/spec/node_local",
                "node-local staging flags require slurm-tmpdir mode",
            )
        )
    return issues


def _validate_pilot_profile(document: dict[str, Any]) -> list[ContractIssue]:
    metadata = document["metadata"]
    spec = document["spec"]
    allocation = spec["allocation"]
    issues: list[ContractIssue] = []
    if allocation["idle_timeout_seconds"] >= allocation["max_lifetime_seconds"]:
        issues.append(
            ContractIssue(
                "/spec/allocation/idle_timeout_seconds",
                "must be less than the maximum pilot lifetime",
            )
        )
    if allocation["drain_before_expiry_seconds"] >= allocation["max_lifetime_seconds"]:
        issues.append(
            ContractIssue(
                "/spec/allocation/drain_before_expiry_seconds",
                "must be less than the maximum pilot lifetime",
            )
        )
    if metadata["status"] == "active":
        if not metadata["evidence"]:
            issues.append(
                ContractIssue(
                    "/metadata/evidence",
                    "is required before a pilot profile can be active",
                )
            )
        if "account" not in spec["scheduler"]:
            issues.append(
                ContractIssue(
                    "/spec/scheduler/account",
                    "is required before a pilot profile can be active",
                )
            )
    return issues


def _validate_slurm_test_cluster(
    document: dict[str, Any],
) -> list[ContractIssue]:
    metadata = document["metadata"]
    spec = document["spec"]
    compose = spec["compose"]
    services = set(compose["services"])
    issues: list[ContractIssue] = []
    if compose["controller_service"] not in services:
        issues.append(
            ContractIssue(
                "/spec/compose/controller_service",
                "must be included in the started services",
            )
        )
    for index, service in enumerate(compose["worker_services"]):
        if service not in services:
            issues.append(
                ContractIssue(
                    f"/spec/compose/worker_services/{index}",
                    "must be included in the started services",
                )
            )
    if not spec["security"]["start_rest_api"] and "slurmrestd" in services:
        issues.append(
            ContractIssue(
                "/spec/compose/services",
                "cannot include slurmrestd while REST startup is disabled",
            )
        )
    relative_paths = [
        ("/spec/compose/compose_file", compose["compose_file"]),
        (
            "/spec/compose/shared_directory/host",
            compose["shared_directory"]["host"],
        ),
        *[
            (f"/spec/compose/overrides/{index}", value)
            for index, value in enumerate(compose["overrides"])
        ],
        *[
            (f"/spec/compatibility/files/{index}/source", item["source"])
            for index, item in enumerate(spec["compatibility"]["files"])
        ],
        *[
            (f"/spec/compatibility/files/{index}/destination", item["destination"])
            for index, item in enumerate(spec["compatibility"]["files"])
        ],
        (
            "/spec/compatibility/build_ca_destination",
            spec["compatibility"]["build_ca_destination"],
        ),
        *[
            (f"/spec/runtime_images/{index}/runtime_manifest", item["runtime_manifest"])
            for index, item in enumerate(spec.get("runtime_images", []))
        ],
    ]
    for path, value in relative_paths:
        parsed = PurePosixPath(value)
        if parsed.is_absolute() or ".." in parsed.parts:
            issues.append(ContractIssue(path, "must be a safe relative path"))
    issues.extend(
        _duplicate_issues(
            (
                item["destination"]
                for item in spec["compatibility"]["files"]
            ),
            "/spec/compatibility/files",
            "compatibility destinations",
        )
    )
    runtime_images = spec.get("runtime_images", [])
    issues.extend(
        _duplicate_issues(
            (item["runtime_id"] for item in runtime_images),
            "/spec/runtime_images",
            "runtime IDs",
        )
    )
    for index, item in enumerate(runtime_images):
        if not item["registry_reference"].endswith("@" + item["digest"]):
            issues.append(
                ContractIssue(
                    f"/spec/runtime_images/{index}/registry_reference",
                    "must end with the declared digest",
                )
            )
    if metadata["status"] == "validated" and not metadata["evidence"]:
        issues.append(
            ContractIssue(
                "/metadata/evidence",
                "is required before a test cluster can be validated",
            )
        )
    return issues


def _semantic_issues(kind: str, document: dict[str, Any]) -> list[ContractIssue]:
    if kind == "capability":
        return _validate_capability(document)
    if kind == "deployment-profile":
        return _validate_deployment_profile(document)
    if kind == "execution-target":
        return _validate_execution_target(document)
    if kind == "hpc-acceptance":
        return _validate_hpc_acceptance(document)
    if kind == "integration-scaffold":
        return _validate_integration_scaffold(document)
    if kind == "operation-interface":
        return _validate_operation_interface(document)
    if kind == "operation-runtime":
        return _validate_operation_runtime(document)
    if kind == "pilot-profile":
        return _validate_pilot_profile(document)
    if kind == "service-interface":
        return _validate_service_interface(document)
    if kind == "slurm-test-cluster":
        return _validate_slurm_test_cluster(document)
    if kind == "storage-profile":
        return _validate_storage_profile(document)
    if kind == "workflow":
        return _validate_workflow(document)
    if kind == "workflow-draft":
        return _validate_workflow_draft(document)
    if kind == "run":
        return _validate_run(document)
    if kind == "registry":
        return _validate_registry(document)
    return []


def validate_contract_data(kind: str, document: dict[str, Any]) -> None:
    normalized = normalize_kind(kind)
    schema = load_schema(normalized)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    schema_errors = sorted(
        validator.iter_errors(document),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    issues = [
        ContractIssue(_json_path(error.absolute_path), error.message)
        for error in schema_errors
    ]
    if not issues:
        issues.extend(_semantic_issues(normalized, document))
    if issues:
        raise ContractError(f"invalid {normalized} contract", issues)


def validate_contract(kind: str, path: str | Path) -> dict[str, Any]:
    document = load_document(path)
    validate_contract_data(kind, document)
    return document
