"""Controlled project API adapters independent of production runtime transport."""

from __future__ import annotations

import ctypes
import importlib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Callable, Mapping


class ProjectAdapterError(ValueError):
    """Raised when an integration input violates its operation interface."""


_TNSIM_HEADER = re.compile(
    r"^=+\s+Measurement\s+\(tests=(?P<shots>[0-9]+)\)\s+=+\s*$",
    re.MULTILINE,
)
_TNSIM_COUNT = re.compile(
    r'^\s*"(?P<state>[01]+)"\s*:\s*(?P<count>[0-9]+)\s*$',
    re.MULTILINE,
)
_FTQC_QASM_HEADER = re.compile(
    r"^\s*OPENQASM\s+(?:2(?:\.0)?|3(?:\.0)?)\s*;",
    re.IGNORECASE | re.MULTILINE,
)
_FTQC_FUNCTION_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_FTQC_IQM_JSON_ATTRIBUTE = re.compile(
    r'ftqc\.iqm_json\s*=\s*"((?:[^"\\]|\\.)*)"'
)


class _FTQCCfg(ctypes.Structure):
    """Exact layout of FTQC's pinned, fixed-storage C API configuration."""

    _fields_ = [
        ("ecc_kind", ctypes.c_char * 64),
        ("ecc_dist", ctypes.c_int),
        ("func_name", ctypes.c_char * 64),
        ("run_steane_pipeline", ctypes.c_int),
        ("run_surface_pipeline", ctypes.c_int),
        ("run_distill_pipeline", ctypes.c_int),
        ("steane_encode", ctypes.c_int),
        ("surface_encode", ctypes.c_int),
        ("use_lattice", ctypes.c_int),
        ("color_encode", ctypes.c_int),
        ("insert_syndrome", ctypes.c_int),
        ("syndrome_method", ctypes.c_char * 32),
        ("syndrome_rounds", ctypes.c_int),
        ("insert_correction", ctypes.c_int),
        ("pauli_frame_opt", ctypes.c_int),
        ("magic_distill", ctypes.c_int),
        ("distill_protocol", ctypes.c_char * 32),
        ("distill_levels", ctypes.c_int),
        ("distill_target_error", ctypes.c_double),
        ("transversal_gates", ctypes.c_int),
        ("decompose_non_transversal", ctypes.c_int),
        ("lower_to_quantum", ctypes.c_int),
        ("lower_to_stim", ctypes.c_int),
        ("lower_to_qir", ctypes.c_int),
        ("lower_to_qasm3", ctypes.c_int),
        ("lower_to_iqm_json", ctypes.c_int),
        ("lower_to_lattice_surgery", ctypes.c_int),
        ("lower_to_iqs", ctypes.c_int),
        ("resource_estimate", ctypes.c_int),
        ("print_report", ctypes.c_int),
        ("fault_path", ctypes.c_int),
        ("fault_path_max_order", ctypes.c_int),
        ("threshold_analysis", ctypes.c_int),
        ("physical_error_rate", ctypes.c_double),
        ("target_error_rate", ctypes.c_double),
        ("lower_to_iqm_json_radians", ctypes.c_int),
        ("lower_to_iqm_json_physical", ctypes.c_int),
    ]


