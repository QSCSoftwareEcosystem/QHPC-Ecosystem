"""Allowlisted adapters for verified local development runtimes."""

from __future__ import annotations

import importlib
import json
import math
import re
import shutil
import subprocess
import sys
from xml.etree import ElementTree
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import numpy as np

from .engine import ArtifactResult, FunctionRunner, TaskRequest, TaskResult
from .local_runtime import resolve_native_runtime, resolve_wheel_runtime


OPENQEVO_CONTEXT_ROOT = Path(__file__).with_name("openqevo_context")
OPENQEVO_REPOSITORY = "https://github.com/QSCSoftwareThrust/OpenQEvo"
OPENQEVO_REVISION = "7ad8ef14b9730adb200d3d0b001ec93730ec360a"
OPENQEVO_DENSE_REFERENCE_METHODS = {
    "exact",
    "trotter_s1",
    "trotter_s2",
    "qdrift",
    "krylov",
    "interaction_picture",
    "annealing",
}
OPENQEVO_DENSE_REFERENCE_MAX_QUBITS = 8
FTQC_OCI_DIGEST = "sha256:710cac493de63ca727a38ba55bbf80329511f16295951312e618732189dd51ac"
FTQC_OCI_REFERENCE = f"docker://qhpc/ftqc@{FTQC_OCI_DIGEST}"
FTQC_OCI_IMAGE = "qhpc/ftqc:779216de-linux-amd64"
FTQC_OCI_PLATFORM = "linux/amd64"
CHATQEC_QEC_TOOLS_OCI_DIGEST = (
    "sha256:4daf23c6253a6ddd3fe36e6f1b6d2e4ac8c655d4d8c1aad8c74a9fc6481e434c"
)
CHATQEC_QEC_TOOLS_OCI_REFERENCE = f"docker://ghcr.io/qscsoftwareecosystem/eqo-stim@{CHATQEC_QEC_TOOLS_OCI_DIGEST}"
CHATQEC_QEC_TOOLS_OCI_IMAGE = "qhpc/stim:0.1.0-linux-amd64"
CHATQEC_QEC_TOOLS_OCI_LOCAL_ID = (
    "sha256:6e71488fd8cc36581295ab23807a538acd9e6b978a1cbc7e77b4f342e0448678"
)
CHATQEC_QEC_TOOLS_OCI_PLATFORM = "linux/amd64"
NWQSIM_OCI_DIGEST = "sha256:80200dfd967c5575b6ca8cf1a71a071ff6aaa03500564d0b412f71d3671f6bbf"
NWQSIM_OCI_REFERENCE = (
    f"docker://ghcr.io/qscsoftwareecosystem/eqo-nwqsim@{NWQSIM_OCI_DIGEST}"
)
NWQSIM_OCI_IMAGE = "qhpc/nwqsim:0.1.0-linux-amd64"
NWQSIM_OCI_LOCAL_ID = "sha256:9e0dfb6168bd03d98165315144150a386314e855c4aacf206da76116a0b8c5bc"
NWQSIM_OCI_PLATFORM = "linux/amd64"
_MAX_CHATQEC_SVG_BYTES = 10 * 1024 * 1024
_FORBIDDEN_SVG_ELEMENTS = {
    "animate",
    "animateMotion",
    "animateTransform",
    "embed",
    "foreignObject",
    "iframe",
    "object",
    "script",
    "set",
}


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


def _ftqc_container_parameters(request: TaskRequest) -> tuple[str, str]:
    """Validate the only two caller-controlled FTQC container arguments."""

    permitted = {"preparation", "function_name"}
    unknown = sorted(
        str(name) for name in request.parameters if name not in permitted
    )
    if unknown:
        raise RuntimeError(f"unsupported FTQC parameters: {', '.join(unknown)}")
    preparation = request.parameters.get("preparation", "device")
    if preparation not in {"device", "steane-logical"}:
        raise RuntimeError("FTQC preparation must be device or steane-logical")
    function_name = request.parameters.get("function_name", "circuit")
    if (
        not isinstance(function_name, str)
        or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", function_name) is None
        or len(function_name.encode("ascii")) > 63
    ):
        raise RuntimeError(
            "FTQC function_name must be an MLIR-compatible identifier of at most "
            "63 bytes"
        )
    return preparation, function_name


