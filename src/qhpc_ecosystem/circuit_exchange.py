"""Bounded Qiskit QPY ↔ EQO CircuitExchange conversion.

The adapter consumes a serialised circuit artifact rather than user-provided
Python source.  It intentionally supports a small, declared gate-model subset
and rejects control flow, custom definitions, and provider-specific metadata.
"""

from __future__ import annotations

import io
from typing import Any

from .contract import ContractError, validate_contract_data


MAX_QPY_BYTES = 8 * 1024 * 1024
MAX_QASM_BYTES = 2 * 1024 * 1024
SUPPORTED_GATES = frozenset(
    {
        "id",
        "x",
        "y",
        "z",
        "h",
        "s",
        "sdg",
        "t",
        "tdg",
        "rx",
        "ry",
        "rz",
        "p",
        "cx",
        "cz",
        "swap",
        "measure",
        "barrier",
    }
)
PARAMETER_GATES = frozenset({"rx", "ry", "rz", "p"})


class CircuitExchangeError(ValueError):
    """Raised for unsupported or non-reproducible circuit interchange."""


def _qiskit_modules() -> tuple[Any, Any, str]:
    try:
        import qiskit
        from qiskit import qpy
    except ImportError as error:
        raise CircuitExchangeError(
            "Qiskit QPY conversion requires the optional qiskit runtime"
        ) from error
    return qiskit, qpy, str(qiskit.__version__)


def _bit_label(circuit: Any, bit: Any, *, classical: bool) -> str:
    index = circuit.find_bit(bit).index
    return f"{'c' if classical else 'q'}[{index}]"


def _parameter_text(value: Any) -> str:
    text = str(value)
    if not text or len(text) > 256:
        raise CircuitExchangeError("circuit parameter has an unsupported representation")
    return text


def circuit_to_exchange(
    circuit: Any,
    *,
    source_name: str = "qiskit",
    source_version: str | None = None,
    adapter: str = "qiskit-qpy-to-circuit-exchange",
) -> dict[str, Any]:
    """Normalise one Qiskit circuit into an immutable exchange document."""
    _, _, qiskit_version = _qiskit_modules()
    operations: list[dict[str, Any]] = []
    limitations: list[str] = []
    for index, instruction in enumerate(circuit.data):
        operation = instruction.operation
        name = str(operation.name).lower()
        if name not in SUPPORTED_GATES:
            limitations.append(f"Unsupported Qiskit instruction: {operation.name}")
            continue
        if getattr(operation, "condition", None) is not None:
            limitations.append(f"Classically conditioned instruction is unsupported: {operation.name}")
            continue
        parameters = [_parameter_text(value) for value in operation.params]
        if name in PARAMETER_GATES and len(parameters) != 1:
            limitations.append(f"Instruction has an unsupported parameter arity: {operation.name}")
            continue
        if name not in PARAMETER_GATES and parameters:
            limitations.append(f"Instruction has unexpected parameters: {operation.name}")
            continue
        operations.append(
            {
                "index": index,
                "gate": name,
                "qubits": [
                    _bit_label(circuit, bit, classical=False)
                    for bit in instruction.qubits
                ],
                "classical_bits": [
                    _bit_label(circuit, bit, classical=True)
                    for bit in instruction.clbits
                ],
                "parameters": parameters,
                "condition": None,
            }
        )
    if limitations:
        raise CircuitExchangeError("; ".join(limitations))
    version = source_version or qiskit_version
    record_id = (
        "qhpc.qiskit-circuit-exchange"
        if source_name == "qiskit"
        else f"qhpc.{source_name}-circuit-exchange"
    )
    record_name = (
        "Qiskit circuit exchange record"
        if source_name == "qiskit"
        else f"{source_name} circuit exchange record"
    )
    parameters = sorted(str(parameter) for parameter in circuit.parameters)
    document = {
        "api_version": "qhpc/v1",
        "kind": "CircuitExchange",
        "metadata": {
            "id": record_id,
            "name": record_name,
            "version": 1,
            "source": {"name": source_name, "version": version},
            "transformation": {
                "adapter": adapter,
                "classification": "exact",
                "target": {"name": "qiskit", "version": qiskit_version},
            },
        },
        "spec": {
            "qubit_order": [f"q[{index}]" for index in range(circuit.num_qubits)],
            "classical_bit_order": [
                f"c[{index}]" for index in range(circuit.num_clbits)
            ],
            "parameters": parameters,
            "global_phase": _parameter_text(circuit.global_phase),
            "operations": operations,
            "limitations": [],
        },
    }
    try:
        validate_contract_data("circuit-exchange", document)
    except ContractError as error:
        raise CircuitExchangeError(f"normalised circuit violates CircuitExchange: {error}") from error
    return document


def qpy_to_exchange(payload: bytes) -> dict[str, Any]:
    """Read a single bounded QPY circuit without evaluating user Python."""
    if not isinstance(payload, bytes) or not payload:
        raise CircuitExchangeError("QPY input must be a non-empty byte artifact")
    if len(payload) > MAX_QPY_BYTES:
        raise CircuitExchangeError(
            f"QPY input exceeds the {MAX_QPY_BYTES // (1024 * 1024)} MiB limit"
        )
    _, qpy, _ = _qiskit_modules()
    try:
        circuits = list(qpy.load(io.BytesIO(payload)))
    except Exception as error:  # Qiskit owns the wire-format parser.
        raise CircuitExchangeError("QPY artifact could not be decoded") from error
    if len(circuits) != 1:
        raise CircuitExchangeError("QPY artifact must contain exactly one circuit")
    return circuit_to_exchange(circuits[0])


