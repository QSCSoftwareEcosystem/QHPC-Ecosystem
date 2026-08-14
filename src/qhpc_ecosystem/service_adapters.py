"""Controlled clients for separately deployed ecosystem services."""

from __future__ import annotations

import json
import re
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlsplit


class ServiceAdapterError(ValueError):
    """Raised when a service request or response violates its interface."""


ServiceTransport = Callable[
    ...,
    tuple[int, Mapping[str, str], bytes],
]

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@-]{0,127}$")
_POLICY_CLASS = re.compile(r"^[a-z][a-z0-9._-]{0,63}$")
_CORPUS_REVISION = re.compile(r"^sha256:[0-9a-f]{64}$")
_MAX_RESPONSE_BYTES = 2_000_000
_MAX_SSE_EVENTS = 10_000
_REQUEST_FIELDS = {
    "request_id",
    "correlation_id",
    "conversation_id",
    "authorized_subject",
    "workspace_id",
    "policy_class",
    "corpus_revision",
    "question",
    "history",
}
_REQUIRED_REQUEST_FIELDS = _REQUEST_FIELDS - {"history"}
_RESPONSE_FIELDS = {
    "request_id",
    "correlation_id",
    "conversation_id",
    "answer",
    "citations",
    "confidence",
    "provider",
    "model",
    "model_response_id",
    "corpus_revision",
    "usage",
    "latency_ms",
}