def _ftqc_container_engine(request: TaskRequest) -> str:
    """Admit the exact locally built FTQC OCI image before it is executed."""

    if request.runtime_reference != FTQC_OCI_REFERENCE:
        raise RuntimeError("FTQC preparation requires the admitted OCI runtime")
    engine = shutil.which("docker") or shutil.which("podman")
    if engine is None:
        raise RuntimeError(
            "FTQC preparation requires Docker or Podman; build the admitted OCI runtime first"
        )
    try:
        inspected = subprocess.run(
            [engine, "image", "inspect", "--format", "{{.Id}}", FTQC_OCI_IMAGE],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as error:
        raise RuntimeError("FTQC OCI runtime inspection failed") from error
    image_id = (inspected.stdout or "").strip()
    if inspected.returncode != 0 or not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id):
        raise RuntimeError(
            "FTQC OCI runtime is not installed; run the documented operation-runtime build"
        )
    if image_id != request.runtime_digest:
        raise RuntimeError(
            "FTQC OCI runtime digest does not match the admitted registry"
        )
    return engine


def _ftqc_container_output(directory: Path, name: str) -> Path:
    path = directory / name
    if path.is_symlink() or not path.is_file():
        raise RuntimeError(f"FTQC OCI runtime did not produce required output: {name}")
    return path


def _chatqec_qec_tools_container_engine(request: TaskRequest) -> str:
    """Admit only the reviewed ChatQEC QEC-tools image for a local run."""

    if (
        request.runtime_reference != CHATQEC_QEC_TOOLS_OCI_REFERENCE
        or request.runtime_digest != CHATQEC_QEC_TOOLS_OCI_DIGEST
    ):
        raise RuntimeError("ChatQEC Stim operations require the admitted OCI runtime")
    engine = shutil.which("docker") or shutil.which("podman")
    if engine is None:
        raise RuntimeError(
            "ChatQEC Stim operations require Docker or Podman and the admitted OCI runtime"
        )
    try:
        inspected = subprocess.run(
            [
                engine,
                "image",
                "inspect",
                "--format",
                "{{.Id}}",
                CHATQEC_QEC_TOOLS_OCI_IMAGE,
            ],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as error:
        raise RuntimeError("ChatQEC QEC-tools OCI runtime inspection failed") from error
    image_id = (inspected.stdout or "").strip()
    if inspected.returncode != 0 or not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id):
        raise RuntimeError(
            "ChatQEC QEC-tools OCI runtime is not installed; run the documented operation-runtime build"
        )
    if image_id != CHATQEC_QEC_TOOLS_OCI_LOCAL_ID:
        raise RuntimeError(
            "ChatQEC QEC-tools OCI runtime digest does not match the admitted registry"
        )
    return engine


def _chatqec_stim_shots(request: TaskRequest) -> int:
    unknown = sorted(str(name) for name in request.parameters if name != "shots")
    if unknown:
        raise RuntimeError("unsupported ChatQEC Stim parameters: " + ", ".join(unknown))
    shots = request.parameters.get("shots", 1024)
    if isinstance(shots, bool) or not isinstance(shots, int) or not 1 <= shots <= 1_000_000:
        raise RuntimeError("ChatQEC Stim shots must be an integer from 1 to 1000000")
    return shots


def _chatqec_no_parameters(request: TaskRequest) -> None:
    if request.parameters:
        unknown = ", ".join(sorted(str(name) for name in request.parameters))
        raise RuntimeError("ChatQEC Stim diagram accepts no parameters: " + unknown)


def _chatqec_container_output(directory: Path, name: str) -> Path:
    path = directory / name
    if path.is_symlink() or not path.is_file():
        raise RuntimeError(
            f"ChatQEC QEC-tools OCI runtime did not produce required output: {name}"
        )
    return path


