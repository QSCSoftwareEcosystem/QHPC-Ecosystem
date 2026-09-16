from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import zipfile
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

import qhpc_ecosystem.local_adapters as local_adapters
from qhpc_ecosystem.engine import TaskRequest
from qhpc_ecosystem.local_adapters import build_local_runner
from qhpc_ecosystem.local_runtime import (
    build_cmake_runtime,
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


def test_ftqc_preparation_uses_only_the_admitted_oci_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "bell.qasm"
    source.write_text("OPENQASM 3.0;\nqubit[2] q;\n", encoding="utf-8")
    work = tmp_path / "work"
    work.mkdir()
    digest = "sha256:" + "f" * 64
    calls: list[list[str]] = []

    def run(command, **_options):
        calls.append(command)
        if command[1:3] == ["image", "inspect"]:
            return SimpleNamespace(returncode=0, stdout=digest + "\n", stderr="")
        assert command[:3] == ["/usr/bin/docker", "run", "--rm"]
        assert "--network" in command
        assert command[command.index("--network") + 1] == "none"
        assert "--read-only" in command
        assert "--cap-drop" in command
        assert command[command.index("--cap-drop") + 1] == "ALL"
        output_mount = next(
            value
            for index, value in enumerate(command)
            if command[index - 1] == "--mount" and "dst=/outputs" in value
        )
        output = Path(output_mount.split(",")[1].removeprefix("src=")).resolve()
        (output / "program.mlir").write_text(
            'module attributes {ftqc.iqm_json = "{}"}\n', encoding="utf-8"
        )
        (output / "iqm-circuit.json").write_text(
            '{"instructions": [], "name": "circuit"}\n', encoding="utf-8"
        )
        (output / "preparation-report.json").write_text(
            '{"device_qubits": 2}\n', encoding="utf-8"
        )
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(
        local_adapters.shutil, "which", lambda _name: "/usr/bin/docker"
    )
    monkeypatch.setattr(local_adapters.subprocess, "run", run)
    result = build_local_runner(tmp_path / "runtimes").execute(
        TaskRequest(
            run_id="run-ftqc",
            node_id="prepare",
            capability_id="ftqc-compiler",
            capability_version="0.4.0",
            operation_id="prepare-iqm",
            runtime_reference=local_adapters.FTQC_OCI_REFERENCE,
            runtime_digest=digest,
            parameters={"preparation": "device", "function_name": "circuit"},
            inputs={"circuit": {"uri": source.as_uri()}},
            output_types={
                "program": "qhpc.ftqc-mlir@1",
                "circuit": "qhpc.iqm-circuit@1",
                "report": "qhpc.ftqc-iqm-preparation-report@1",
            },
            work_directory=work,
        )
    )

    assert len(calls) == 2
    assert "admitted OCI runtime" in result.log
    assert Path(result.outputs["report"].uri.removeprefix("file://")).is_file()


def test_ftqc_preparation_rejects_a_native_or_tampered_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        local_adapters.shutil, "which", lambda _name: "/usr/bin/docker"
    )
    request = TaskRequest(
        run_id="run-ftqc",
        node_id="prepare",
        capability_id="ftqc-compiler",
        capability_version="0.4.0",
        operation_id="prepare-iqm",
        runtime_reference="qhpc-runtime://native/ftqc.zip",
        runtime_digest="sha256:" + "0" * 64,
        parameters={},
        inputs={},
        output_types={},
        work_directory=tmp_path,
    )

    with pytest.raises(RuntimeError, match="admitted OCI runtime"):
        local_adapters._ftqc_container_engine(request)


