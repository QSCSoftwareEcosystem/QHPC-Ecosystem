from __future__ import annotations

from pathlib import Path
from types import ModuleType

from qhpc_ecosystem.chatqec_agent_service import (
    ChatQECMCPAgentResponder,
    DirectCircuitTools,
    _extract_circuit,
)
from qhpc_ecosystem.chatqec_readiness import MCP_DIRECT_TOOLS, validate_chatqec_health
from qhpc_ecosystem.service_adapters import build_chatqec_request


def _source(root: Path) -> Path:
    canonical = root / "knowledge" / "canonical"
    canonical.mkdir(parents=True)
    (canonical / "surface-code.md").write_text(
        "---\ntopic_slug: surface-code\ntitle: Surface Code\n---\n# Surface Code\n",
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
