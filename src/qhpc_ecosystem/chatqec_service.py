"""Loopback-only ChatQEC development service over the pinned canonical corpus."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import subprocess
import time
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import urlparse

import yaml

from .contract import validate_contract
from .service_adapters import (
    ServiceAdapterError,
    validate_chatqec_request,
    validate_chatqec_response,
)


class ChatQECServiceError(RuntimeError):
    """Raised when the development service cannot be prepared or served."""


@dataclass(frozen=True)
class CanonicalPage:
    slug: str
    title: str
    aliases: tuple[str, ...]
    body: str
    relative_path: str
    digest: str


_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9+.-]*")
_WIKI_LINK = re.compile(r"\[\[([^\]]+)\]\]")
_STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "can",
    "do",
    "does",
    "for",
    "from",
    "how",
    "in",
    "is",
    "it",
    "of",
    "on",
    "the",
    "to",
    "what",
    "why",
    "with",
}


def _repository_identity(value: str) -> str:
    normalized = value.strip().rstrip("/")
    return normalized[:-4] if normalized.endswith(".git") else normalized


def _run(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:
        raise ChatQECServiceError(f"cannot execute {command[0]}: {error}") from error


class ChatQECSource:
    """Prepare and verify the exact ChatQEC source selected by the contract."""

    def __init__(
        self,
        repository: str,
        revision: str,
        checkout: str | Path,
    ) -> None:
        self.repository = repository
        self.revision = revision
        self.checkout = Path(checkout).expanduser().resolve()

    @classmethod
    def from_contract(
        cls,
        contract_path: str | Path,
        checkout: str | Path | None = None,
    ) -> ChatQECSource:
        document = validate_contract("service-interface", contract_path)
        source = document["metadata"]["source"]
        destination = (
            Path(checkout)
            if checkout is not None
            else Path.cwd()
            / ".qhpc"
            / "services"
            / f"chatqec-{source['revision'][:12]}"
        )
        return cls(source["url"], source["revision"], destination)

    def _checked(self, command: Sequence[str], action: str) -> str:
        result = _run(command)
        if result.returncode:
            detail = result.stderr.strip() or result.stdout.strip() or "no output"
            raise ChatQECServiceError(f"{action} failed: {detail}")
        return result.stdout.strip()

    def _git(self, *arguments: str) -> tuple[str, ...]:
        return ("git", "-C", str(self.checkout), *arguments)

    def prepare(self) -> Path:
        if self.checkout.exists() and not self.checkout.is_dir():
            raise ChatQECServiceError(
                f"ChatQEC checkout is not a directory: {self.checkout}"
            )
        if not (self.checkout / ".git").is_dir():
            if self.checkout.exists() and any(self.checkout.iterdir()):
                raise ChatQECServiceError(
                    "ChatQEC checkout is non-empty and is not a Git repository"
                )
            self.checkout.parent.mkdir(parents=True, exist_ok=True)
            self._checked(
                (
                    "git",
                    "clone",
                    self.repository,
                    str(self.checkout),
                ),
                "ChatQEC clone",
            )

        origin = self._checked(
            self._git("remote", "get-url", "origin"),
            "ChatQEC origin check",
        )
        if _repository_identity(origin) != _repository_identity(self.repository):
            raise ChatQECServiceError(f"unexpected ChatQEC origin: {origin}")

        worktree_is_empty = not any(
            child.name != ".git" for child in self.checkout.iterdir()
        )
        head = self._checked(self._git("rev-parse", "HEAD"), "ChatQEC HEAD check")
        if head != self.revision or worktree_is_empty:
            # A failed generated clone can leave only .git plus an index whose
            # tracked files all appear deleted. That state has no user files to
            # preserve, so it is safe to materialize the pinned commit.
            if worktree_is_empty:
                lookup = _run(
                    self._git("cat-file", "-e", f"{self.revision}^{{commit}}")
                )
                if lookup.returncode:
                    self._checked(
                        self._git("fetch", "--depth", "1", "origin", self.revision),
                        "ChatQEC revision fetch",
                    )
                self._checked(
                    self._git("checkout", "--detach", "--force", self.revision),
                    "ChatQEC interrupted checkout recovery",
                )
                self.verify()
                return self.checkout
            dirty = self._checked(
                self._git("status", "--porcelain"),
                "ChatQEC worktree check",
            )
            if dirty:
                raise ChatQECServiceError(
                    "ChatQEC checkout has tracked or untracked changes and "
                    "cannot be repinned"
                )
            lookup = _run(
                self._git("cat-file", "-e", f"{self.revision}^{{commit}}")
            )
            if lookup.returncode:
                self._checked(
                    self._git("fetch", "--depth", "1", "origin", self.revision),
                    "ChatQEC revision fetch",
                )
            self._checked(
                self._git("checkout", "--detach", self.revision),
                "ChatQEC revision checkout",
            )

        self.verify()
        return self.checkout

    def verify(self) -> None:
        if not (self.checkout / ".git").is_dir():
            raise ChatQECServiceError("ChatQEC checkout is not prepared")
        head = self._checked(self._git("rev-parse", "HEAD"), "ChatQEC revision check")
        if head != self.revision:
            raise ChatQECServiceError(
                f"ChatQEC revision is {head}; expected {self.revision}"
            )
        dirty = self._checked(
            self._git("status", "--porcelain"),
            "ChatQEC worktree check",
        )
        if dirty:
            raise ChatQECServiceError(
                "ChatQEC checkout contains tracked or untracked changes"
            )
        if not (self.checkout / "LICENSE").is_file():
            raise ChatQECServiceError("ChatQEC source license file is missing")
        canonical = self.checkout / "knowledge" / "canonical"
        if not canonical.is_dir() or not any(canonical.glob("*.md")):
            raise ChatQECServiceError("ChatQEC canonical corpus is missing")


def _parse_page(path: Path, root: Path) -> CanonicalPage:
    payload = path.read_bytes()
    text = payload.decode("utf-8")
    if not text.startswith("---\n"):
        raise ChatQECServiceError(f"canonical page lacks frontmatter: {path.name}")
    try:
        _, raw_metadata, body = text.split("---", 2)
    except ValueError as error:
        raise ChatQECServiceError(
            f"canonical page has invalid frontmatter: {path.name}"
        ) from error
    metadata = yaml.safe_load(raw_metadata)
    if not isinstance(metadata, dict):
        raise ChatQECServiceError(f"canonical metadata is invalid: {path.name}")
    slug = metadata.get("topic_slug")
    title = metadata.get("title")
    aliases = metadata.get("aliases", [])
    if not isinstance(slug, str) or not slug:
        raise ChatQECServiceError(f"canonical topic_slug is invalid: {path.name}")
    if not isinstance(title, str) or not title:
        raise ChatQECServiceError(f"canonical title is invalid: {path.name}")
    if not isinstance(aliases, list) or any(
        not isinstance(value, str) or not value for value in aliases
    ):
        raise ChatQECServiceError(f"canonical aliases are invalid: {path.name}")
    relative = path.resolve().relative_to(root.resolve()).as_posix()
    return CanonicalPage(
        slug=slug,
        title=title,
        aliases=tuple(aliases),
        body=body.strip(),
        relative_path=relative,
        digest="sha256:" + hashlib.sha256(payload).hexdigest(),
    )


def _tokens(value: str) -> set[str]:
    result: set[str] = set()
    for raw in _WORD.findall(value):
        token = raw.lower()
        if len(token) <= 1 or token in _STOP_WORDS:
            continue
        result.add(token)
        if len(token) > 5 and token.endswith("ing"):
            result.add(token[:-3])
        elif len(token) > 4 and token.endswith("ed"):
            result.add(token[:-2])
        elif len(token) > 4 and token.endswith("s"):
            result.add(token[:-1])
    return result


def _plain_wiki_links(value: str) -> str:
    def label(match: re.Match[str]) -> str:
        target, separator, display = match.group(1).partition("|")
        return display if separator else target.replace("-", " ")

    return _WIKI_LINK.sub(label, value)


def _paragraphs(value: str) -> list[str]:
    return [
        _plain_wiki_links(block.strip())
        for block in re.split(r"\n\s*\n", value)
        if block.strip() and not block.lstrip().startswith("#")
    ]


def _sections(body: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, list[str]]] = []
    current_title = ""
    current_lines: list[str] = []
    for line in body.splitlines():
        if line.startswith("## "):
            if current_lines:
                sections.append((current_title, current_lines))
            current_title = line[3:].strip()
            current_lines = []
        elif not line.startswith("# "):
            current_lines.append(line)
    if current_lines:
        sections.append((current_title, current_lines))
    return [(title, "\n".join(lines).strip()) for title, lines in sections]


class CanonicalChatQEC:
    """Cited extractive development backend over ChatQEC-owned source pages."""

    def __init__(
        self,
        source_root: str | Path,
        *,
        source_url: str,
        source_revision: str,
    ) -> None:
        self.source_root = Path(source_root).expanduser().resolve()
        self.source_url = _repository_identity(source_url)
        self.source_revision = source_revision
        canonical_root = self.source_root / "knowledge" / "canonical"
        if not canonical_root.is_dir():
            raise ChatQECServiceError(
                f"ChatQEC canonical corpus not found: {canonical_root}"
            )
        paths = sorted(
            path
            for path in canonical_root.glob("*.md")
            if not path.name.startswith("_")
        )
        self.pages = tuple(_parse_page(path, self.source_root) for path in paths)
        if not self.pages:
            raise ChatQECServiceError("ChatQEC canonical corpus has no pages")
        digest = hashlib.sha256()
        for page in self.pages:
            digest.update(page.relative_path.encode("utf-8"))
            digest.update(b"\0")
            digest.update(page.digest.encode("ascii"))
            digest.update(b"\0")
        self.corpus_revision = "sha256:" + digest.hexdigest()

    def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "chatqec",
            "mode": "canonical-extractive-development",
            "source_revision": self.source_revision,
            "corpus_revision": self.corpus_revision,
            "pages": len(self.pages),
            "tool_execution": False,
        }

    def _rank(self, question: str) -> list[tuple[int, CanonicalPage]]:
        normalized = " ".join(question.lower().split())
        query_tokens = _tokens(question)
        ranked: list[tuple[int, CanonicalPage]] = []
        for page in self.pages:
            names = (page.title, page.slug.replace("-", " "), *page.aliases)
            name_text = " ".join(names).lower()
            name_tokens = _tokens(name_text)
            body_tokens = _tokens(page.body)
            phrase_score = (
                20
                if any(name.lower() in normalized for name in names)
                else 0
            )
            score = (
                phrase_score
                + 5 * len(query_tokens & name_tokens)
                + min(4, len(query_tokens & body_tokens))
            )
            if score:
                ranked.append((score, page))
        return sorted(ranked, key=lambda item: (-item[0], item[1].slug))

    def _extract(self, page: CanonicalPage, question: str) -> tuple[str, str]:
        sections = _sections(page.body)
        introduction = next(
            (
                paragraph
                for title, content in sections
                if not title
                for paragraph in _paragraphs(content)
            ),
            "",
        )
        query_tokens = _tokens(question)
        ranked_sections: list[tuple[int, str, str]] = []
        for title, content in sections:
            if not title:
                continue
            score = 4 * len(query_tokens & _tokens(title)) + len(
                query_tokens & _tokens(content)
            )
            paragraphs = _paragraphs(content)
            if score and paragraphs:
                ranked_sections.append((score, title, paragraphs[0]))
        answer_parts = [introduction] if introduction else []
        locator = page.relative_path
        if ranked_sections:
            _, section_title, paragraph = max(
                ranked_sections,
                key=lambda item: (item[0], item[1]),
            )
            if paragraph != introduction:
                answer_parts.append(f"**{section_title}.** {paragraph}")
                locator += f"#{section_title.lower().replace(' ', '-')}"
        if not answer_parts:
            answer_parts.append(
                f"ChatQEC identifies this topic as **{page.title}**, but the "
                "canonical page has no extractable summary."
            )
        return "\n\n".join(answer_parts), locator

    def answer(self, request: dict[str, Any]) -> dict[str, Any]:
        normalized = validate_chatqec_request(request)
        if normalized["corpus_revision"] != self.corpus_revision:
            raise ServiceAdapterError(
                "request corpus_revision does not match the active corpus"
            )
        started = time.monotonic()
        retrieval_started = time.monotonic()
        ranked = self._rank(normalized["question"])
        retrieval_ms = (time.monotonic() - retrieval_started) * 1000
        if ranked and ranked[0][0] >= 5:
            score, page = ranked[0]
            answer, locator = self._extract(page, normalized["question"])
            confidence = round(min(0.95, 0.55 + score / 100), 4)
            citations = [
                {
                    "id": f"canonical:{page.slug}",
                    "title": page.title,
                    "source_uri": (
                        f"{self.source_url}/blob/{self.source_revision}/"
                        f"{page.relative_path}"
                    ),
                    "source_revision": page.digest,
                    "locator": locator,
                }
            ]
        else:
            answer = (
                "The local ChatQEC canonical corpus does not contain enough "
                "cited QEC material to answer that question. Refine the question "
                "to a quantum error-correction code, decoder, noise model, or "
                "fault-tolerance topic."
            )
            confidence = 0.15
            citations = []
        input_text = normalized["question"] + " ".join(
            message["content"] for message in normalized.get("history", [])
        )
        input_tokens = max(1, len(input_text.split()) * 4 // 3)
        output_tokens = max(1, len(answer.split()) * 4 // 3)
        total_ms = (time.monotonic() - started) * 1000
        response = {
            "request_id": normalized["request_id"],
            "correlation_id": normalized["correlation_id"],
            "conversation_id": normalized["conversation_id"],
            "answer": answer,
            "citations": citations,
            "confidence": confidence,
            "provider": "chatqec-local",
            "model": "canonical-extractive-v1",
            "model_response_id": "local-" + hashlib.sha256(
                f"{normalized['request_id']}\0{answer}".encode("utf-8")
            ).hexdigest()[:24],
            "corpus_revision": self.corpus_revision,
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
            },
            "latency_ms": {
                "retrieval": round(retrieval_ms, 3),
                "rerank": 0.0,
                "generation": 0.0,
                "total": round(total_ms, 3),
            },
        }
        return validate_chatqec_response(response, normalized)


class ChatQECDevelopmentServer(ThreadingHTTPServer):
    daemon_threads = True
    responder: CanonicalChatQEC
    identity_token: str


def handler_for(
    responder: CanonicalChatQEC,
    identity_token: str,
) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "ChatQECDevelopment/0.1"

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _json(self, status: int, value: Any) -> None:
            payload = json.dumps(value, sort_keys=True).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(payload)

        def _authorized(self) -> bool:
            supplied = self.headers.get("Authorization", "")
            expected = f"Bearer {identity_token}"
            return hmac.compare_digest(supplied, expected)

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
                self._json(
                    HTTPStatus.UNAUTHORIZED,
                    {"error": "workload identity required"},
                )
                return
            try:
                request = self._body()
                response = responder.answer(request)
            except ServiceAdapterError as error:
                self._json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
                return
            if path == "/v1/answers":
                self._json(HTTPStatus.OK, response)
                return
            events = [
                {
                    "request_id": response["request_id"],
                    "sequence": 0,
                    "event": "token",
                    "data": {"text": response["answer"]},
                }
            ]
            for citation in response["citations"]:
                events.append(
                    {
                        "request_id": response["request_id"],
                        "sequence": len(events),
                        "event": "citation",
                        "data": {"citation": citation},
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


def server_for(
    responder: CanonicalChatQEC,
    identity_token: str,
    host: str = "127.0.0.1",
    port: int = 0,
) -> ChatQECDevelopmentServer:
    if host not in {"127.0.0.1", "::1", "localhost"}:
        raise ChatQECServiceError(
            "the extractive ChatQEC development service must bind to loopback"
        )
    if len(identity_token) < 32:
        raise ChatQECServiceError(
            "ChatQEC development workload identity must be at least 32 characters"
        )
    server = ChatQECDevelopmentServer(
        (host, port),
        handler_for(responder, identity_token),
    )
    server.responder = responder
    server.identity_token = identity_token
    return server


def serve(
    responder: CanonicalChatQEC,
    identity_token: str,
    host: str = "127.0.0.1",
    port: int = 8096,
) -> None:
    server = server_for(responder, identity_token, host, port)
    with server:
        server.serve_forever()
