from __future__ import annotations

import json
import shutil
import subprocess
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from qhpc_ecosystem.assistant import ChatQECGateway
from qhpc_ecosystem.chatqec_service import (
    CanonicalChatQEC,
    ChatQECServiceError,
    ChatQECSource,
    server_for,
)
from qhpc_ecosystem.service_adapters import (
    ServiceAdapterError,
    build_chatqec_request,
    parse_chatqec_sse,
)


SOURCE_REVISION = "4c017510511f835001bfe5901a9d59e86cc130cd"
IDENTITY_TOKEN = "development-identity-token-" + "x" * 32


def _source(tmp_path: Path) -> Path:
    root = tmp_path / "chatqec"
    canonical = root / "knowledge" / "canonical"
    canonical.mkdir(parents=True)
    (root / "LICENSE").write_text("Apache License 2.0\n", encoding="utf-8")
    (canonical / "surface-code.md").write_text(
        """---
topic_slug: surface-code
title: Surface Code
aliases: [planar surface code, toric code]
---

# Surface Code

The surface code is a topological CSS quantum error-correcting code on a
two-dimensional lattice.

## Decoding

[[mwpm-decoder|Minimum-weight perfect matching]] is commonly used to decode
its syndrome graph.
""",
        encoding="utf-8",
    )
    (canonical / "threshold-theorem.md").write_text(
        """---
topic_slug: threshold-theorem
title: Threshold Theorem
aliases: [fault tolerance threshold]
---

# Threshold Theorem

Below a construction-dependent physical error threshold, increasing code
distance can suppress logical errors.
""",
        encoding="utf-8",
    )
    return root


def test_canonical_chatqec_returns_source_pinned_cited_answers(
    tmp_path: Path,
) -> None:
    responder = CanonicalChatQEC(
        _source(tmp_path),
        source_url="https://github.com/QSCSoftwareThrust/ChatQEC",
        source_revision=SOURCE_REVISION,
    )
    request = build_chatqec_request(
        request_id="req-test",
        correlation_id="corr-test",
        conversation_id="conversation-test",
        authorized_subject="subject-test",
        workspace_id="workspace-test",
        policy_class="public-qec",
        corpus_revision=responder.corpus_revision,
        question="How is the surface code decoded?",
    )

    response = responder.answer(request)

    assert "topological CSS" in response["answer"]
    assert "Minimum-weight perfect matching" in response["answer"]
    assert response["provider"] == "chatqec-local"
    assert response["model"] == "canonical-extractive-v1"
    assert response["corpus_revision"] == responder.corpus_revision
    assert response["citations"][0]["id"] == "canonical:surface-code"
    assert SOURCE_REVISION in response["citations"][0]["source_uri"]
    assert response["usage"]["total_tokens"] == (
        response["usage"]["input_tokens"] + response["usage"]["output_tokens"]
    )


