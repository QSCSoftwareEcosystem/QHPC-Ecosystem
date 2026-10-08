from __future__ import annotations

from pathlib import Path
from types import ModuleType

import pytest

from qhpc_ecosystem.chatqec_agent_service import (
    ChatQECAgentServiceError,
    ChatQECMCPAgentResponder,
    DirectCircuitTools,
    OpenAIResponse,
    OpenAIResponsesBackend,
    _extract_circuit,
)
from qhpc_ecosystem.chatqec_readiness import MCP_DIRECT_TOOLS, validate_chatqec_health
from qhpc_ecosystem.service_adapters import build_chatqec_request


def _source(root: Path) -> Path:
    canonical = root / "knowledge" / "canonical"
    canonical.mkdir(parents=True)
    (canonical / "surface-code.md").write_text(
        "---\ntopic_slug: surface-code\ntitle: Surface Code\n---\n"
        "# Surface Code\n\n"
        "The surface code is a topological CSS quantum error-correcting code.\n\n"
        "## Decoding\n\n"
        "A decoder infers the most likely error from the measured syndrome.\n",
        encoding="utf-8",
    )
    return root


def test_extract_circuit_accepts_the_prompt_format_used_by_chatqec() -> None:
    question = (
        "Simulate this magic-state preparation circuit with a T gate and report detector samples: R 0\n"
        "T 0\nH 0\nM 0\nDETECTOR rec[-1]"
    )

    assert _extract_circuit(question) == "R 0\nT 0\nH 0\nM 0\nDETECTOR rec[-1]"


def test_extract_circuit_accepts_literal_newline_escapes_from_a_web_prompt() -> None:
    question = (
        "Simulate this magic-state preparation circuit with a T gate and report detector samples: "
        "R 0\\nT 0\\nH 0\\nM 0\\nDETECTOR rec[-1]"
    )

    assert _extract_circuit(question) == "R 0\nT 0\nH 0\nM 0\nDETECTOR rec[-1]"


def test_direct_agent_routes_a_t_gate_circuit_to_the_pinned_tsim_tool(
    monkeypatch,
) -> None:
    calls: list[object] = []

    class TsimSimulateInput:
        def __init__(self, *, circuit: str, shots: int) -> None:
            self.circuit = circuit
            self.shots = shots

    class Result:
        ok = True
        shots = 10
        samples_preview = [[1], [0], [1]]
        summary = "shape=(10, 1); showing first 10 rows"

    def tsim_simulate(request: TsimSimulateInput) -> Result:
        calls.append(request)
        return Result()

    package = ModuleType("chatqec_mcp_tools")
    package.__path__ = []  # type: ignore[attr-defined]
    tools = ModuleType("chatqec_mcp_tools.tools")
    tools.__path__ = []  # type: ignore[attr-defined]
    module = ModuleType("chatqec_mcp_tools.tools.tsim_simulate")
    module.TsimSimulateInput = TsimSimulateInput
    module.tsim_simulate = tsim_simulate
    monkeypatch.setitem(__import__("sys").modules, "chatqec_mcp_tools", package)
    monkeypatch.setitem(__import__("sys").modules, "chatqec_mcp_tools.tools", tools)
    monkeypatch.setitem(
        __import__("sys").modules, "chatqec_mcp_tools.tools.tsim_simulate", module
    )

    answer, tool_calls = DirectCircuitTools()(
        "Simulate this magic-state preparation circuit with a T gate and report detector samples: R 0\n"
        "T 0\nH 0\nM 0\nDETECTOR rec[-1]"
    ) or ("", [])

    assert len(calls) == 1
    assert calls[0].circuit == "R 0\nT 0\nH 0\nM 0\nDETECTOR rec[-1]"
    assert calls[0].shots == 10
    assert "Tsim circuit simulated successfully over 10 shots" in answer
    assert "Measurement Sample Output" in answer
    assert "Detector Sample Output" not in answer
    assert tool_calls == [
        {
            "name": "tsim_simulate",
            "status": "completed",
            "summary": "shape=(10, 1); showing first 10 rows",
        }
    ]


