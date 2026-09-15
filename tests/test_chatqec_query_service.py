from __future__ import annotations

import json
import threading
from pathlib import Path
from types import SimpleNamespace
from urllib.request import Request, urlopen

import pytest
from jsonschema import Draft202012Validator

from qhpc_ecosystem.contract import load_document
from qhpc_ecosystem.chatqec_query_container import (
    prepare_query_context,
    verify_query_context,
)
from qhpc_ecosystem.chatqec_query_service import (
    PINNED_CHATQEC_REVISION,
    ChatQECQueryDeployment,
    ChatQECQueryResponder,
    CorpusManifest,
    CorpusSource,
    server_for,
)
from qhpc_ecosystem.chatqec_readiness import (
    CANONICAL_EXTRACTIVE_FALLBACK,
    UPSTREAM_RAG_READ_ONLY,
    validate_chatqec_health,
)
from qhpc_ecosystem.service_adapters import build_chatqec_request, parse_chatqec_sse


IDENTITY_TOKEN = "query-identity-token-" + "x" * 32


def corpus() -> CorpusManifest:
    return CorpusManifest(
        snapshot_digest="sha256:" + "a" * 64,
        source_revision=PINNED_CHATQEC_REVISION,
        source_registry_digest="sha256:" + "b" * 64,
        qdrant_snapshot_digest="sha256:" + "c" * 64,
        collection="chatqec_chunks",
        pages=2,
        embedding_model="approved-embedding",
        reranker_model="approved-reranker",
        sources={
            "canonical:surface-code": CorpusSource(
                source_id="canonical:surface-code",
                title="Surface Code",
                source_uri="https://example.test/surface-code",
                source_revision="source-revision-1",
            )
        },
    )


def deployment() -> ChatQECQueryDeployment:
    return ChatQECQueryDeployment(
        source_revision=PINNED_CHATQEC_REVISION,
        provider="anthropic",
        model="approved-model",
        credential_environment="ANTHROPIC_API_KEY",
        qdrant_url="http://qdrant:6333",
        upstream_config_directory=Path("/etc/eqo/upstream-config"),
        corpus=corpus(),
    )


def request() -> dict[str, object]:
    return build_chatqec_request(
        request_id="req-upstream",
        correlation_id="corr-upstream",
        conversation_id="conversation-upstream",
        authorized_subject="subject-upstream",
        workspace_id="workspace-upstream",
        policy_class="public-qec",
        corpus_revision=corpus().snapshot_digest,
        question="How is the surface code decoded?",
        history=[{"role": "user", "content": "Tell me about QEC."}],
    )


class FakeBackend:
    def __init__(self, calls: list[tuple[str, list[dict[str, str]]]]) -> None:
        self.calls = calls

    def answer(self, question: str, history):
        self.calls.append((question, list(history)))
        return SimpleNamespace(
            text="Minimum-weight perfect matching decodes the syndrome graph.",
            confidence="high",
            citations=[
                SimpleNamespace(
                    source_id="canonical:surface-code",
                    chunk_id="canonical:surface-code#decoding",
                )
            ],
            tool_calls=[],
            figure_paths=[],
        )


def responder(calls: list[tuple[str, list[dict[str, str]]]]) -> ChatQECQueryResponder:
    return ChatQECQueryResponder(
        deployment(),
        backend_factory=lambda _deployment: FakeBackend(calls),
        qdrant_probe=lambda _url, _collection: True,
    )


def test_query_adapter_reports_degraded_without_a_deployment() -> None:
    health = ChatQECQueryResponder(None).health()

    assert health["status"] == "degraded"
    assert health["mode"] == UPSTREAM_RAG_READ_ONLY
    assert health["tool_execution"] is False
    assert health["readiness"]["model"] == "not-configured"
    assert validate_chatqec_health(health)["available"] is False