def test_source_prepare_recovers_an_interrupted_empty_worktree(
    tmp_path: Path,
) -> None:
    upstream = _source(tmp_path)
    subprocess.run(["git", "init", "-b", "main", upstream], check=True)
    subprocess.run(
        ["git", "-C", upstream, "config", "user.email", "test@example.org"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", upstream, "config", "user.name", "QHPC Test"],
        check=True,
    )
    subprocess.run(["git", "-C", upstream, "add", "."], check=True)
    subprocess.run(
        ["git", "-C", upstream, "commit", "-m", "fixture"],
        check=True,
        capture_output=True,
    )
    revision = subprocess.run(
        ["git", "-C", upstream, "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    checkout = tmp_path / "checkout"
    source = ChatQECSource(str(upstream), revision, checkout)

    assert source.prepare() == checkout
    for child in checkout.iterdir():
        if child.name == ".git":
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()

    assert source.prepare() == checkout
    assert (checkout / "knowledge/canonical/surface-code.md").is_file()
    (checkout / "knowledge/canonical/untracked.md").write_text(
        "unreviewed corpus content\n",
        encoding="utf-8",
    )
    with pytest.raises(ChatQECServiceError, match="tracked or untracked"):
        source.verify()


def test_canonical_chatqec_refuses_uncited_topics(tmp_path: Path) -> None:
    responder = CanonicalChatQEC(
        _source(tmp_path),
        source_url="https://github.com/QSCSoftwareThrust/ChatQEC",
        source_revision=SOURCE_REVISION,
    )
    request = build_chatqec_request(
        request_id="req-refusal",
        correlation_id="corr-refusal",
        conversation_id="conversation-refusal",
        authorized_subject="subject-test",
        workspace_id="workspace-test",
        policy_class="public-qec",
        corpus_revision=responder.corpus_revision,
        question="What is tomorrow's weather?",
    )

    response = responder.answer(request)

    assert "does not contain enough cited QEC material" in response["answer"]
    assert response["citations"] == []
    assert response["confidence"] < 0.2


def test_chatqec_gateway_authenticates_and_validates_json_and_sse(
    tmp_path: Path,
) -> None:
    responder = CanonicalChatQEC(
        _source(tmp_path),
        source_url="https://github.com/QSCSoftwareThrust/ChatQEC",
        source_revision=SOURCE_REVISION,
    )
    try:
        server = server_for(responder, IDENTITY_TOKEN)
    except PermissionError:
        pytest.skip("test runner does not permit binding a localhost socket")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_port}"
    try:
        gateway = ChatQECGateway(origin, IDENTITY_TOKEN)
        status = gateway.status()
        assert status["pages"] == 2
        assert status["mode"] == "canonical-extractive-development"

        response = gateway.ask(
            "What is the threshold theorem?",
            conversation_id="conversation-browser",
        )
        assert response["conversation_id"] == "conversation-browser"
        assert response["citations"][0]["id"] == "canonical:threshold-theorem"

        with pytest.raises(HTTPError) as unauthorized:
            urlopen(
                Request(
                    origin + "/v1/answers",
                    data=b"{}",
                    headers={"Content-Type": "application/json"},
                    method="POST",
                ),
                timeout=3,
            )
        assert unauthorized.value.code == 401

        stream_request = build_chatqec_request(
            request_id="req-stream",
            correlation_id="corr-stream",
            conversation_id="conversation-stream",
            authorized_subject="subject-test",
            workspace_id="workspace-test",
            policy_class="public-qec",
            corpus_revision=responder.corpus_revision,
            question="What is the surface code?",
        )
        request = Request(
            origin + "/v1/answers/stream",
            data=json.dumps(stream_request).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {IDENTITY_TOKEN}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urlopen(request, timeout=3) as stream:
            events = parse_chatqec_sse(stream.read(), stream_request)
        assert [event["event"] for event in events] == [
            "token",
            "citation",
            "final",
        ]
        assert events[-1]["data"]["response"]["request_id"] == "req-stream"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_extract_backend_rejects_non_loopback_binding(tmp_path: Path) -> None:
    responder = CanonicalChatQEC(
        _source(tmp_path),
        source_url="https://github.com/QSCSoftwareThrust/ChatQEC",
        source_revision=SOURCE_REVISION,
    )
    with pytest.raises(ChatQECServiceError, match="loopback"):
        server_for(responder, IDENTITY_TOKEN, host="0.0.0.0")


def test_gateway_rejects_health_that_enables_tool_execution() -> None:
    gateway = ChatQECGateway("http://127.0.0.1:8096", IDENTITY_TOKEN)

    class UnsafeHealthTransport:
        def request(self, *_args, **_kwargs):
            return (
                200,
                {"Content-Type": "application/json"},
                json.dumps(
                    {
                        "status": "ok",
                        "service": "chatqec",
                        "mode": "unsafe",
                        "source_revision": SOURCE_REVISION,
                        "corpus_revision": "sha256:" + ("a" * 64),
                        "pages": 60,
                        "tool_execution": True,
                    }
                ).encode("utf-8"),
            )

    gateway.transport = UnsafeHealthTransport()

    with pytest.raises(ServiceAdapterError, match="prohibited tool execution"):
        gateway.status()
