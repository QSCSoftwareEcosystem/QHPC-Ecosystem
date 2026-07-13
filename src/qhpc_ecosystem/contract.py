"""Load and validate versioned QHPC integration contracts."""

from __future__ import annotations

import json
from hashlib import sha256
from collections import Counter, deque
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any, Iterable

import yaml
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError


CONTRACT_SCHEMAS = {
    "artifact": "artifact-v1.schema.json",
    "artifact-type": "artifact-type-v1.schema.json",
    "capability": "capability-v1.schema.json",
    "execution-target": "execution-target-v1.schema.json",
    "registry": "registry-v1.schema.json",
    "run": "run-v1.schema.json",
    "workflow": "workflow-v1.schema.json",
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


def _validate_run(document: dict[str, Any]) -> list[ContractIssue]:
    return _duplicate_issues(
        (task["node_id"] for task in document["spec"]["tasks"]),
        "/spec/tasks",
        "task node IDs",
    )


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


def _semantic_issues(kind: str, document: dict[str, Any]) -> list[ContractIssue]:
    if kind == "capability":
        return _validate_capability(document)
    if kind == "workflow":
        return _validate_workflow(document)
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
