"""Allowlisted adapters for verified local development runtimes."""

from __future__ import annotations

import importlib
import json
import math
import re
import sys
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from .engine import ArtifactResult, FunctionRunner, TaskRequest, TaskResult
from .local_runtime import resolve_native_runtime, resolve_wheel_runtime
from .project_adapters import prepare_ftqc_iqm


OPENQEVO_CONTEXT_ROOT = Path(__file__).with_name("openqevo_context")
OPENQEVO_REPOSITORY = "https://github.com/QSCSoftwareThrust/OpenQEvo"
OPENQEVO_REVISION = "250550a3992bd57c032d4066843c2b03055c4b9d"
FTQC_REVISION = "779216de8805ea0c1d473c640eaf17d6cbfa04e8"


def _load_openqevo(root: Path, request: TaskRequest) -> Any:
    wheel = resolve_wheel_runtime(
        root, request.runtime_reference, request.runtime_digest
    )
    wheel_value = str(wheel)
    if wheel_value not in sys.path:
        sys.path.insert(0, wheel_value)
    return importlib.import_module("openqevo")


def _input_file(request: TaskRequest, port: str) -> Path:
    parsed = urlparse(request.inputs[port]["uri"])
    if parsed.scheme != "file":
        raise RuntimeError(f"{port} must be a file artifact")
    path = Path(unquote(parsed.path)).resolve()
    if not path.is_file():
        raise RuntimeError(f"{port} artifact not found: {path}")
    return path


