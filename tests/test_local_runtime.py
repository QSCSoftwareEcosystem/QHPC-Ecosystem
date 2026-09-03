from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

import qhpc_ecosystem.local_adapters as local_adapters
from qhpc_ecosystem.engine import TaskRequest
from qhpc_ecosystem.local_adapters import build_local_runner
from qhpc_ecosystem.local_runtime import (
    build_cpp_runtime,
    build_wheel_runtime,
    install_local_runtime,
    list_local_runtimes,
    remove_local_runtime,
    resolve_native_runtime,
    resolve_wheel_runtime,
)


def test_optional_runtime_install_inventory_and_remove(tmp_path: Path) -> None:
    artifact = tmp_path / "openqevo-0.1.0-py3-none-any.whl"
    artifact.write_bytes(b"verified optional runtime")
    digest = "sha256:" + hashlib.sha256(artifact.read_bytes()).hexdigest()
    root = tmp_path / "runtimes"
    reference = "qhpc-runtime://wheels/" + artifact.name

    installed = install_local_runtime(
        root,
        artifact,
        reference=reference,
        digest=digest,
    )

    assert installed["installed"] is True
    assert install_local_runtime(
        root,
        artifact,
        reference=reference,
        digest=digest,
    )["installed"] is False
    assert list_local_runtimes(root) == [
        {
            "kind": "python-wheel",
            "reference": reference,
            "digest": digest,
            "size": len(b"verified optional runtime"),
        }
    ]
    assert remove_local_runtime(root, reference)
    assert not remove_local_runtime(root, reference)
    assert list_local_runtimes(root) == []


def test_optional_runtime_install_rejects_wrong_digest_and_unsafe_reference(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "runtime.whl"
    artifact.write_bytes(b"runtime")

    with pytest.raises(RuntimeError, match="digest mismatch"):
        install_local_runtime(
            tmp_path / "runtimes",
            artifact,
            reference="qhpc-runtime://wheels/runtime.whl",
            digest="sha256:" + "0" * 64,
        )
    with pytest.raises(RuntimeError, match="invalid python-wheel"):
        install_local_runtime(
            tmp_path / "runtimes",
            artifact,
            reference="qhpc-runtime://wheels/../runtime.whl",
            digest="sha256:" + hashlib.sha256(artifact.read_bytes()).hexdigest(),
        )


def test_missing_optional_runtime_fails_with_an_actionable_error(tmp_path: Path) -> None:
    digest = "sha256:" + "0" * 64

    with pytest.raises(RuntimeError, match="wheel runtime not installed"):
        resolve_wheel_runtime(
            tmp_path / "runtimes",
            "qhpc-runtime://wheels/missing.whl",
            digest,
        )


def make_openqevo_fixture(root: Path) -> str:
    (root / "openqevo").mkdir(parents=True)
    (root / "openqevo/__init__.py").write_text(
        "def list_methods():\n    return ['exact', 'qiskit_trotter', 'trotter_s2']\n\n"
        "def list_methods_detail():\n"
        "    return [\n"
        "        {'name': 'exact', 'description': 'reference', 'source': 'fixture'},\n"
        "        {'name': 'qiskit_trotter', 'description': 'adapter', 'source': 'qiskit'},\n"
        "        {'name': 'trotter_s2', 'description': 'symmetric', 'source': 'algorithms-thrust'},\n"
        "    ]\n",
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


def test_wheel_runtime_is_reproducible_verified_and_allowlisted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    runner = build_local_runner(tmp_path / "runtime-1")
    result = runner.execute(request)
    output = Path(result.outputs["methods"].uri.removeprefix("file://"))
    assert (
        json.loads(output.read_text(encoding="utf-8"))["methods"][0]["name"] == "exact"
    )

    context_work = tmp_path / "context-work"
    context_work.mkdir()
    context_result = runner.execute(
        TaskRequest(
            run_id="run-context",
            node_id="describe",
            capability_id="openqevo-library",
            capability_version="0.1.0",
            operation_id="describe-method",
            runtime_reference=first.reference,
            runtime_digest=first.digest,
            parameters={"method": "trotter_s2"},
            inputs={},
            output_types={"context": "qhpc.evolution-method-context@1"},
            work_directory=context_work,
        )
    )
    context_output = Path(
        context_result.outputs["context"].uri.removeprefix("file://")
    )
    context = json.loads(context_output.read_text(encoding="utf-8"))
    assert context["method"]["name"] == "trotter_s2"
    assert context["context_status"] == "available"
    assert context["context"]["complexity"]["error_scaling"].endswith("/ n^2)")

    monkeypatch.setattr(
        local_adapters,
        "_synthesize_qiskit_trotter",
        lambda hamiltonian, **parameters: (
            "OPENQASM 2.0;\ninclude \"qelib1.inc\";\nqreg q[2];\n",
            {"depth": 3, "gate_counts": {"cx": 2}},
        ),
    )
    hamiltonian = tmp_path / "hamiltonian.json"
    hamiltonian.write_text(
        json.dumps(
            {
                "qubits": 2,
                "terms": [
                    {"pauli": "ZI", "coefficient": 1.0},
                    {"pauli": "XX", "coefficient": 0.25},
                ],
            }
        ),
        encoding="utf-8",
    )
    synthesis_work = tmp_path / "synthesis-work"
    synthesis_work.mkdir()
    synthesis_result = runner.execute(
        TaskRequest(
            run_id="run-synthesis",
            node_id="synthesize",
            capability_id="openqevo-library",
            capability_version="0.1.0",
            operation_id="synthesize-evolution",
            runtime_reference=first.reference,
            runtime_digest=first.digest,
            parameters={
                "method": "qiskit_trotter",
                "evolution_time": 1.0,
                "steps": 4,
                "order": 2,
            },
            inputs={"hamiltonian": {"uri": hamiltonian.resolve().as_uri()}},
            output_types={
                "circuit": "qhpc.quantum-circuit@1",
                "report": "qhpc.evolution-synthesis-report@1",
            },
            work_directory=synthesis_work,
        )
    )
    report_output = Path(
        synthesis_result.outputs["report"].uri.removeprefix("file://")
    )
    report = json.loads(report_output.read_text(encoding="utf-8"))
    assert report["method"] == "qiskit_trotter"
    assert report["gate_counts"] == {"cx": 2}
    assert report["bridge_status"] == "development"

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
