from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Mapping

import pytest
from jsonschema import Draft202012Validator

from qhpc_ecosystem.contract import load_document
from qhpc_ecosystem.engine import TaskRejectedError, TaskRequest
from qhpc_ecosystem.iqm_runner import IQMAdapterError, IQMAsyncRunner


ROOT = Path(__file__).resolve().parents[1]
TOKEN = "worker-only-IQM-token"
SUBMITTED_AT = "2026-09-04T12:00:00Z"
COMPLETED_AT = "2026-09-04T12:01:00Z"


def steane_circuit() -> dict[str, Any]:
    return {
        "name": "logical0",
        "instructions": [
            {
                "name": "measure",
                "locus": [f"QB{index + 1}"],
                "args": {"key": f"mL0_{index}"},
            }
            for index in range(7)
        ],
    }


class MockIQMService:
    def __init__(self) -> None:
        self.tokens: list[str] = []
        self.submissions: list[dict[str, Any]] = []
        self.status_state = "running"
        self.cancellations: list[str] = []
        self.fail_action: str | None = None

    def _observe(self, action: str, token: str) -> None:
        self.tokens.append(token)
        if self.fail_action == action:
            raise RuntimeError(f"provider failure included {token}")

    def submit(
        self,
        circuit: Mapping[str, Any],
        *,
        device_alias: str,
        shots: int,
        token: str,
    ) -> Mapping[str, Any]:
        self._observe("submit", token)
        self.submissions.append(
            {"circuit": dict(circuit), "device_alias": device_alias, "shots": shots}
        )
        layout = [
            {"source": f"QB{index}", "target": f"QB{index + 7}"}
            for index in range(1, 8)
        ]
        return {
            "job_id": "job-mock-001",
            "state": "queued",
            "device": {
                "alias": device_alias,
                "quantum_computer_id": "mock-qpu-20",
                "calibration_id": "cal-2026-09-04T1155Z",
            },
            "submitted_at": SUBMITTED_AT,
            "routed_circuit": dict(circuit),
            "initial_layout": [
                {"source": f"QB{index}", "target": f"QB{index}"}
                for index in range(1, 8)
            ],
            "final_layout": layout,
            "routing_metrics": {
                "total_operation_count": 7,
                "two_qubit_gate_count": 0,
                "move_count": 0,
                "explicit_swap_count": 0,
            },
        }

    def status(self, job_id: str, *, token: str) -> Mapping[str, Any]:
        self._observe("status", token)
        return {"job_id": job_id, "state": self.status_state}

    def result(self, job_id: str, *, token: str) -> Mapping[str, Any]:
        self._observe("result", token)
        return {
            "job_id": job_id,
            "counts": {"0000000": 3, "0000001": 1},
            "bit_order": "qiskit-little-endian",
            "completed_at": COMPLETED_AT,
        }

    def cancel(self, job_id: str, *, token: str) -> None:
        self._observe("cancel", token)
        self.cancellations.append(job_id)


def request(tmp_path: Path, **parameter_changes: Any) -> TaskRequest:
    circuit = tmp_path / "input.json"
    circuit_document = steane_circuit()
    circuit.write_text(json.dumps(circuit_document), encoding="utf-8")
    report = tmp_path / "report.json"
    report.write_text(
        json.dumps(
            {
                "schema": "qhpc.ftqc-iqm-preparation-report.v1",
                "preparation": "steane-logical",
                "compiler_interface": "ftqc_qasm_opt",
                "source_revision": "7" * 40,
                "ecc": {"kind": "steane", "distance": 3},
                "logical_qubits": 1,
                "device_qubits": 7,
                "instruction_count": len(circuit_document["instructions"]),
                "gate_counts": {"measure": 7},
                "loci": [f"QB{index}" for index in range(1, 8)],
                "angle_units": "radians",
                "routing": {
                    "status": "not-performed",
                    "requirement": "required-before-hardware",
                    "reason": "mock fixture",
                },
                "submission": {
                    "status": "not-submitted",
                    "execution_class": "quantum-backend",
                },
                "claim_boundary": "mock fixture",
            }
        ),
        encoding="utf-8",
    )
    parameters = {
        "device_alias": "mock",
        "shots": 4,
        "credential_reference": "secret://env/IQM_TOKEN",
        "max_wait_seconds": 300,
    }
    parameters.update(parameter_changes)
    return TaskRequest(
        run_id="run-iqm-test",
        node_id="execute",
        capability_id="ftqc-compiler",
        capability_version="0.3.0",
        operation_id="route-submit-collect",
        runtime_reference="qhpc-runtime://wheels/qhpc_iqm_adapter-0.1.0.whl",
        runtime_digest="sha256:" + "a" * 64,
        parameters=parameters,
        inputs={
            "circuit": {"uri": circuit.resolve().as_uri()},
            "report": {"uri": report.resolve().as_uri()},
        },
        output_types={
            "layout": "qhpc.iqm-routed-layout@1",
            "receipt": "qhpc.iqm-job-receipt@1",
            "counts": "qhpc.iqm-raw-counts@1",
            "logical_result": "qhpc.ftqc-logical-result@1",
        },
        work_directory=tmp_path / "work",
        execution_target="local-development",
        execution_class="quantum-backend",
    )


def secret_resolver(reference: str) -> str:
    assert reference == "secret://env/IQM_TOKEN"
    return TOKEN


