from __future__ import annotations

import ctypes
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from jsonschema import Draft202012Validator

from qhpc_ecosystem.contract import load_document
from qhpc_ecosystem import project_adapters
from qhpc_ecosystem.project_adapters import ProjectAdapterError


ROOT = Path(__file__).resolve().parents[1]


def _tnsim_executable(tmp_path: Path) -> Path:
    executable = tmp_path / "nwq_qasm"
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    executable.chmod(0o755)
    return executable


def _ftqc_executable(tmp_path: Path) -> Path:
    executable = tmp_path / "qasm3-import"
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    executable.chmod(0o755)
    return executable


def test_nwqec_adapter_normalizes_public_api_output(tmp_path, monkeypatch) -> None:
    circuit_path = tmp_path / "input.qasm"
    circuit_path.write_text("OPENQASM 2.0;\n", encoding="utf-8")
    circuit = SimpleNamespace(num_qubits=lambda: 3)
    calls = {}

    def get_counts(value, **parameters):
        calls["circuit"] = value
        calls["parameters"] = parameters
        return {"tdg": 2, "h": 4, "t": 5}

    module = SimpleNamespace(
        load_qasm=lambda path: circuit,
        get_clifford_t_counts=get_counts,
    )
    monkeypatch.setattr(project_adapters.importlib, "import_module", lambda _: module)

    result = project_adapters.count_nwqec_clifford_t(
        circuit_path,
        {"keep_ccx": True, "rz_error_policy": "relative", "epsilon": 0.02},
    )

    assert result == {
        "counts": {"h": 4, "t": 5, "tdg": 2},
        "total_t_count": 7,
        "source_qubits": 3,
        "rz_error_policy": "relative",
        "epsilon": 0.02,
    }
    assert calls["circuit"] is circuit
    assert calls["parameters"] == {
        "keep_ccx": True,
        "rz_err": "relative",
        "epsilon": 0.02,
    }


def test_ftprimitivebench_adapter_uses_public_memory_and_noise_apis(
    monkeypatch,
) -> None:
    calls = {}

    class Circuit:
        def __str__(self) -> str:
            return "DETECTOR rec[-1]\nOBSERVABLE_INCLUDE(0) rec[-1]"

    def memory(**parameters):
        calls["memory"] = parameters
        return "clean"

    class NoiseModel:
        def noisy_circuit(self, circuit):
            calls["clean"] = circuit
            return Circuit()

    def uniform_depolarizing(*, p):
        calls["p"] = p
        return NoiseModel()

    modules = {
        "ft_primitive_bench.surface_code.circuits": SimpleNamespace(memory=memory),
        "ft_primitive_bench.noise_models": SimpleNamespace(
            uniform_depolarizing=uniform_depolarizing
        ),
    }
    monkeypatch.setattr(
        project_adapters.importlib, "import_module", modules.__getitem__
    )

    result = project_adapters.build_ftprimitivebench_memory(
        {
            "x_distance": 3,
            "z_distance": 5,
            "rounds": 4,
            "measurement_basis": "X",
            "physical_error_rate": 0.005,
        }
    )

    assert result.endswith("\n")
    assert calls["memory"] == {
        "x_distance": 3,
        "z_distance": 5,
        "rounds": 4,
        "meas_basis": "X",
    }
    assert calls["p"] == 0.005
    assert calls["clean"] == "clean"


def test_lightstim_adapter_returns_contract_shaped_statistics(monkeypatch) -> None:
    calls = {}

    class Circuit:
        num_detectors = 12
        num_observables = 1

        def __init__(self, text):
            calls["text"] = text

    class Stats:
        shots = 100
        post_selected_shots = 90
        errors = 4
        logical_error_rate = 4 / 90
        seconds = 0.25
        decoder = "pymatching"

        def ler_error_bar(self):
            return 0.02

    class Pipeline:
        def __init__(self, **parameters):
            calls["pipeline"] = parameters

        def run(self, circuit):
            calls["circuit"] = circuit
            return Stats()

    simulation = SimpleNamespace(
        DecoderConfig=lambda name: ("decoder", name),
        SimulationPipeline=Pipeline,
    )
    modules = {
        "stim": SimpleNamespace(Circuit=Circuit),
        "lightstim.simulation.decoder_backend": simulation,
    }
    monkeypatch.setattr(
        project_adapters.importlib, "import_module", modules.__getitem__
    )

    result = project_adapters.estimate_lightstim_logical_error(
        "DETECTOR rec[-1]\nOBSERVABLE_INCLUDE(0) rec[-1]\n",
        {
            "decoder": "pymatching",
            "max_shots": 100,
            "max_errors": 5,
            "batch_size": 25,
            "num_workers": 1,
        },
    )

    assert result == {
        "shots": 100,
        "post_selected_shots": 90,
        "errors": 4,
        "logical_error_rate": 4 / 90,
        "error_bar": 0.02,
        "seconds": 0.25,
        "decoder": "pymatching",
    }
    assert calls["pipeline"]["decoder_config"] == ("decoder", "pymatching")
    assert calls["pipeline"]["print_progress"] is False