def test_chatqec_stim_simulation_uses_only_the_admitted_oci_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "bell.stim"
    source.write_text("H 0\nM 0\n", encoding="utf-8")
    work = tmp_path / "work"
    work.mkdir()
    calls: list[list[str]] = []

    def run(command, **_options):
        calls.append(command)
        if command[1:3] == ["image", "inspect"]:
            return SimpleNamespace(
                returncode=0,
                stdout=local_adapters.CHATQEC_QEC_TOOLS_OCI_LOCAL_ID + "\n",
                stderr="",
            )
        assert command[:3] == ["/usr/bin/docker", "run", "--rm"]
        assert command[command.index("--network") + 1] == "none"
        assert "--read-only" in command
        assert command[command.index("--cap-drop") + 1] == "ALL"
        assert command[-3:] == ["stim-simulate", "--shots", "4"]
        output_mount = next(
            value
            for index, value in enumerate(command)
            if command[index - 1] == "--mount" and "dst=/outputs" in value
        )
        output = Path(output_mount.split(",")[1].removeprefix("src=")).resolve()
        (output / "samples.json").write_text(
            '{"schema": "qhpc.stim-simulation-samples.v1", "shots": 4}\n',
            encoding="utf-8",
        )
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(
        local_adapters.shutil, "which", lambda _name: "/usr/bin/docker"
    )
    monkeypatch.setattr(local_adapters.subprocess, "run", run)
    result = build_local_runner(tmp_path / "runtimes").execute(
        TaskRequest(
            run_id="run-stim",
            node_id="simulate",
            capability_id="stim-simulation",
            capability_version="0.1.0",
            operation_id="simulate",
            runtime_reference=local_adapters.CHATQEC_QEC_TOOLS_OCI_REFERENCE,
            runtime_digest=local_adapters.CHATQEC_QEC_TOOLS_OCI_DIGEST,
            parameters={"shots": 4},
            inputs={"circuit": {"uri": source.as_uri()}},
            output_types={"samples": "qhpc.stim-simulation-samples@1"},
            work_directory=work,
        )
    )

    assert len(calls) == 2
    assert "admitted OCI runtime" in result.log
    assert Path(result.outputs["samples"].uri.removeprefix("file://")).is_file()