def _nwqsim_container_engine(request: TaskRequest) -> str:
    """Admit only the reviewed local NWQ-Sim CPU operation image."""

    if (
        request.runtime_reference != NWQSIM_OCI_REFERENCE
        or request.runtime_digest != NWQSIM_OCI_DIGEST
    ):
        raise RuntimeError("NWQ-Sim simulation requires the admitted OCI runtime")
    engine = shutil.which("docker") or shutil.which("podman")
    if engine is None:
        raise RuntimeError(
            "NWQ-Sim simulation requires Docker or Podman and the admitted OCI runtime"
        )
    try:
        inspected = subprocess.run(
            [engine, "image", "inspect", "--format", "{{.Id}}", NWQSIM_OCI_IMAGE],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as error:
        raise RuntimeError("NWQ-Sim OCI runtime inspection failed") from error
    image_id = (inspected.stdout or "").strip()
    if inspected.returncode != 0 or not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id):
        raise RuntimeError(
            "NWQ-Sim OCI runtime is not installed; run the documented operation-runtime build"
        )
    if image_id != NWQSIM_OCI_LOCAL_ID:
        raise RuntimeError("NWQ-Sim OCI runtime digest does not match the admitted registry")
    return engine


def _nwqsim_parameters(request: TaskRequest) -> tuple[int, int, int]:
    permitted = {"shots", "random_seed", "max_qubits"}
    unknown = sorted(str(name) for name in request.parameters if name not in permitted)
    if unknown:
        raise RuntimeError("unsupported NWQ-Sim parameters: " + ", ".join(unknown))
    shots = request.parameters.get("shots", 1024)
    random_seed = request.parameters.get("random_seed", 42)
    max_qubits = request.parameters.get("max_qubits", 16)
    if isinstance(shots, bool) or not isinstance(shots, int) or not 1 <= shots <= 1_000_000:
        raise RuntimeError("NWQ-Sim shots must be an integer from 1 to 1000000")
    if (
        isinstance(random_seed, bool)
        or not isinstance(random_seed, int)
        or not 0 <= random_seed <= 2_147_483_647
    ):
        raise RuntimeError("NWQ-Sim random_seed must be an integer from 0 to 2147483647")
    if isinstance(max_qubits, bool) or not isinstance(max_qubits, int) or not 1 <= max_qubits <= 16:
        raise RuntimeError("NWQ-Sim max_qubits must be an integer from 1 to 16")
    return shots, random_seed, max_qubits


def _nwqsim_measurements_output(directory: Path, shots: int) -> Path:
    path = directory / "measurements.json"
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("NWQ-Sim OCI runtime did not produce measurements.json")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError("NWQ-Sim OCI runtime produced invalid measurements") from error
    counts = payload.get("counts") if isinstance(payload, dict) else None
    if (
        not isinstance(counts, dict)
        or not counts
        or payload.get("backend") != "CPU"
        or payload.get("simulation_method") != "sv"
        or payload.get("source_revision") != "b35763d846e6512ed817d3f88ac8ce79a7e82a7e"
        or payload.get("shots") != shots
    ):
        raise RuntimeError("NWQ-Sim OCI runtime produced an invalid measurement result")
    if any(
            not isinstance(state, str)
            or re.fullmatch(r"[01]+", state) is None
            or isinstance(count, bool)
            or not isinstance(count, int)
            or count < 1
            for state, count in counts.items()
    ) or sum(counts.values()) != shots:
        raise RuntimeError("NWQ-Sim OCI runtime produced an invalid measurement result")
    return path


def _validated_chatqec_svg(path: Path) -> None:
    if path.stat().st_size > _MAX_CHATQEC_SVG_BYTES:
        raise RuntimeError("ChatQEC Stim diagram exceeds the 10 MiB artifact limit")
    try:
        root = ElementTree.fromstring(path.read_bytes())
    except ElementTree.ParseError as error:
        raise RuntimeError("ChatQEC Stim diagram is not valid SVG XML") from error
    if root.tag.rsplit("}", 1)[-1] != "svg":
        raise RuntimeError("ChatQEC Stim diagram did not produce an SVG root element")
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] in _FORBIDDEN_SVG_ELEMENTS:
            raise RuntimeError("ChatQEC Stim diagram contains an active SVG element")
        for attribute, value in element.attrib.items():
            name = attribute.rsplit("}", 1)[-1].lower()
            normalized = value.strip().lower()
            if name.startswith("on") or normalized.startswith("javascript:"):
                raise RuntimeError("ChatQEC Stim diagram contains active SVG content")
            if name == "href" and ":" in normalized:
                raise RuntimeError("ChatQEC Stim diagram contains an external SVG reference")


