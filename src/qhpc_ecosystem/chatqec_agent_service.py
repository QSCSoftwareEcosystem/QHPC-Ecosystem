"""Container-only ChatQEC circuit-tool boundary for EQO.

The full model-directed ChatQEC MCP loop belongs to the separately governed
query deployment. Until that deployment has an approved provider and corpus,
this service offers a deliberately narrow direct-circuit path: it invokes the
same pinned Tsim or Stim tool code inside this container and never invents a
simulation result.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlparse

from .chatqec_readiness import MCP_DIRECT_TOOLS
from .service_adapters import (
    ServiceAdapterError,
    validate_chatqec_request,
    validate_chatqec_response,
)


_INSTRUCTION = re.compile(
    r"^\s*(?:R|RX|RY|RZ|H|S|S_DAG|X|Y|Z|T|T_DAG|CX|CNOT|CZ|M|MX|MY|MZ|"
    r"DETECTOR|OBSERVABLE_INCLUDE|QUBIT_COORDS|SHIFT_COORDS|TICK|REPEAT)\b"
)
_NON_CLIFFORD = re.compile(
    r"^\s*(?:T|T_DAG|U3|TPP|TPP_DAG|R_XX|R_YY|R_ZZ|R_PAULI|CCZ|CCX)\b"
)
_SHOTS = re.compile(r"\b(\d{1,6})\s+shots?\b", re.IGNORECASE)
PINNED_CHATQEC_REVISION = "a1ddc2e4916b1f4152fba4c94c9c7512eea0d977"
UNCONFIGURED_CORPUS_REVISION = "sha256:" + ("0" * 64)


class ChatQECAgentServiceError(RuntimeError):
    """Raised when an EQO ChatQEC MCP-agent request cannot be completed."""


def _canonical_corpus_revision(root: Path) -> tuple[str, int]:
    pages = sorted(
        page for page in (root / "knowledge" / "canonical").glob("*.md")
        if not page.name.startswith("_")
    )
    if not pages:
        return UNCONFIGURED_CORPUS_REVISION, 0
    digest = hashlib.sha256()
    for page in pages:
        digest.update(page.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(page.read_bytes()).hexdigest().encode("ascii"))
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest(), len(pages)


def _extract_circuit(question: str) -> str | None:
    """Extract only explicitly supplied Stim/Tsim instruction lines.

    This is intentionally *not* a natural-language circuit synthesizer. The
    full upstream agent handles that when a model provider is configured; the
    direct path accepts a concrete circuit and executes it verbatim. Browser
    text areas and copied JSON often represent line breaks as literal ``\\n``;
    accept that equivalent pasted form before parsing circuit instructions.
    """

    lines: list[str] = []
    normalized_question = (
        question.replace("\\r\\n", "\n")
        .replace("\\n", "\n")
        .replace("\r\n", "\n")
    )
    for raw_line in normalized_question.split("\n"):
        candidates = [raw_line]
        if ":" in raw_line:
            candidates.append(raw_line.split(":", 1)[1])
        for candidate in candidates:
            value = candidate.strip()
            if _INSTRUCTION.match(value):
                lines.append(value)
                break
    return "\n".join(lines) if lines else None


def _requested_shots(question: str) -> int:
    match = _SHOTS.search(question)
    shots = int(match.group(1)) if match else 10
    if not 1 <= shots <= 100_000:
        raise ChatQECAgentServiceError("ChatQEC direct circuit requests allow 1 to 100000 shots")
    return shots


def _format_samples(samples: Sequence[Sequence[Any]], *, label: str) -> str:
    width = max((len(row) for row in samples), default=0)
    headers = " ".join(f"D{index}" for index in range(width)) or "(no detector columns)"
    rows = [f"Shot Detector {headers}"]
    for index, row in enumerate(samples, start=1):
        values = " ".join(str(int(value)) for value in row) if row else "-"
        rows.append(f"{index} {values}")
    return f"{label}\n" + "\n".join(rows)


class DirectCircuitTools:
    """The bounded non-model path, implemented by pinned ChatQEC tool code."""

    def __call__(self, question: str) -> tuple[str, list[dict[str, str]]] | None:
        circuit = _extract_circuit(question)
        if circuit is None:
            return None
        lower = question.lower()
        wants_diagram = "diagram" in lower or "draw" in lower or "visual" in lower
        shots = _requested_shots(question)
        lines = circuit.splitlines()
        try:
            if wants_diagram:
                if any(_NON_CLIFFORD.match(line) for line in lines):
                    raise ChatQECAgentServiceError(
                        "The direct diagram path supports Stim circuits only; configure the full ChatQEC MCP agent for a non-Clifford visualization."
                    )
                from chatqec_mcp_tools.tools.stim_diagram import (  # type: ignore[import-not-found]
                    StimDiagramInput,
                    stim_diagram,
                )

                result = stim_diagram(StimDiagramInput(circuit=circuit))
                if not result.ok:
                    raise ChatQECAgentServiceError(result.error_message or "Stim diagram failed")
                return (
                    "ChatQEC ran `stim_diagram` in its admitted container. "
                    "The current ChatQEC response contract does not persist SVG artifacts; "
                    "use the Workbench Stim Diagram operation when you need a saved SVG.",
                    [{"name": "stim_diagram", "status": "completed", "summary": "SVG diagram rendered"}],
                )

            if any(_NON_CLIFFORD.match(line) for line in lines):
                from chatqec_mcp_tools.tools.tsim_simulate import (  # type: ignore[import-not-found]
                    TsimSimulateInput,
                    tsim_simulate,
                )

                result = tsim_simulate(TsimSimulateInput(circuit=circuit, shots=shots))
                if not result.ok:
                    raise ChatQECAgentServiceError(result.error_message or "Tsim simulation failed")
                samples = result.samples_preview
                fired = sum(1 for row in samples if any(int(value) for value in row))
                previewed = len(samples)
                text = (
                    f"The Tsim circuit simulated successfully over {result.shots} shots.\n\n"
                    + _format_samples(samples, label=f"Detector Sample Output ({result.shots} shots)")
                    + f"\n\n{fired} of {previewed} previewed shots fired a detector; "
                    f"{previewed - fired} did not.\n\n```text\n{circuit}\n```"
                )
                return (
                    text,
                    [{"name": "tsim_simulate", "status": "completed", "summary": result.summary}],
                )

            from chatqec_mcp_tools.tools.stim_simulate import (  # type: ignore[import-not-found]
                StimSimulateInput,
                stim_simulate,
            )

            result = stim_simulate(StimSimulateInput(circuit=circuit, shots=shots))
            if not result.ok:
                raise ChatQECAgentServiceError(result.error_message or "Stim simulation failed")
            text = (
                f"The Stim circuit simulated successfully over {result.shots} shots.\n\n"
                + _format_samples(result.samples_preview, label=f"Detector Sample Output ({result.shots} shots)")
                + f"\n\n```stim\n{circuit}\n```"
            )
            return (
                text,
                [{"name": "stim_simulate", "status": "completed", "summary": result.summary}],
            )
        except ChatQECAgentServiceError:
            raise
        except Exception as error:  # Tool libraries preserve their own safe diagnostics.
            raise ChatQECAgentServiceError("ChatQEC circuit tool failed") from error


class ChatQECMCPAgentResponder:
    """Contained ChatQEC tool responder for explicit Stim/Tsim circuits."""

    def __init__(
        self,
        deployment: object | None,
        *,
        source_root: str | Path = "/opt/chatqec",
        direct_tools: Callable[[str], tuple[str, list[dict[str, str]]] | None] | None = None,
    ) -> None:
        self.deployment = deployment
        self.source_root = Path(source_root)
        self.corpus_revision, self.pages = _canonical_corpus_revision(self.source_root)
        self.direct_tools = direct_tools or DirectCircuitTools()
        # The full model/RAG agent is deliberately activated only through the
        # separately governed query deployment profile.  Local direct tools do
        # not import model SDKs, Qdrant, or any provider credentials.
        self.upstream = None

    def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "chatqec",
            "mode": MCP_DIRECT_TOOLS,
            "source_revision": PINNED_CHATQEC_REVISION,
            "corpus_revision": self.corpus_revision,
            "pages": self.pages,
            "tool_execution": True,
            "readiness": {
                "source": "ready",
                "model": "not-configured",
                "qdrant": "not-provisioned",
                "corpus": "ready" if self.pages else "not-provisioned",
                "embeddings": "not-configured",
                "reranker": "not-configured",
                "knowledge": "disabled",
            },
            "capabilities": {
                "model_rag": False,
                "streaming": True,
                "source_ledger": False,
                "tool_proposals": False,
                "mcp_tools": True,
            },
        }

    def answer(self, request: Mapping[str, Any]) -> dict[str, Any]:
        normalized = validate_chatqec_request(request)
        direct = self.direct_tools(normalized["question"])
        if direct is None:
            raise ServiceAdapterError(
                "ChatQEC's model-backed agent is not configured. Supply a concrete Stim/Tsim circuit, or configure the approved provider, Qdrant corpus, and MCP profile."
            )
        if normalized["corpus_revision"] != self.corpus_revision:
            raise ServiceAdapterError("request corpus_revision does not match the active corpus")
        answer, tool_calls = direct
        started = time.monotonic()
        input_tokens = max(1, len(normalized["question"].split()) * 4 // 3)
        output_tokens = max(1, len(answer.split()) * 4 // 3)
        response = {
            "request_id": normalized["request_id"],
            "correlation_id": normalized["correlation_id"],
            "conversation_id": normalized["conversation_id"],
            "answer": answer,
            "citations": [],
            "confidence": 0.9,
            "provider": "chatqec-mcp-tools",
            "model": tool_calls[0]["name"],
            "model_response_id": "mcp-" + hashlib.sha256(
                (normalized["request_id"] + "\0" + answer).encode("utf-8")
            ).hexdigest()[:24],
            "corpus_revision": self.corpus_revision,
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
            },
            "latency_ms": {"retrieval": 0.0, "rerank": 0.0, "generation": 0.0, "total": round((time.monotonic() - started) * 1000, 3)},
            "tool_calls": tool_calls,
        }
        return validate_chatqec_response(response, normalized)


def _handler_for(
    responder: ChatQECMCPAgentResponder,
    identity_token: str,
) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "EQOChatQECMCPAgent/0.1"

        def log_message(self, _format: str, *_args: Any) -> None:
            return

        def _json(self, status: HTTPStatus, value: Mapping[str, Any]) -> None:
            payload = json.dumps(value, sort_keys=True).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(payload)

        def _authorized(self) -> bool:
            return hmac.compare_digest(
                self.headers.get("Authorization", ""), f"Bearer {identity_token}"
            )

        def _body(self) -> dict[str, Any]:
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError as error:
                raise ServiceAdapterError("invalid Content-Length") from error
            if not 0 < length <= 64_000:
                raise ServiceAdapterError("request body size is invalid")
            try:
                value = json.loads(self.rfile.read(length))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise ServiceAdapterError("request body is not valid JSON") from error
            if not isinstance(value, dict):
                raise ServiceAdapterError("request body must be an object")
            return value

        def do_GET(self) -> None:  # noqa: N802
            if urlparse(self.path).path == "/v1/health":
                self._json(HTTPStatus.OK, responder.health())
                return
            self._json(HTTPStatus.NOT_FOUND, {"error": "route not found"})

        def do_POST(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path not in {"/v1/answers", "/v1/answers/stream"}:
                self._json(HTTPStatus.NOT_FOUND, {"error": "route not found"})
                return
            if not self._authorized():
                self._json(HTTPStatus.UNAUTHORIZED, {"error": "workload identity required"})
                return
            try:
                response = responder.answer(self._body())
            except (ServiceAdapterError, ChatQECAgentServiceError) as error:
                self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": str(error)})
                return
            if path == "/v1/answers":
                self._json(HTTPStatus.OK, response)
                return
            events: list[dict[str, Any]] = []
            for offset in range(0, len(response["answer"]), 4096):
                events.append(
                    {
                        "request_id": response["request_id"],
                        "sequence": len(events),
                        "event": "token",
                        "data": {"text": response["answer"][offset : offset + 4096]},
                    }
                )
            events.append(
                {
                    "request_id": response["request_id"],
                    "sequence": len(events),
                    "event": "final",
                    "data": {"response": response},
                }
            )
            payload = "".join(
                f"event: {event['event']}\n"
                f"data: {json.dumps(event, sort_keys=True)}\n\n"
                for event in events
            ).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(payload)

    return Handler


def serve_agent(
    responder: ChatQECMCPAgentResponder,
    identity_token: str,
    *,
    host: str,
    port: int,
) -> None:
    if host not in {"127.0.0.1", "::1", "localhost", "0.0.0.0"}:
        raise ChatQECAgentServiceError("ChatQEC agent must bind to loopback or its container interface")
    if len(identity_token) < 32:
        raise ChatQECAgentServiceError("ChatQEC agent workload identity must be at least 32 characters")
    server = ThreadingHTTPServer((host, port), _handler_for(responder, identity_token))
    server.daemon_threads = True
    with server:
        server.serve_forever()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="eqo-chatqec-agent")
    parser.add_argument("--host", default=os.environ.get("QHPC_CHATQEC_LISTEN_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("QHPC_CHATQEC_LISTEN_PORT", "8096")))
    options = parser.parse_args(argv)
    identity_token = os.environ.get("QHPC_CHATQEC_IDENTITY_TOKEN", "")
    responder = ChatQECMCPAgentResponder(None)
    serve_agent(responder, identity_token, host=options.host, port=options.port)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
