from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from qhpc_ecosystem.engine import TaskRequest
from qhpc_ecosystem.local_adapters import build_local_runner
from qhpc_ecosystem.local_runtime import build_wheel_runtime, resolve_wheel_runtime
from qhpc_ecosystem.local_runtime import build_cpp_runtime, resolve_native_runtime


def make_openqevo_fixture(root: Path) -> str:
    (root / "openqevo").mkdir(parents=True)
    (root / "openqevo/__init__.py").write_text(
        "def list_methods():\n    return ['exact']\n\n"
        "def list_methods_detail():\n"
        "    return [{'name': 'exact', 'description': 'reference', 'source': 'fixture'}]\n",
        encoding="utf-8",
    )
    (root / "pyproject.toml").write_text(
        "[build-system]\nrequires=['setuptools>=68']\nbuild-backend='setuptools.build_meta'\n"
        "[project]\nname='openqevo'\nversion='0.1.0'\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "-c",
            "user.name=QHPC Test",
            "-c",
            "user.email=qhpc@example.invalid",
            "commit",
            "-q",
            "-m",
            "fixture",
        ],
        check=True,
    )
    return subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def test_wheel_runtime_is_reproducible_verified_and_allowlisted(tmp_path: Path) -> None:
    source = tmp_path / "source"
    revision = make_openqevo_fixture(source)
    first = build_wheel_runtime(
        source, tmp_path / "runtime-1/wheels", revision=revision
    )
    second = build_wheel_runtime(
        source, tmp_path / "runtime-2/wheels", revision=revision
    )

    assert first.digest == second.digest
    assert (
        resolve_wheel_runtime(tmp_path / "runtime-1", first.reference, first.digest)
        == first.path
    )

    work = tmp_path / "work"
    work.mkdir()
    request = TaskRequest(
        run_id="run-test",
        node_id="list-methods",
        capability_id="openqevo-library",
        capability_version="0.1.0",
        operation_id="list-methods",
        runtime_reference=first.reference,
        runtime_digest=first.digest,
        parameters={"detailed": True},
        inputs={},
        output_types={"methods": "qhpc.method-catalog@1"},
        work_directory=work,
    )
    result = build_local_runner(tmp_path / "runtime-1").execute(request)
    output = Path(result.outputs["methods"].uri.removeprefix("file://"))
    assert (
        json.loads(output.read_text(encoding="utf-8"))["methods"][0]["name"] == "exact"
    )

    first.path.write_bytes(first.path.read_bytes() + b"tamper")
    with pytest.raises(RuntimeError, match="digest mismatch"):
        resolve_wheel_runtime(tmp_path / "runtime-1", first.reference, first.digest)


def test_native_runtime_is_reproducible_and_stabsim_adapter_parses_metrics(
    tmp_path: Path,
) -> None:
    source = tmp_path / "native-source"
    source.mkdir()
    (source / "metrics.cpp").write_text(
        "#include <iostream>\n"
        'int main(){std::cout << "Circuit Depth: 3; One-qubit Gates: 4; "'
        '"Two-qubit Gates: 1; Gate Density: 0.5; Retention Lifespan: 2.0; "'
        '"Measurement Density: 0.25; Entanglement Variance: 1.5\\n";}\n',
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q", str(source)], check=True)
    subprocess.run(["git", "-C", str(source), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(source),
            "-c",
            "user.name=QHPC Test",
            "-c",
            "user.email=qhpc@example.invalid",
            "commit",
            "-q",
            "-m",
            "native fixture",
        ],
        check=True,
    )
    revision = subprocess.run(
        ["git", "-C", str(source), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    first = build_cpp_runtime(
        source,
        tmp_path / "native-1/native",
        revision=revision,
        name="stabsim",
        executable="nwq_qasm",
        source_files=("metrics.cpp",),
    )
    second = build_cpp_runtime(
        source,
        tmp_path / "native-2/native",
        revision=revision,
        name="stabsim",
        executable="nwq_qasm",
        source_files=("metrics.cpp",),
    )
    assert first.digest == second.digest
    assert (
        resolve_native_runtime(tmp_path / "native-1", first.reference, first.digest)
        / "bin/nwq_qasm"
    ).is_file()

    circuit = tmp_path / "input.qasm"
    circuit.write_text("OPENQASM 2.0;\nqreg q[1];\n", encoding="utf-8")
    work = tmp_path / "native-work"
    work.mkdir()
    request = TaskRequest(
        run_id="run-native",
        node_id="analyze",
        capability_id="stabsim-simulator",
        capability_version="0.1.0",
        operation_id="analyze-metrics",
        runtime_reference=first.reference,
        runtime_digest=first.digest,
        parameters={"random_seed": 42},
        inputs={"circuit": {"uri": circuit.resolve().as_uri()}},
        output_types={"metrics": "qhpc.circuit-metrics@1"},
        work_directory=work,
    )
    result = build_local_runner(tmp_path / "native-1").execute(request)
    output = Path(result.outputs["metrics"].uri.removeprefix("file://"))
    metrics = json.loads(output.read_text(encoding="utf-8"))
    assert metrics["circuit_depth"] == 3
    assert metrics["two_qubit_gates"] == 1
