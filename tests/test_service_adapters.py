from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from qhpc_ecosystem.contract import load_document
from qhpc_ecosystem.service_adapters import (
    ServiceAdapterError,
    ask_chatqec,
    build_chatqec_request,
    parse_chatqec_sse,
    validate_chatqec_response,
)


ROOT = Path(__file__).resolve().parents[1]
CHATQEC = ROOT / "integrations" / "chatqec"


def _fixture(name: str):
    return json.loads((CHATQEC / "fixtures" / name).read_text(encoding="utf-8"))


def test_chatqec_fixtures_match_the_service_contract() -> None:
    contract = load_document(CHATQEC / "service.yaml")
    schemas = contract["spec"]["schemas"]
    request = _fixture("ask-request.json")
    response = _fixture("answer-response.json")

    Draft202012Validator(
        schemas["ask-request"], format_checker=FormatChecker()
    ).validate(request)
    Draft202012Validator(
        schemas["answer-response"], format_checker=FormatChecker()
    ).validate(response)

    stream = (CHATQEC / "fixtures" / "answer-stream.sse").read_text(
        encoding="utf-8"
    )
    events = parse_chatqec_sse(stream, request)
    stream_validator = Draft202012Validator(
        schemas["answer-stream-event"], format_checker=FormatChecker()
    )
    for event in events:
        stream_validator.validate(event)
    assert events[-1]["data"]["response"] == response


def test_chatqec_adapter_uses_the_fixed_endpoint_without_credentials() -> None:
    request = _fixture("ask-request.json")
    response = _fixture("answer-response.json")
    call = {}

    def transport(**arguments):
        call.update(arguments)
        return (
            200,
            {"Content-Type": "application/json; charset=utf-8"},
            json.dumps(response).encode("utf-8"),
        )

    result = ask_chatqec(
        "https://chatqec.internal.example",
        request,
        transport=transport,
    )

    assert call["url"] == "https://chatqec.internal.example/v1/answers"
    assert call["timeout_seconds"] == 60.0
    assert "Authorization" not in call["headers"]
    assert call["headers"]["X-QHPC-Request-ID"] == request["request_id"]
    assert json.loads(call["body"]) == request
    assert result == response


def test_chatqec_request_builder_enforces_bounded_isolated_context() -> None:
    request = build_chatqec_request(
        request_id="req-2",
        correlation_id="corr-2",
        conversation_id="conversation-2",
        authorized_subject="subject-2",
        workspace_id="workspace-2",
        policy_class="public-qec",
        corpus_revision="sha256:" + "c" * 64,
        question="How does syndrome extraction work?",
        history=[{"role": "assistant", "content": "Start with stabilizers."}],
    )

    assert request["authorized_subject"] == "subject-2"
    assert request["workspace_id"] == "workspace-2"
    assert request["history"][0]["role"] == "assistant"
    assert not {"authorization", "token", "credential"} & set(request)

    with pytest.raises(ServiceAdapterError, match="exceeds 20 messages"):
        build_chatqec_request(
            request_id="req-2",
            correlation_id="corr-2",
            conversation_id="conversation-2",
            authorized_subject="subject-2",
            workspace_id="workspace-2",
            policy_class="public-qec",
            corpus_revision="sha256:" + "c" * 64,
            question="Question",
            history=[{"role": "user", "content": "message"}] * 21,
        )


@pytest.mark.parametrize(
    "base_url",
    [
        "http://chatqec.internal.example",
        "https://user:secret@chatqec.internal.example",
        "https://chatqec.internal.example/service",
        "https://chatqec.internal.example?token=secret",
    ],
)
def test_chatqec_adapter_rejects_uncontrolled_base_urls(base_url: str) -> None:
    with pytest.raises(ServiceAdapterError, match="base URL"):
        ask_chatqec(
            base_url,
            _fixture("ask-request.json"),
            transport=lambda **_: (_ for _ in ()).throw(
                AssertionError("transport must not be called")
            ),
        )


def test_chatqec_adapter_rejects_response_provenance_drift() -> None:
    request = _fixture("ask-request.json")
    response = copy.deepcopy(_fixture("answer-response.json"))
    response["corpus_revision"] = "sha256:" + "d" * 64

    with pytest.raises(
        ServiceAdapterError,
        match="corpus_revision does not match",
    ):
        validate_chatqec_response(response, request)


def test_chatqec_stream_requires_one_contiguous_final_event() -> None:
    request = _fixture("ask-request.json")
    incomplete = (
        "event: token\n"
        'data: {"request_id":"req-0001","sequence":0,'
        '"event":"token","data":{"text":"partial"}}\n\n'
    )

    with pytest.raises(ServiceAdapterError, match="exactly one final event"):
        parse_chatqec_sse(incomplete, request)
