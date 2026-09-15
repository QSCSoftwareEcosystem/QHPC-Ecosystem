"""Versioned readiness vocabulary for the governed ChatQEC service boundary.

The HTTP health response intentionally contains deployment state rather than
configuration details.  It tells the Workbench whether the service is an
offline extractive fallback or an admitted upstream RAG deployment without
disclosing provider endpoints, secret locations, corpus paths, or command
lines.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

from .service_adapters import ServiceAdapterError


CANONICAL_EXTRACTIVE_FALLBACK = "canonical-corpus-extractive-fallback"
UPSTREAM_RAG_READ_ONLY = "upstream-rag-read-only"
UPSTREAM_MCP_AGENT = "upstream-mcp-agent"
MCP_DIRECT_TOOLS = "mcp-direct-tools"
LEGACY_EXTRACTIVE_MODE = "canonical-extractive-development"

_SOURCE_REVISION = re.compile(r"^[0-9a-f]{40,64}$")
_CORPUS_REVISION = re.compile(r"^sha256:[0-9a-f]{64}$")
_READINESS_COMPONENTS = (
    "source",
    "model",
    "qdrant",
    "corpus",
    "embeddings",
    "reranker",
    "knowledge",
)
_READINESS_STATES = {
    "ready",
    "disabled",
    "not-configured",
    "not-provisioned",
    "unavailable",
}
_CAPABILITY_FIELDS = (
    "model_rag",
    "streaming",
    "source_ledger",
    "tool_proposals",
    "mcp_tools",
)


def fallback_readiness() -> dict[str, str]:
    """Return the fixed dependency state of the bundled offline fallback."""

    return {
        "source": "ready",
        "model": "disabled",
        "qdrant": "disabled",
        "corpus": "ready",
        "embeddings": "disabled",
        "reranker": "disabled",
        "knowledge": "disabled",
    }


def fallback_capabilities() -> dict[str, bool]:
    """Return capabilities that the deterministic fallback actually provides."""

    return {
        "model_rag": False,
        "streaming": True,
        "source_ledger": False,
        "tool_proposals": False,
        "mcp_tools": False,
    }


def _object(
    value: Any,
    label: str,
    *,
    required: set[str],
    allowed: set[str],
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ServiceAdapterError(f"{label} must be an object")
    keys = set(value)
    missing = sorted(required - keys)
    unexpected = sorted(keys - allowed)
    if missing:
        raise ServiceAdapterError(f"{label} is missing fields: {', '.join(missing)}")
    if unexpected:
        raise ServiceAdapterError(
            f"{label} contains unsupported fields: {', '.join(unexpected)}"
        )
    return value


def _readiness(value: Any, *, mode: str) -> dict[str, str]:
    if value is None:
        # Existing v1 servers did not report component readiness.  Preserve
        # their service compatibility while making the legacy condition obvious
        # to a new UI instead of silently treating it as model-backed RAG.
        return (
            fallback_readiness()
            if mode in {CANONICAL_EXTRACTIVE_FALLBACK, LEGACY_EXTRACTIVE_MODE}
            else {component: "not-configured" for component in _READINESS_COMPONENTS}
        )
    document = _object(
        value,
        "ChatQEC readiness",
        required=set(_READINESS_COMPONENTS),
        allowed=set(_READINESS_COMPONENTS),
    )
    normalized: dict[str, str] = {}
    for component in _READINESS_COMPONENTS:
        state = document[component]
        if state not in _READINESS_STATES:
            raise ServiceAdapterError(
                f"ChatQEC readiness {component} has an invalid state"
            )
        normalized[component] = state
    return normalized


def _capabilities(value: Any, *, mode: str) -> dict[str, bool]:
    if value is None:
        return (
            fallback_capabilities()
            if mode in {CANONICAL_EXTRACTIVE_FALLBACK, LEGACY_EXTRACTIVE_MODE}
            else {field: False for field in _CAPABILITY_FIELDS}
        )
    # v1 read-only deployments predate the explicit MCP capability. Treat an
    # omitted field as false so clients can upgrade without fabricating access.
    if isinstance(value, Mapping) and "mcp_tools" not in value:
        value = {**value, "mcp_tools": False}
    document = _object(
        value,
        "ChatQEC capabilities",
        required=set(_CAPABILITY_FIELDS),
        allowed=set(_CAPABILITY_FIELDS),
    )
    normalized: dict[str, bool] = {}
    for field in _CAPABILITY_FIELDS:
        item = document[field]
        if not isinstance(item, bool):
            raise ServiceAdapterError(f"ChatQEC capability {field} must be boolean")
        normalized[field] = item
    return normalized


def validate_chatqec_health(value: Any) -> dict[str, Any]:
    """Normalize the bounded v1/v1.1 ChatQEC health response.

    A health response may be ``degraded`` so QHPC can show which non-secret
    dependency is missing before it sends an answer request. Only ``ok`` is
    considered answer-available.  MCP execution is allowed only in the two
    explicitly named agent modes; every other mode remains read-only.
    """

    document = _object(
        value,
        "ChatQEC health response",
        required={
            "status",
            "service",
            "mode",
            "source_revision",
            "corpus_revision",
            "pages",
            "tool_execution",
        },
        allowed={
            "status",
            "service",
            "mode",
            "source_revision",
            "corpus_revision",
            "pages",
            "tool_execution",
            "readiness",
            "capabilities",
        },
    )
    status = document["status"]
    if status not in {"ok", "degraded"}:
        raise ServiceAdapterError("ChatQEC health response status is invalid")
    if document["service"] != "chatqec":
        raise ServiceAdapterError("ChatQEC health response service is invalid")
    mode = document["mode"]
    if not isinstance(mode, str) or not mode or len(mode) > 128:
        raise ServiceAdapterError("ChatQEC health response mode is invalid")
    source_revision = document["source_revision"]
    if not isinstance(source_revision, str) or _SOURCE_REVISION.fullmatch(source_revision) is None:
        raise ServiceAdapterError("ChatQEC health response source revision is invalid")
    corpus_revision = document["corpus_revision"]
    if not isinstance(corpus_revision, str) or _CORPUS_REVISION.fullmatch(corpus_revision) is None:
        raise ServiceAdapterError("ChatQEC health response corpus revision is invalid")
    pages = document["pages"]
    if isinstance(pages, bool) or not isinstance(pages, int) or pages < 0:
        raise ServiceAdapterError("ChatQEC health response pages is invalid")
    if status == "ok" and pages <= 0:
        raise ServiceAdapterError("ready ChatQEC health response has no corpus pages")
    tool_execution = document["tool_execution"]
    if not isinstance(tool_execution, bool):
        raise ServiceAdapterError("ChatQEC health response tool_execution must be boolean")
    if tool_execution and mode not in {UPSTREAM_MCP_AGENT, MCP_DIRECT_TOOLS}:
        raise ServiceAdapterError(
            "ChatQEC health response enables prohibited tool execution outside an admitted mode"
        )
    readiness = _readiness(document.get("readiness"), mode=mode)
    capabilities = _capabilities(document.get("capabilities"), mode=mode)
    if status == "ok" and mode == UPSTREAM_RAG_READ_ONLY:
        required = ("source", "model", "qdrant", "corpus", "embeddings", "reranker")
        if any(readiness[component] != "ready" for component in required):
            raise ServiceAdapterError("ready upstream ChatQEC has incomplete readiness")
        if not capabilities["model_rag"]:
            raise ServiceAdapterError("ready upstream ChatQEC does not report model RAG")
    return {
        "status": status,
        "service": "chatqec",
        "mode": mode,
        "source_revision": source_revision,
        "corpus_revision": corpus_revision,
        "pages": pages,
        "tool_execution": tool_execution,
        "readiness": readiness,
        "capabilities": capabilities,
        "available": status == "ok",
    }
