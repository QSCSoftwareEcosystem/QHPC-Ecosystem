"""Artifact-first, bounded circuit interchange for EQO.

The service only reads an existing, checksum-verified EQO circuit artifact.
It intentionally has no Python-source importer: callers must provide a
serialised QPY, OpenQASM 2, OpenQASM 3, or CircuitExchange artifact.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .circuit_exchange import (
    CircuitExchangeError,
    exchange_to_qasm2,
    exchange_to_qasm3,
    exchange_to_pytket,
    exchange_to_qpy,
    pytket_conversion_report,
    qasm2_to_exchange,
    qasm3_to_exchange,
    qpy_to_exchange,
)
from .contract import ContractError, validate_contract_data
from .engine import WorkflowEngine


SOURCE_FORMATS = frozenset({"openqasm-2", "openqasm-3", "qiskit-qpy", "circuit-exchange"})
TARGET_FORMATS = frozenset(
    {"openqasm-2", "openqasm-3", "qiskit-qpy", "pytket-json"}
)
SOURCE_ARTIFACT_TYPES = frozenset(
    {
        "qhpc.quantum-circuit@1",
        "qhpc.transpiled-circuit@1",
        "qhpc.circuit-exchange@1",
    }
)
EXCHANGE_ARTIFACT_TYPE = "qhpc.circuit-exchange@1"
REPORT_ARTIFACT_TYPE = "qhpc.transpilation-report@1"


class TranspilationServiceError(ValueError):
    """Raised when a requested artifact conversion is unsafe or unsupported."""


def _canonical_json(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _safe_stem(name: str) -> str:
    stem = Path(name).stem.strip()
    if not stem:
        return "circuit"
    return "".join(character if character.isalnum() or character in {"-", "_"} else "-" for character in stem)[:80] or "circuit"


class TranspilationService:
    """Convert an admitted circuit artifact and persist a complete evidence chain."""

    def __init__(self, engine: WorkflowEngine) -> None:
        self.engine = engine

    @staticmethod
    def _exchange_from_payload(source_format: str, payload: bytes) -> dict[str, Any]:
        try:
            if source_format == "openqasm-2":
                return qasm2_to_exchange(payload)
            if source_format == "openqasm-3":
                return qasm3_to_exchange(payload)
            if source_format == "qiskit-qpy":
                return qpy_to_exchange(payload)
            if source_format == "circuit-exchange":
                try:
                    document = json.loads(payload.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as error:
                    raise TranspilationServiceError(
                        "CircuitExchange input must be a UTF-8 JSON artifact"
                    ) from error
                if not isinstance(document, dict):
                    raise TranspilationServiceError("CircuitExchange input must be a JSON object")
                validate_contract_data("circuit-exchange", document)
                return document
        except (CircuitExchangeError, ContractError) as error:
            raise TranspilationServiceError(str(error)) from error
        raise TranspilationServiceError(f"unsupported source format: {source_format}")

    @staticmethod
    def _target_from_exchange(
        target_format: str,
        document: dict[str, Any],
    ) -> tuple[bytes, str, str, dict[str, Any] | None]:
        try:
            if target_format == "openqasm-2":
                return (
                    exchange_to_qasm2(document).encode("utf-8"),
                    "qasm",
                    "circuit-exchange-to-openqasm-2",
                    None,
                )
            if target_format == "openqasm-3":
                return (
                    exchange_to_qasm3(document).encode("utf-8"),
                    "qasm",
                    "circuit-exchange-to-openqasm-3",
                    None,
                )
            if target_format == "qiskit-qpy":
                return (
                    exchange_to_qpy(document),
                    "qpy",
                    "circuit-exchange-to-qiskit-qpy",
                    None,
                )
            if target_format == "pytket-json":
                circuit = exchange_to_pytket(document)
                return (
                    _canonical_json(circuit.to_dict()),
                    "pytket.json",
                    "circuit-exchange-to-pytket",
                    pytket_conversion_report(document),
                )
        except CircuitExchangeError as error:
            raise TranspilationServiceError(str(error)) from error
        raise TranspilationServiceError(f"unsupported target format: {target_format}")

    def convert(
        self,
        source_artifact_id: str,
        *,
        source_format: str,
        target_format: str,
        created_by: str,
    ) -> dict[str, Any]:
        """Convert one verified circuit artifact and record immutable evidence.

        The source artifact stays untouched.  The returned records are input
        artifacts so their checksums, labels, and content remain available even
        when this conversion is not yet attached to a workflow run.
        """
        if not isinstance(source_artifact_id, str) or not source_artifact_id:
            raise TranspilationServiceError("source artifact identifier is required")
        if source_format not in SOURCE_FORMATS:
            raise TranspilationServiceError(
                "source format must be one of: " + ", ".join(sorted(SOURCE_FORMATS))
            )
        if target_format not in TARGET_FORMATS:
            raise TranspilationServiceError(
                "target format must be one of: " + ", ".join(sorted(TARGET_FORMATS))
            )
        if not isinstance(created_by, str) or not created_by.strip() or len(created_by) > 256:
            raise TranspilationServiceError("created_by must be a non-empty string no longer than 256 characters")

        source, payload, source_name = self.engine.read_artifact_content(source_artifact_id)
        if source.get("artifact_type") not in SOURCE_ARTIFACT_TYPES:
            raise TranspilationServiceError(
                "source artifact must be a declared EQO circuit artifact type"
            )
        exchange = self._exchange_from_payload(source_format, payload)
        transformed, extension, target_adapter, target_evidence = self._target_from_exchange(
            target_format,
            exchange,
        )
        normalized_payload = _canonical_json(exchange)
        limitations = exchange["spec"].get("limitations", [])
        if not isinstance(limitations, list):  # Defensive: contract validation above guards this.
            raise TranspilationServiceError("CircuitExchange limitations are invalid")
        source_metadata = exchange["metadata"]["transformation"]
        if not isinstance(source_metadata, dict):
            raise TranspilationServiceError("CircuitExchange transformation evidence is invalid")

        stem = _safe_stem(source_name)
        normalized_artifact = self.engine.register_input_artifact(
            artifact_type=EXCHANGE_ARTIFACT_TYPE,
            content=normalized_payload,
            name=f"{stem}.circuit-exchange.json",
            created_by=created_by,
            labels={
                "eqo.transpilation.source-artifact": source_artifact_id,
                "eqo.transpilation.role": "normalized-circuit",
                "eqo.transpilation.source-format": source_format,
            },
        )
        transformed_artifact = self.engine.register_input_artifact(
            artifact_type="qhpc.transpiled-circuit@1",
            content=transformed,
            name=f"{stem}.{target_format}.{extension}",
            created_by=created_by,
            labels={
                "eqo.transpilation.source-artifact": source_artifact_id,
                "eqo.transpilation.normalized-artifact": normalized_artifact["id"],
                "eqo.transpilation.role": "transformed-circuit",
                "eqo.transpilation.target-format": target_format,
            },
        )
        report = {
            "api_version": "qhpc/v1",
            "kind": "TranspilationReport",
            "classification": source_metadata.get("classification", "exact"),
            "source": {
                "artifact_id": source_artifact_id,
                "format": source_format,
                "checksum": source["checksum"],
            },
            "normalized": {
                "artifact_id": normalized_artifact["id"],
                "format": "circuit-exchange",
                "adapter": source_metadata.get("adapter"),
            },
            "transformed": {
                "artifact_id": transformed_artifact["id"],
                "format": target_format,
                "adapter": target_adapter,
            },
            "qubit_mapping": [
                {"source": label, "target": label}
                for label in exchange["spec"]["qubit_order"]
            ],
            "implicit_swaps": [],
            "gate_decompositions": [],
            "compiler_options": {},
            "target_profile": None,
            "warnings": limitations,
        }
        if target_evidence is not None:
            report = {
                **report,
                "classification": target_evidence["classification"],
                "qubit_mapping": target_evidence["qubit_mapping"],
                "implicit_swaps": target_evidence["implicit_swaps"],
                "gate_decompositions": target_evidence["gate_decompositions"],
                "compiler_options": target_evidence["compiler_options"],
                "target_profile": target_evidence["target_profile"],
                "warnings": [*limitations, *target_evidence["warnings"]],
            }
        report_artifact = self.engine.register_input_artifact(
            artifact_type=REPORT_ARTIFACT_TYPE,
            content=_canonical_json(report),
            name=f"{stem}.transpilation-report.json",
            created_by=created_by,
            labels={
                "eqo.transpilation.source-artifact": source_artifact_id,
                "eqo.transpilation.normalized-artifact": normalized_artifact["id"],
                "eqo.transpilation.transformed-artifact": transformed_artifact["id"],
                "eqo.transpilation.role": "conversion-report",
            },
        )
        return {
            "source_artifact": source,
            "normalized_artifact": normalized_artifact,
            "transformed_artifact": transformed_artifact,
            "report_artifact": report_artifact,
            "report": report,
        }