def test_tnsim_adapter_builds_controlled_cpu_mps_command(tmp_path) -> None:
    executable = _tnsim_executable(tmp_path)
    circuit = ROOT / "integrations" / "tn-sim" / "fixtures" / "bell.qasm"
    stdout = (
        ROOT / "integrations" / "tn-sim" / "fixtures" / "bell-stdout.txt"
    ).read_text(encoding="utf-8")
    call = {}

    def executor(command, **options):
        call["command"] = command
        call["options"] = options
        return SimpleNamespace(returncode=0, stdout=stdout, stderr="")

    result = project_adapters.simulate_tnsim_mps(
        executable,
        circuit,
        {
            "shots": 16,
            "max_bond_dimension": 256,
            "singular_value_cutoff": 0.000001,
            "random_seed": 7,
        },
        executor=executor,
    )

    assert call["command"] == [
        str(executable.resolve()),
        "--qasm_file",
        str(circuit.resolve()),
        "--shots",
        "16",
        "--backend",
        "CPU",
        "--sim",
        "tn",
        "--max_dim",
        "256",
        "--sv_cutoff",
        "1e-06",
        "--random_seed",
        "7",
    ]
    assert call["options"] == {
        "capture_output": True,
        "text": True,
        "check": False,
    }
    assert result == {
        "shots": 16,
        "counts": {"00": 9, "11": 7},
        "backend": "CPU",
        "simulation_method": "tn",
        "max_bond_dimension": 256,
        "singular_value_cutoff": 0.000001,
        "random_seed": 7,
    }

    artifact_type = load_document(
        ROOT / "artifact-types" / "measurement-counts-v1.yaml"
    )
    Draft202012Validator(artifact_type["spec"]["json_schema"]).validate(result)


def test_tnsim_adapter_rejects_incomplete_measurement_output(tmp_path) -> None:
    executable = _tnsim_executable(tmp_path)
    circuit = ROOT / "integrations" / "tn-sim" / "fixtures" / "bell.qasm"

    def executor(_command, **_options):
        return SimpleNamespace(
            returncode=0,
            stdout=(
                "===============  Measurement (tests=16) ================\n"
                '"00" : 8\n'
                '"11" : 7\n'
            ),
            stderr="",
        )

    with pytest.raises(ProjectAdapterError, match="sum to 15; expected 16"):
        project_adapters.simulate_tnsim_mps(
            executable,
            circuit,
            {"shots": 16},
            executor=executor,
        )


def test_tnsim_adapter_rejects_unknown_parameters_without_execution(
    tmp_path,
) -> None:
    executable = _tnsim_executable(tmp_path)
    circuit = ROOT / "integrations" / "tn-sim" / "fixtures" / "bell.qasm"

    def executor(_command, **_options):
        raise AssertionError("executor must not be called")

    with pytest.raises(
        ProjectAdapterError, match="unsupported TN-Sim parameters: backend"
    ):
        project_adapters.simulate_tnsim_mps(
            executable,
            circuit,
            {"backend": "TN_TAMM_GPU"},
            executor=executor,
        )


def test_ftqc_adapter_builds_controlled_import_command(tmp_path) -> None:
    executable = _ftqc_executable(tmp_path)
    circuit = ROOT / "integrations" / "ftqc" / "fixtures" / "bell.qasm"
    output = (
        ROOT / "integrations" / "ftqc" / "fixtures" / "bell.ftqc.mlir"
    ).read_text(encoding="utf-8")
    call = {}

    def executor(command, **options):
        call["command"] = command
        call["options"] = options
        return SimpleNamespace(returncode=0, stdout=output, stderr="")

    result = project_adapters.import_ftqc_qasm(
        executable,
        circuit,
        {"ecc": "surface", "distance": 5, "function_name": "bell_surface"},
        executor=executor,
    )

    assert call["command"] == [
        str(executable.resolve()),
        "--ecc=surface",
        "--distance=5",
        "--func-name=bell_surface",
        str(circuit.resolve()),
    ]
    assert call["options"] == {
        "capture_output": True,
        "text": True,
        "check": False,
    }
    assert result == output


def test_ftqc_adapter_rejects_uncontrolled_parameters_without_execution(
    tmp_path,
) -> None:
    executable = _ftqc_executable(tmp_path)
    circuit = ROOT / "integrations" / "ftqc" / "fixtures" / "bell.qasm"

    def executor(_command, **_options):
        raise AssertionError("executor must not be called")

    with pytest.raises(
        ProjectAdapterError, match="unsupported FTQC parameters: output_file"
    ):
        project_adapters.import_ftqc_qasm(
            executable,
            circuit,
            {"output_file": "/tmp/uncontrolled.mlir"},
            executor=executor,
        )


def test_ftqc_adapter_requires_openqasm_input(tmp_path) -> None:
    executable = _ftqc_executable(tmp_path)
    circuit = tmp_path / "not-qasm.txt"
    circuit.write_text("h q[0];\n", encoding="utf-8")

    with pytest.raises(
        ProjectAdapterError, match="must declare OPENQASM 2.0 or 3.0"
    ):
        project_adapters.import_ftqc_qasm(executable, circuit, {})


