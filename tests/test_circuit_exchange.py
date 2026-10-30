from __future__ import annotations

import io

import pytest

from qhpc_ecosystem.circuit_exchange import (
    CircuitExchangeError,
    MAX_QASM_BYTES,
    MAX_QPY_BYTES,
    exchange_to_qasm2,
    exchange_to_qpy,
    qasm2_to_exchange,
    qpy_to_exchange,
)
from qhpc_ecosystem.contract import validate_contract_data


qiskit = pytest.importorskip("qiskit")
from qiskit import QuantumCircuit, qpy  # noqa: E402


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
