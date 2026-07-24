"""Controlled project API adapters independent of production runtime transport."""

from __future__ import annotations

import importlib
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