def test_chatqec_stim_diagram_rejects_active_svg(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "bell.stim"
    source.write_text("H 0\nM 0\n", encoding="utf-8")
    work = tmp_path / "work"
    work.mkdir()

    def run(command, **_options):
        if command[1:3] == ["image", "inspect"]:
            return SimpleNamespace(
                returncode=0,
                stdout=local_adapters.CHATQEC_QEC_TOOLS_OCI_LOCAL_ID + "\n",
                stderr="",
            )
        output_mount = next(
            value
            for index, value in enumerate(command)
            if command[index - 1] == "--mount" and "dst=/outputs" in value
        )
        output = Path(output_mount.split(",")[1].removeprefix("src=")).resolve()
        (output / "diagram.svg").write_text(
            "<svg onload=\"alert(1)\"/>", encoding="utf-8"
        )
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(
        local_adapters.shutil, "which", lambda _name: "/usr/bin/docker"
    )
    monkeypatch.setattr(local_adapters.subprocess, "run", run)
    request = TaskRequest(
        run_id="run-stim",
        node_id="diagram",
            capability_id="stim-simulation",
        capability_version="0.1.0",
            operation_id="render-diagram",
        runtime_reference=local_adapters.CHATQEC_QEC_TOOLS_OCI_REFERENCE,
        runtime_digest=local_adapters.CHATQEC_QEC_TOOLS_OCI_DIGEST,
        parameters={},
        inputs={"circuit": {"uri": source.as_uri()}},
        output_types={"diagram": "qhpc.stim-diagram@1"},
        work_directory=work,
    )

    with pytest.raises(RuntimeError, match="active SVG content"):
        build_local_runner(tmp_path / "runtimes").execute(request)


def test_cmake_runtime_packages_an_explicit_shared_library(tmp_path: Path) -> None:
    if platform.system() not in {"Darwin", "Linux"}:
        pytest.skip("shared-library fixture currently covers Darwin and Linux")
    source = tmp_path / "cmake-source"
    source.mkdir()
    (source / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 3.20)\n"
        "project(runtime_fixture LANGUAGES CXX)\n"
        "add_library(runtime_fixture SHARED library.cpp)\n"
        "add_executable(runtime-tool tool.cpp)\n",
        encoding="utf-8",
    )
    (source / "library.cpp").write_text(
        'extern "C" int answer() { return 42; }\n', encoding="utf-8"
    )
    (source / "tool.cpp").write_text(
        "int main() { return 0; }\n", encoding="utf-8"
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
            "cmake fixture",
        ],
        check=True,
    )
    revision = subprocess.run(
        ["git", "-C", str(source), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    suffix = ".dylib" if platform.system() == "Darwin" else ".so"

    runtime = build_cmake_runtime(
        source,
        tmp_path / "runtimes/native",
        revision=revision,
        name="runtime-fixture",
        target="all",
        executable="runtime-tool",
        libraries=(f"libruntime_fixture{suffix}",),
    )

    with zipfile.ZipFile(runtime.path) as archive:
        names = set(archive.namelist())
        manifest = json.loads(archive.read("manifest.json"))
    assert "bin/runtime-tool" in names
    assert f"lib/libruntime_fixture{suffix}" in names
    assert manifest["libraries"] == [f"lib/libruntime_fixture{suffix}"]


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
    assert "O(t^3/n^2)" in context["context"]["complexity"]["error_scaling"]

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


def test_openqevo_dense_reference_adapter_preserves_result_and_unitary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class PauliTerm:
        def __init__(self, *, coefficient, pauli_word) -> None:
            self.coefficient = coefficient
            self.pauli_word = pauli_word

    class PauliHamiltonian:
        def __init__(self, *, terms, identifier, source) -> None:
            self.terms = terms
            self.identifier = identifier
            self.source = source
            self.n_qubits = len(terms[0].pauli_word)

    class Result:
        unitary = np.eye(2, dtype=complex)

        def to_metadata(self):
            return {
                "schema_version": "openqevo-evolution-result/v1",
                "representation": "unitary",
                "method": "krylov",
                "implementation": {
                    "package": "openqevo",
                    "version": "0.1.0",
                    "source": "fixture",
                },
                "parameters": {"krylov_dim": 2, "tolerance": 1e-12},
                "costs": {
                    "formula_level_pauli_operations": None,
                    "adjacent_merged_pauli_operations": None,
                    "compiled_one_qubit_gates": None,
                    "compiled_two_qubit_gates": None,
                    "circuit_depth": None,
                },
                "hamiltonian": {"representation": "pauli_sum"},
                "seed": None,
                "sampled_sequence": None,
                "runtime_seconds": None,
                "environment": {},
                "warnings": ["fixture warning"],
                "limitations": ["fixture limitation"],
                "output": {
                    "python_type": "ndarray",
                    "shape": [2, 2],
                    "dtype": "complex128",
                    "sha256": "0" * 64,
                },
            }

    class Method:
        def run(self, hamiltonian, evolution_time, **parameters):
            assert hamiltonian.n_qubits == 1
            assert evolution_time == 0.75
            assert parameters == {"krylov_dim": 2, "tolerance": 1e-12}
            return Result()

    fake_openqevo = SimpleNamespace(
        PauliTerm=PauliTerm,
        PauliHamiltonian=PauliHamiltonian,
        get=lambda method: Method() if method == "krylov" else None,
        list_methods_detail=lambda: [
            {"name": "krylov", "description": "fixture", "source": "fixture"}
        ],
    )
    monkeypatch.setattr(
        local_adapters, "_load_openqevo", lambda _root, _request: fake_openqevo
    )
    hamiltonian = tmp_path / "hamiltonian.json"
    hamiltonian.write_text(
        json.dumps(
            {
                "qubits": 1,
                "terms": [{"pauli": "Z", "coefficient": 1.0}],
            }
        ),
        encoding="utf-8",
    )
    work = tmp_path / "dense-reference-work"
    work.mkdir()
    result = build_local_runner(tmp_path / "runtimes").execute(
        TaskRequest(
            run_id="run-dense-reference",
            node_id="evaluate",
            capability_id="openqevo-library",
            capability_version="0.1.0",
            operation_id="evaluate-dense-reference",
            runtime_reference="qhpc-runtime://wheels/fixture.whl",
            runtime_digest="sha256:" + "0" * 64,
            parameters={
                "method": "krylov",
                "evolution_time": 0.75,
                "steps": 32,
                "krylov_dim": 2,
                "tolerance": 1e-12,
            },
            inputs={"hamiltonian": {"uri": hamiltonian.resolve().as_uri()}},
            output_types={
                "result": "qhpc.evolution-result@1",
                "unitary": "qhpc.dense-unitary@1",
            },
            work_directory=work,
        )
    )

    report = Path(result.outputs["result"].uri.removeprefix("file://"))
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["method"] == "krylov"
    assert payload["parameters"]["eqo_source_revision"] == local_adapters.OPENQEVO_REVISION
    unitary = Path(result.outputs["unitary"].uri.removeprefix("file://"))
    np.testing.assert_allclose(np.load(unitary, allow_pickle=False), np.eye(2))


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
