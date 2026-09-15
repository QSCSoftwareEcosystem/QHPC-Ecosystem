"""Fail-closed validation for non-executing ChatQEC tool proposals.

ChatQEC can recommend a governed calculation, but this module deliberately does
not submit a run or invoke an MCP server.  A proposal is usable only when its
exact target resolves in the immutable EQO registry snapshot supplied by the
caller and still requires an explicit user confirmation.
"""

from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from .contract import ContractError, validate_contract_data
from .registry import RegistryError, find_registry_entry, registry_digest


class ChatQECProposalError(ValueError):
    """Raised when a ChatQEC proposal cannot be safely reviewed."""


MCP_TOOLS_REPOSITORY = "https://github.com/QSCSoftwareEcosystem/chatqec-mcp-tools"
MCP_TOOLS_REVISION = "dd19a85b08637a61dc1afc124d2f4b32745b527b"

# Every inspected source tool now has a bounded EQO operation record. A model
# cannot use this mapping to target another existing EQO capability.
_P1_OPERATION_BY_TOOL = {
    # The source repository uses Python-style names.  The hyphenated aliases
    # are retained for proposal records created by the initial EQO UI draft.
    "code_params": "code-params",
    "code-params": "code-params",
    "stim_simulate": "stim-simulate",
    "stim-simulate": "stim-simulate",
    "stim_diagram": "stim-diagram",
    "stim-diagram": "stim-diagram",
    "pymatching_decode": "pymatching-decode",
    "pymatching-decode": "pymatching-decode",
    "threshold_sweep": "threshold-sweep",
    "threshold-sweep": "threshold-sweep",
    "qec_circuit_build": "qec-circuit-build",
    "qec-circuit-build": "qec-circuit-build",
    "tsim_simulate": "tsim-simulate",
    "tsim-simulate": "tsim-simulate",
    "glcb_visualize_url": "glcb-visualize-url",
    "glcb-visualize-url": "glcb-visualize-url",
}


def _proposal_error(message: str) -> ChatQECProposalError:
    return ChatQECProposalError(f"ChatQEC tool proposal {message}")


def _timestamp(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise _proposal_error(f"{field} is not an RFC 3339 timestamp") from error
    if parsed.tzinfo is None:
        raise _proposal_error(f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _type_matches(value: Any, type_name: str) -> bool:
    if type_name == "string":
        return isinstance(value, str)
    if type_name == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if type_name == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if type_name == "boolean":
        return isinstance(value, bool)
    return False


def _validate_parameters(
    proposal_parameters: Mapping[str, Any],
    operation: Mapping[str, Any],
) -> None:
    declared = operation.get("parameters", {})
    if not isinstance(declared, Mapping):
        raise _proposal_error("targets an operation with invalid parameters")
    unknown = sorted(set(proposal_parameters) - set(declared))
    if unknown:
        raise _proposal_error(
            "contains unsupported parameters: " + ", ".join(unknown)
        )
    missing = sorted(
        name
        for name, definition in declared.items()
        if definition.get("required") and name not in proposal_parameters
    )
    if missing:
        raise _proposal_error(
            "omits required parameters: " + ", ".join(missing)
        )
    for name, value in proposal_parameters.items():
        definition = declared[name]
        type_name = definition.get("type")
        if not _type_matches(value, type_name):
            raise _proposal_error(f"parameter {name} does not match its declared type")
        if "enum" in definition and value not in definition["enum"]:
            raise _proposal_error(f"parameter {name} is not an admitted value")
        if "minimum" in definition and value < definition["minimum"]:
            raise _proposal_error(f"parameter {name} is below its admitted minimum")
        if "maximum" in definition and value > definition["maximum"]:
            raise _proposal_error(f"parameter {name} exceeds its admitted maximum")


def _declared_ports(operation: Mapping[str, Any], direction: str) -> dict[str, str]:
    ports = operation.get(direction, {})
    if not isinstance(ports, Mapping):
        raise _proposal_error(f"targets an operation with invalid {direction}")
    result: dict[str, str] = {}
    for name, port in ports.items():
        if not isinstance(port, Mapping) or not isinstance(port.get("artifact_type"), str):
            raise _proposal_error(f"targets an operation with invalid {direction}")
        result[str(name)] = port["artifact_type"]
    return result


def validate_tool_proposal(
    proposal: Mapping[str, Any],
    registry: Mapping[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Validate a proposal against one immutable admitted registry snapshot.

    The returned mapping is a JSON-safe copy.  It has no run ID and confers no
    execution authority.  Callers must bind user-selected input artifacts and
    submit a normal EQO run only after separate confirmation.
    """

    try:
        validated = copy.deepcopy(dict(proposal))
        validate_contract_data("chatqec-tool-proposal", validated)
    except ContractError as error:
        raise _proposal_error(f"does not match the v1 contract: {error}") from error

    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    created = _timestamp(validated["metadata"]["created_at"], "created_at")
    expires = _timestamp(validated["metadata"]["expires_at"], "expires_at")
    if expires <= current:
        raise _proposal_error("has expired")
    if expires <= created:
        raise _proposal_error("expires_at must follow created_at")
    if expires - created > timedelta(hours=24):
        raise _proposal_error("lifetime exceeds 24 hours")

    spec = validated["spec"]
    source = spec["source"]
    if (
        source["repository"] != MCP_TOOLS_REPOSITORY
        or source["revision"] != MCP_TOOLS_REVISION
    ):
        raise _proposal_error("source is not the pinned chatqec-mcp-tools revision")
    expected_operation = _P1_OPERATION_BY_TOOL.get(source["tool"])
    if expected_operation is None:
        raise _proposal_error("source tool is not admitted for proposal review")
    target = spec["target"]
    if target["operation"] != expected_operation:
        raise _proposal_error("target operation does not match the source tool")

    try:
        actual_registry_digest = registry_digest(dict(registry))
    except (KeyError, TypeError, ValueError) as error:
        raise _proposal_error("registry snapshot is invalid") from error
    if spec["registry_digest"] != actual_registry_digest:
        raise _proposal_error("registry digest does not match the admitted snapshot")

    try:
        entry = find_registry_entry(
            dict(registry), target["capability"], target["version"]
        )
    except RegistryError as error:
        raise _proposal_error("does not resolve to an admitted capability") from error
    capability = entry["capability"]
    operations = capability.get("spec", {}).get("operations", [])
    operation = next(
        (
            item
            for item in operations
            if isinstance(item, Mapping) and item.get("id") == target["operation"]
        ),
        None,
    )
    if operation is None:
        raise _proposal_error("does not resolve to an admitted operation")

    if spec["execution_target"] not in operation.get("execution_targets", []):
        raise _proposal_error("execution target is not admitted for the operation")
    _validate_parameters(spec["parameters"], operation)
    if spec["input_requirements"] != _declared_ports(operation, "inputs"):
        raise _proposal_error("input requirements do not match the admitted operation")
    if spec["expected_outputs"] != _declared_ports(operation, "outputs"):
        raise _proposal_error("expected outputs do not match the admitted operation")

    resources = operation.get("resources", {})
    for name, value in spec["resource_estimate"].items():
        limit = resources.get(name)
        if isinstance(limit, int) and value > limit:
            raise _proposal_error(f"resource estimate exceeds the admitted {name}")
    return validated
