"""Contained ChatQEC tools with a pinned local source ledger.

EQO Local always executes supplied Stim/Tsim circuits through the pinned tool
code.  It also retrieves concise excerpts from the immutable canonical ChatQEC
bundle, returns source-ledger citations, and can pass that evidence to an
explicitly configured OpenAI Responses model.  This is deliberately distinct
from the separately governed upstream Qdrant deployment: it has no vector
index, embedding model, reranker, or model-directed tool proposals.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import time
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

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
_OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
_OPENAI_MAX_OUTPUT_TOKENS = 4096
_CANONICAL_SOURCE_URL = "https://github.com/QSCSoftwareEcosystem/ChatQEC"
_MODEL_INSTRUCTIONS = """You are ChatQEC, a careful quantum-error-correction assistant.
Answer concisely, identify assumptions, and distinguish an explanation from an
executed result. If a local circuit-tool result is supplied, use it as the only
claim that a simulation executed. Raw measurement samples are not detector-event
samples: call them measurement data. Treat the supplied pinned source-ledger
excerpts as the only local corpus evidence. When an excerpt supports a factual
claim, mark it with its matching ``[S#]`` identifier; do not invent citations.
Do not claim access to external tools, sources, or hardware beyond the supplied
local result and source ledger."""
_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9+.-]*")
_WIKI_LINK = re.compile(r"\[\[([^\]]+)\]\]")
_TITLE = re.compile(r"^title:\s*(?:\"([^\"]+)\"|'([^']+)'|(.+?))\s*$", re.MULTILINE)
_H1 = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
_STOP_WORDS = {
    "a", "an", "and", "are", "can", "do", "does", "for", "from", "how",
    "in", "is", "it", "of", "on", "or", "the", "to", "what", "why", "with",
}


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


def _tokens(value: str) -> set[str]:
    """Normalize a small lexical vocabulary without a model or embedding index."""

    result: set[str] = set()
    for raw in _WORD.findall(value):
        token = raw.lower()
        if len(token) <= 1 or token in _STOP_WORDS:
            continue
        result.add(token)
        for part in re.split(r"[-_]", token):
            if len(part) > 1 and part not in _STOP_WORDS:
                result.add(part)
        if len(token) > 5 and token.endswith("ing"):
            result.add(token[:-3])
        elif len(token) > 4 and token.endswith("ed"):
            result.add(token[:-2])
        elif len(token) > 4 and token.endswith("s"):
            result.add(token[:-1])
    return result


def _plain_wiki_links(value: str) -> str:
    """Make canonical wiki links useful source context for a model and reader."""

    def label(match: re.Match[str]) -> str:
        target, separator, display = match.group(1).partition("|")
        return display if separator else target.replace("-", " ")

    return _WIKI_LINK.sub(label, value)


@dataclass(frozen=True)
class LocalCorpusPage:
    """One immutable canonical page, retained with its exact source digest."""

    slug: str
    title: str
    relative_path: str
    digest: str
    lines: tuple[str, ...]


@dataclass(frozen=True)
class SourceEvidence:
    """A cited local excerpt selected by deterministic lexical retrieval."""

    page: LocalCorpusPage
    score: int
    locator: str
    excerpt: str

    def citation(self) -> dict[str, str]:
        return {
            "id": f"canonical:{self.page.slug}",
            "title": self.page.title,
            "source_uri": (
                f"{_CANONICAL_SOURCE_URL}/blob/{PINNED_CHATQEC_REVISION}/"
                f"{self.page.relative_path}"
            ),
            "source_revision": self.page.digest,
            "locator": self.locator,
        }


class LocalSourceLedger:
    """Deterministic source retrieval over the canonical pages bundled in the image.

    This is intentionally small and auditable.  It does not claim vector search
    or semantic reranking, and every returned result carries a stable page digest
    plus an exact line locator.
    """

    def __init__(self, root: Path) -> None:
        canonical_root = root / "knowledge" / "canonical"
        self.root = root
        self.pages = tuple(
            self._load_page(path)
            for path in sorted(canonical_root.glob("*.md"))
            if not path.name.startswith("_")
        )

    def _load_page(self, path: Path) -> LocalCorpusPage:
        payload = path.read_bytes()
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ChatQECAgentServiceError(
                f"canonical ChatQEC page is not UTF-8: {path.name}"
            ) from error
        title_match = _TITLE.search(text)
        h1_match = _H1.search(text)
        title = next(
            (
                value.strip()
                for value in (
                    title_match.group(1) if title_match else None,
                    title_match.group(2) if title_match else None,
                    title_match.group(3) if title_match else None,
                    h1_match.group(1) if h1_match else None,
                )
                if value and value.strip()
            ),
            path.stem.replace("-", " ").title(),
        )
        return LocalCorpusPage(
            slug=path.stem,
            title=title,
            relative_path=path.relative_to(self.root).as_posix(),
            digest="sha256:" + hashlib.sha256(payload).hexdigest(),
            lines=tuple(text.splitlines()),
        )

    @staticmethod
    def _page_score(page: LocalCorpusPage, question: str) -> int:
        normalized = " ".join(question.lower().split())
        query_tokens = _tokens(question)
        names = (page.title.lower(), page.slug.replace("-", " ").lower())
        name_tokens = _tokens(" ".join(names))
        body_tokens = _tokens("\n".join(page.lines))
        phrase_score = 20 if any(name in normalized for name in names) else 0
        return (
            phrase_score
            + 5 * len(query_tokens & name_tokens)
            + min(4, len(query_tokens & body_tokens))
        )

    @staticmethod
    def _excerpt(page: LocalCorpusPage, question: str) -> tuple[str, str]:
        query_tokens = _tokens(question)
        best_index = 0
        best_score = -1
        for index, line in enumerate(page.lines):
            stripped = line.strip()
            if not stripped or stripped == "---":
                continue
            if stripped.startswith("# "):
                # The H1 repeats the page title and is never the most useful
                # evidence excerpt when a question targets a specific section.
                continue
            score = len(query_tokens & _tokens(stripped))
            if stripped.startswith("##"):
                score += 2
            if score > best_score:
                best_score = score
                best_index = index
        start = max(0, best_index - 1)
        end = min(len(page.lines), best_index + 6)
        excerpt_lines = [
            _plain_wiki_links(line.strip())
            for line in page.lines[start:end]
            if line.strip() and line.strip() != "---" and not line.startswith("title:")
        ]
        excerpt = " ".join(excerpt_lines).strip()
        if not excerpt:
            excerpt = page.title
            start = 0
            end = 1
        return excerpt[:1800], f"{page.relative_path}:L{start + 1}-L{end}"

    def retrieve(self, question: str, *, limit: int = 3) -> tuple[SourceEvidence, ...]:
        ranked = [
            (self._page_score(page, question), page)
            for page in self.pages
        ]
        ranked_matches = sorted(
            ((score, page) for score, page in ranked if score >= 5),
            key=lambda item: (-item[0], item[1].slug),
        )
        if not ranked_matches:
            return ()
        strongest = ranked_matches[0][0]
        selected = [
            item for item in ranked_matches
            if item[0] >= max(5, strongest * 0.5)
        ][:limit]
        return tuple(
            SourceEvidence(
                page=page,
                score=score,
                locator=locator,
                excerpt=excerpt,
            )
            for score, page in selected
            for excerpt, locator in (self._excerpt(page, question),)
        )

    @staticmethod
    def context(evidence: Sequence[SourceEvidence]) -> str:
        if not evidence:
            return ""
        blocks = ["Pinned ChatQEC source ledger (not external browsing):"]
        for index, item in enumerate(evidence, start=1):
            blocks.append(
                f"[S{index}] {item.page.title} — {item.locator}\n{item.excerpt}"
            )
        return "\n\n".join(blocks)

    @staticmethod
    def extractive_answer(evidence: Sequence[SourceEvidence]) -> str:
        if not evidence:
            raise ChatQECAgentServiceError("no source evidence is available")
        snippets = [
            f"**{item.page.title} [S{index}].** {item.excerpt}"
            for index, item in enumerate(evidence, start=1)
        ]
        return "\n\n".join(snippets)

    @staticmethod
    def evidence_coverage(
        evidence: Sequence[SourceEvidence], *, executed_tool: bool
    ) -> float:
        """Report evidence coverage, never a model-correctness probability."""

        if not evidence:
            return 0.55 if executed_tool else 0.15
        strongest = evidence[0].score
        coverage = 0.45 + min(0.33, strongest * 0.015)
        coverage += min(0.10, (len(evidence) - 1) * 0.05)
        if executed_tool:
            coverage += 0.05
        return round(min(0.95, coverage), 4)


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


def _format_samples(
    samples: Sequence[Sequence[Any]], *, label: str, column_prefix: str = "M"
) -> str:
    width = max((len(row) for row in samples), default=0)
    headers = " ".join(f"{column_prefix}{index}" for index in range(width)) or "(no columns)"
    rows = [f"Shot Measurement {headers}"]
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
                    + _format_samples(samples, label=f"Measurement Sample Output ({result.shots} shots)")
                    + f"\n\n{fired} of {previewed} previewed shots contained a non-zero measurement; "
                    f"{previewed - fired} did not. These are raw measurements, not detector events."
                    f"\n\n```text\n{circuit}\n```"
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
                + _format_samples(result.samples_preview, label=f"Measurement Sample Output ({result.shots} shots)")
                + "\n\nThese are raw measurements, not detector-event samples."
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


@dataclass(frozen=True)
class OpenAIResponse:
    """The limited provider data allowed to cross the local service boundary."""

    text: str
    response_id: str
    input_tokens: int
    output_tokens: int


OpenAITransport = Callable[[Request, float], Mapping[str, Any]]


def _openai_response_text(payload: Mapping[str, Any]) -> str:
    direct = payload.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    status = payload.get("status")
    if status == "incomplete":
        details = payload.get("incomplete_details")
        reason = details.get("reason") if isinstance(details, Mapping) else None
        if reason == "max_output_tokens":
            raise ChatQECAgentServiceError(
                "OpenAI model response was incomplete because its output-token "
                "budget was exhausted"
            )
        if reason == "content_filter":
            raise ChatQECAgentServiceError(
                "OpenAI model response was stopped by its content filter"
            )
        raise ChatQECAgentServiceError("OpenAI model response was incomplete")
    if status == "failed":
        raise ChatQECAgentServiceError("OpenAI model response failed")
    output = payload.get("output")
    if not isinstance(output, list):
        raise ChatQECAgentServiceError("OpenAI model response did not contain answer text")
    fragments: list[str] = []
    for item in output:
        if not isinstance(item, Mapping) or item.get("type") != "message":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if (
                isinstance(part, Mapping)
                and part.get("type") == "output_text"
                and isinstance(part.get("text"), str)
            ):
                fragments.append(part["text"])
    text = "".join(fragments).strip()
    if not text:
        raise ChatQECAgentServiceError("OpenAI model response did not contain answer text")
    return text


def _openai_usage(payload: Mapping[str, Any], name: str) -> int:
    usage = payload.get("usage")
    value = usage.get(name) if isinstance(usage, Mapping) else 0
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


class OpenAIResponsesBackend:
    """Small stdlib-only OpenAI Responses client for the optional local mode."""

    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        transport: OpenAITransport | None = None,
    ) -> None:
        if not model.strip():
            raise ChatQECAgentServiceError("an OpenAI model identifier is required")
        if not api_key.strip():
            raise ChatQECAgentServiceError("an OpenAI API key is required")
        self.model = model.strip()
        self.api_key = api_key.strip()
        self.transport = transport or self._request

    @staticmethod
    def _request(request: Request, timeout_seconds: float) -> Mapping[str, Any]:
        try:
            with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310 - fixed HTTPS origin
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            raise ChatQECAgentServiceError(
                f"OpenAI model request failed (HTTP {error.code})"
            ) from error
        except (OSError, TimeoutError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ChatQECAgentServiceError("OpenAI model request failed") from error
        if not isinstance(payload, Mapping):
            raise ChatQECAgentServiceError("OpenAI model response was invalid")
        return payload

    def __call__(
        self,
        question: str,
        history: Sequence[Mapping[str, str]],
        tool_result: str | None,
        source_context: str = "",
    ) -> OpenAIResponse:
        messages = [
            {"role": item["role"], "content": item["content"]}
            for item in history
        ]
        final_input = question
        if tool_result is not None:
            final_input += (
                "\n\nA bounded local circuit tool executed before this request. "
                "Use its result faithfully; do not call raw measurement samples detector events.\n"
                "--- local tool result ---\n"
                + tool_result[:24_000]
                + "\n--- end local tool result ---"
            )
        if source_context:
            final_input += (
                "\n\n--- pinned source ledger ---\n"
                + source_context[:12_000]
                + "\n--- end pinned source ledger ---"
            )
        messages.append({"role": "user", "content": final_input})
        body = json.dumps(
            {
                "model": self.model,
                "store": False,
                # GPT-5.6 defaults to medium reasoning effort.  This
                # interactive assistant uses low effort and leaves enough
                # shared output budget for both reasoning and visible text.
                "reasoning": {"effort": "low", "context": "current_turn"},
                "max_output_tokens": _OPENAI_MAX_OUTPUT_TOKENS,
                "instructions": _MODEL_INSTRUCTIONS,
                "input": messages,
            },
            separators=(",", ":"),
        ).encode("utf-8")
        request = Request(
            _OPENAI_RESPONSES_URL,
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        payload = self.transport(request, 60.0)
        response_id = payload.get("id")
        if not isinstance(response_id, str) or not response_id.strip():
            response_id = "openai-" + hashlib.sha256(body).hexdigest()[:24]
        return OpenAIResponse(
            text=_openai_response_text(payload),
            response_id=response_id[:256],
            input_tokens=_openai_usage(payload, "input_tokens"),
            output_tokens=_openai_usage(payload, "output_tokens"),
        )


class ChatQECMCPAgentResponder:
    """Contained ChatQEC tool responder with an optional model explainer."""

    def __init__(
        self,
        deployment: object | None,
        *,
        source_root: str | Path = "/opt/chatqec",
        direct_tools: Callable[[str], tuple[str, list[dict[str, str]]] | None] | None = None,
        openai_model: str | None = None,
        openai_api_key: str | None = None,
        model_backend: Callable[
            [str, Sequence[Mapping[str, str]], str | None, str], OpenAIResponse
        ] | None = None,
    ) -> None:
        self.deployment = deployment
        self.source_root = Path(source_root)
        self.corpus_revision, self.pages = _canonical_corpus_revision(self.source_root)
        self.source_ledger = LocalSourceLedger(self.source_root)
        if len(self.source_ledger.pages) != self.pages:
            raise ChatQECAgentServiceError(
                "the canonical ChatQEC source ledger does not match its corpus"
            )
        self.direct_tools = direct_tools or DirectCircuitTools()
        if bool(openai_model) != bool(openai_api_key):
            raise ChatQECAgentServiceError(
                "the local OpenAI ChatQEC mode requires both a model and an API key"
            )
        if model_backend is not None and not openai_model:
            raise ChatQECAgentServiceError("a model backend requires an OpenAI model identifier")
        self.openai_model = openai_model.strip() if openai_model else None
        # The key is supplied only to the container environment.  Retrieval is
        # deterministic over the pinned local pages, never an implicit external
        # provider, vector store, or embedding service.
        self.model_backend = model_backend or (
            OpenAIResponsesBackend(model=self.openai_model, api_key=openai_api_key or "")
            if self.openai_model
            else None
        )
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
                "model": "ready" if self.model_backend is not None else "not-configured",
                "qdrant": "not-provisioned",
                "corpus": "ready" if self.pages else "not-provisioned",
                "embeddings": "not-configured",
                "reranker": "not-configured",
                "knowledge": "ready" if self.pages else "not-provisioned",
            },
            "capabilities": {
                "model_rag": self.model_backend is not None and bool(self.pages),
                "streaming": True,
                "source_ledger": bool(self.pages),
                "tool_proposals": False,
                "mcp_tools": True,
            },
        }

    def answer(self, request: Mapping[str, Any]) -> dict[str, Any]:
        normalized = validate_chatqec_request(request)
        if normalized["corpus_revision"] != self.corpus_revision:
            raise ServiceAdapterError("request corpus_revision does not match the active corpus")
        started = time.monotonic()
        retrieval_started = started
        evidence = self.source_ledger.retrieve(normalized["question"])
        retrieval_ms = round((time.monotonic() - retrieval_started) * 1000, 3)
        direct = self.direct_tools(normalized["question"])
        if direct is None and self.model_backend is None and not evidence:
            raise ServiceAdapterError(
                "ChatQEC could not find enough evidence in its pinned canonical corpus. "
                "Ask about a QEC code, decoder, noise model, or fault-tolerance topic; "
                "or configure the optional OpenAI model for a broader explanation."
            )
        answer, tool_calls = direct or (None, [])
        generation_ms = 0.0
        if self.model_backend is not None:
            generation_started = time.monotonic()
            try:
                model_response = self.model_backend(
                    normalized["question"],
                    normalized.get("history", ()),
                    answer,
                    self.source_ledger.context(evidence),
                )
            except ChatQECAgentServiceError:
                # A reasoning response can end before producing visible text.
                # Preserve a useful, attributable local response instead of
                # turning a verified tool run or cited corpus answer into a
                # gateway failure.  With neither, surface the model error.
                if answer is None and not evidence:
                    raise
                local_answer = (
                    answer
                    if answer is not None
                    else self.source_ledger.extractive_answer(evidence)
                )
                response_answer = (
                    local_answer
                    + "\n\nThe configured OpenAI model did not return visible text for "
                    "this request, so ChatQEC is showing the verified local result "
                    "and pinned source evidence instead."
                )
                provider = "chatqec-local"
                model = "verified-local-fallback-v1"
                model_response_id = "fallback-" + hashlib.sha256(
                    (normalized["request_id"] + "\0" + response_answer).encode("utf-8")
                ).hexdigest()[:24]
                input_tokens = max(1, len(normalized["question"].split()) * 4 // 3)
                output_tokens = max(1, len(response_answer.split()) * 4 // 3)
            else:
                response_answer = model_response.text
                provider = "openai"
                model = self.openai_model or "openai"
                model_response_id = model_response.response_id
                input_tokens = model_response.input_tokens
                output_tokens = model_response.output_tokens
            generation_ms = round((time.monotonic() - generation_started) * 1000, 3)
        elif answer is not None:
            response_answer = answer
            provider = "chatqec-mcp-tools"
            model = tool_calls[0]["name"]
            model_response_id = "mcp-" + hashlib.sha256(
                (normalized["request_id"] + "\0" + response_answer).encode("utf-8")
            ).hexdigest()[:24]
            input_tokens = max(1, len(normalized["question"].split()) * 4 // 3)
            output_tokens = max(1, len(response_answer.split()) * 4 // 3)
        else:
            response_answer = self.source_ledger.extractive_answer(evidence)
            provider = "chatqec-local"
            model = "canonical-source-ledger-v1"
            model_response_id = "ledger-" + hashlib.sha256(
                (normalized["request_id"] + "\0" + response_answer).encode("utf-8")
            ).hexdigest()[:24]
            input_tokens = max(1, len(normalized["question"].split()) * 4 // 3)
            output_tokens = max(1, len(response_answer.split()) * 4 // 3)
        response = {
            "request_id": normalized["request_id"],
            "correlation_id": normalized["correlation_id"],
            "conversation_id": normalized["conversation_id"],
            "answer": response_answer,
            "citations": [item.citation() for item in evidence],
            # The response field is contractual.  The Workbench labels it as
            # evidence coverage because it measures retrieved support, not a
            # calibrated probability that a model statement is correct.
            "confidence": self.source_ledger.evidence_coverage(
                evidence, executed_tool=bool(tool_calls)
            ),
            "provider": provider,
            "model": model,
            "model_response_id": model_response_id,
            "corpus_revision": self.corpus_revision,
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
            },
            "latency_ms": {"retrieval": retrieval_ms, "rerank": 0.0, "generation": generation_ms, "total": round((time.monotonic() - started) * 1000, 3)},
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
    responder = ChatQECMCPAgentResponder(
        None,
        openai_model=os.environ.get("QHPC_CHATQEC_OPENAI_MODEL"),
        openai_api_key=os.environ.get("OPENAI_API_KEY"),
    )
    serve_agent(responder, identity_token, host=options.host, port=options.port)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
