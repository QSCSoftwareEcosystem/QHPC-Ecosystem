"""Resolve and validate workflow definitions against a capability registry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .contract import (
    ContractError,
    ContractIssue,
    document_digest,
    validate_contract_data,
)
from .registry import RegistryError, find_registry_entry


@dataclass(frozen=True)
class ResolvedOperation:
    node_id: str
    capability_id: str
    capability_version: str
    project: str
    operation: dict[str, Any]


@dataclass(frozen=True)
class ResolvedWorkflow:
    definition: dict[str, Any]
    digest: str
    operations: dict[str, ResolvedOperation]


def _parameter_valid(value: Any, parameter: dict[str, Any]) -> bool:
    expected = parameter["type"]
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, str)


def _resolve_node(
    node: dict[str, Any], registry: dict[str, Any], issues: list[ContractIssue]
) -> ResolvedOperation | None:
    reference = node["operation"]
    path = f"/spec/nodes/{node['id']}"
    try:
        entry = find_registry_entry(
            registry, reference["capability"], reference["version"]
        )
    except RegistryError as error:
        issues.append(ContractIssue(path + "/operation", str(error)))
        return None

    capability = entry["capability"]
    matches = [
        operation
        for operation in capability["spec"].get("operations", [])
        if operation["id"] == reference["operation"]
    ]
    if not matches:
        issues.append(
            ContractIssue(
                path + "/operation/operation",
                f"operation not found: {reference['operation']}",
            )
        )
        return None
    if capability["metadata"].get("deprecated"):
        issues.append(ContractIssue(path + "/operation", "capability is deprecated"))
    operation = matches[0]
    target = node.get("execution_target")
    if target and target not in operation["execution_targets"]:
        issues.append(
            ContractIssue(
                path + "/execution_target",
                f"operation does not support execution target {target}",
            )
        )

    declared = operation.get("parameters", {})
    supplied = node["parameters"]
    for name in sorted(set(supplied) - set(declared)):
        issues.append(ContractIssue(path + f"/parameters/{name}", "unknown parameter"))
    for name, parameter in declared.items():
        parameter_path = path + f"/parameters/{name}"
        if name not in supplied:
            if parameter.get("required") and "default" not in parameter:
                issues.append(
                    ContractIssue(parameter_path, "required parameter missing")
                )
            continue
        value = supplied[name]
        if not _parameter_valid(value, parameter):
            issues.append(
                ContractIssue(
                    parameter_path,
                    f"value does not match declared type {parameter['type']}",
                )
            )
            continue
        if "enum" in parameter and value not in parameter["enum"]:
            issues.append(ContractIssue(parameter_path, "value is not in enum"))
        if "minimum" in parameter and value < parameter["minimum"]:
            issues.append(ContractIssue(parameter_path, "value is below minimum"))
        if "maximum" in parameter and value > parameter["maximum"]:
            issues.append(ContractIssue(parameter_path, "value is above maximum"))

    return ResolvedOperation(
        node_id=node["id"],
        capability_id=capability["metadata"]["id"],
        capability_version=capability["metadata"]["version"],
        project=capability["metadata"]["project"],
        operation=operation,
    )


def resolve_workflow(
    workflow: dict[str, Any], registry: dict[str, Any]
) -> ResolvedWorkflow:
    """Validate a workflow and resolve every operation and port against a registry."""
    validate_contract_data("workflow", workflow)
    issues: list[ContractIssue] = []
    resolved: dict[str, ResolvedOperation] = {}
    for node in workflow["spec"]["nodes"]:
        operation = _resolve_node(node, registry, issues)
        if operation:
            resolved[node["id"]] = operation

    incoming: dict[tuple[str, str], int] = {}
    for index, edge in enumerate(workflow["spec"]["edges"]):
        path = f"/spec/edges/{index}"
        source = edge["from"]
        target = edge["to"]
        source_operation = resolved.get(source["node"])
        target_operation = resolved.get(target["node"])
        if source_operation:
            output = source_operation.operation["outputs"].get(source["port"])
            if not output:
                issues.append(
                    ContractIssue(path + "/from/port", "output port not found")
                )
            elif output["artifact_type"] != source["artifact_type"]:
                issues.append(
                    ContractIssue(
                        path + "/from/artifact_type", "does not match output port"
                    )
                )
        if target_operation:
            input_port = target_operation.operation["inputs"].get(target["port"])
            if not input_port:
                issues.append(ContractIssue(path + "/to/port", "input port not found"))
            elif input_port["artifact_type"] != target["artifact_type"]:
                issues.append(
                    ContractIssue(
                        path + "/to/artifact_type", "does not match input port"
                    )
                )
            key = (target["node"], target["port"])
            incoming[key] = incoming.get(key, 0) + 1
            if input_port and not input_port.get("multiple") and incoming[key] > 1:
                issues.append(
                    ContractIssue(path + "/to", "input accepts only one artifact")
                )

    for name, workflow_input in workflow["spec"]["inputs"].items():
        target = workflow_input["to"]
        operation = resolved.get(target["node"])
        path = f"/spec/inputs/{name}"
        if operation:
            input_port = operation.operation["inputs"].get(target["port"])
            if not input_port:
                issues.append(ContractIssue(path + "/to/port", "input port not found"))
            elif input_port["artifact_type"] != workflow_input["artifact_type"]:
                issues.append(
                    ContractIssue(path + "/artifact_type", "does not match input port")
                )
            incoming[(target["node"], target["port"])] = (
                incoming.get((target["node"], target["port"]), 0) + 1
            )

    for name, workflow_output in workflow["spec"]["outputs"].items():
        source = workflow_output["from"]
        operation = resolved.get(source["node"])
        path = f"/spec/outputs/{name}"
        if operation:
            output = operation.operation["outputs"].get(source["port"])
            if not output:
                issues.append(
                    ContractIssue(path + "/from/port", "output port not found")
                )
            elif output["artifact_type"] != workflow_output["artifact_type"]:
                issues.append(
                    ContractIssue(path + "/artifact_type", "does not match output port")
                )

    for node_id, operation in resolved.items():
        for port, definition in operation.operation["inputs"].items():
            if definition.get("required", True) and not incoming.get((node_id, port)):
                issues.append(
                    ContractIssue(
                        f"/spec/nodes/{node_id}/inputs/{port}",
                        "required input is not connected",
                    )
                )

    if issues:
        raise ContractError("workflow is incompatible with registry", issues)
    return ResolvedWorkflow(workflow, document_digest(workflow), resolved)


def topological_nodes(workflow: dict[str, Any]) -> tuple[str, ...]:
    """Return deterministic topological order for an already valid workflow."""
    nodes = [node["id"] for node in workflow["spec"]["nodes"]]
    adjacency = {node: set() for node in nodes}
    indegree = {node: 0 for node in nodes}
    for edge in workflow["spec"]["edges"]:
        source = edge["from"]["node"]
        target = edge["to"]["node"]
        if target not in adjacency[source]:
            adjacency[source].add(target)
            indegree[target] += 1
    ready = sorted(node for node, degree in indegree.items() if degree == 0)
    ordered: list[str] = []
    while ready:
        node = ready.pop(0)
        ordered.append(node)
        for target in sorted(adjacency[node]):
            indegree[target] -= 1
            if indegree[target] == 0:
                ready.append(target)
                ready.sort()
    return tuple(ordered)