def submitted_clock() -> datetime:
    return datetime.fromisoformat(SUBMITTED_AT.replace("Z", "+00:00"))


def artifact_document(result, port: str) -> dict[str, Any]:
    uri = result.outputs[port].uri
    path = Path(uri.removeprefix("file://"))
    return json.loads(path.read_text(encoding="utf-8"))


def test_mock_iqm_submit_poll_collect_is_typed_and_secret_free(tmp_path: Path) -> None:
    service = MockIQMService()
    first = IQMAsyncRunner(
        service, secret_resolver=secret_resolver, clock=submitted_clock
    )
    task = request(tmp_path)

    submission = first.submit(task)
    assert submission.handle == "job-mock-001"
    assert submission.state == "queued"
    assert submission.metadata == {
        "provider": "iqm",
        "device_alias": "mock",
        "quantum_computer_id": "mock-qpu-20",
        "calibration_id": "cal-2026-09-04T1155Z",
        "shots": 4,
    }

    recovered = IQMAsyncRunner(
        service, secret_resolver=secret_resolver, clock=submitted_clock
    )
    assert recovered.poll(task, submission.handle).state == "running"
    service.status_state = "succeeded"
    assert recovered.poll(task, submission.handle).state == "succeeded"
    result = recovered.collect(task, submission.handle)

    assert set(result.outputs) == {"layout", "receipt", "counts", "logical_result"}
    assert artifact_document(result, "receipt")["routed_layout_checksum"] == (
        result.outputs["layout"].checksum
    )
    assert artifact_document(result, "counts")["counts"] == {
        "0000000": 3,
        "0000001": 1,
    }
    logical = artifact_document(result, "logical_result")
    assert logical["raw_logical_counts"] == {"0": 3, "1": 1}
    assert logical["corrected_logical_counts"] == {"0": 4, "1": 0}

    schemas = {
        "layout": "iqm-routed-layout-v1.yaml",
        "receipt": "iqm-job-receipt-v1.yaml",
        "counts": "iqm-raw-counts-v1.yaml",
        "logical_result": "ftqc-logical-result-v1.yaml",
    }
    for port, filename in schemas.items():
        artifact_type = load_document(ROOT / "artifact-types" / filename)
        Draft202012Validator(artifact_type["spec"]["json_schema"]).validate(
            artifact_document(result, port)
        )

    assert service.tokens == [TOKEN, TOKEN, TOKEN, TOKEN]
    assert TOKEN not in json.dumps(submission.metadata)
    assert TOKEN not in result.log
    assert TOKEN not in json.dumps(result.metadata)
    assert all(
        TOKEN.encode() not in path.read_bytes()
        for path in task.work_directory.iterdir()
    )


def test_mock_iqm_reports_failed_status_and_propagates_cancel(tmp_path: Path) -> None:
    service = MockIQMService()
    runner = IQMAsyncRunner(
        service, secret_resolver=secret_resolver, clock=submitted_clock
    )
    task = request(tmp_path)
    submission = runner.submit(task)

    service.status_state = "failed"
    assert runner.poll(task, submission.handle).state == "failed"
    runner.cancel(task, submission.handle)
    assert service.cancellations == [submission.handle]


def test_mock_iqm_timeout_cancels_remote_job(tmp_path: Path) -> None:
    service = MockIQMService()
    now = datetime.fromisoformat(SUBMITTED_AT.replace("Z", "+00:00")) + timedelta(
        seconds=31
    )
    runner = IQMAsyncRunner(
        service,
        secret_resolver=secret_resolver,
        clock=lambda: now,
    )
    task = request(tmp_path, max_wait_seconds=30)
    submission = runner.submit(task)

    with pytest.raises(IQMAdapterError, match="exceeded the configured wait limit"):
        runner.poll(task, submission.handle)
    assert service.cancellations == [submission.handle]


def test_iqm_worker_rejects_plaintext_secret_and_unknown_token_field(
    tmp_path: Path,
) -> None:
    service = MockIQMService()
    runner = IQMAsyncRunner(service, secret_resolver=secret_resolver)

    with pytest.raises(TaskRejectedError, match="secret://"):
        runner.submit(request(tmp_path, credential_reference=TOKEN))
    with pytest.raises(TaskRejectedError, match="unsupported IQM parameters: token"):
        runner.submit(request(tmp_path, token=TOKEN))
    assert service.tokens == []


def test_iqm_worker_derives_preparation_from_ftqc_report(tmp_path: Path) -> None:
    service = MockIQMService()
    runner = IQMAsyncRunner(service, secret_resolver=secret_resolver)
    task = request(tmp_path)
    report_path = Path(task.inputs["report"]["uri"].removeprefix("file://"))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["preparation"] = "device"
    report["logical_qubits"] = None
    report_path.write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(TaskRejectedError, match="does not match its reported mode"):
        runner.submit(task)
    assert service.tokens == []


def test_iqm_provider_exception_cannot_leak_resolved_token(tmp_path: Path) -> None:
    service = MockIQMService()
    service.fail_action = "submit"
    runner = IQMAsyncRunner(service, secret_resolver=secret_resolver)

    with pytest.raises(IQMAdapterError) as error:
        runner.submit(request(tmp_path))
    assert str(error.value) == "IQM backend submission failed"
    assert TOKEN not in str(error.value)