def test_direct_agent_reports_the_executed_tool_without_a_model_provider(tmp_path: Path) -> None:
    responder = ChatQECMCPAgentResponder(
        None,
        source_root=_source(tmp_path),
        direct_tools=lambda _question: (
            "Tsim circuit simulated successfully over 10 shots.",
            [{"name": "tsim_simulate", "status": "completed", "summary": "10 samples"}],
        ),
    )
    health = validate_chatqec_health(responder.health())
    assert health["mode"] == MCP_DIRECT_TOOLS
    assert health["tool_execution"] is True
    assert health["available"] is True

    request = build_chatqec_request(
        request_id="req-agent",
        correlation_id="corr-agent",
        conversation_id="conversation-agent",
        authorized_subject="subject-agent",
        workspace_id="workspace-agent",
        policy_class="public-qec",
        corpus_revision=health["corpus_revision"],
        question="R 0\nT 0\nH 0\nM 0\nDETECTOR rec[-1]",
    )
    response = responder.answer(request)

    assert response["tool_calls"] == [
        {"name": "tsim_simulate", "status": "completed", "summary": "10 samples"}
    ]
    assert response["citations"] == []
    assert response["confidence"] == 0.55


def test_local_source_ledger_returns_citations_and_extractive_answer(tmp_path: Path) -> None:
    responder = ChatQECMCPAgentResponder(
        None,
        source_root=_source(tmp_path),
        direct_tools=lambda _question: None,
    )
    health = validate_chatqec_health(responder.health())
    assert health["capabilities"]["source_ledger"] is True
    assert health["capabilities"]["model_rag"] is False
    assert health["readiness"]["knowledge"] == "ready"

    request = build_chatqec_request(
        request_id="req-ledger",
        correlation_id="corr-ledger",
        conversation_id="conversation-ledger",
        authorized_subject="subject-ledger",
        workspace_id="workspace-ledger",
        policy_class="public-qec",
        corpus_revision=health["corpus_revision"],
        question="How is the surface code decoded?",
    )
    response = responder.answer(request)

    assert response["provider"] == "chatqec-local"
    assert response["model"] == "canonical-source-ledger-v1"
    assert "Surface Code [S1]" in response["answer"]
    assert response["citations"] == [
        {
            "id": "canonical:surface-code",
            "title": "Surface Code",
            "source_uri": "https://github.com/QSCSoftwareEcosystem/ChatQEC/blob/a1ddc2e4916b1f4152fba4c94c9c7512eea0d977/knowledge/canonical/surface-code.md",
            "source_revision": response["citations"][0]["source_revision"],
            "locator": response["citations"][0]["locator"],
        }
    ]
    assert response["citations"][0]["locator"].startswith("knowledge/canonical/surface-code.md:L")
    assert response["confidence"] > 0.55


def test_optional_openai_model_answers_general_questions_and_receives_tool_results(
    tmp_path: Path,
) -> None:
    calls: list[tuple[str, object, str | None, str]] = []

    def model(question, history, tool_result, source_context) -> OpenAIResponse:
        calls.append((question, history, tool_result, source_context))
        return OpenAIResponse(
            text="A stabilizer is a measured parity constraint.",
            response_id="resp-local-test",
            input_tokens=12,
            output_tokens=9,
        )

    responder = ChatQECMCPAgentResponder(
        None,
        source_root=_source(tmp_path),
        direct_tools=lambda _question: None,
        openai_model="gpt-5.6-terra",
        openai_api_key="test-key",
        model_backend=model,
    )
    health = validate_chatqec_health(responder.health())
    assert health["readiness"]["model"] == "ready"
    assert health["capabilities"]["model_rag"] is True
    assert health["capabilities"]["source_ledger"] is True

    request = build_chatqec_request(
        request_id="req-openai",
        correlation_id="corr-openai",
        conversation_id="conversation-openai",
        authorized_subject="subject-openai",
        workspace_id="workspace-openai",
        policy_class="public-qec",
        corpus_revision=health["corpus_revision"],
        question="What does a surface-code stabilizer measure?",
    )
    response = responder.answer(request)

    assert len(calls) == 1
    assert calls[0][:3] == ("What does a surface-code stabilizer measure?", (), None)
    assert "Pinned ChatQEC source ledger" in calls[0][3]
    assert "[S1] Surface Code" in calls[0][3]
    assert response["answer"] == "A stabilizer is a measured parity constraint."
    assert response["provider"] == "openai"
    assert response["model"] == "gpt-5.6-terra"
    assert response["model_response_id"] == "resp-local-test"
    assert response["usage"] == {"input_tokens": 12, "output_tokens": 9, "total_tokens": 21}
    assert response["citations"][0]["id"] == "canonical:surface-code"
    assert response["confidence"] > 0.55