def qasm2_to_exchange(payload: str | bytes) -> dict[str, Any]:
    """Read a bounded OpenQASM 2 artifact through Qiskit's non-executing parser."""
    if isinstance(payload, bytes):
        if len(payload) > MAX_QASM_BYTES:
            raise CircuitExchangeError(
                f"OpenQASM input exceeds the {MAX_QASM_BYTES // (1024 * 1024)} MiB limit"
            )
        try:
            source = payload.decode("utf-8")
        except UnicodeDecodeError as error:
            raise CircuitExchangeError("OpenQASM input must be UTF-8 text") from error
    elif isinstance(payload, str):
        if len(payload.encode("utf-8")) > MAX_QASM_BYTES:
            raise CircuitExchangeError(
                f"OpenQASM input exceeds the {MAX_QASM_BYTES // (1024 * 1024)} MiB limit"
            )
        source = payload
    else:
        raise CircuitExchangeError("OpenQASM input must be text or a byte artifact")
    if not source.strip():
        raise CircuitExchangeError("OpenQASM input must not be empty")
    try:
        from qiskit import qasm2

        circuit = qasm2.loads(source)
    except ImportError as error:
        raise CircuitExchangeError(
            "OpenQASM conversion requires the optional qiskit runtime"
        ) from error
    except Exception as error:  # Qiskit owns the grammar parser.
        raise CircuitExchangeError("OpenQASM 2 artifact could not be decoded") from error
    return circuit_to_exchange(
        circuit,
        source_name="openqasm",
        source_version="2.0",
        adapter="openqasm-2-to-circuit-exchange",
    )


def _bit_index(label: str, prefix: str, maximum: int) -> int:
    if not label.startswith(f"{prefix}[") or not label.endswith("]"):
        raise CircuitExchangeError(f"invalid {prefix} bit label: {label}")
    try:
        index = int(label[2:-1])
    except ValueError as error:
        raise CircuitExchangeError(f"invalid {prefix} bit label: {label}") from error
    if not 0 <= index < maximum:
        raise CircuitExchangeError(f"{prefix} bit is out of range: {label}")
    return index


def _qiskit_parameter(value: str, parameters: dict[str, Any]) -> Any:
    if value in parameters:
        return parameters[value]
    try:
        return float(value)
    except ValueError:
        pass
    if value == "pi":
        import math

        return math.pi
    if value in {"pi/2", "pi / 2"}:
        import math

        return math.pi / 2
    if value in {"-pi", "-pi/2", "-pi / 2"}:
        import math

        return -math.pi if value == "-pi" else -math.pi / 2
    raise CircuitExchangeError(
        f"parameter expression {value!r} is not in the safe exchange subset"
    )


def _exchange_to_qiskit_circuit(document: dict[str, Any]) -> Any:
    """Construct a Qiskit circuit only from a validated exchange document."""
    try:
        validate_contract_data("circuit-exchange", document)
    except ContractError as error:
        raise CircuitExchangeError(f"invalid CircuitExchange document: {error}") from error
    if document["spec"]["limitations"]:
        raise CircuitExchangeError(
            "CircuitExchange with declared limitations cannot be emitted as QPY"
        )
    try:
        from qiskit import QuantumCircuit
        from qiskit.circuit import Parameter
    except ImportError as error:
        raise CircuitExchangeError(
            "Qiskit QPY conversion requires the optional qiskit runtime"
        ) from error

    specification = document["spec"]
    circuit = QuantumCircuit(
        len(specification["qubit_order"]),
        len(specification["classical_bit_order"]),
    )
    parameters = {name: Parameter(name) for name in specification["parameters"]}
    global_phase = specification.get("global_phase")
    if global_phase not in {None, "0", "0.0"}:
        circuit.global_phase = _qiskit_parameter(str(global_phase), parameters)

    for operation in specification["operations"]:
        gate = operation["gate"]
        if gate not in SUPPORTED_GATES:
            raise CircuitExchangeError(f"unsupported target gate: {gate}")
        qubits = [
            _bit_index(value, "q", circuit.num_qubits)
            for value in operation["qubits"]
        ]
        classical_bits = [
            _bit_index(value, "c", circuit.num_clbits)
            for value in operation["classical_bits"]
        ]
        parameter_values = [
            _qiskit_parameter(value, parameters)
            for value in operation["parameters"]
        ]
        if gate == "measure":
            if len(qubits) != 1 or len(classical_bits) != 1:
                raise CircuitExchangeError("measure requires exactly one qubit and classical bit")
            circuit.measure(qubits[0], classical_bits[0])
        elif gate == "barrier":
            circuit.barrier(*qubits)
        else:
            method = getattr(circuit, gate, None)
            if not callable(method):
                raise CircuitExchangeError(f"Qiskit does not expose supported gate {gate}")
            method(*parameter_values, *qubits)
    return circuit


def exchange_to_qpy(document: dict[str, Any]) -> bytes:
    """Emit one QPY artifact from the declared CircuitExchange subset."""
    circuit = _exchange_to_qiskit_circuit(document)
    _, qpy, _ = _qiskit_modules()
    target = io.BytesIO()
    try:
        qpy.dump(circuit, target)
    except Exception as error:
        raise CircuitExchangeError("CircuitExchange could not be encoded as QPY") from error
    return target.getvalue()


def exchange_to_qasm2(document: dict[str, Any]) -> str:
    """Emit OpenQASM 2 from the declared CircuitExchange subset."""
    circuit = _exchange_to_qiskit_circuit(document)
    try:
        from qiskit import qasm2

        return qasm2.dumps(circuit)
    except ImportError as error:
        raise CircuitExchangeError(
            "OpenQASM conversion requires the optional qiskit runtime"
        ) from error
    except Exception as error:
        raise CircuitExchangeError(
            "CircuitExchange could not be encoded as OpenQASM 2"
        ) from error
