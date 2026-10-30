from __future__ import annotations

import io
import json

import pytest

from qhpc_ecosystem.circuit_exchange import (
    CircuitExchangeError,
    MAX_QASM_BYTES,
    MAX_QPY_BYTES,
    exchange_to_qasm2,
    exchange_to_qasm3,
    exchange_to_pytket,
    exchange_to_qpy,
    exchange_to_cirq,
    cirq_to_exchange,
    qasm2_to_exchange,
    qasm3_to_exchange,
    pytket_conversion_report,
    pytket_to_exchange,
    qpy_to_exchange,
)
from qhpc_ecosystem.contract import validate_contract_data
from qhpc_ecosystem.engine import WorkflowEngine
from qhpc_ecosystem.transpilation_service import (
    TranspilationService,
    TranspilationServiceError,
)


qiskit = pytest.importorskip("qiskit")
from qiskit import QuantumCircuit, qpy  # noqa: E402

cirq = pytest.importorskip("cirq")


def qpy_payload(circuit: QuantumCircuit) -> bytes:
    stream = io.BytesIO()
    qpy.dump(circuit, stream)
    return stream.getvalue()


def test_qpy_exchange_round_trip_preserves_a_bell_measurement_circuit() -> None:
    circuit = QuantumCircuit(2, 2)
    circuit.h(0)
    circuit.cx(0, 1)
    circuit.measure(0, 0)
    circuit.measure(1, 1)

    exchange = qpy_to_exchange(qpy_payload(circuit))

    validate_contract_data("circuit-exchange", exchange)
    assert exchange["metadata"]["transformation"]["classification"] == "exact"
    assert exchange["spec"]["qubit_order"] == ["q[0]", "q[1]"]
    assert [item["gate"] for item in exchange["spec"]["operations"]] == [
        "h",
        "cx",
        "measure",
        "measure",
    ]

    restored = list(qpy.load(io.BytesIO(exchange_to_qpy(exchange))))
    assert len(restored) == 1
    assert restored[0].num_qubits == 2
    assert restored[0].num_clbits == 2
    assert list(restored[0].count_ops().items()) == [("measure", 2), ("h", 1), ("cx", 1)]


def test_qpy_exchange_rejects_multi_circuit_or_oversized_payloads() -> None:
    first = QuantumCircuit(1)
    second = QuantumCircuit(1)
    stream = io.BytesIO()
    qpy.dump([first, second], stream)

    with pytest.raises(CircuitExchangeError, match="exactly one circuit"):
        qpy_to_exchange(stream.getvalue())
    with pytest.raises(CircuitExchangeError, match="exceeds"):
        qpy_to_exchange(b"0" * (MAX_QPY_BYTES + 1))


def test_openqasm_2_exchange_round_trip_preserves_bell_measurements() -> None:
    source = """OPENQASM 2.0;
include \"qelib1.inc\";
qreg q[2];
creg c[2];
h q[0];
cx q[0],q[1];
measure q[0] -> c[0];
measure q[1] -> c[1];
"""

    exchange = qasm2_to_exchange(source)

    assert exchange["metadata"]["source"] == {"name": "openqasm", "version": "2.0"}
    assert exchange["metadata"]["transformation"]["adapter"] == (
        "openqasm-2-to-circuit-exchange"
    )
    rendered = exchange_to_qasm2(exchange)
    assert rendered.startswith("OPENQASM 2.0;")
    restored = qasm2_to_exchange(rendered)
    assert [item["gate"] for item in restored["spec"]["operations"]] == [
        "h",
        "cx",
        "measure",
        "measure",
    ]


def test_openqasm_2_exchange_rejects_invalid_or_oversized_input() -> None:
    with pytest.raises(CircuitExchangeError, match="could not be decoded"):
        qasm2_to_exchange("OPENQASM 2.0; this is not valid;")
    with pytest.raises(CircuitExchangeError, match="exceeds"):
        qasm2_to_exchange("0" * (MAX_QASM_BYTES + 1))


def test_openqasm_3_exchange_round_trip_preserves_static_bell_measurements() -> None:
    pytest.importorskip("qiskit_qasm3_import")
    source = """OPENQASM 3.0;
include \"stdgates.inc\";
qubit[2] q;
bit[2] c;
h q[0];
cx q[0], q[1];
c[0] = measure q[0];
c[1] = measure q[1];
"""

    exchange = qasm3_to_exchange(source)

    assert exchange["metadata"]["source"] == {"name": "openqasm", "version": "3.0"}
    assert exchange["metadata"]["transformation"]["adapter"] == (
        "openqasm-3-to-circuit-exchange"
    )
    rendered = exchange_to_qasm3(exchange)
    assert rendered.startswith("OPENQASM 3.0;")
    restored = qasm3_to_exchange(rendered)
    assert [item["gate"] for item in restored["spec"]["operations"]] == [
        "h",
        "cx",
        "measure",
        "measure",
    ]


def test_openqasm_3_exchange_rejects_other_versions_and_dynamic_control() -> None:
    with pytest.raises(CircuitExchangeError, match="OPENQASM 3 header"):
        qasm3_to_exchange("OPENQASM 2.0; include \"qelib1.inc\";")
    with pytest.raises(
        CircuitExchangeError,
        match="could not be decoded|Unsupported Qiskit instruction",
    ):
        qasm3_to_exchange("""OPENQASM 3.0;
include \"stdgates.inc\";
qubit q;
bit c;
c = measure q;
if (c == 1) { x q; }
""")


