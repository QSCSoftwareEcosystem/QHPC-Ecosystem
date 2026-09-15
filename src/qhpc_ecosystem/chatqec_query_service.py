"""Container-only adapter for the pinned upstream ChatQEC read-only stack.

This module owns the HTTP/SSE boundary used by EQO.  It deliberately does not
reuse Streamlit, start MCP servers, expose upstream administration commands, or
choose a provider.  A deployment profile selects one approved provider and an
immutable corpus manifest; without those inputs the container remains alive
only to report a bounded, non-secret ``degraded`` readiness response.
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
from typing import Any, Callable, Mapping, Protocol, Sequence
from urllib.error import URLError
from urllib.parse import urlparse, urlsplit
from urllib.request import ProxyHandler, Request, build_opener

import yaml

from .chatqec_readiness import UPSTREAM_MCP_AGENT, UPSTREAM_RAG_READ_ONLY
from .service_adapters import (
    ServiceAdapterError,
    validate_chatqec_request,
    validate_chatqec_response,
)


PINNED_CHATQEC_REVISION = "a1ddc2e4916b1f4152fba4c94c9c7512eea0d977"
UNCONFIGURED_CORPUS_REVISION = "sha256:" + ("0" * 64)
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_REVISION = re.compile(r"^[0-9a-f]{40}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@-]{0,127}$")
_DIRECT_OPENER = build_opener(ProxyHandler({}))


class ChatQECQueryServiceError(RuntimeError):
    """Raised when the container query deployment violates its fixed boundary."""


@dataclass(frozen=True)
class CorpusSource:
    source_id: str
    title: str
    source_uri: str
    source_revision: str


@dataclass(frozen=True)
class CorpusManifest:
    """Read-only corpus metadata required before upstream RAG is admitted."""

    snapshot_digest: str
    source_revision: str
    source_registry_digest: str
    qdrant_snapshot_digest: str
    collection: str
    pages: int
    embedding_model: str
    reranker_model: str
    sources: Mapping[str, CorpusSource]

    @classmethod
    def from_path(cls, path: str | Path) -> CorpusManifest:
        source = Path(path).expanduser().resolve()
        try:
            document = json.loads(source.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise ChatQECQueryServiceError("ChatQEC corpus manifest is not present") from error
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ChatQECQueryServiceError("ChatQEC corpus manifest is invalid") from error
        if not isinstance(document, Mapping):
            raise ChatQECQueryServiceError("ChatQEC corpus manifest must be an object")
        required = {
            "schema_version",
            "snapshot_digest",
            "source_revision",
            "source_registry_digest",
            "qdrant_snapshot_digest",
            "collection",
            "pages",
            "embedding",
            "reranker",
            "sources",
        }
        if set(document) != required:
            raise ChatQECQueryServiceError("ChatQEC corpus manifest fields are invalid")
        if document["schema_version"] != 1:
            raise ChatQECQueryServiceError("ChatQEC corpus manifest schema version is invalid")
        for field in (
            "snapshot_digest",
            "source_registry_digest",
            "qdrant_snapshot_digest",
        ):
            if not isinstance(document[field], str) or _DIGEST.fullmatch(document[field]) is None:
                raise ChatQECQueryServiceError(f"ChatQEC corpus manifest {field} is invalid")
        if not isinstance(document["source_revision"], str) or _REVISION.fullmatch(document["source_revision"]) is None:
            raise ChatQECQueryServiceError("ChatQEC corpus manifest source revision is invalid")
        collection = document["collection"]
        if not isinstance(collection, str) or not _IDENTIFIER.fullmatch(collection):
            raise ChatQECQueryServiceError("ChatQEC corpus manifest collection is invalid")
        pages = document["pages"]
        if isinstance(pages, bool) or not isinstance(pages, int) or pages <= 0:
            raise ChatQECQueryServiceError("ChatQEC corpus manifest pages is invalid")
        embedding = document["embedding"]
        reranker = document["reranker"]
        if (
            not isinstance(embedding, Mapping)
            or set(embedding) != {"model", "dimensions"}
            or not isinstance(embedding["model"], str)
            or not embedding["model"]
            or isinstance(embedding["dimensions"], bool)
            or not isinstance(embedding["dimensions"], int)
            or embedding["dimensions"] <= 0
        ):
            raise ChatQECQueryServiceError("ChatQEC corpus manifest embedding is invalid")
        if (
            not isinstance(reranker, Mapping)
            or set(reranker) != {"model"}
            or not isinstance(reranker["model"], str)
            or not reranker["model"]
        ):
            raise ChatQECQueryServiceError("ChatQEC corpus manifest reranker is invalid")
        source_records = document["sources"]
        if not isinstance(source_records, list) or not source_records:
            raise ChatQECQueryServiceError("ChatQEC corpus manifest sources are invalid")
        sources: dict[str, CorpusSource] = {}
        for record in source_records:
            if not isinstance(record, Mapping) or set(record) != {
                "source_id",
                "title",
                "source_uri",
                "source_revision",
            }:
                raise ChatQECQueryServiceError("ChatQEC corpus source record is invalid")
            source_id = record["source_id"]
            title = record["title"]
            source_uri = record["source_uri"]
            source_revision = record["source_revision"]
            if not isinstance(source_id, str) or _IDENTIFIER.fullmatch(source_id) is None:
                raise ChatQECQueryServiceError("ChatQEC corpus source ID is invalid")
            if not isinstance(title, str) or not title or len(title) > 1000:
                raise ChatQECQueryServiceError("ChatQEC corpus source title is invalid")
            parsed = urlsplit(str(source_uri))
            if (
                not isinstance(source_uri, str)
                or parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.username
                or parsed.password
            ):
                raise ChatQECQueryServiceError("ChatQEC corpus source URI is invalid")
            if not isinstance(source_revision, str) or not source_revision or len(source_revision) > 128:
                raise ChatQECQueryServiceError("ChatQEC corpus source revision is invalid")
            if source_id in sources:
                raise ChatQECQueryServiceError("ChatQEC corpus source IDs must be unique")
            sources[source_id] = CorpusSource(
                source_id=source_id,
                title=title,
                source_uri=source_uri,
                source_revision=source_revision,
            )
        return cls(
            snapshot_digest=document["snapshot_digest"],
            source_revision=document["source_revision"],
            source_registry_digest=document["source_registry_digest"],
            qdrant_snapshot_digest=document["qdrant_snapshot_digest"],
            collection=collection,
            pages=pages,
            embedding_model=embedding["model"],
            reranker_model=reranker["model"],
            sources=sources,
        )


@dataclass(frozen=True)
class ChatQECQueryDeployment:
    """Non-secret deployment selection mounted read-only into the query image."""

    source_revision: str
    provider: str
    model: str | None
    credential_environment: str | None
    qdrant_url: str | None
    upstream_config_directory: Path | None
    corpus: CorpusManifest | None
    mcp_enabled: bool = False

    @classmethod
    def from_path(cls, path: str | Path) -> ChatQECQueryDeployment:
        profile_path = Path(path).expanduser().resolve()
        try:
            document = json.loads(profile_path.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise ChatQECQueryServiceError("ChatQEC deployment profile is not present") from error
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ChatQECQueryServiceError("ChatQEC deployment profile is invalid") from error
        if not isinstance(document, Mapping) or set(document) != {
            "api_version", "kind", "metadata", "spec"
        }:
            raise ChatQECQueryServiceError("ChatQEC deployment profile fields are invalid")
        if document["api_version"] != "qhpc/v1" or document["kind"] != "ChatQECQueryDeployment":
            raise ChatQECQueryServiceError("ChatQEC deployment profile identity is invalid")
        metadata = document["metadata"]
        spec = document["spec"]
        if not isinstance(metadata, Mapping) or set(metadata) != {"source_revision"}:
            raise ChatQECQueryServiceError("ChatQEC deployment metadata is invalid")
        source_revision = metadata["source_revision"]
        if source_revision != PINNED_CHATQEC_REVISION:
            raise ChatQECQueryServiceError("ChatQEC deployment does not select the pinned revision")
        if not isinstance(spec, Mapping) or set(spec) != {
            "provider", "qdrant_url", "upstream_config_directory", "corpus_manifest", "features"
        }:
            raise ChatQECQueryServiceError("ChatQEC deployment specification is invalid")
        provider = spec["provider"]
        if not isinstance(provider, Mapping) or set(provider) != {
            "name", "model", "credential_environment"
        }:
            raise ChatQECQueryServiceError("ChatQEC provider selection is invalid")
        provider_name = provider["name"]
        if provider_name not in {"unconfigured", "anthropic", "gemini", "huggingface"}:
            raise ChatQECQueryServiceError("ChatQEC provider must select one supported provider")
        model = provider["model"]
        credential_environment = provider["credential_environment"]
        expected_credentials = {
            "anthropic": "ANTHROPIC_API_KEY",
            "gemini": "GEMINI_API_KEY",
            "huggingface": "HF_TOKEN",
        }
        if provider_name == "unconfigured":
            if model is not None or credential_environment is not None:
                raise ChatQECQueryServiceError("unconfigured ChatQEC provider cannot name a model or credential")
        else:
            if not isinstance(model, str) or not model or len(model) > 128:
                raise ChatQECQueryServiceError("ChatQEC provider model is invalid")
            if credential_environment != expected_credentials[provider_name]:
                raise ChatQECQueryServiceError("ChatQEC provider credential environment is invalid")
        qdrant_url = spec["qdrant_url"]
        if qdrant_url is not None:
            if not isinstance(qdrant_url, str):
                raise ChatQECQueryServiceError("ChatQEC Qdrant URL is invalid")
            parsed = urlsplit(qdrant_url)
            if (
                parsed.scheme != "http"
                or not parsed.netloc
                or parsed.username
                or parsed.password
                or parsed.path not in {"", "/"}
                or parsed.query
                or parsed.fragment
            ):
                raise ChatQECQueryServiceError("ChatQEC Qdrant URL is invalid")
        config_directory = spec["upstream_config_directory"]
        if config_directory is not None and (
            not isinstance(config_directory, str) or not Path(config_directory).is_absolute()
        ):
            raise ChatQECQueryServiceError("ChatQEC upstream config directory is invalid")
        manifest_path = spec["corpus_manifest"]
        if manifest_path is not None and (
            not isinstance(manifest_path, str) or not Path(manifest_path).is_absolute()
        ):
            raise ChatQECQueryServiceError("ChatQEC corpus manifest path is invalid")
        features = spec["features"]
        if not isinstance(features, Mapping) or set(features) != {
            "mcp", "qappswiki", "web_fallback", "images"
        } or any(
            not isinstance(value, bool) for value in features.values()
        ) or any(features[name] for name in ("qappswiki", "web_fallback", "images")):
            raise ChatQECQueryServiceError(
                "ChatQEC query deployment must disable optional knowledge, web fallback, and images"
            )
        corpus = CorpusManifest.from_path(manifest_path) if manifest_path else None
        if corpus is not None and corpus.source_revision != source_revision:
            raise ChatQECQueryServiceError("ChatQEC corpus manifest source revision differs")
        deployment = cls(
            source_revision=source_revision,
            provider=provider_name,
            model=model if isinstance(model, str) else None,
            credential_environment=credential_environment if isinstance(credential_environment, str) else None,
            qdrant_url=qdrant_url,
            upstream_config_directory=Path(config_directory) if config_directory else None,
            corpus=corpus,
            mcp_enabled=features["mcp"],
        )
        deployment._validate_upstream_configuration()
        return deployment

    def _validate_upstream_configuration(self) -> None:
        """Reject upstream defaults that violate the EQO deployment profile."""

        if self.provider == "unconfigured":
            return
        if self.upstream_config_directory is None or self.corpus is None or self.qdrant_url is None:
            raise ChatQECQueryServiceError("configured ChatQEC provider lacks corpus, Qdrant, or upstream configuration")
        config_path = self.upstream_config_directory / "config.yaml"
        try:
            config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
            raise ChatQECQueryServiceError("ChatQEC upstream configuration is invalid") from error
        if not isinstance(config, Mapping):
            raise ChatQECQueryServiceError("ChatQEC upstream configuration is invalid")
        models = config.get("models")
        store = config.get("store")
        if not isinstance(models, Mapping) or models.get("provider") != self.provider:
            raise ChatQECQueryServiceError("ChatQEC upstream configuration provider differs")
        if not isinstance(store, Mapping) or store.get("qdrant_url") != self.qdrant_url:
            raise ChatQECQueryServiceError("ChatQEC upstream configuration Qdrant URL differs")
        if store.get("collection") != self.corpus.collection:
            raise ChatQECQueryServiceError("ChatQEC upstream configuration collection differs")
        mcp = config.get("mcp")
        wiki = config.get("wiki")
        if not isinstance(mcp, Mapping) or mcp.get("enabled") is not self.mcp_enabled:
            raise ChatQECQueryServiceError("ChatQEC upstream configuration MCP setting differs")
        if not isinstance(wiki, Mapping) or wiki.get("enabled") is not False:
            raise ChatQECQueryServiceError("ChatQEC upstream configuration enables optional knowledge")
        if self.provider == "anthropic":
            selected_synthesizer = models.get("synthesizer")
        else:
            provider_models = models.get("gemini" if self.provider == "gemini" else "hf")
            selected_synthesizer = (
                provider_models.get("synthesizer")
                if isinstance(provider_models, Mapping)
                else None
            )
        if selected_synthesizer != self.model:
            raise ChatQECQueryServiceError(
                "ChatQEC upstream configuration does not admit the selected model"
            )

    def readiness(
        self,
        *,
        environment: Mapping[str, str] | None = None,
        qdrant_probe: Callable[[str, str], bool] | None = None,
    ) -> dict[str, str]:
        environment = os.environ if environment is None else environment
        configured = self.provider != "unconfigured"
        model_ready = bool(
            configured
            and self.credential_environment
            and environment.get(self.credential_environment, "")
        )
        corpus_ready = self.corpus is not None
        qdrant_ready = bool(corpus_ready and self.qdrant_url)
        if qdrant_ready and qdrant_probe is not None:
            qdrant_ready = qdrant_probe(self.qdrant_url or "", self.corpus.collection)
        return {
            "source": "ready",
            "model": "ready" if model_ready else "not-configured",
            "qdrant": "ready" if qdrant_ready else "not-provisioned",
            "corpus": "ready" if corpus_ready else "not-provisioned",
            "embeddings": "ready" if corpus_ready and configured else "not-configured",
            "reranker": "ready" if corpus_ready and configured else "not-configured",
            "knowledge": "disabled",
        }


class QueryBackend(Protocol):
    def answer(self, question: str, history: Sequence[Mapping[str, str]]) -> Any: ...


class UpstreamChatQECBackend:
    """Construct a fresh upstream object per EQO request for isolation.

    The upstream factory is used only after the deployment profile has rejected
    ``auto`` provider selection, direct MCP configuration, web fallback, and
    unbounded process-global conversation memory.  The original library has no
    structured stream-final result, so this adapter performs exactly one
    ``ask`` call and streams the completed text as bounded SSE chunks followed
    by its citations and final metadata.
    """

    def __init__(self, deployment: ChatQECQueryDeployment) -> None:
        self.deployment = deployment

    def answer(self, question: str, history: Sequence[Mapping[str, str]]) -> Any:
        if self.deployment.provider == "unconfigured":
            raise ChatQECQueryServiceError("ChatQEC provider is not configured")
        forbidden = {"TAVILY_API_KEY": os.environ.get("TAVILY_API_KEY", "")}
        if any(value for value in forbidden.values()) or os.environ.get("CHATQEC_WEB_FALLBACK", "").lower() not in {"", "0", "false", "no"}:
            raise ChatQECQueryServiceError("ChatQEC query deployment enables a prohibited upstream feature")
        if self.deployment.upstream_config_directory is None:
            raise ChatQECQueryServiceError("ChatQEC upstream configuration is unavailable")
        os.environ["CHATQEC_CONF_DIR"] = str(self.deployment.upstream_config_directory)
        from chatqec.cli import _build_chatqec  # type: ignore[import-not-found]

        bot = _build_chatqec(
            mcp_server="chatqec-mcp-tools" if self.deployment.mcp_enabled else None
        )
        has_mcp_adapter = getattr(getattr(bot, "synthesizer", None), "mcp_adapter", None) is not None
        if has_mcp_adapter is not self.deployment.mcp_enabled:
            raise ChatQECQueryServiceError("ChatQEC MCP adapter does not match the deployment")
        memory = getattr(bot, "memory", None)
        if memory is None or not hasattr(memory, "clear"):
            raise ChatQECQueryServiceError("ChatQEC upstream conversation memory is unavailable")
        memory.clear()
        for message in history:
            if message["role"] == "user":
                memory.add_user(message["content"])
            else:
                memory.add_assistant(message["content"])
        result = bot.ask(question)
        if not self.deployment.mcp_enabled and (
            getattr(result, "tool_calls", ()) or getattr(result, "figure_paths", ())
        ):
            raise ChatQECQueryServiceError("ChatQEC upstream returned a prohibited tool or figure result")
        return result


def _qdrant_collection_ready(base_url: str, collection: str) -> bool:
    request = Request(
        base_url.rstrip("/") + "/collections/" + collection,
        headers={"Accept": "application/json"},
        method="GET",
    )
    try:
        with _DIRECT_OPENER.open(request, timeout=1.0) as response:
            return response.status == HTTPStatus.OK
    except (OSError, URLError):
        return False


def _confidence(value: Any) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return max(0.0, min(1.0, float(value)))
    return {"high": 0.85, "medium": 0.65, "low": 0.35}.get(str(value).lower(), 0.2)


class ChatQECQueryResponder:
    """Map one governed request to one upstream ChatQEC query invocation."""

    def __init__(
        self,
        deployment: ChatQECQueryDeployment | None,
        *,
        backend_factory: Callable[[ChatQECQueryDeployment], QueryBackend] = UpstreamChatQECBackend,
        qdrant_probe: Callable[[str, str], bool] = _qdrant_collection_ready,
    ) -> None:
        self.deployment = deployment
        self.backend_factory = backend_factory
        self.qdrant_probe = qdrant_probe

    @property
    def source_revision(self) -> str:
        return self.deployment.source_revision if self.deployment else PINNED_CHATQEC_REVISION

    @property
    def corpus_revision(self) -> str:
        if self.deployment and self.deployment.corpus:
            return self.deployment.corpus.snapshot_digest
        return UNCONFIGURED_CORPUS_REVISION

    def readiness(self) -> dict[str, str]:
        if self.deployment is None:
            return {
                "source": "ready",
                "model": "not-configured",
                "qdrant": "not-provisioned",
                "corpus": "not-provisioned",
                "embeddings": "not-configured",
                "reranker": "not-configured",
                "knowledge": "disabled",
            }
        return self.deployment.readiness(qdrant_probe=self.qdrant_probe)

    def health(self) -> dict[str, Any]:
        readiness = self.readiness()
        required = ("source", "model", "qdrant", "corpus", "embeddings", "reranker")
        ready = all(readiness[item] == "ready" for item in required)
        return {
            "status": "ok" if ready else "degraded",
            "service": "chatqec",
            "mode": UPSTREAM_MCP_AGENT if self.deployment and self.deployment.mcp_enabled else UPSTREAM_RAG_READ_ONLY,
            "source_revision": self.source_revision,
            "corpus_revision": self.corpus_revision,
            "pages": self.deployment.corpus.pages if self.deployment and self.deployment.corpus else 0,
            "tool_execution": bool(self.deployment and self.deployment.mcp_enabled),
            "readiness": readiness,
            "capabilities": {
                "model_rag": ready,
                "streaming": True,
                "source_ledger": True,
                "tool_proposals": False,
                "mcp_tools": bool(self.deployment and self.deployment.mcp_enabled),
            },
        }

    def _require_ready(self) -> ChatQECQueryDeployment:
        if self.deployment is None or self.deployment.corpus is None:
            raise ServiceAdapterError("ChatQEC upstream RAG service is not configured")
        readiness = self.readiness()
        required = ("source", "model", "qdrant", "corpus", "embeddings", "reranker")
        missing = [item for item in required if readiness[item] != "ready"]
        if missing:
            raise ServiceAdapterError(
                "ChatQEC upstream RAG service is not ready: " + ", ".join(missing)
            )
        return self.deployment

    def _citation(self, upstream: Any, corpus: CorpusManifest) -> dict[str, str]:
        source_id = getattr(upstream, "source_id", None)
        chunk_id = getattr(upstream, "chunk_id", None)
        if not isinstance(source_id, str) or source_id not in corpus.sources:
            raise ServiceAdapterError("ChatQEC upstream returned an ungoverned source")
        if not isinstance(chunk_id, str) or not chunk_id or len(chunk_id) > 500:
            raise ServiceAdapterError("ChatQEC upstream returned an invalid source locator")
        source = corpus.sources[source_id]
        return {
            "id": source.source_id,
            "title": source.title,
            "source_uri": source.source_uri,
            "source_revision": source.source_revision,
            "locator": chunk_id,
        }

    def answer(self, request: Mapping[str, Any]) -> dict[str, Any]:
        normalized = validate_chatqec_request(request)
        deployment = self._require_ready()
        assert deployment.corpus is not None
        if normalized["corpus_revision"] != deployment.corpus.snapshot_digest:
            raise ServiceAdapterError("request corpus_revision does not match the active corpus")
        started = time.monotonic()
        try:
            result = self.backend_factory(deployment).answer(
                normalized["question"], normalized.get("history", ())
            )
        except ChatQECQueryServiceError:
            raise
        except Exception as error:
            raise ChatQECQueryServiceError(
                "ChatQEC upstream query failed without a governed result"
            ) from error
        answer = getattr(result, "text", None)
        if not isinstance(answer, str) or not answer.strip() or len(answer) > 100_000:
            raise ServiceAdapterError("ChatQEC upstream returned an invalid answer")
        citations = [
            self._citation(citation, deployment.corpus)
            for citation in getattr(result, "citations", ())
        ]
        input_text = normalized["question"] + " ".join(
            item["content"] for item in normalized.get("history", ())
        )
        input_tokens = max(1, len(input_text.split()) * 4 // 3)
        output_tokens = max(1, len(answer.split()) * 4 // 3)
        elapsed = round((time.monotonic() - started) * 1000, 3)
        response = {
            "request_id": normalized["request_id"],
            "correlation_id": normalized["correlation_id"],
            "conversation_id": normalized["conversation_id"],
            "answer": answer,
            "citations": citations,
            "confidence": _confidence(getattr(result, "confidence", "low")),
            "provider": deployment.provider,
            "model": deployment.model,
            # The upstream public Answer type does not expose a provider request
            # identifier.  This is an adapter correlation token, not a claim
            # about a provider-native response ID.
            "model_response_id": "adapter-" + hashlib.sha256(
                (normalized["request_id"] + "\0" + answer).encode("utf-8")
            ).hexdigest()[:24],
            "corpus_revision": deployment.corpus.snapshot_digest,
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
            },
            "latency_ms": {
                # The upstream public API returns no stage metrics.  The adapter
                # therefore publishes total elapsed time only; zero stages mean
                # "not exposed by this pinned upstream API", never zero work.
                "retrieval": 0.0,
                "rerank": 0.0,
                "generation": 0.0,
                "total": elapsed,
            },
        }
        if deployment.mcp_enabled:
            response["tool_calls"] = [
                {
                    "name": str(getattr(tool, "name", "")),
                    "status": "completed",
                    "summary": str(getattr(tool, "output", ""))[:4000]
                    or "ChatQEC MCP tool completed",
                }
                for tool in getattr(result, "tool_calls", ())
            ]
        return validate_chatqec_response(response, normalized)


class ChatQECQueryServer(ThreadingHTTPServer):
    daemon_threads = True


def handler_for(
    responder: ChatQECQueryResponder,
    identity_token: str,
) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "EQOChatQECQuery/0.1"

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
            return hmac.compare_digest(supplied, f"Bearer {identity_token}")

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
            except (ServiceAdapterError, ChatQECQueryServiceError) as error:
                self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": str(error)})
                return
            if path == "/v1/answers":
                self._json(HTTPStatus.OK, response)
                return
            events: list[dict[str, Any]] = []
            # Chunk a completed, single upstream invocation.  This preserves the
            # v1 token/final event contract without the upstream Streamlit
            # application's second request used to collect citations.
            for offset in range(0, len(response["answer"]), 4096):
                events.append(
                    {
                        "request_id": response["request_id"],
                        "sequence": len(events),
                        "event": "token",
                        "data": {"text": response["answer"][offset : offset + 4096]},
                    }
                )
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
    responder: ChatQECQueryResponder,
    identity_token: str,
    host: str = "127.0.0.1",
    port: int = 0,
    *,
    containerized: bool = False,
) -> ChatQECQueryServer:
    allowed_hosts = {"127.0.0.1", "::1", "localhost"}
    if containerized:
        allowed_hosts.add("0.0.0.0")
    if host not in allowed_hosts:
        raise ChatQECQueryServiceError("ChatQEC query service must bind to loopback or its container interface")
    if len(identity_token) < 32:
        raise ChatQECQueryServiceError("ChatQEC query workload identity must be at least 32 characters")
    return ChatQECQueryServer((host, port), handler_for(responder, identity_token))


def serve(
    responder: ChatQECQueryResponder,
    identity_token: str,
    *,
    host: str,
    port: int,
    containerized: bool,
) -> None:
    server = server_for(
        responder,
        identity_token,
        host=host,
        port=port,
        containerized=containerized,
    )
    with server:
        server.serve_forever()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="eqo-chatqec-query",
        description="Run the container-only EQO adapter for pinned upstream ChatQEC.",
    )
    parser.add_argument("--profile", default=os.environ.get("QHPC_CHATQEC_QUERY_PROFILE"))
    parser.add_argument("--host", default=os.environ.get("QHPC_CHATQEC_LISTEN_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("QHPC_CHATQEC_LISTEN_PORT", "8096")))
    options = parser.parse_args(argv)
    identity_token = os.environ.get("QHPC_CHATQEC_IDENTITY_TOKEN", "")
    if not options.profile:
        deployment = None
    else:
        try:
            deployment = ChatQECQueryDeployment.from_path(options.profile)
        except ChatQECQueryServiceError:
            # Startup without a provisioned profile is a deliberate degraded
            # state.  Details remain in deployment-side logs, never in health.
            deployment = None
    responder = ChatQECQueryResponder(deployment)
    serve(
        responder,
        identity_token,
        host=options.host,
        port=options.port,
        containerized=os.environ.get("QHPC_CHATQEC_CONTAINERIZED") == "1",
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