def _bounded_text(
    value: Any,
    name: str,
    *,
    maximum: int,
    pattern: re.Pattern[str] | None = None,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ServiceAdapterError(f"{name} must be non-empty text")
    if len(value) > maximum:
        raise ServiceAdapterError(f"{name} exceeds {maximum} characters")
    if pattern is not None and pattern.fullmatch(value) is None:
        raise ServiceAdapterError(f"{name} has an invalid format")
    return value


def _object_fields(
    value: Any,
    name: str,
    *,
    required: set[str],
    allowed: set[str],
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ServiceAdapterError(f"{name} must be an object")
    missing = sorted(required - set(value))
    if missing:
        raise ServiceAdapterError(f"{name} is missing: {', '.join(missing)}")
    unknown = sorted(str(field) for field in set(value) - allowed)
    if unknown:
        raise ServiceAdapterError(
            f"{name} contains unsupported fields: {', '.join(unknown)}"
        )
    return value


def _non_negative_integer(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ServiceAdapterError(f"{name} must be a non-negative integer")
    return value


def _non_negative_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise ServiceAdapterError(f"{name} must be a non-negative number")
    return float(value)


def build_chatqec_request(
    *,
    request_id: str,
    correlation_id: str,
    conversation_id: str,
    authorized_subject: str,
    workspace_id: str,
    policy_class: str,
    corpus_revision: str,
    question: str,
    history: Sequence[Mapping[str, str]] = (),
) -> dict[str, Any]:
    """Build a bounded ChatQEC request without credentials or deployment secrets."""
    request: dict[str, Any] = {
        "request_id": request_id,
        "correlation_id": correlation_id,
        "conversation_id": conversation_id,
        "authorized_subject": authorized_subject,
        "workspace_id": workspace_id,
        "policy_class": policy_class,
        "corpus_revision": corpus_revision,
        "question": question,
    }
    if history:
        request["history"] = [dict(item) for item in history]
    return _normalize_chatqec_request(request)


def _normalize_chatqec_request(request: Mapping[str, Any]) -> dict[str, Any]:
    value = _object_fields(
        request,
        "ChatQEC request",
        required=_REQUIRED_REQUEST_FIELDS,
        allowed=_REQUEST_FIELDS,
    )
    normalized: dict[str, Any] = {}
    for field in (
        "request_id",
        "correlation_id",
        "conversation_id",
        "authorized_subject",
        "workspace_id",
    ):
        normalized[field] = _bounded_text(
            value[field], field, maximum=128, pattern=_IDENTIFIER
        )
    normalized["policy_class"] = _bounded_text(
        value["policy_class"],
        "policy_class",
        maximum=64,
        pattern=_POLICY_CLASS,
    )
    normalized["corpus_revision"] = _bounded_text(
        value["corpus_revision"],
        "corpus_revision",
        maximum=71,
        pattern=_CORPUS_REVISION,
    )
    normalized["question"] = _bounded_text(
        value["question"], "question", maximum=8000
    )

    history = value.get("history", [])
    if not isinstance(history, Sequence) or isinstance(history, (str, bytes)):
        raise ServiceAdapterError("history must be an array")
    if len(history) > 20:
        raise ServiceAdapterError("history exceeds 20 messages")
    normalized_history: list[dict[str, str]] = []
    for index, item in enumerate(history):
        message = _object_fields(
            item,
            f"history[{index}]",
            required={"role", "content"},
            allowed={"role", "content"},
        )
        role = message["role"]
        if role not in {"user", "assistant"}:
            raise ServiceAdapterError(
                f"history[{index}].role must be user or assistant"
            )
        normalized_history.append(
            {
                "role": role,
                "content": _bounded_text(
                    message["content"],
                    f"history[{index}].content",
                    maximum=8000,
                ),
            }
        )
    if normalized_history:
        normalized["history"] = normalized_history
    return normalized


def validate_chatqec_request(request: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and normalize a request at a ChatQEC service boundary."""
    return _normalize_chatqec_request(request)


def _validate_citation(value: Any, name: str) -> dict[str, Any]:
    citation = _object_fields(
        value,
        name,
        required={"id", "title", "source_uri", "source_revision"},
        allowed={"id", "title", "source_uri", "source_revision", "locator"},
    )
    source_uri = _bounded_text(
        citation["source_uri"], f"{name}.source_uri", maximum=4000
    )
    if not urlsplit(source_uri).scheme:
        raise ServiceAdapterError(f"{name}.source_uri must be an absolute URI")
    normalized = {
        "id": _bounded_text(
            citation["id"], f"{name}.id", maximum=128, pattern=_IDENTIFIER
        ),
        "title": _bounded_text(
            citation["title"], f"{name}.title", maximum=1000
        ),
        "source_uri": source_uri,
        "source_revision": _bounded_text(
            citation["source_revision"],
            f"{name}.source_revision",
            maximum=128,
        ),
    }
    if "locator" in citation:
        normalized["locator"] = _bounded_text(
            citation["locator"], f"{name}.locator", maximum=500
        )
    return normalized


def validate_chatqec_response(
    response: Mapping[str, Any],
    request: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate identity, provenance, accounting, and latency in an answer."""
    expected = _normalize_chatqec_request(request)
    value = _object_fields(
        response,
        "ChatQEC response",
        required=_RESPONSE_FIELDS,
        allowed=_RESPONSE_FIELDS,
    )
    normalized: dict[str, Any] = {}
    for field in ("request_id", "correlation_id", "conversation_id"):
        normalized[field] = _bounded_text(
            value[field], field, maximum=128, pattern=_IDENTIFIER
        )
        if normalized[field] != expected[field]:
            raise ServiceAdapterError(f"response {field} does not match the request")

    normalized["corpus_revision"] = _bounded_text(
        value["corpus_revision"],
        "corpus_revision",
        maximum=71,
        pattern=_CORPUS_REVISION,
    )
    if normalized["corpus_revision"] != expected["corpus_revision"]:
        raise ServiceAdapterError(
            "response corpus_revision does not match the request"
        )
    normalized["answer"] = _bounded_text(value["answer"], "answer", maximum=100_000)

    citations = value["citations"]
    if not isinstance(citations, list):
        raise ServiceAdapterError("citations must be an array")
    if len(citations) > 100:
        raise ServiceAdapterError("citations exceeds 100 entries")
    normalized["citations"] = [
        _validate_citation(citation, f"citations[{index}]")
        for index, citation in enumerate(citations)
    ]

    confidence = value["confidence"]
    if (
        isinstance(confidence, bool)
        or not isinstance(confidence, (int, float))
        or not 0 <= confidence <= 1
    ):
        raise ServiceAdapterError("confidence must be a number between 0 and 1")
    normalized["confidence"] = float(confidence)
    for field, maximum in (
        ("provider", 128),
        ("model", 128),
        ("model_response_id", 256),
    ):
        normalized[field] = _bounded_text(value[field], field, maximum=maximum)

    usage = _object_fields(
        value["usage"],
        "usage",
        required={"input_tokens", "output_tokens", "total_tokens"},
        allowed={"input_tokens", "output_tokens", "total_tokens"},
    )
    normalized_usage = {
        field: _non_negative_integer(usage[field], f"usage.{field}")
        for field in ("input_tokens", "output_tokens", "total_tokens")
    }
    if normalized_usage["total_tokens"] != (
        normalized_usage["input_tokens"] + normalized_usage["output_tokens"]
    ):
        raise ServiceAdapterError(
            "usage.total_tokens must equal input_tokens plus output_tokens"
        )
    normalized["usage"] = normalized_usage

    latency = _object_fields(
        value["latency_ms"],
        "latency_ms",
        required={"retrieval", "rerank", "generation", "total"},
        allowed={"retrieval", "rerank", "generation", "total"},
    )
    normalized_latency = {
        field: _non_negative_number(latency[field], f"latency_ms.{field}")
        for field in ("retrieval", "rerank", "generation", "total")
    }
    if normalized_latency["total"] < max(
        normalized_latency["retrieval"],
        normalized_latency["rerank"],
        normalized_latency["generation"],
    ):
        raise ServiceAdapterError(
            "latency_ms.total cannot be less than an individual stage"
        )
    normalized["latency_ms"] = normalized_latency
    return normalized


def _chatqec_endpoint(base_url: str, path: str) -> str:
    parsed = urlsplit(base_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ServiceAdapterError("ChatQEC base URL must be an HTTPS origin")
    if parsed.username is not None or parsed.password is not None:
        raise ServiceAdapterError("ChatQEC base URL must not contain credentials")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise ServiceAdapterError(
            "ChatQEC base URL must not contain a path, query, or fragment"
        )
    return f"https://{parsed.netloc}/v1{path}"


def ask_chatqec(
    base_url: str,
    request: Mapping[str, Any],
    *,
    transport: ServiceTransport,
    timeout_seconds: float = 60.0,
) -> dict[str, Any]:
    """Call the fixed JSON endpoint through an identity-configured transport."""
    normalized_request = _normalize_chatqec_request(request)
    if (
        isinstance(timeout_seconds, bool)
        or not isinstance(timeout_seconds, (int, float))
        or not 0 < timeout_seconds <= 300
    ):
        raise ServiceAdapterError("timeout_seconds must be between 0 and 300")
    body = json.dumps(
        normalized_request,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-QHPC-Correlation-ID": normalized_request["correlation_id"],
        "X-QHPC-Request-ID": normalized_request["request_id"],
    }
    try:
        status, response_headers, response_body = transport(
            url=_chatqec_endpoint(base_url, "/answers"),
            headers=headers,
            body=body,
            timeout_seconds=float(timeout_seconds),
        )
    except (OSError, TimeoutError) as error:
        raise ServiceAdapterError(f"ChatQEC transport failed: {error}") from error
    if status != 200:
        raise ServiceAdapterError(f"ChatQEC returned HTTP status {status}")
    content_type = next(
        (
            value
            for name, value in response_headers.items()
            if name.lower() == "content-type"
        ),
        "",
    )
    if content_type.split(";", 1)[0].strip().lower() != "application/json":
        raise ServiceAdapterError("ChatQEC response must be application/json")
    if not isinstance(response_body, bytes):
        raise ServiceAdapterError("ChatQEC response body must be bytes")
    if len(response_body) > _MAX_RESPONSE_BYTES:
        raise ServiceAdapterError("ChatQEC response exceeds the size limit")
    try:
        decoded = json.loads(response_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ServiceAdapterError("ChatQEC returned invalid JSON") from error
    return validate_chatqec_response(decoded, normalized_request)


def parse_chatqec_sse(
    payload: str | bytes,
    request: Mapping[str, Any],
) -> tuple[dict[str, Any], ...]:
    """Parse a bounded complete SSE response and validate its final answer."""
    normalized_request = _normalize_chatqec_request(request)
    if isinstance(payload, bytes):
        if len(payload) > _MAX_RESPONSE_BYTES:
            raise ServiceAdapterError("ChatQEC stream exceeds the size limit")
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ServiceAdapterError("ChatQEC stream must be UTF-8") from error
    elif isinstance(payload, str):
        if len(payload.encode("utf-8")) > _MAX_RESPONSE_BYTES:
            raise ServiceAdapterError("ChatQEC stream exceeds the size limit")
        text = payload
    else:
        raise ServiceAdapterError("ChatQEC stream must be text or bytes")

    frames = [
        frame
        for frame in text.replace("\r\n", "\n").replace("\r", "\n").split("\n\n")
        if frame.strip()
    ]
    if len(frames) > _MAX_SSE_EVENTS:
        raise ServiceAdapterError("ChatQEC stream exceeds the event limit")

    events: list[dict[str, Any]] = []
    for sequence, frame in enumerate(frames):
        fields: dict[str, list[str]] = {}
        for line in frame.splitlines():
            if not line or line.startswith(":"):
                continue
            name, separator, value = line.partition(":")
            if not separator or name not in {"event", "data"}:
                raise ServiceAdapterError("ChatQEC stream contains an invalid SSE field")
            fields.setdefault(name, []).append(value.lstrip(" "))
        if set(fields) != {"event", "data"} or len(fields["event"]) != 1:
            raise ServiceAdapterError(
                "each ChatQEC SSE frame requires one event and data"
            )
        try:
            event = json.loads("\n".join(fields["data"]))
        except json.JSONDecodeError as error:
            raise ServiceAdapterError("ChatQEC SSE data is not valid JSON") from error
        value = _object_fields(
            event,
            f"SSE event {sequence}",
            required={"request_id", "sequence", "event", "data"},
            allowed={"request_id", "sequence", "event", "data"},
        )
        if value["event"] != fields["event"][0]:
            raise ServiceAdapterError("ChatQEC SSE event name does not match its data")
        if value["event"] not in {"token", "citation", "final", "error"}:
            raise ServiceAdapterError("ChatQEC SSE event type is unsupported")
        if value["request_id"] != normalized_request["request_id"]:
            raise ServiceAdapterError("ChatQEC SSE request_id does not match")
        if value["sequence"] != sequence:
            raise ServiceAdapterError("ChatQEC SSE sequence is not contiguous")
        if not isinstance(value["data"], Mapping):
            raise ServiceAdapterError("ChatQEC SSE data payload must be an object")
        event_type = value["event"]
        if event_type == "token":
            data = _object_fields(
                value["data"],
                f"SSE event {sequence} data",
                required={"text"},
                allowed={"text"},
            )
            normalized_data: dict[str, Any] = {
                "text": _bounded_text(
                    data["text"],
                    f"SSE event {sequence} text",
                    maximum=32_000,
                )
            }
        elif event_type == "citation":
            data = _object_fields(
                value["data"],
                f"SSE event {sequence} data",
                required={"citation"},
                allowed={"citation"},
            )
            normalized_data = {
                "citation": _validate_citation(
                    data["citation"], f"SSE event {sequence} citation"
                )
            }
        elif event_type == "final":
            data = _object_fields(
                value["data"],
                f"SSE event {sequence} data",
                required={"response"},
                allowed={"response"},
            )
            normalized_data = {
                "response": validate_chatqec_response(
                    data["response"], normalized_request
                )
            }
        else:
            data = _object_fields(
                value["data"],
                f"SSE event {sequence} data",
                required={"code", "message"},
                allowed={"code", "message"},
            )
            code = _bounded_text(
                data["code"], "ChatQEC stream error code", maximum=64
            )
            message = _bounded_text(
                data["message"], "ChatQEC stream error message", maximum=1000
            )
            raise ServiceAdapterError(f"ChatQEC stream error {code}: {message}")
        events.append(
            {
                "request_id": value["request_id"],
                "sequence": value["sequence"],
                "event": event_type,
                "data": normalized_data,
            }
        )

    finals = [event for event in events if event["event"] == "final"]
    if len(finals) != 1 or not events or events[-1]["event"] != "final":
        raise ServiceAdapterError(
            "ChatQEC stream must end with exactly one final event"
        )
    return tuple(events)