def _run_chatqec_stim_container(
    request: TaskRequest,
    *,
    tool: str,
    arguments: tuple[str, ...] = (),
) -> Path:
    engine = _chatqec_qec_tools_container_engine(request)
    input_directory = request.work_directory / "chatqec-stim-input"
    output_directory = request.work_directory / "chatqec-stim-output"
    if input_directory.exists() or output_directory.exists():
        raise RuntimeError("ChatQEC OCI runtime staging directory already exists")
    input_directory.mkdir()
    output_directory.mkdir()
    output_directory.chmod(0o777)
    shutil.copyfile(_input_file(request, "circuit"), input_directory / "circuit.stim")
    command = [
        engine,
        "run",
        "--rm",
        "--platform",
        CHATQEC_QEC_TOOLS_OCI_PLATFORM,
        "--network",
        "none",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,size=16m",
        "--mount",
        f"type=bind,src={input_directory},dst=/inputs,readonly",
        "--mount",
        f"type=bind,src={output_directory},dst=/outputs",
        CHATQEC_QEC_TOOLS_OCI_IMAGE,
        tool,
        *arguments,
    ]
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise RuntimeError("ChatQEC Stim OCI runtime could not be started") from error
    if completed.returncode != 0:
        raise RuntimeError("ChatQEC Stim OCI runtime failed")
    return output_directory


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


def _openqevo_dense_hamiltonian(openqevo: Any, payload: dict[str, Any]) -> Any:
    """Convert the EQO JSON input shape into OpenQEvo's canonical contract."""

    qubits = int(payload["qubits"])
    if qubits > OPENQEVO_DENSE_REFERENCE_MAX_QUBITS:
        raise RuntimeError(
            "OpenQEvo dense-reference evaluation is limited to "
            f"{OPENQEVO_DENSE_REFERENCE_MAX_QUBITS} qubits"
        )
    try:
        terms = tuple(
            openqevo.PauliTerm(
                coefficient=term["coefficient"],
                pauli_word=term["pauli"],
            )
            for term in payload["terms"]
        )
        return openqevo.PauliHamiltonian(
            terms=terms,
            identifier="eqo-supplied-hamiltonian",
            source="EQO local-development input",
        )
    except (TypeError, ValueError) as error:
        raise RuntimeError(f"OpenQEvo rejected the Pauli Hamiltonian: {error}") from error


def _positive_integer_parameter(
    parameters: dict[str, Any], name: str, *, maximum: int
) -> int:
    value = parameters.get(name)
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
        raise RuntimeError(f"{name} must be an integer from 1 to {maximum}")
    return value


def _nonnegative_integer_parameter(
    parameters: dict[str, Any], name: str, *, maximum: int
) -> int:
    value = parameters.get(name)
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= maximum:
        raise RuntimeError(f"{name} must be an integer from 0 to {maximum}")
    return value


