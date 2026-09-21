from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import pytest

from qhpc_ecosystem.iqm_provider import QiskitIQMBackendClient
from qhpc_ecosystem import iqm_worker


TOKEN = "worker-only-provider-token"


class FakeArchitecture:
    calibration_set_id = "calibration-2026-09-10"
    quantum_computer_name = "iqm-test-qpu"


class FakeJob:
    def __init__(self) -> None:
        self.cancelled = False

    def job_id(self) -> str:
        return "iqm-job-001"

    def status(self) -> str:
        return "CANCELLED" if self.cancelled else "QUEUED"

    def result(self):
        class Result:
            date = "2026-09-10T12:01:00Z"

            @staticmethod
            def get_counts() -> dict[str, int]:
                return {"0000000": 3, "0000001": 1}

        return Result()

    def cancel(self) -> None:
        self.cancelled = True


class FakeBackend:
    architecture = FakeArchitecture()
    name = "iqm-test-qpu"

    def __init__(self) -> None:
        self.job = FakeJob()

    @staticmethod
    def index_to_qubit_name(index: int) -> str:
        return f"QB{index + 11}"

    @staticmethod
    def serialize_circuit(circuit: Any) -> dict[str, Any]:
        return {
            "name": circuit.name,
            "instructions": [
                {
                    "name": "measure",
                    "locus": [f"QB{index + 11}"],
                    "args": {"key": f"m{index}"},
                }
                for index in range(7)
            ],
        }

    def run(self, circuit: Any, *, shots: int) -> FakeJob:
        assert circuit.num_qubits == 7
        assert shots == 4
        return self.job

    def retrieve_job(self, job_id: str) -> FakeJob:
        assert job_id == "iqm-job-001"
        return self.job


class FakeProvider:
    backend = FakeBackend()

    def __init__(self, _endpoint: str, *, quantum_computer: str, token: str) -> None:
        assert quantum_computer == "approved-qpu"
        assert token == TOKEN

    def get_backend(self) -> FakeBackend:
        return self.backend


def steane_circuit() -> dict[str, Any]:
    return {
        "name": "logical0",
        "instructions": [
            {"name": "measure", "locus": [f"QB{index + 1}"], "args": {"key": f"m{index}"}}
            for index in range(7)
        ],
    }


def test_qiskit_iqm_client_routes_and_recovers_a_job_without_exposing_token() -> None:
    pytest.importorskip("qiskit")
    client = QiskitIQMBackendClient(
        "https://iqm.example.test/cocos",
        "approved-qpu",
        provider_factory=FakeProvider,
        transpiler=lambda circuit, _backend: circuit,
        clock=lambda: datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc),
    )

    submission = client.submit(
        steane_circuit(), device_alias="approved-qpu", shots=4, token=TOKEN
    )
    assert submission["job_id"] == "iqm-job-001"
    assert submission["device"] == {
        "alias": "approved-qpu",
        "quantum_computer_id": "iqm-test-qpu",
        "calibration_id": "calibration-2026-09-10",
    }
    assert submission["final_layout"][0] == {"source": "QB1", "target": "QB11"}
    assert submission["routing_metrics"]["total_operation_count"] == 7
    assert TOKEN not in json.dumps(submission)

    assert client.status("iqm-job-001", token=TOKEN) == {
        "job_id": "iqm-job-001",
        "state": "queued",
    }
    assert client.result("iqm-job-001", token=TOKEN) == {
        "job_id": "iqm-job-001",
        "counts": {"0000000": 3, "0000001": 1},
        "bit_order": "qiskit-little-endian",
        "completed_at": "2026-09-10T12:01:00Z",
    }
    client.cancel("iqm-job-001", token=TOKEN)
    assert client.status("iqm-job-001", token=TOKEN)["state"] == "canceled"


def test_named_iqm_worker_entrypoint_preserves_global_catalog_option(monkeypatch) -> None:
    observed: list[str] = []

    def fake_main(arguments: list[str]) -> int:
        observed.extend(arguments)
        return 17

    monkeypatch.setattr(iqm_worker, "cli_main", fake_main)
    assert iqm_worker.main(["--catalog", "ecosystem.yaml", "--once"]) == 17
    assert observed == ["--catalog", "ecosystem.yaml", "iqm-worker", "--once"]