def _method_details(openqevo: Any, method: str) -> dict[str, str]:
    details = {
        item["name"]: item
        for item in openqevo.list_methods_detail()
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    if method not in details:
        available = ", ".join(sorted(details)) or "(none)"
        raise RuntimeError(
            f"OpenQEvo method {method!r} is unavailable; registered methods: {available}"
        )
    return details[method]


def _openqevo_context(method: str) -> tuple[dict[str, Any] | None, str | None]:
    path = OPENQEVO_CONTEXT_ROOT / f"{method}.json"
    if not path.is_file():
        return None, None
    return json.loads(path.read_text(encoding="utf-8")), f"context/{path.name}"


def _pauli_hamiltonian(path: Path) -> dict[str, Any]:
    if path.stat().st_size > 1_000_000:
        raise RuntimeError("Pauli Hamiltonian input exceeds the 1 MB development limit")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Pauli Hamiltonian is not valid JSON: {error}") from error
    if not isinstance(payload, dict) or set(payload) != {"qubits", "terms"}:
        raise RuntimeError(
            "Pauli Hamiltonian must contain exactly 'qubits' and 'terms'"
        )
    qubits = payload["qubits"]
    terms = payload["terms"]
    if (
        not isinstance(qubits, int)
        or isinstance(qubits, bool)
        or not 1 <= qubits <= 32
    ):
        raise RuntimeError("Pauli Hamiltonian qubits must be an integer from 1 to 32")
    if not isinstance(terms, list) or not 1 <= len(terms) <= 256:
        raise RuntimeError("Pauli Hamiltonian must contain 1 to 256 terms")
    normalized: list[dict[str, Any]] = []
    for index, term in enumerate(terms):
        if not isinstance(term, dict) or set(term) != {"pauli", "coefficient"}:
            raise RuntimeError(
                f"Pauli Hamiltonian term {index} must contain pauli and coefficient"
            )
        pauli = term["pauli"]
        coefficient = term["coefficient"]
        if (
            not isinstance(pauli, str)
            or len(pauli) != qubits
            or re.fullmatch(r"[IXYZ]+", pauli) is None
        ):
            raise RuntimeError(
                f"Pauli Hamiltonian term {index} must use an {qubits}-character "
                "I/X/Y/Z string"
            )
        if (
            not isinstance(coefficient, (int, float))
            or isinstance(coefficient, bool)
            or not math.isfinite(float(coefficient))
        ):
            raise RuntimeError(
                f"Pauli Hamiltonian term {index} coefficient must be finite"
            )
        normalized.append(
            {"pauli": pauli, "coefficient": float(coefficient)}
        )
    return {"qubits": qubits, "terms": normalized}


def _synthesize_qiskit_trotter(
    hamiltonian: dict[str, Any],
    *,
    evolution_time: float,
    steps: int,
    order: int,
) -> tuple[str, dict[str, Any]]:
    try:
        from qiskit import QuantumCircuit, qasm2, transpile
        from qiskit.circuit.library import PauliEvolutionGate
        from qiskit.quantum_info import SparsePauliOp
        from qiskit.synthesis import SuzukiTrotter
    except ImportError as error:
        raise RuntimeError(
            "The OpenQEvo Qiskit synthesis bridge requires the qiskit adapter runtime"
        ) from error

    operator = SparsePauliOp.from_list(
        [
            (term["pauli"], term["coefficient"])
            for term in hamiltonian["terms"]
        ]
    )
    synthesis = SuzukiTrotter(order=order, reps=steps)
    gate = PauliEvolutionGate(
        operator,
        time=evolution_time,
        synthesis=synthesis,
    )
    circuit = QuantumCircuit(hamiltonian["qubits"])
    circuit.append(gate, range(hamiltonian["qubits"]))
    basis_circuit = transpile(
        circuit,
        basis_gates=["u1", "u2", "u3", "cx"],
        optimization_level=0,
        seed_transpiler=0,
    )
    qasm = qasm2.dumps(basis_circuit)
    metrics = {
        "depth": int(basis_circuit.depth()),
        "gate_counts": {
            str(name): int(count)
            for name, count in sorted(basis_circuit.count_ops().items())
        },
    }
    return qasm, metrics


def build_local_runner(runtime_root: str | Path) -> FunctionRunner:
    root = Path(runtime_root).expanduser().resolve()
    runner = FunctionRunner()

    def list_openqevo_methods(request: TaskRequest) -> TaskResult:
        openqevo = _load_openqevo(root, request)
        detailed = request.parameters.get("detailed", True)
        methods = (
            openqevo.list_methods_detail() if detailed else openqevo.list_methods()
        )
        output = request.work_directory / "methods.json"
        output.write_text(
            json.dumps({"methods": methods}, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return TaskResult(
            {
                "methods": ArtifactResult.from_path(
                    request.output_types["methods"], output
                )
            },
            f"OpenQEvo returned {len(methods)} registered methods",
        )

    runner.register("openqevo-library", "list-methods", list_openqevo_methods)

    def describe_openqevo_method(request: TaskRequest) -> TaskResult:
        openqevo = _load_openqevo(root, request)
        method = str(request.parameters.get("method", "trotter_s2"))
        details = _method_details(openqevo, method)
        context, source_path = _openqevo_context(method)
        document = {
            "method": details,
            "available": True,
            "context_status": "available" if context is not None else "not-published",
            "context": context,
            "provenance": {
                "repository": OPENQEVO_REPOSITORY,
                "revision": OPENQEVO_REVISION,
                "path": source_path,
            },
        }
        output = request.work_directory / "method-context.json"
        output.write_text(
            json.dumps(document, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return TaskResult(
            {
                "context": ArtifactResult.from_path(
                    request.output_types["context"], output
                )
            },
            (
                f"OpenQEvo method context returned for {method}"
                if context is not None
                else f"OpenQEvo has not published structured context for {method}"
            ),
        )

    runner.register(
        "openqevo-library", "describe-method", describe_openqevo_method
    )

    def synthesize_openqevo_evolution(request: TaskRequest) -> TaskResult:
        openqevo = _load_openqevo(root, request)
        method = str(request.parameters.get("method", "qiskit_trotter"))
        details = _method_details(openqevo, method)
        if method != "qiskit_trotter":
            raise RuntimeError(
                "The current circuit bridge supports only qiskit_trotter"
            )
        evolution_time = float(request.parameters.get("evolution_time", 1.0))
        steps = int(request.parameters.get("steps", 4))
        order = int(request.parameters.get("order", 2))
        if not math.isfinite(evolution_time) or evolution_time <= 0:
            raise RuntimeError("evolution_time must be a finite positive number")
        if not 1 <= steps <= 256:
            raise RuntimeError("steps must be an integer from 1 to 256")
        if order not in {1, 2, 4}:
            raise RuntimeError("order must be one of 1, 2, or 4")

        hamiltonian = _pauli_hamiltonian(_input_file(request, "hamiltonian"))
        if len(hamiltonian["terms"]) * steps > 4096:
            raise RuntimeError(
                "term count multiplied by steps exceeds the 4096 development limit"
            )
        qasm, metrics = _synthesize_qiskit_trotter(
            hamiltonian,
            evolution_time=evolution_time,
            steps=steps,
            order=order,
        )
        circuit = request.work_directory / "evolution.qasm"
        circuit.write_text(qasm, encoding="utf-8")
        report = request.work_directory / "synthesis-report.json"
        report.write_text(
            json.dumps(
                {
                    "method": method,
                    "method_source": details["source"],
                    "framework": "qiskit",
                    "circuit_format": "openqasm-2.0",
                    "qubits": hamiltonian["qubits"],
                    "term_count": len(hamiltonian["terms"]),
                    "evolution_time": evolution_time,
                    "steps": steps,
                    "order": order,
                    "depth": metrics["depth"],
                    "gate_counts": metrics["gate_counts"],
                    "source_revision": OPENQEVO_REVISION,
                    "bridge_status": "development",
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        return TaskResult(
            {
                "circuit": ArtifactResult.from_path(
                    request.output_types["circuit"], circuit
                ),
                "report": ArtifactResult.from_path(
                    request.output_types["report"], report
                ),
            },
            (
                f"OpenQEvo/Qiskit synthesized {hamiltonian['qubits']} qubits "
                f"from {len(hamiltonian['terms'])} Pauli terms"
            ),
        )

    runner.register(
        "openqevo-library",
        "synthesize-evolution",
        synthesize_openqevo_evolution,
    )

    def transpile_qasm(request: TaskRequest) -> TaskResult:
        runtime = resolve_native_runtime(
            root, request.runtime_reference, request.runtime_digest
        )
        input_uri = request.inputs["circuit"]["uri"]
        parsed = urlparse(input_uri)
        if parsed.scheme != "file":
            raise RuntimeError("QASMTrans local adapter requires a file artifact")
        input_path = Path(unquote(parsed.path)).resolve()
        if not input_path.is_file():
            raise RuntimeError(f"input circuit not found: {input_path}")
        mode = request.parameters.get("mode", "ibmq")
        backend = request.parameters.get("backend", "ibmq_toronto")
        if mode != "ibmq" or backend != "ibmq_toronto":
            raise RuntimeError("QASMTrans local adapter allows only audited targets")
        output = request.work_directory / "transpiled.qasm"
        command = [
            str(runtime / "bin/QASMTrans"),
            "-i",
            str(input_path),
            "-m",
            mode,
            "-c",
            str(runtime / "data/devices/ibmq_toronto.json"),
            "-o",
            str(output),
            "-v",
            "1",
        ]
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=60, check=False
        )
        log = (completed.stdout + completed.stderr).strip()
        if completed.returncode or not output.is_file():
            raise RuntimeError(
                f"QASMTrans failed with exit {completed.returncode}: {log}"
            )
        return TaskResult(
            {
                "circuit": ArtifactResult.from_path(
                    request.output_types["circuit"], output
                )
            },
            log,
        )

    runner.register("qasmtrans-transpiler", "transpile", transpile_qasm)

    def analyze_stabsim_metrics(request: TaskRequest) -> TaskResult:
        runtime = resolve_native_runtime(
            root, request.runtime_reference, request.runtime_digest
        )
        parsed = urlparse(request.inputs["circuit"]["uri"])
        if parsed.scheme != "file":
            raise RuntimeError("STABSim local adapter requires a file artifact")
        input_path = Path(unquote(parsed.path)).resolve()
        if not input_path.is_file():
            raise RuntimeError(f"input circuit not found: {input_path}")
        completed = subprocess.run(
            [
                str(runtime / "bin/nwq_qasm"),
                "--qasm_file",
                str(input_path),
                "--metrics",
                "--backend",
                "cpu",
                "--sim",
                "stab",
                "--random_seed",
                str(request.parameters.get("random_seed", 42)),
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        log = (completed.stdout + completed.stderr).strip()
        if completed.returncode:
            raise RuntimeError(
                f"STABSim metrics failed with exit {completed.returncode}: {log}"
            )
        match = re.search(
            r"Circuit Depth: ([0-9]+); One-qubit Gates: ([0-9]+); "
            r"Two-qubit Gates: ([0-9]+); Gate Density: ([0-9.]+); "
            r"Retention Lifespan: ([0-9.]+); Measurement Density: ([0-9.]+); "
            r"Entanglement Variance: ([0-9.]+)",
            log,
        )
        if not match:
            raise RuntimeError(f"STABSim returned unrecognized metrics: {log}")
        names = (
            "circuit_depth",
            "one_qubit_gates",
            "two_qubit_gates",
            "gate_density",
            "retention_lifespan",
            "measurement_density",
            "entanglement_variance",
        )
        values = match.groups()
        metrics = {
            name: int(value) if index < 3 else float(value)
            for index, (name, value) in enumerate(zip(names, values))
        }
        output = request.work_directory / "circuit-metrics.json"
        output.write_text(
            json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return TaskResult(
            {
                "metrics": ArtifactResult.from_path(
                    request.output_types["metrics"], output
                )
            },
            log,
        )

    runner.register("stabsim-simulator", "analyze-metrics", analyze_stabsim_metrics)

    def prepare_ftqc_iqm_circuit(request: TaskRequest) -> TaskResult:
        runtime = resolve_native_runtime(
            root, request.runtime_reference, request.runtime_digest
        )
        libraries = sorted(
            path
            for path in (runtime / "lib").glob("libftqc.*")
            if path.is_file() and path.suffix in {".dylib", ".so", ".dll"}
        )
        if len(libraries) != 1:
            raise RuntimeError(
                "FTQC local runtime must contain exactly one compiler library"
            )
        result = prepare_ftqc_iqm(
            libraries[0],
            _input_file(request, "circuit"),
            request.parameters,
            source_revision=FTQC_REVISION,
        )
        program = request.work_directory / "program.mlir"
        program.write_text(result["program"], encoding="utf-8")
        iqm_circuit = request.work_directory / "iqm-circuit.json"
        iqm_circuit.write_text(
            json.dumps(result["circuit"], indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        report = request.work_directory / "preparation-report.json"
        report.write_text(
            json.dumps(result["report"], indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return TaskResult(
            {
                "program": ArtifactResult.from_path(
                    request.output_types["program"], program
                ),
                "circuit": ArtifactResult.from_path(
                    request.output_types["circuit"], iqm_circuit
                ),
                "report": ArtifactResult.from_path(
                    request.output_types["report"], report
                ),
            },
            (
                "FTQC prepared "
                f"{result['report']['device_qubits']} IQM loci; "
                "routing and hardware submission were not performed"
            ),
        )

    runner.register("ftqc-compiler", "prepare-iqm", prepare_ftqc_iqm_circuit)
    return runner