def _positive_float_parameter(
    parameters: dict[str, Any], name: str, *, maximum: float
) -> float:
    value = parameters.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RuntimeError(f"{name} must be a finite positive number")
    normalized = float(value)
    if not math.isfinite(normalized) or not 0 < normalized <= maximum:
        raise RuntimeError(f"{name} must be a finite positive number up to {maximum}")
    return normalized


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

    def evaluate_openqevo_dense_reference(request: TaskRequest) -> TaskResult:
        """Run a deliberately bounded dense reference and preserve its outputs."""

        unknown = sorted(
            str(name)
            for name in request.parameters
            if name
            not in {
                "method",
                "evolution_time",
                "steps",
                "krylov_dim",
                "tolerance",
                "random_seed",
            }
        )
        if unknown:
            raise RuntimeError(
                "unsupported OpenQEvo dense-reference parameters: "
                + ", ".join(unknown)
            )
        openqevo = _load_openqevo(root, request)
        method = str(request.parameters.get("method", "krylov"))
        if method not in OPENQEVO_DENSE_REFERENCE_METHODS:
            available = ", ".join(sorted(OPENQEVO_DENSE_REFERENCE_METHODS))
            raise RuntimeError(
                f"OpenQEvo dense-reference method {method!r} is unavailable; "
                f"choose one of: {available}"
            )
        _method_details(openqevo, method)
        evolution_time = _positive_float_parameter(
            request.parameters, "evolution_time", maximum=1_000_000.0
        )
        hamiltonian = _openqevo_dense_hamiltonian(
            openqevo, _pauli_hamiltonian(_input_file(request, "hamiltonian"))
        )
        method_parameters: dict[str, Any] = {}
        if method == "krylov":
            method_parameters = {
                "krylov_dim": _positive_integer_parameter(
                    request.parameters, "krylov_dim", maximum=256
                ),
                "tolerance": _positive_float_parameter(
                    request.parameters, "tolerance", maximum=1.0
                ),
            }
        elif method in {
            "trotter_s1",
            "trotter_s2",
            "qdrift",
            "interaction_picture",
            "annealing",
        }:
            method_parameters = {
                "steps": _positive_integer_parameter(
                    request.parameters, "steps", maximum=4096
                )
            }
            if method == "qdrift":
                method_parameters["seed"] = _nonnegative_integer_parameter(
                    request.parameters, "random_seed", maximum=2**32 - 1
                )

        result = openqevo.get(method).run(
            hamiltonian, evolution_time, **method_parameters
        )
        unitary = request.work_directory / "evolution-unitary.npy"
        np.save(unitary, result.unitary, allow_pickle=False)
        document = result.to_metadata()
        document["parameters"] = {
            **document["parameters"],
            "eqo_source_revision": OPENQEVO_REVISION,
        }
        report = request.work_directory / "evolution-result.json"
        report.write_text(
            json.dumps(document, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return TaskResult(
            {
                "result": ArtifactResult.from_path(
                    request.output_types["result"], report
                ),
                "unitary": ArtifactResult.from_path(
                    request.output_types["unitary"], unitary
                ),
            },
            (
                f"OpenQEvo evaluated {method} on {hamiltonian.n_qubits} qubits "
                "as a bounded dense reference"
            ),
        )

    runner.register(
        "openqevo-library",
        "evaluate-dense-reference",
        evaluate_openqevo_dense_reference,
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
        preparation, function_name = _ftqc_container_parameters(request)
        engine = _ftqc_container_engine(request)
        input_directory = request.work_directory / "ftqc-container-input"
        output_directory = request.work_directory / "ftqc-container-output"
        if input_directory.exists() or output_directory.exists():
            raise RuntimeError("FTQC OCI runtime staging directory already exists")
        input_directory.mkdir()
        output_directory.mkdir()
        output_directory.chmod(0o777)
        shutil.copyfile(
            _input_file(request, "circuit"), input_directory / "circuit.qasm"
        )
        command = [
            engine,
            "run",
            "--rm",
            "--platform",
            FTQC_OCI_PLATFORM,
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=16m",
            "--mount",
            f"type=bind,src={input_directory},dst=/inputs,readonly",
            "--mount",
            f"type=bind,src={output_directory},dst=/outputs",
            FTQC_OCI_IMAGE,
            "--preparation",
            preparation,
            "--function-name",
            function_name,
        ]
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise RuntimeError("FTQC OCI preparation could not be started") from error
        if completed.returncode != 0:
            raise RuntimeError("FTQC OCI preparation failed")
        program = _ftqc_container_output(output_directory, "program.mlir")
        iqm_circuit = _ftqc_container_output(
            output_directory, "iqm-circuit.json"
        )
        report = _ftqc_container_output(
            output_directory, "preparation-report.json"
        )
        try:
            report_data = json.loads(report.read_text(encoding="utf-8"))
            device_qubits = report_data["device_qubits"]
        except (KeyError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise RuntimeError(
                "FTQC OCI runtime produced an invalid preparation report"
            ) from error
        if isinstance(device_qubits, bool) or not isinstance(device_qubits, int):
            raise RuntimeError("FTQC OCI runtime reported an invalid device width")
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
                f"{device_qubits} IQM loci in the admitted OCI runtime; "
                "routing and hardware submission were not performed"
            ),
        )

    runner.register("ftqc-compiler", "prepare-iqm", prepare_ftqc_iqm_circuit)

    def simulate_chatqec_stim_circuit(request: TaskRequest) -> TaskResult:
        shots = _chatqec_stim_shots(request)
        output_directory = _run_chatqec_stim_container(
            request,
            tool="stim-simulate",
            arguments=("--shots", str(shots)),
        )
        samples = _chatqec_container_output(output_directory, "samples.json")
        try:
            payload = json.loads(samples.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise RuntimeError(
                "ChatQEC Stim OCI runtime produced invalid simulation samples"
            ) from error
        if (
            not isinstance(payload, dict)
            or payload.get("schema") != "qhpc.stim-simulation-samples.v1"
            or payload.get("shots") != shots
        ):
            raise RuntimeError(
                "ChatQEC Stim OCI runtime produced an invalid simulation result"
            )
        return TaskResult(
            {
                "samples": ArtifactResult.from_path(
                    request.output_types["samples"], samples
                )
            },
            f"ChatQEC Stim sampled {shots} shots in the admitted OCI runtime",
        )

    runner.register("stim-simulation", "simulate", simulate_chatqec_stim_circuit)

    def render_chatqec_stim_diagram(request: TaskRequest) -> TaskResult:
        _chatqec_no_parameters(request)
        output_directory = _run_chatqec_stim_container(
            request,
            tool="stim-diagram",
        )
        diagram = _chatqec_container_output(output_directory, "diagram.svg")
        _validated_chatqec_svg(diagram)
        return TaskResult(
            {
                "diagram": ArtifactResult.from_path(
                    request.output_types["diagram"], diagram
                )
            },
            "ChatQEC Stim rendered a validated SVG diagram in the admitted OCI runtime",
        )

    runner.register("stim-simulation", "render-diagram", render_chatqec_stim_diagram)

    def simulate_nwqsim_qasm(request: TaskRequest) -> TaskResult:
        shots, random_seed, max_qubits = _nwqsim_parameters(request)
        engine = _nwqsim_container_engine(request)
        input_directory = request.work_directory / "nwqsim-container-input"
        output_directory = request.work_directory / "nwqsim-container-output"
        if input_directory.exists() or output_directory.exists():
            raise RuntimeError("NWQ-Sim OCI runtime staging directory already exists")
        input_directory.mkdir()
        output_directory.mkdir()
        output_directory.chmod(0o777)
        shutil.copyfile(_input_file(request, "circuit"), input_directory / "circuit.qasm")
        command = [
            engine,
            "run",
            "--rm",
            "--platform",
            NWQSIM_OCI_PLATFORM,
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=16m",
            "--mount",
            f"type=bind,src={input_directory},dst=/inputs,readonly",
            "--mount",
            f"type=bind,src={output_directory},dst=/outputs",
            NWQSIM_OCI_IMAGE,
            "--shots",
            str(shots),
            "--random-seed",
            str(random_seed),
            "--max-qubits",
            str(max_qubits),
        ]
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise RuntimeError("NWQ-Sim OCI simulation could not be started") from error
        if completed.returncode != 0:
            raise RuntimeError("NWQ-Sim OCI simulation failed")
        measurements = _nwqsim_measurements_output(output_directory, shots)
        return TaskResult(
            {
                "measurements": ArtifactResult.from_path(
                    request.output_types["measurements"], measurements
                )
            },
            "NWQ-Sim sampled "
            f"{shots} shots on the admitted CPU state-vector OCI runtime",
        )

    runner.register("nwqsim-cpu-simulation", "simulate-qasm", simulate_nwqsim_qasm)
    return runner
