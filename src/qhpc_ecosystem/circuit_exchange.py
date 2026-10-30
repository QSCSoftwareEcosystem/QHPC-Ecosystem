"""Bounded Qiskit QPY ↔ EQO CircuitExchange conversion.

The adapter consumes a serialised circuit artifact rather than user-provided
Python source.  It intentionally supports a small, declared gate-model subset
and rejects control flow, custom definitions, and provider-specific metadata.
"""

from __future__ import annotations

import io
import math
import re
from typing import Any

from .contract import ContractError, validate_contract_data


MAX_QPY_BYTES = 8 * 1024 * 1024
MAX_QASM_BYTES = 2 * 1024 * 1024
MAX_CIRQ_OPERATIONS = 10_000
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
_CIRQ_CLASSICAL_KEY = re.compile(r"^c([0-9]+)$")


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


def qasm3_to_exchange(payload: str | bytes) -> dict[str, Any]:
    """Read a bounded static OpenQASM 3 artifact through Qiskit's parser.

    Qiskit's importer can represent broader OpenQASM 3 programs than the
    CircuitExchange contract.  `circuit_to_exchange` therefore remains the
    second, fail-closed gate: dynamic control flow, timing, custom operations,
    and any unrepresented instruction cannot cross this adapter.
    """
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
    if re.search(r"^\s*OPENQASM\s+3(?:\.\d+)?\s*;", source) is None:
        raise CircuitExchangeError("OpenQASM 3 input must declare an OPENQASM 3 header")
    try:
        from qiskit import qasm3

        circuit = qasm3.loads(source)
    except ImportError as error:
        raise CircuitExchangeError(
            "OpenQASM 3 conversion requires qiskit and qiskit-qasm3-import"
        ) from error
    except Exception as error:  # Qiskit owns the grammar parser.
        raise CircuitExchangeError("OpenQASM 3 artifact could not be decoded") from error
    return circuit_to_exchange(
        circuit,
        source_name="openqasm",
        source_version="3.0",
        adapter="openqasm-3-to-circuit-exchange",
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


def exchange_to_qasm3(document: dict[str, Any]) -> str:
    """Emit a static OpenQASM 3 artifact from the declared exchange subset."""
    circuit = _exchange_to_qiskit_circuit(document)
    try:
        from qiskit import qasm3

        return qasm3.dumps(circuit)
    except ImportError as error:
        raise CircuitExchangeError(
            "OpenQASM 3 conversion requires the optional qiskit runtime"
        ) from error
    except Exception as error:
        raise CircuitExchangeError(
            "CircuitExchange could not be encoded as OpenQASM 3"
        ) from error


def _pytket_modules() -> tuple[Any, Any, str]:
    try:
        import pytket
        from pytket import Circuit
        from pytket.circuit import OpType
    except ImportError as error:
        raise CircuitExchangeError(
            "pytket conversion requires the optional pytket runtime"
        ) from error
    return Circuit, OpType, str(pytket.__version__)


def _static_float(value: str, *, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise CircuitExchangeError(
            f"{field} must be a finite numeric value in the initial pytket subset"
        ) from error
    if not math.isfinite(number):
        raise CircuitExchangeError(f"{field} must be finite")
    return number


def _pytket_bit_index(bit: Any, *, register: str, maximum: int) -> int:
    if getattr(bit, "reg_name", None) != register:
        raise CircuitExchangeError(
            f"pytket {register} register is required for the initial exchange subset"
        )
    index = getattr(bit, "index", ())
    if not isinstance(index, (tuple, list)) or len(index) != 1:
        raise CircuitExchangeError(f"pytket {register} bit index is unsupported")
    try:
        number = int(index[0])
    except (TypeError, ValueError) as error:
        raise CircuitExchangeError(f"pytket {register} bit index is unsupported") from error
    if not 0 <= number < maximum:
        raise CircuitExchangeError(f"pytket {register} bit is out of range")
    return number


def exchange_to_pytket(document: dict[str, Any]) -> Any:
    """Build a static pytket circuit from a validated CircuitExchange record.

    The bridge preserves the Qiskit-style logical `q`/`c` ordering and emits a
    companion report through :func:`pytket_conversion_report`; it neither
    chooses a provider nor submits a job.  pytket angles use half-turns while
    CircuitExchange angles are radians, so the conversion is explicit.
    """
    try:
        validate_contract_data("circuit-exchange", document)
    except ContractError as error:
        raise CircuitExchangeError(f"invalid CircuitExchange document: {error}") from error
    specification = document["spec"]
    if specification["limitations"]:
        raise CircuitExchangeError(
            "CircuitExchange with declared limitations cannot be emitted as pytket"
        )
    if specification["parameters"]:
        raise CircuitExchangeError(
            "symbolic parameters are outside the initial pytket bridge subset"
        )
    Circuit, OpType, _ = _pytket_modules()
    circuit = Circuit(
        len(specification["qubit_order"]),
        len(specification["classical_bit_order"]),
    )
    global_phase = specification.get("global_phase")
    if global_phase not in {None, "0", "0.0"}:
        circuit.add_phase(_static_float(str(global_phase), field="global phase") / math.pi)

    methods = {
        "x": "X",
        "y": "Y",
        "z": "Z",
        "h": "H",
        "s": "S",
        "sdg": "Sdg",
        "t": "T",
        "tdg": "Tdg",
        "cx": "CX",
        "cz": "CZ",
        "swap": "SWAP",
    }
    for operation in specification["operations"]:
        gate = operation["gate"]
        qubits = [
            _bit_index(value, "q", circuit.n_qubits)
            for value in operation["qubits"]
        ]
        classical_bits = [
            _bit_index(value, "c", circuit.n_bits)
            for value in operation["classical_bits"]
        ]
        parameters = operation["parameters"]
        if gate == "measure":
            if len(qubits) != 1 or len(classical_bits) != 1:
                raise CircuitExchangeError("measure requires exactly one qubit and classical bit")
            circuit.Measure(qubits[0], classical_bits[0])
        elif gate == "id":
            if len(qubits) != 1:
                raise CircuitExchangeError("id requires exactly one qubit")
            circuit.add_gate(OpType.noop, qubits)
        elif gate in {"rx", "ry", "rz", "p"}:
            if len(qubits) != 1 or len(parameters) != 1:
                raise CircuitExchangeError(f"{gate} requires one qubit and one angle")
            angle = _static_float(parameters[0], field=f"{gate} angle") / math.pi
            method = {"rx": "Rx", "ry": "Ry", "rz": "Rz", "p": "U1"}[gate]
            getattr(circuit, method)(angle, qubits[0])
        elif gate == "barrier":
            raise CircuitExchangeError("barrier is outside the initial pytket bridge subset")
        elif gate in methods:
            getattr(circuit, methods[gate])(*qubits)
        else:
            raise CircuitExchangeError(f"unsupported pytket target gate: {gate}")
    return circuit


def pytket_to_exchange(circuit: Any) -> dict[str, Any]:
    """Normalise one static pytket circuit into CircuitExchange.

    This deliberately accepts only the no-routing, identity-mapped bridge
    subset. Any implicit permutation, multi-register layout, symbolic angle,
    conditional, or native gate that cannot be represented exactly fails.
    """
    _, _, pytket_version = _pytket_modules()
    qubits = list(getattr(circuit, "qubits", ()))
    bits = list(getattr(circuit, "bits", ()))
    if any(
        _pytket_bit_index(bit, register="q", maximum=len(qubits)) != index
        for index, bit in enumerate(qubits)
    ):
        raise CircuitExchangeError("pytket qubits must be contiguous q[0..n] bits")
    if any(
        _pytket_bit_index(bit, register="c", maximum=len(bits)) != index
        for index, bit in enumerate(bits)
    ):
        raise CircuitExchangeError("pytket bits must be contiguous c[0..n] bits")
    phase = _static_float(str(getattr(circuit, "phase", 0)), field="pytket global phase")
    operations: list[dict[str, Any]] = []
    gate_names = {
        "noop": "id",
        "X": "x",
        "Y": "y",
        "Z": "z",
        "H": "h",
        "S": "s",
        "Sdg": "sdg",
        "T": "t",
        "Tdg": "tdg",
        "CX": "cx",
        "CZ": "cz",
        "SWAP": "swap",
    }
    for index, command in enumerate(circuit.get_commands()):
        operation = command.op
        operation_type = operation.type.name
        arguments = list(command.args)
        if operation_type == "Measure":
            if len(arguments) != 2:
                raise CircuitExchangeError("pytket measure must have one qubit and one bit")
            qubit = _pytket_bit_index(arguments[0], register="q", maximum=len(qubits))
            bit = _pytket_bit_index(arguments[1], register="c", maximum=len(bits))
            gate, operation_qubits, classical_bits, parameters = (
                "measure",
                [f"q[{qubit}]"],
                [f"c[{bit}]"],
                [],
            )
        elif operation_type in {"Rx", "Ry", "Rz", "U1"}:
            if len(arguments) != 1 or len(operation.params) != 1:
                raise CircuitExchangeError(
                    f"pytket {operation_type} must have one qubit and one angle"
                )
            qubit = _pytket_bit_index(arguments[0], register="q", maximum=len(qubits))
            gate = {"Rx": "rx", "Ry": "ry", "Rz": "rz", "U1": "p"}[operation_type]
            operation_qubits = [f"q[{qubit}]"]
            classical_bits = []
            parameters = [
                repr(_static_float(str(operation.params[0]), field=f"pytket {operation_type} angle") * math.pi)
            ]
        elif operation_type in gate_names:
            gate = gate_names[operation_type]
            operation_qubits = [
                f"q[{_pytket_bit_index(argument, register='q', maximum=len(qubits))}]"
                for argument in arguments
            ]
            classical_bits = []
            parameters = []
        else:
            raise CircuitExchangeError(f"Unsupported pytket operation: {operation_type}")
        operations.append(
            {
                "index": index,
                "gate": gate,
                "qubits": operation_qubits,
                "classical_bits": classical_bits,
                "parameters": parameters,
                "condition": None,
            }
        )
    document = {
        "api_version": "qhpc/v1",
        "kind": "CircuitExchange",
        "metadata": {
            "id": "qhpc.pytket-circuit-exchange",
            "name": "pytket circuit exchange record",
            "version": 1,
            "source": {"name": "pytket", "version": pytket_version},
            "transformation": {
                "adapter": "pytket-to-circuit-exchange",
                "classification": "exact",
                "target": {"name": "qiskit", "version": _qiskit_modules()[2]},
            },
        },
        "spec": {
            "qubit_order": [f"q[{index}]" for index in range(len(qubits))],
            "classical_bit_order": [f"c[{index}]" for index in range(len(bits))],
            "parameters": [],
            "global_phase": repr(phase * math.pi),
            "operations": operations,
            "limitations": [],
        },
    }
    try:
        validate_contract_data("circuit-exchange", document)
    except ContractError as error:
        raise CircuitExchangeError(f"normalised pytket circuit violates CircuitExchange: {error}") from error
    return document


def pytket_conversion_report(document: dict[str, Any]) -> dict[str, Any]:
    """Return identity mapping/loss evidence for the static pytket bridge."""
    try:
        validate_contract_data("circuit-exchange", document)
    except ContractError as error:
        raise CircuitExchangeError(f"invalid CircuitExchange document: {error}") from error
    if document["spec"]["parameters"] or document["spec"]["limitations"]:
        raise CircuitExchangeError("pytket report requires a fully represented static circuit")
    return {
        "adapter": "circuit-exchange-to-pytket",
        "classification": "exact",
        "qubit_mapping": [
            {"source": label, "target": label}
            for label in document["spec"]["qubit_order"]
        ],
        "implicit_swaps": [],
        "gate_decompositions": [],
        "compiler_options": {},
        "target_profile": None,
        "warnings": [],
    }


def _cirq_modules() -> tuple[Any, Any, str]:
    try:
        import cirq
        import sympy
    except ImportError as error:
        raise CircuitExchangeError(
            "Cirq conversion requires the optional cirq runtime"
        ) from error
    return cirq, sympy, str(cirq.__version__)


def _cirq_angle_text(value: Any) -> str:
    """Keep only numeric angles in the deliberately static Cirq subset."""
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise CircuitExchangeError(
            "parameterized Cirq gates are outside the initial static subset"
        ) from error
    if not math.isfinite(number):
        raise CircuitExchangeError("Cirq gate angle must be finite")
    return repr(number)


def _cirq_gate_to_exchange(
    cirq: Any,
    operation: Any,
) -> tuple[str, list[str], list[str]]:
    gate = getattr(operation, "gate", None)
    if gate is None:
        raise CircuitExchangeError("Cirq operation must expose a gate")
    if isinstance(gate, cirq.MeasurementGate):
        if len(operation.qubits) != 1 or gate.invert_mask:
            raise CircuitExchangeError(
                "Cirq measurements must be single-qubit and non-inverted"
            )
        key_match = _CIRQ_CLASSICAL_KEY.fullmatch(str(gate.key))
        if key_match is None:
            raise CircuitExchangeError(
                "Cirq measurement keys must use the c<number> convention"
            )
        return "measure", [], [f"c[{key_match.group(1)}]"]
    if gate == cirq.I:
        return "id", [], []
    if gate == cirq.X:
        return "x", [], []
    if gate == cirq.Y:
        return "y", [], []
    if gate == cirq.Z:
        return "z", [], []
    if gate == cirq.H:
        return "h", [], []
    if gate == cirq.CNOT:
        return "cx", [], []
    if gate == cirq.CZ:
        return "cz", [], []
    if gate == cirq.SWAP:
        return "swap", [], []
    if isinstance(gate, cirq.Rx):
        return "rx", [_cirq_angle_text(gate._rads)], []
    if isinstance(gate, cirq.Ry):
        return "ry", [_cirq_angle_text(gate._rads)], []
    if isinstance(gate, cirq.Rz):
        return "rz", [_cirq_angle_text(gate._rads)], []
    if isinstance(gate, cirq.ZPowGate) and gate.global_shift == 0:
        exponent = _cirq_angle_text(gate.exponent)
        if exponent == "0.5":
            return "s", [], []
        if exponent == "-0.5":
            return "sdg", [], []
        if exponent == "0.25":
            return "t", [], []
        if exponent == "-0.25":
            return "tdg", [], []
        return "p", [repr(float(exponent) * math.pi)], []
    raise CircuitExchangeError(f"Unsupported Cirq gate: {gate!r}")


def cirq_to_exchange(circuit: Any) -> dict[str, Any]:
    """Normalise a bounded static Cirq circuit into CircuitExchange."""
    cirq, _, version = _cirq_modules()
    operations = list(circuit.all_operations())
    if len(operations) > MAX_CIRQ_OPERATIONS:
        raise CircuitExchangeError(
            f"Cirq circuit exceeds the {MAX_CIRQ_OPERATIONS} operation limit"
        )
    qubits = sorted(circuit.all_qubits())
    if not all(isinstance(qubit, cirq.LineQubit) for qubit in qubits):
        raise CircuitExchangeError("Cirq conversion supports LineQubit circuits only")
    if [qubit.x for qubit in qubits] != list(range(len(qubits))):
        raise CircuitExchangeError(
            "Cirq LineQubit indices must start at zero and be contiguous"
        )
    qubit_labels = {qubit: f"q[{qubit.x}]" for qubit in qubits}
    records: list[dict[str, Any]] = []
    classical_indices: set[int] = set()
    for index, operation in enumerate(operations):
        gate, parameters, classical_bits = _cirq_gate_to_exchange(cirq, operation)
        if gate == "measure":
            classical_indices.add(int(classical_bits[0][2:-1]))
        records.append(
            {
                "index": index,
                "gate": gate,
                "qubits": [qubit_labels[qubit] for qubit in operation.qubits],
                "classical_bits": classical_bits,
                "parameters": parameters,
                "condition": None,
            }
        )
    if classical_indices and classical_indices != set(range(max(classical_indices) + 1)):
        raise CircuitExchangeError("Cirq measurement keys must be contiguous from c0")
    document = {
        "api_version": "qhpc/v1",
        "kind": "CircuitExchange",
        "metadata": {
            "id": "qhpc.cirq-circuit-exchange",
            "name": "Cirq circuit exchange record",
            "version": 1,
            "source": {"name": "cirq", "version": version},
            "transformation": {
                "adapter": "cirq-to-circuit-exchange",
                "classification": "exact",
                "target": {"name": "cirq", "version": version},
            },
        },
        "spec": {
            "qubit_order": [f"q[{index}]" for index in range(len(qubits))],
            "classical_bit_order": [
                f"c[{index}]" for index in range(max(classical_indices) + 1)
            ] if classical_indices else [],
            "parameters": [],
            "global_phase": "0.0",
            "operations": records,
            "limitations": [],
        },
    }
    try:
        validate_contract_data("circuit-exchange", document)
    except ContractError as error:
        raise CircuitExchangeError(
            f"normalised Cirq circuit violates CircuitExchange: {error}"
        ) from error
    return document


def _cirq_parameter(value: str, parameters: dict[str, Any], sympy: Any) -> Any:
    if value in parameters:
        return parameters[value]
    try:
        return float(value)
    except ValueError:
        pass
    if value == "pi":
        return sympy.pi
    if value in {"pi/2", "pi / 2"}:
        return sympy.pi / 2
    if value in {"-pi", "-pi/2", "-pi / 2"}:
        return -sympy.pi if value == "-pi" else -sympy.pi / 2
    raise CircuitExchangeError(
        f"parameter expression {value!r} is not in the safe Cirq subset"
    )


def exchange_to_cirq(document: dict[str, Any]) -> Any:
    """Emit a static Cirq circuit from the declared CircuitExchange subset."""
    try:
        validate_contract_data("circuit-exchange", document)
    except ContractError as error:
        raise CircuitExchangeError(f"invalid CircuitExchange document: {error}") from error
    specification = document["spec"]
    if specification["limitations"]:
        raise CircuitExchangeError(
            "CircuitExchange with declared limitations cannot be emitted as Cirq"
        )
    if specification.get("global_phase") not in {None, "0", "0.0"}:
        raise CircuitExchangeError("non-zero global phase is outside the initial Cirq subset")
    cirq, sympy, _ = _cirq_modules()
    qubits = cirq.LineQubit.range(len(specification["qubit_order"]))
    circuit = cirq.Circuit()
    parameters = {name: sympy.Symbol(name) for name in specification["parameters"]}
    for operation in specification["operations"]:
        gate = operation["gate"]
        selected_qubits = [
            qubits[_bit_index(value, "q", len(qubits))]
            for value in operation["qubits"]
        ]
        parameter_values = [
            _cirq_parameter(value, parameters, sympy)
            for value in operation["parameters"]
        ]
        if gate == "measure":
            bits = operation["classical_bits"]
            if len(selected_qubits) != 1 or len(bits) != 1:
                raise CircuitExchangeError("measure requires exactly one qubit and classical bit")
            bit_index = _bit_index(bits[0], "c", len(specification["classical_bit_order"]))
            cirq_operation = cirq.measure(selected_qubits[0], key=f"c{bit_index}")
        elif gate == "barrier":
            raise CircuitExchangeError("barrier is outside the initial Cirq subset")
        elif gate == "id" and len(selected_qubits) == 1:
            cirq_operation = cirq.I(selected_qubits[0])
        elif gate == "x" and len(selected_qubits) == 1:
            cirq_operation = cirq.X(selected_qubits[0])
        elif gate == "y" and len(selected_qubits) == 1:
            cirq_operation = cirq.Y(selected_qubits[0])
        elif gate == "z" and len(selected_qubits) == 1:
            cirq_operation = cirq.Z(selected_qubits[0])
        elif gate == "h" and len(selected_qubits) == 1:
            cirq_operation = cirq.H(selected_qubits[0])
        elif gate == "s" and len(selected_qubits) == 1:
            cirq_operation = cirq.S(selected_qubits[0])
        elif gate == "sdg" and len(selected_qubits) == 1:
            cirq_operation = (cirq.S ** -1)(selected_qubits[0])
        elif gate == "t" and len(selected_qubits) == 1:
            cirq_operation = cirq.T(selected_qubits[0])
        elif gate == "tdg" and len(selected_qubits) == 1:
            cirq_operation = (cirq.T ** -1)(selected_qubits[0])
        elif gate == "rx" and len(selected_qubits) == 1 and len(parameter_values) == 1:
            cirq_operation = cirq.rx(parameter_values[0])(selected_qubits[0])
        elif gate == "ry" and len(selected_qubits) == 1 and len(parameter_values) == 1:
            cirq_operation = cirq.ry(parameter_values[0])(selected_qubits[0])
        elif gate == "rz" and len(selected_qubits) == 1 and len(parameter_values) == 1:
            cirq_operation = cirq.rz(parameter_values[0])(selected_qubits[0])
        elif gate == "p" and len(selected_qubits) == 1 and len(parameter_values) == 1:
            cirq_operation = cirq.ZPowGate(
                exponent=parameter_values[0] / sympy.pi,
                global_shift=0,
            )(selected_qubits[0])
        elif gate == "cx" and len(selected_qubits) == 2:
            cirq_operation = cirq.CNOT(*selected_qubits)
        elif gate == "cz" and len(selected_qubits) == 2:
            cirq_operation = cirq.CZ(*selected_qubits)
        elif gate == "swap" and len(selected_qubits) == 2:
            cirq_operation = cirq.SWAP(*selected_qubits)
        else:
            raise CircuitExchangeError(f"unsupported Cirq target gate or arity: {gate}")
        circuit.append(cirq_operation, strategy=cirq.InsertStrategy.NEW)
    return circuit
