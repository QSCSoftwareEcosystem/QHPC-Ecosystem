"""Allowlisted adapters for verified local development runtimes."""

from __future__ import annotations

import importlib
import json
import re
import sys
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlparse

from .engine import ArtifactResult, FunctionRunner, TaskRequest, TaskResult
from .local_runtime import resolve_native_runtime, resolve_wheel_runtime


def build_local_runner(runtime_root: str | Path) -> FunctionRunner:
    root = Path(runtime_root).expanduser().resolve()
    runner = FunctionRunner()

    def list_openqevo_methods(request: TaskRequest) -> TaskResult:
        wheel = resolve_wheel_runtime(
            root, request.runtime_reference, request.runtime_digest
        )
        wheel_value = str(wheel)
        if wheel_value not in sys.path:
            sys.path.insert(0, wheel_value)
        openqevo = importlib.import_module("openqevo")
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
    return runner