def test_query_adapter_maps_governed_sources_and_uses_one_upstream_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "selected-secret-not-persisted")
    calls: list[tuple[str, list[dict[str, str]]]] = []

    value = responder(calls)
    health = value.health()
    assert health["status"] == "ok"
    assert health["mode"] == UPSTREAM_RAG_READ_ONLY
    assert health["capabilities"]["model_rag"] is True

    response = value.answer(request())

    assert len(calls) == 1
    assert calls[0][0] == "How is the surface code decoded?"
    assert calls[0][1] == [{"role": "user", "content": "Tell me about QEC."}]
    assert response["provider"] == "anthropic"
    assert response["model"] == "approved-model"
    assert response["citations"] == [
        {
            "id": "canonical:surface-code",
            "title": "Surface Code",
            "source_uri": "https://example.test/surface-code",
            "source_revision": "source-revision-1",
            "locator": "canonical:surface-code#decoding",
        }
    ]
    assert response["model_response_id"].startswith("adapter-")


def test_query_adapter_streams_final_metadata_without_a_second_upstream_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "selected-secret-not-persisted")
    calls: list[tuple[str, list[dict[str, str]]]] = []
    try:
        server = server_for(responder(calls), IDENTITY_TOKEN)
    except PermissionError:
        pytest.skip("test runner does not permit binding a localhost socket")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        payload = request()
        origin = f"http://127.0.0.1:{server.server_port}"
        stream_request = Request(
            origin + "/v1/answers/stream",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {IDENTITY_TOKEN}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urlopen(stream_request, timeout=3) as stream:
            events = parse_chatqec_sse(stream.read(), payload)
        assert [event["event"] for event in events] == ["token", "citation", "final"]
        assert events[-1]["data"]["response"]["citations"][0]["id"] == "canonical:surface-code"
        assert len(calls) == 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_readiness_contract_distinguishes_the_extractive_fallback() -> None:
    value = validate_chatqec_health(
        {
            "status": "ok",
            "service": "chatqec",
            "mode": CANONICAL_EXTRACTIVE_FALLBACK,
            "source_revision": PINNED_CHATQEC_REVISION,
            "corpus_revision": "sha256:" + "d" * 64,
            "pages": 60,
            "tool_execution": False,
            "readiness": {
                "source": "ready",
                "model": "disabled",
                "qdrant": "disabled",
                "corpus": "ready",
                "embeddings": "disabled",
                "reranker": "disabled",
                "knowledge": "disabled",
            },
            "capabilities": {
                "model_rag": False,
                "streaming": True,
                "source_ledger": False,
                "tool_proposals": False,
            },
        }
    )
    assert value["available"] is True
    assert value["capabilities"]["model_rag"] is False
    schema = load_document("integrations/chatqec/service.yaml")["spec"]["schemas"][
        "health-response"
    ]
    Draft202012Validator(schema).validate(
        {
            key: value[key]
            for key in (
                "status",
                "service",
                "mode",
                "source_revision",
                "corpus_revision",
                "pages",
                "tool_execution",
                "readiness",
                "capabilities",
            )
        }
    )


def test_deployment_profile_rejects_auto_provider_and_disabled_features(
    tmp_path: Path,
) -> None:
    path = tmp_path / "profile.json"
    path.write_text(
        json.dumps(
            {
                "api_version": "qhpc/v1",
                "kind": "ChatQECQueryDeployment",
                "metadata": {"source_revision": PINNED_CHATQEC_REVISION},
                "spec": {
                    "provider": {
                        "name": "auto",
                        "model": "unapproved",
                        "credential_environment": "UNAPPROVED",
                    },
                    "qdrant_url": None,
                    "upstream_config_directory": None,
                    "corpus_manifest": None,
                    "features": {
                        "mcp": False,
                        "qappswiki": False,
                        "web_fallback": False,
                        "images": False,
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(Exception, match="supported provider"):
        ChatQECQueryDeployment.from_path(path)


def test_query_context_is_pinned_and_offline(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / "ChatQEC"
    if not source.is_dir():
        pytest.skip("pinned ChatQEC checkout is not available beside EQO")
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    # Context preparation validates transport integrity rather than wheel
    # contents; a release must supply a complete reviewed wheelhouse to build.
    (wheelhouse / "example-0-py3-none-any.whl").write_bytes(b"fixture wheel")
    destination = tmp_path / "context"

    prepared = prepare_query_context(source, wheelhouse, destination)
    metadata = verify_query_context(destination)

    assert prepared.source_revision == PINNED_CHATQEC_REVISION
    assert metadata["source_archive_digest"] == prepared.source_archive_digest
    assert metadata["wheels"][0]["filename"] == "example-0-py3-none-any.whl"