def test_agent_falls_back_to_pinned_evidence_when_model_has_no_visible_text(
    tmp_path: Path,
) -> None:
    def no_visible_text(*_args) -> OpenAIResponse:
        raise ChatQECAgentServiceError(
            "OpenAI model response was incomplete because its output-token budget was exhausted"
        )

    responder = ChatQECMCPAgentResponder(
        None,
        source_root=_source(tmp_path),
        direct_tools=lambda _question: None,
        openai_model="gpt-5.6-terra",
        openai_api_key="test-key",
        model_backend=no_visible_text,
    )
    health = validate_chatqec_health(responder.health())
    request = build_chatqec_request(
        request_id="req-model-fallback",
        correlation_id="corr-model-fallback",
        conversation_id="conversation-model-fallback",
        authorized_subject="subject-model-fallback",
        workspace_id="workspace-model-fallback",
        policy_class="public-qec",
        corpus_revision=health["corpus_revision"],
        question="How is the surface code decoded?",
    )

    response = responder.answer(request)

    assert response["provider"] == "chatqec-local"
    assert response["model"] == "verified-local-fallback-v1"
    assert "Surface Code [S1]" in response["answer"]
    assert "did not return visible text" in response["answer"]
    assert response["citations"][0]["id"] == "canonical:surface-code"


def test_openai_responses_backend_uses_the_responses_endpoint_without_storage() -> None:
    captured: list[object] = []

    def transport(request, timeout_seconds):
        captured.extend((request, timeout_seconds))
        return {
            "id": "resp-test",
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": "Grounded answer."}],
                }
            ],
            "usage": {"input_tokens": 7, "output_tokens": 4},
        }

    backend = OpenAIResponsesBackend(
        model="gpt-5.6-terra", api_key="test-key", transport=transport
    )
    result = backend(
        "Explain syndrome extraction.",
        (),
        "Measurement Sample Output",
        "Pinned ChatQEC source ledger (not external browsing):\n\n[S1] Syndrome Extraction",
    )

    request = captured[0]
    assert request.full_url == "https://api.openai.com/v1/responses"
    assert request.get_header("Authorization") == "Bearer test-key"
    payload = __import__("json").loads(request.data)
    assert payload["model"] == "gpt-5.6-terra"
    assert payload["store"] is False
    assert payload["reasoning"] == {"effort": "low", "context": "current_turn"}
    assert payload["max_output_tokens"] == 4096
    assert "Measurement Sample Output" in payload["input"][-1]["content"]
    assert "Pinned ChatQEC source ledger" in payload["input"][-1]["content"]
    assert captured[1] == 60.0
    assert result == OpenAIResponse("Grounded answer.", "resp-test", 7, 4)


def test_openai_responses_backend_identifies_an_incomplete_reasoning_response() -> None:
    backend = OpenAIResponsesBackend(
        model="gpt-5.6-terra",
        api_key="test-key",
        transport=lambda _request, _timeout: {
            "id": "resp-incomplete",
            "status": "incomplete",
            "incomplete_details": {"reason": "max_output_tokens"},
            "output": [{"type": "reasoning", "summary": []}],
            "usage": {"input_tokens": 7, "output_tokens": 4096},
        },
    )

    with pytest.raises(
        ChatQECAgentServiceError,
        match="output-token budget was exhausted",
    ):
        backend("Explain syndrome extraction.", (), None)
