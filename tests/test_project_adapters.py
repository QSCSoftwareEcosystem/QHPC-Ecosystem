from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from jsonschema import Draft202012Validator

from qhpc_ecosystem.contract import load_document
from qhpc_ecosystem import project_adapters
from qhpc_ecosystem.project_adapters import ProjectAdapterError


ROOT = Path(__file__).resolve().parents[1]


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