def _integer(
    parameters: Mapping[str, Any],
    name: str,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    value = parameters.get(name, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ProjectAdapterError(f"{name} must be an integer")
    if value < minimum or value > maximum:
        raise ProjectAdapterError(
            f"{name} must be between {minimum} and {maximum}"
        )
    return value


def _number(
    parameters: Mapping[str, Any],
    name: str,
    default: float,
    minimum: float,
    maximum: float,
    *,
    inclusive_minimum: bool = True,
) -> float:
    value = parameters.get(name, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProjectAdapterError(f"{name} must be a number")
    normalized = float(value)
    below_minimum = (
        normalized < minimum if inclusive_minimum else normalized <= minimum
    )
    if below_minimum or normalized > maximum:
        qualifier = "between" if inclusive_minimum else "greater than"
        if inclusive_minimum:
            detail = f"{minimum} and {maximum}"
        else:
            detail = f"{minimum} and at most {maximum}"
        raise ProjectAdapterError(f"{name} must be {qualifier} {detail}")
    return normalized


def count_nwqec_clifford_t(
    circuit_path: str | Path, parameters: Mapping[str, Any]
) -> dict[str, Any]:
    """Count the Clifford and T representation through NWQEC's public API."""
    path = Path(circuit_path).expanduser().resolve()
    if not path.is_file():
        raise ProjectAdapterError(f"input circuit not found: {path}")
    keep_ccx = parameters.get("keep_ccx", False)
    if not isinstance(keep_ccx, bool):
        raise ProjectAdapterError("keep_ccx must be a boolean")
    policy = parameters.get("rz_error_policy", "total")
    if policy not in {"per-gate", "total", "relative"}:
        raise ProjectAdapterError(
            "rz_error_policy must be per-gate, total, or relative"
        )
    epsilon = _number(
        parameters,
        "epsilon",
        0.01,
        0.0,
        0.5,
        inclusive_minimum=False,
    )

    nwqec = importlib.import_module("nwqec")
    circuit = nwqec.load_qasm(str(path))
    raw_counts = nwqec.get_clifford_t_counts(
        circuit,
        keep_ccx=keep_ccx,
        rz_err=policy,
        epsilon=epsilon,
    )
    counts = {str(name): int(value) for name, value in sorted(raw_counts.items())}
    return {
        "counts": counts,
        "total_t_count": counts.get("t", 0) + counts.get("tdg", 0),
        "source_qubits": int(circuit.num_qubits()),
        "rz_error_policy": policy,
        "epsilon": epsilon,
    }


def build_ftprimitivebench_memory(parameters: Mapping[str, Any]) -> str:
    """Build a detector-annotated noisy memory circuit as Stim text."""
    x_distance = _integer(parameters, "x_distance", 3, 1, 31)
    z_distance = _integer(parameters, "z_distance", 3, 1, 31)
    rounds = _integer(parameters, "rounds", 3, 1, 100)
    basis = parameters.get("measurement_basis", "Z")
    if basis not in {"X", "Z"}:
        raise ProjectAdapterError("measurement_basis must be X or Z")
    error_rate = _number(
        parameters, "physical_error_rate", 0.001, 0.0, 0.5
    )

    circuits = importlib.import_module(
        "ft_primitive_bench.surface_code.circuits"
    )
    noise_models = importlib.import_module("ft_primitive_bench.noise_models")
    clean = circuits.memory(
        x_distance=x_distance,
        z_distance=z_distance,
        rounds=rounds,
        meas_basis=basis,
    )
    noisy = noise_models.uniform_depolarizing(p=error_rate).noisy_circuit(clean)
    serialized = str(noisy).strip() + "\n"
    if "DETECTOR" not in serialized or "OBSERVABLE_INCLUDE" not in serialized:
        raise ProjectAdapterError(
            "FTPrimitiveBench output lacks detector or observable annotations"
        )
    return serialized


def estimate_lightstim_logical_error(
    circuit_text: str, parameters: Mapping[str, Any]
) -> dict[str, Any]:
    """Estimate logical errors through LightStim's public simulation pipeline."""
    if not circuit_text.strip():
        raise ProjectAdapterError("Stim circuit input is empty")
    decoder = parameters.get("decoder", "pymatching")
    if decoder != "pymatching":
        raise ProjectAdapterError("the initial LightStim adapter allows pymatching only")
    max_shots = _integer(parameters, "max_shots", 1000, 1, 100_000_000)
    max_errors = _integer(parameters, "max_errors", 100, 1, 1_000_000)
    batch_size = _integer(parameters, "batch_size", 1000, 1, 1_000_000)
    num_workers = _integer(parameters, "num_workers", 1, 1, 256)

    stim = importlib.import_module("stim")
    simulation = importlib.import_module("lightstim.simulation.decoder_backend")
    circuit = stim.Circuit(circuit_text)
    if circuit.num_detectors < 1 or circuit.num_observables < 1:
        raise ProjectAdapterError(
            "Stim circuit requires at least one detector and one observable"
        )
    pipeline = simulation.SimulationPipeline(
        decoder_config=simulation.DecoderConfig(decoder),
        max_errors=max_errors,
        max_shots=max_shots,
        batch_size=batch_size,
        num_workers=num_workers,
        print_progress=False,
    )
    stats = pipeline.run(circuit)
    return {
        "shots": int(stats.shots),
        "post_selected_shots": int(stats.post_selected_shots),
        "errors": int(stats.errors),
        "logical_error_rate": float(stats.logical_error_rate),
        "error_bar": float(stats.ler_error_bar()),
        "seconds": float(stats.seconds),
        "decoder": str(stats.decoder),
    }


def _parse_tnsim_counts(stdout: str, expected_shots: int) -> dict[str, int]:
    header = _TNSIM_HEADER.search(stdout)
    if header is None:
        raise ProjectAdapterError(
            "TN-Sim output lacks the measurement-count header"
        )
    reported_shots = int(header.group("shots"))
    if reported_shots != expected_shots:
        raise ProjectAdapterError(
            "TN-Sim reported "
            f"{reported_shots} shots; expected {expected_shots}"
        )

    counts: dict[str, int] = {}
    for match in _TNSIM_COUNT.finditer(stdout, header.end()):
        state = match.group("state")
        if state in counts:
            raise ProjectAdapterError(
                f"TN-Sim output repeats measurement state {state}"
            )
        count = int(match.group("count"))
        if count < 1:
            raise ProjectAdapterError(
                f"TN-Sim output has a non-positive count for state {state}"
            )
        counts[state] = count

    if not counts:
        raise ProjectAdapterError("TN-Sim output contains no measurement counts")
    counted_shots = sum(counts.values())
    if counted_shots != expected_shots:
        raise ProjectAdapterError(
            "TN-Sim measurement counts sum to "
            f"{counted_shots}; expected {expected_shots}"
        )
    return dict(sorted(counts.items()))


def simulate_tnsim_mps(
    executable_path: str | Path,
    circuit_path: str | Path,
    parameters: Mapping[str, Any],
    *,
    executor: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    """Execute the audited NWQ-Sim CPU MPS CLI and normalize shot counts."""
    executable = Path(executable_path).expanduser().resolve()
    if not executable.is_file():
        raise ProjectAdapterError(f"TN-Sim executable not found: {executable}")
    if not os.access(executable, os.X_OK):
        raise ProjectAdapterError(
            f"TN-Sim executable is not executable: {executable}"
        )

    circuit = Path(circuit_path).expanduser().resolve()
    if not circuit.is_file():
        raise ProjectAdapterError(f"input circuit not found: {circuit}")
    try:
        circuit_text = circuit.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise ProjectAdapterError("input circuit must be UTF-8 text") from error
    if re.search(r"(?m)^\s*OPENQASM\s+2\.0\s*;", circuit_text) is None:
        raise ProjectAdapterError("input circuit must declare OPENQASM 2.0")

    allowed_parameters = {
        "shots",
        "max_bond_dimension",
        "singular_value_cutoff",
        "random_seed",
    }
    unknown = sorted(
        str(name) for name in parameters if name not in allowed_parameters
    )
    if unknown:
        raise ProjectAdapterError(
            f"unsupported TN-Sim parameters: {', '.join(unknown)}"
        )

    shots = _integer(parameters, "shots", 1024, 1, 10_000_000)
    max_bond_dimension = _integer(
        parameters, "max_bond_dimension", 100, 1, 65_536
    )
    singular_value_cutoff = _number(
        parameters, "singular_value_cutoff", 0.0, 0.0, 1.0
    )
    random_seed = _integer(
        parameters, "random_seed", 42, 0, 2_147_483_647
    )

    command = [
        str(executable),
        "--qasm_file",
        str(circuit),
        "--shots",
        str(shots),
        "--backend",
        "CPU",
        "--sim",
        "tn",
        "--max_dim",
        str(max_bond_dimension),
        "--sv_cutoff",
        str(singular_value_cutoff),
        "--random_seed",
        str(random_seed),
    ]
    try:
        completed = executor(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:
        raise ProjectAdapterError(f"TN-Sim execution failed: {error}") from error
    if completed.returncode != 0:
        detail = (completed.stderr or "").strip()
        suffix = f": {detail[-500:]}" if detail else ""
        raise ProjectAdapterError(
            f"TN-Sim exited with status {completed.returncode}{suffix}"
        )

    return {
        "shots": shots,
        "counts": _parse_tnsim_counts(completed.stdout or "", shots),
        "backend": "CPU",
        "simulation_method": "tn",
        "max_bond_dimension": max_bond_dimension,
        "singular_value_cutoff": singular_value_cutoff,
        "random_seed": random_seed,
    }


def import_ftqc_qasm(
    executable_path: str | Path,
    circuit_path: str | Path,
    parameters: Mapping[str, Any],
    *,
    executor: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> str:
    """Run FTQC's standalone QASM importer through a constrained CLI boundary."""
    executable = Path(executable_path).expanduser().resolve()
    if not executable.is_file():
        raise ProjectAdapterError(f"FTQC importer not found: {executable}")
    if not os.access(executable, os.X_OK):
        raise ProjectAdapterError(f"FTQC importer is not executable: {executable}")

    circuit = Path(circuit_path).expanduser().resolve()
    if not circuit.is_file():
        raise ProjectAdapterError(f"input circuit not found: {circuit}")
    try:
        circuit_text = circuit.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise ProjectAdapterError("input circuit must be UTF-8 text") from error
    if _FTQC_QASM_HEADER.search(circuit_text) is None:
        raise ProjectAdapterError(
            "input circuit must declare OPENQASM 2.0 or 3.0"
        )

    allowed_parameters = {"ecc", "distance", "function_name"}
    unknown = sorted(
        str(name) for name in parameters if name not in allowed_parameters
    )
    if unknown:
        raise ProjectAdapterError(
            f"unsupported FTQC parameters: {', '.join(unknown)}"
        )

    ecc = parameters.get("ecc", "steane")
    if ecc not in {"steane", "surface", "color_code"}:
        raise ProjectAdapterError(
            "ecc must be steane, surface, or color_code"
        )
    distance = _integer(parameters, "distance", 3, 1, 31)
    function_name = parameters.get("function_name", "circuit")
    if (
        not isinstance(function_name, str)
        or _FTQC_FUNCTION_NAME.fullmatch(function_name) is None
    ):
        raise ProjectAdapterError(
            "function_name must be an MLIR-compatible identifier"
        )

    command = [
        str(executable),
        f"--ecc={ecc}",
        f"--distance={distance}",
        f"--func-name={function_name}",
        str(circuit),
    ]
    try:
        completed = executor(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:
        raise ProjectAdapterError(f"FTQC import failed: {error}") from error
    if completed.returncode != 0:
        detail = (completed.stderr or "").strip()
        suffix = f": {detail[-500:]}" if detail else ""
        raise ProjectAdapterError(
            f"FTQC importer exited with status {completed.returncode}{suffix}"
        )

    output = (completed.stdout or "").strip()
    if "ftqc." not in output or re.search(r"(?m)^\s*func\.func\s+@", output) is None:
        raise ProjectAdapterError(
            "FTQC importer output lacks an FTQC MLIR function"
        )
    return output + "\n"


def _mlir_string_value(value: str) -> str:
    """Decode the escape form used by MLIR string attributes."""

    output = bytearray()
    index = 0
    while index < len(value):
        if value[index] != "\\":
            output.extend(value[index].encode("utf-8"))
            index += 1
            continue
        if index + 2 < len(value) and re.fullmatch(
            r"[0-9A-Fa-f]{2}", value[index + 1 : index + 3]
        ):
            output.append(int(value[index + 1 : index + 3], 16))
            index += 3
            continue
        if index + 1 >= len(value):
            raise ProjectAdapterError("FTQC returned an invalid MLIR string escape")
        escaped = value[index + 1]
        if escaped not in {'"', "\\"}:
            raise ProjectAdapterError("FTQC returned an unsupported MLIR string escape")
        output.extend(escaped.encode("utf-8"))
        index += 2
    try:
        return output.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ProjectAdapterError("FTQC returned a non-UTF-8 MLIR string") from error


def _validated_iqm_circuit(program: str) -> dict[str, Any]:
    match = _FTQC_IQM_JSON_ATTRIBUTE.search(program)
    if match is None:
        raise ProjectAdapterError("FTQC output lacks its IQM JSON module attribute")
    try:
        payload = json.loads(_mlir_string_value(match.group(1)))
    except json.JSONDecodeError as error:
        raise ProjectAdapterError(f"FTQC emitted invalid IQM JSON: {error}") from error
    if not isinstance(payload, dict) or set(payload) != {"name", "instructions"}:
        raise ProjectAdapterError("FTQC IQM output must contain name and instructions")
    if not isinstance(payload["name"], str) or not payload["name"]:
        raise ProjectAdapterError("FTQC IQM circuit name is invalid")
    instructions = payload["instructions"]
    if not isinstance(instructions, list) or not 1 <= len(instructions) <= 100_000:
        raise ProjectAdapterError("FTQC IQM circuit must contain 1 to 100000 instructions")
    for index, instruction in enumerate(instructions):
        if not isinstance(instruction, dict) or set(instruction) != {
            "name",
            "locus",
            "args",
        }:
            raise ProjectAdapterError(f"FTQC IQM instruction {index} is malformed")
        if instruction["name"] not in {"prx", "cz", "measure"}:
            raise ProjectAdapterError(
                f"FTQC IQM instruction {index} uses an unsupported gate"
            )
        locus = instruction["locus"]
        if (
            not isinstance(locus, list)
            or not locus
            or any(
                not isinstance(qubit, str)
                or re.fullmatch(r"QB[1-9][0-9]*", qubit) is None
                for qubit in locus
            )
        ):
            raise ProjectAdapterError(f"FTQC IQM instruction {index} has an invalid locus")
        if not isinstance(instruction["args"], dict):
            raise ProjectAdapterError(f"FTQC IQM instruction {index} has invalid arguments")
    return payload


def prepare_ftqc_iqm(
    library_path: str | Path,
    circuit_path: str | Path,
    parameters: Mapping[str, Any],
    *,
    source_revision: str,
) -> dict[str, Any]:
    """Compile QASM through FTQC's C API without routing or submission."""

    library_file = Path(library_path).expanduser().resolve()
    if not library_file.is_file():
        raise ProjectAdapterError(f"FTQC compiler library not found: {library_file}")

    circuit = Path(circuit_path).expanduser().resolve()
    if not circuit.is_file():
        raise ProjectAdapterError(f"input circuit not found: {circuit}")
    if circuit.stat().st_size > 1_000_000:
        raise ProjectAdapterError("FTQC circuit input exceeds the 1 MB limit")
    try:
        circuit_data = circuit.read_bytes()
        circuit_text = circuit_data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ProjectAdapterError("input circuit must be UTF-8 text") from error
    if _FTQC_QASM_HEADER.search(circuit_text) is None:
        raise ProjectAdapterError("input circuit must declare OPENQASM 2.0 or 3.0")

    allowed_parameters = {"preparation", "function_name"}
    unknown = sorted(str(name) for name in parameters if name not in allowed_parameters)
    if unknown:
        raise ProjectAdapterError(
            f"unsupported FTQC parameters: {', '.join(unknown)}"
        )
    preparation = parameters.get("preparation", "device")
    if preparation not in {"device", "steane-logical"}:
        raise ProjectAdapterError("preparation must be device or steane-logical")
    function_name = parameters.get("function_name", "circuit")
    if (
        not isinstance(function_name, str)
        or _FTQC_FUNCTION_NAME.fullmatch(function_name) is None
        or len(function_name.encode("utf-8")) > 63
    ):
        raise ProjectAdapterError(
            "function_name must be an MLIR-compatible identifier of at most 63 bytes"
        )

    try:
        library = ctypes.CDLL(str(library_file))
        compiler = library.ftqc_qasm_opt
        compiler.argtypes = [
            ctypes.c_void_p,
            ctypes.c_size_t,
            ctypes.POINTER(_FTQCCfg),
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(ctypes.c_size_t),
        ]
        compiler.restype = ctypes.c_int
        release = library.ftqc_free
        release.argtypes = [ctypes.c_void_p]
        release.restype = None
    except (AttributeError, OSError) as error:
        raise ProjectAdapterError(f"FTQC compiler library could not be loaded: {error}") from error

    configuration = _FTQCCfg()
    configuration.ecc_kind = b"steane"
    configuration.ecc_dist = 3
    configuration.func_name = function_name.encode("ascii")
    configuration.lower_to_iqm_json = 1
    configuration.lower_to_iqm_json_radians = 1
    configuration.lower_to_iqm_json_physical = int(preparation == "steane-logical")

    output_pointer = ctypes.c_void_p()
    output_size = ctypes.c_size_t()
    input_buffer = ctypes.create_string_buffer(circuit_data)
    try:
        status = compiler(
            input_buffer,
            len(circuit_data),
            ctypes.byref(configuration),
            ctypes.byref(output_pointer),
            ctypes.byref(output_size),
        )
    except (OSError, ValueError) as error:
        raise ProjectAdapterError(f"FTQC compilation failed: {error}") from error
    if status != 0 or not output_pointer.value or output_size.value < 1:
        if output_pointer.value:
            release(output_pointer)
        raise ProjectAdapterError(f"FTQC compilation exited with status {status}")
    try:
        program = ctypes.string_at(output_pointer, output_size.value).decode("utf-8")
    except UnicodeDecodeError as error:
        raise ProjectAdapterError("FTQC compiler output must be UTF-8 text") from error
    finally:
        release(output_pointer)

    iqm_circuit = _validated_iqm_circuit(program)
    gate_counts: dict[str, int] = {}
    loci: set[str] = set()
    for instruction in iqm_circuit["instructions"]:
        name = instruction["name"]
        gate_counts[name] = gate_counts.get(name, 0) + 1
        loci.update(instruction["locus"])

    if preparation == "device":
        expected_loci = {"QB1", "QB2"}
        if loci != expected_loci or gate_counts.get("measure") != 2:
            raise ProjectAdapterError(
                "device preparation is restricted to a measured two-qubit circuit"
            )
        logical_qubits: int | None = None
        routing_requirement = "calibration-check-required"
        claim_boundary = (
            "Direct two-device-qubit lowering; FTQC's intermediate retains ECC "
            "type metadata, but no Steane block expansion is performed."
        )
    else:
        expected_loci = {f"QB{index}" for index in range(1, 8)}
        if loci != expected_loci or gate_counts.get("measure") != 7:
            raise ProjectAdapterError(
                "Steane logical preparation is restricted to one seven-data-qubit block"
            )
        logical_qubits = 1
        routing_requirement = "required-before-hardware"
        claim_boundary = (
            "One Steane [[7,1,3]] logical qubit expanded to seven data qubits; "
            "this preparation alone is not evidence of error suppression."
        )

    report = {
        "schema": "qhpc.ftqc-iqm-preparation-report.v1",
        "preparation": preparation,
        "compiler_interface": "ftqc_qasm_opt",
        "source_revision": source_revision,
        "ecc": {"kind": "steane", "distance": 3},
        "logical_qubits": logical_qubits,
        "device_qubits": len(loci),
        "instruction_count": len(iqm_circuit["instructions"]),
        "gate_counts": dict(sorted(gate_counts.items())),
        "loci": sorted(loci, key=lambda value: int(value[2:])),
        "angle_units": "radians",
        "routing": {
            "status": "not-performed",
            "requirement": routing_requirement,
            "reason": (
                "Topology routing needs qiskit-iqm and current device calibration; "
                "it is outside this credential-free local stage."
            ),
        },
        "submission": {
            "status": "not-submitted",
            "execution_class": "quantum-backend",
        },
        "claim_boundary": claim_boundary,
    }
    return {
        "program": program.rstrip() + "\n",
        "circuit": iqm_circuit,
        "report": report,
    }