def test_cirq_exchange_round_trip_preserves_static_bell_operations() -> None:
    source = QuantumCircuit(2, 2)
    source.h(0)
    source.cx(0, 1)
    source.measure(0, 0)
    source.measure(1, 1)
    exchange = qpy_to_exchange(qpy_payload(source))

    cirq_circuit = exchange_to_cirq(exchange)
    restored = cirq_to_exchange(cirq_circuit)

    assert [item["gate"] for item in restored["spec"]["operations"]] == [
        "h",
        "cx",
        "measure",
        "measure",
    ]
    assert restored["spec"]["classical_bit_order"] == ["c[0]", "c[1]"]


def test_cirq_exchange_rejects_unmapped_qubits_and_measurement_keys() -> None:
    named = cirq.Circuit(cirq.H(cirq.NamedQubit("source")))
    with pytest.raises(CircuitExchangeError, match="LineQubit"):
        cirq_to_exchange(named)

    invalid_measurement = cirq.Circuit(
        cirq.measure(cirq.LineQubit(0), key="result")
    )
    with pytest.raises(CircuitExchangeError, match="c<number>"):
        cirq_to_exchange(invalid_measurement)


def test_pytket_bridge_preserves_a_static_bell_circuit_and_identity_mapping() -> None:
    pytest.importorskip("pytket")
    source = QuantumCircuit(2, 2)
    source.h(0)
    source.cx(0, 1)
    source.rz(0.25, 1)
    source.measure(0, 0)
    source.measure(1, 1)
    exchange = qpy_to_exchange(qpy_payload(source))

    pytket_circuit = exchange_to_pytket(exchange)
    restored = pytket_to_exchange(pytket_circuit)
    report = pytket_conversion_report(exchange)

    assert sorted(item["gate"] for item in restored["spec"]["operations"]) == [
        "cx",
        "h",
        "measure",
        "measure",
        "rz",
    ]
    rz = next(item for item in restored["spec"]["operations"] if item["gate"] == "rz")
    assert float(rz["parameters"][0]) == pytest.approx(0.25)
    assert report == {
        "adapter": "circuit-exchange-to-pytket",
        "classification": "exact",
        "qubit_mapping": [
            {"source": "q[0]", "target": "q[0]"},
            {"source": "q[1]", "target": "q[1]"},
        ],
        "implicit_swaps": [],
        "gate_decompositions": [],
        "compiler_options": {},
        "target_profile": None,
        "warnings": [],
    }


def test_pytket_bridge_rejects_symbolic_and_barrier_exchange_semantics() -> None:
    pytest.importorskip("pytket")
    source = QuantumCircuit(1)
    source.barrier(0)
    exchange = qpy_to_exchange(qpy_payload(source))
    with pytest.raises(CircuitExchangeError, match="barrier"):
        exchange_to_pytket(exchange)


def test_transpilation_service_persists_a_complete_artifact_evidence_chain(
    tmp_path,
) -> None:
    engine = WorkflowEngine(tmp_path / "engine.sqlite", tmp_path / "artifacts")
    source = engine.register_input_artifact(
        artifact_type="qhpc.quantum-circuit@1",
        content=b'''OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0],q[1];
measure q[0] -> c[0];
measure q[1] -> c[1];
''',
        name="bell.qasm",
        created_by="test",
    )

    result = TranspilationService(engine).convert(
        source["id"],
        source_format="openqasm-2",
        target_format="openqasm-3",
        created_by="test",
    )

    assert result["source_artifact"]["id"] == source["id"]
    assert result["normalized_artifact"]["artifact_type"] == "qhpc.circuit-exchange@1"
    assert result["transformed_artifact"]["artifact_type"] == "qhpc.transpiled-circuit@1"
    assert result["report_artifact"]["artifact_type"] == "qhpc.transpilation-report@1"
    _, normalized, _ = engine.read_artifact_content(result["normalized_artifact"]["id"])
    validate_contract_data("circuit-exchange", json.loads(normalized))
    _, transformed, _ = engine.read_artifact_content(result["transformed_artifact"]["id"])
    assert transformed.decode("utf-8").startswith("OPENQASM 3.0;")
    _, report_bytes, _ = engine.read_artifact_content(result["report_artifact"]["id"])
    report = json.loads(report_bytes)
    assert report["source"]["artifact_id"] == source["id"]
    assert report["normalized"]["artifact_id"] == result["normalized_artifact"]["id"]
    assert report["transformed"]["artifact_id"] == result["transformed_artifact"]["id"]
    assert report["warnings"] == []


def test_transpilation_service_requires_a_preexisting_circuit_artifact(tmp_path) -> None:
    engine = WorkflowEngine(tmp_path / "engine.sqlite", tmp_path / "artifacts")
    non_circuit = engine.register_input_artifact(
        artifact_type="qhpc.measurement-results@1",
        content=b"{}",
        name="results.json",
        created_by="test",
    )

    with pytest.raises(TranspilationServiceError, match="declared EQO circuit"):
        TranspilationService(engine).convert(
            non_circuit["id"],
            source_format="openqasm-2",
            target_format="openqasm-3",
            created_by="test",
        )
