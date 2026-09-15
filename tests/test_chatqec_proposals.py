from __future__ import annotations

import copy
from datetime import datetime, timezone
from pathlib import Path

import pytest

from qhpc_ecosystem.chatqec_proposals import (
    ChatQECProposalError,
    validate_tool_proposal,
)
from qhpc_ecosystem.contract import load_document, validate_contract
from qhpc_ecosystem.registry import registry_digest


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "contracts" / "valid" / "chatqec-tool-proposal.yaml"


def _registry() -> dict:
    """A future admitted runtime snapshot used only to test proposal validation."""

    return {
        "api_version": "qhpc/v1",
        "kind": "Registry",
        "metadata": {"entry_count": 1, "catalog_digest": "sha256:" + "a" * 64},
        "spec": {
            "entries": [
                {
                    "capability": {
                        "metadata": {
                            "id": "chatqec-qec-tools",
                            "version": "0.1.0",
                        },
                        "spec": {
                            "operations": [
                                {
                                    "id": "code-params",
                                    "inputs": {},
                                    "outputs": {
                                        "parameters": {
                                            "artifact_type": "qhpc.qec-code-parameters@1"
                                        }
                                    },
                                    "parameters": {
                                        "code_family": {
                                            "type": "string",
                                            "required": True,
                                            "enum": [
                                                "surface_code_rotated",
                                                "repetition_code",
                                                "color_code",
                                            ],
                                        },
                                        "distance": {
                                            "type": "integer",
                                            "required": True,
                                            "minimum": 3,
                                            "maximum": 15,
                                        },
                                    },
                                    "execution_targets": ["local-development"],
                                    "resources": {
                                        "cpu": 1,
                                        "memory_mb": 512,
                                        "walltime_seconds": 60,
                                    },
                                }
                            ]
                        },
                    }
                }
            ]
        },
    }


def _proposal(registry: dict) -> dict:
    proposal = load_document(EXAMPLE)
    proposal["metadata"]["created_at"] = "2026-09-11T12:00:00Z"
    proposal["metadata"]["expires_at"] = "2026-09-11T12:15:00Z"
    proposal["spec"]["registry_digest"] = registry_digest(registry)
    return proposal


def test_tool_proposal_contract_is_valid_and_resolves_one_admitted_operation() -> None:
    validate_contract("chatqec-tool-proposal", EXAMPLE)
    registry = _registry()
    proposal = _proposal(registry)

    assert validate_tool_proposal(
        proposal,
        registry,
        now=datetime(2026, 9, 11, 12, 1, tzinfo=timezone.utc),
    ) == proposal


def test_tool_proposal_rejects_unadmitted_or_mismatched_targets() -> None:
    registry = _registry()
    proposal = _proposal(registry)
    proposal["spec"]["target"]["operation"] = "stim-simulate"

    with pytest.raises(ChatQECProposalError, match="does not match the source tool"):
        validate_tool_proposal(
            proposal,
            registry,
            now=datetime(2026, 9, 11, 12, 1, tzinfo=timezone.utc),
        )

    proposal = _proposal(registry)
    proposal["spec"]["target"]["capability"] = "missing-capability"
    proposal["spec"]["registry_digest"] = registry_digest(registry)
    with pytest.raises(ChatQECProposalError, match="does not resolve to an admitted capability"):
        validate_tool_proposal(
            proposal,
            registry,
            now=datetime(2026, 9, 11, 12, 1, tzinfo=timezone.utc),
        )


def test_tool_proposal_cannot_smuggle_commands_or_bypass_confirmation() -> None:
    registry = _registry()
    proposal = _proposal(registry)
    proposal["spec"]["parameters"]["command"] = "python -c unsafe"

    with pytest.raises(ChatQECProposalError, match="unsupported parameters: command"):
        validate_tool_proposal(
            proposal,
            registry,
            now=datetime(2026, 9, 11, 12, 1, tzinfo=timezone.utc),
        )

    proposal = _proposal(registry)
    proposal["spec"]["confirmation"]["required"] = False
    with pytest.raises(ChatQECProposalError, match="does not match the v1 contract"):
        validate_tool_proposal(
            proposal,
            registry,
            now=datetime(2026, 9, 11, 12, 1, tzinfo=timezone.utc),
        )


def test_tool_proposal_expires_and_does_not_mutate_the_input() -> None:
    registry = _registry()
    proposal = _proposal(registry)
    original = copy.deepcopy(proposal)

    with pytest.raises(ChatQECProposalError, match="has expired"):
        validate_tool_proposal(
            proposal,
            registry,
            now=datetime(2026, 9, 11, 12, 16, tzinfo=timezone.utc),
        )
    assert proposal == original