def test_ftqc_iqm_preparation_uses_c_api_and_reports_unrouted_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    library_path = tmp_path / "libftqc.dylib"
    library_path.write_bytes(b"fixture")
    circuit_path = tmp_path / "bell.qasm"
    circuit_path.write_text("OPENQASM 3.0;\nqubit[2] q;\n", encoding="utf-8")
    iqm_circuit = {
        "name": "bell",
        "instructions": [
            {"name": "cz", "locus": ["QB1", "QB2"], "args": {}},
            {
                "name": "measure",
                "locus": ["QB1"],
                "args": {"key": "m1"},
            },
            {
                "name": "measure",
                "locus": ["QB2"],
                "args": {"key": "m2"},
            },
        ],
    }
    encoded = json.dumps(iqm_circuit, separators=(",", ":")).replace('"', "\\22")
    program = (
        f'module attributes {{ftqc.iqm_json = "{encoded}"}} '
        "{ func.func @bell() }\n"
    ).encode()
    buffers = []
    observed = {}

    class Function:
        def __init__(self, callback):
            self.callback = callback

        def __call__(self, *arguments):
            return self.callback(*arguments)

    def compile_qasm(_data, size, configuration, output, output_size):
        observed["size"] = size
        config = ctypes.cast(
            configuration, ctypes.POINTER(project_adapters._FTQCCfg)
        ).contents
        observed["physical"] = config.lower_to_iqm_json_physical
        observed["radians"] = config.lower_to_iqm_json_radians
        buffer = ctypes.create_string_buffer(program)
        buffers.append(buffer)
        ctypes.cast(output, ctypes.POINTER(ctypes.c_void_p))[0] = ctypes.cast(
            buffer, ctypes.c_void_p
        )
        ctypes.cast(output_size, ctypes.POINTER(ctypes.c_size_t))[0] = len(program)
        return 0

    fake_library = SimpleNamespace(
        ftqc_qasm_opt=Function(compile_qasm),
        ftqc_free=Function(lambda _pointer: None),
    )
    monkeypatch.setattr(project_adapters.ctypes, "CDLL", lambda _path: fake_library)

    result = project_adapters.prepare_ftqc_iqm(
        library_path,
        circuit_path,
        {"preparation": "device", "function_name": "bell"},
        source_revision="7" * 40,
    )

    assert result["circuit"] == iqm_circuit
    assert result["report"]["device_qubits"] == 2
    assert result["report"]["routing"]["status"] == "not-performed"
    assert result["report"]["submission"]["status"] == "not-submitted"
    assert observed == {
        "size": len(circuit_path.read_bytes()),
        "physical": 0,
        "radians": 1,
    }
    artifact_type = load_document(
        ROOT / "artifact-types" / "ftqc-iqm-preparation-report-v1.yaml"
    )
    Draft202012Validator(artifact_type["spec"]["json_schema"]).validate(
        result["report"]
    )


def test_ftqc_iqm_preparation_rejects_unknown_parameters_before_loading(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    library_path = tmp_path / "libftqc.dylib"
    library_path.write_bytes(b"fixture")
    circuit_path = tmp_path / "bell.qasm"
    circuit_path.write_text("OPENQASM 3.0;\nqubit[2] q;\n", encoding="utf-8")
    monkeypatch.setattr(
        project_adapters.ctypes,
        "CDLL",
        lambda _path: (_ for _ in ()).throw(AssertionError("must not load")),
    )

    with pytest.raises(ProjectAdapterError, match="unsupported FTQC parameters: token"):
        project_adapters.prepare_ftqc_iqm(
            library_path,
            circuit_path,
            {"token": "browser-secret"},
            source_revision="7" * 40,
        )


def test_adapter_outputs_match_draft_json_artifact_types(tmp_path, monkeypatch) -> None:
    circuit_path = tmp_path / "input.qasm"
    circuit_path.write_text("OPENQASM 2.0;\n", encoding="utf-8")
    circuit = SimpleNamespace(num_qubits=lambda: 1)
    module = SimpleNamespace(
        load_qasm=lambda _: circuit,
        get_clifford_t_counts=lambda *_args, **_kwargs: {"t": 2},
    )
    monkeypatch.setattr(project_adapters.importlib, "import_module", lambda _: module)
    counts = project_adapters.count_nwqec_clifford_t(circuit_path, {})

    artifact_type = load_document(
        ROOT / "artifact-types" / "clifford-t-counts-v1.yaml"
    )
    Draft202012Validator(artifact_type["spec"]["json_schema"]).validate(counts)


@pytest.mark.parametrize(
    ("function", "parameters", "message"),
    [
        (
            project_adapters.build_ftprimitivebench_memory,
            {"measurement_basis": "Y"},
            "measurement_basis must be X or Z",
        ),
        (
            lambda parameters: project_adapters.estimate_lightstim_logical_error(
                "circuit", parameters
            ),
            {"decoder": "mwpf"},
            "allows pymatching only",
        ),
    ],
)
def test_project_adapters_reject_out_of_contract_parameters(
    function, parameters, message
) -> None:
    with pytest.raises(ProjectAdapterError, match=message):
        function(parameters)
