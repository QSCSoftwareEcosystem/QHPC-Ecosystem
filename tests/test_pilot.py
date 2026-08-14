from __future__ import annotations

import copy
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from qhpc_ecosystem import cli
from qhpc_ecosystem.contract import ContractError, load_document, validate_contract_data
from qhpc_ecosystem.engine import TaskRequest
from qhpc_ecosystem.pilot import PilotStore, PilotUnavailable


ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "infrastructure/pilot-profiles/doe-short-interactive.yaml"


def _active_profile() -> dict:
    profile = copy.deepcopy(load_document(PROFILE))
    profile["metadata"]["status"] = "active"
    profile["metadata"]["evidence"] = ["docs/evidence/simulated-pilot.md"]
    profile["spec"]["scheduler"]["account"] = "qsc"
    return profile


def _request(tmp_path: Path, *, attempt: str = "attempt-one") -> TaskRequest:
    digest = "sha256:" + "0" * 64
    return TaskRequest(
        run_id="run-one",
        node_id="transpile",
        capability_id="qasmtrans-transpiler",
        capability_version="0.1.0",
        operation_id="transpile",
        runtime_reference="/images/qasmtrans.sif",
        runtime_digest=digest,
        parameters={"mode": "ibmq", "backend": "ibmq_toronto"},
        inputs={},
        output_types={"circuit": "qhpc.transpiled-circuit@1"},
        work_directory=tmp_path / attempt,
        project="compilation-tools",
        attempt_id=attempt,
        execution_target="doe-slurm-apptainer",
        execution_class="interactive-hpc-pilot",
        runtime_type="apptainer",
        resources={
            "cpu": 1,
            "memory_mb": 1024,
            "gpu": 0,
            "walltime_seconds": 60,
        },
    )


def test_pilot_store_closes_database_connections_after_each_operation(
    tmp_path: Path,
) -> None:
    store = PilotStore(tmp_path / "pilots.sqlite")

    with store._connect() as connection:
        assert connection.execute("SELECT 1").fetchone()[0] == 1

    with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
        connection.execute("SELECT 1")


def test_active_pilot_profile_requires_evidence_and_account() -> None:
    profile = load_document(PROFILE)
    validate_contract_data("pilot-profile", profile)
    profile["metadata"]["status"] = "active"

    with pytest.raises(ContractError) as error:
        validate_contract_data("pilot-profile", profile)

    assert "metadata/evidence" in str(error.value)
    assert "scheduler/account" in str(error.value)


def test_pilot_capacity_health_drain_and_batch_fallback(tmp_path: Path) -> None:
    current = [datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)]
    store = PilotStore(tmp_path / "pilots.sqlite", clock=lambda: current[0])
    profile = _active_profile()
    pilot = store.request_allocation(profile, created_by="test-user")
    assert pilot["state"] == "requested"
    store.assign_scheduler_handle(pilot["id"], "51001")
    ready = store.mark_ready(pilot["id"])
    assert ready["state"] == "ready"

    reserved = store.reserve(profile, _request(tmp_path))
    assert reserved.execution_class == "interactive-hpc-pilot"
    assert reserved.pilot_id == pilot["id"]
    assert store.get(pilot["id"])["reserved"] == 1

    fallback = store.reserve(profile, _request(tmp_path, attempt="attempt-two"))
    assert fallback.execution_class == "batch-hpc"
    assert fallback.reason == "no-ready-capacity"
    with pytest.raises(PilotUnavailable, match="no-ready-capacity"):
        store.reserve(
            profile,
            _request(tmp_path, attempt="attempt-required"),
            require_pilot=True,
        )

    store.release(reserved.reservation_id)
    assert store.get(pilot["id"])["reserved"] == 0
    current[0] += timedelta(seconds=61)
    reconciled = store.reconcile(profile)[0]
    assert reconciled["state"] == "termination-requested"
    terminated = store.mark_terminated(pilot["id"])
    assert terminated["state"] == "terminated"
    assert [event["event_type"] for event in store.events(pilot["id"])] == [
        "pilot.requested",
        "pilot.submitted",
        "pilot.ready",
        "pilot.capacity-reserved",
        "pilot.capacity-released",
        "pilot.draining",
        "pilot.termination-requested",
        "pilot.terminated",
    ]


def test_ineligible_pilot_request_falls_back_without_consuming_capacity(
    tmp_path: Path,
) -> None:
    store = PilotStore(tmp_path / "pilots.sqlite")
    profile = _active_profile()
    pilot = store.request_allocation(profile, created_by="test-user")
    store.assign_scheduler_handle(pilot["id"], "51002")
    store.mark_ready(pilot["id"])
    request = _request(tmp_path)
    request = TaskRequest(
        **{
            **request.__dict__,
            "resources": {**request.resources, "walltime_seconds": 121},
        }
    )

    decision = store.reserve(profile, request)

    assert decision.execution_class == "batch-hpc"
    assert decision.reason == "walltime_seconds-exceeds-pilot-limit"
    assert store.get(pilot["id"])["reserved"] == 0


def test_pilot_cli_lists_empty_control_store(tmp_path: Path, capsys) -> None:
    assert (
        cli.main(
            [
                "pilot",
                "list",
                "--database",
                str(tmp_path / "pilots.sqlite"),
            ]
        )
        == 0
    )
    assert capsys.readouterr().out.strip() == "[]"
