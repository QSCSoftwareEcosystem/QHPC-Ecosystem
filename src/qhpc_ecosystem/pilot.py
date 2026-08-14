"""Durable warm-pilot allocation, capacity, and fallback policy."""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterator

from .contract import document_digest, validate_contract_data
from .engine import TaskRequest


class PilotUnavailable(RuntimeError):
    """Warm capacity is required but no authorized pilot can accept the task."""


@dataclass(frozen=True)
class PilotDecision:
    execution_class: str
    reason: str
    pilot_id: str | None = None
    reservation_id: str | None = None


Clock = Callable[[], datetime]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _timestamp(value: datetime) -> str:
    checked = value.astimezone(timezone.utc)
    return checked.isoformat().replace("+00:00", "Z")


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


class PilotStore:
    """SQLite pilot control state shared by dispatch and allocation services."""

    def __init__(self, database: str | Path, *, clock: Clock = _utc_now) -> None:
        self.database = Path(database).expanduser().resolve()
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self.clock = clock
        self._initialize()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode = WAL;
                CREATE TABLE IF NOT EXISTS pilot_allocations (
                    id TEXT PRIMARY KEY,
                    profile_id TEXT NOT NULL,
                    profile_version TEXT NOT NULL,
                    profile_digest TEXT NOT NULL,
                    execution_target TEXT NOT NULL,
                    state TEXT NOT NULL,
                    scheduler_handle TEXT,
                    capacity INTEGER NOT NULL,
                    reserved INTEGER NOT NULL DEFAULT 0,
                    requested_at TEXT NOT NULL,
                    ready_at TEXT,
                    expires_at TEXT NOT NULL,
                    last_heartbeat_at TEXT,
                    last_activity_at TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}'
                );
                CREATE TABLE IF NOT EXISTS pilot_reservations (
                    id TEXT PRIMARY KEY,
                    pilot_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    attempt_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    released_at TEXT,
                    FOREIGN KEY (pilot_id) REFERENCES pilot_allocations(id)
                );
                CREATE UNIQUE INDEX IF NOT EXISTS pilot_active_attempt_index
                  ON pilot_reservations(attempt_id)
                  WHERE state='active';
                CREATE TABLE IF NOT EXISTS pilot_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    id TEXT NOT NULL UNIQUE,
                    pilot_id TEXT NOT NULL,
                    reservation_id TEXT,
                    event_type TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    details TEXT NOT NULL DEFAULT '{}',
                    FOREIGN KEY (pilot_id) REFERENCES pilot_allocations(id),
                    FOREIGN KEY (reservation_id) REFERENCES pilot_reservations(id)
                );
                CREATE INDEX IF NOT EXISTS pilot_ready_index
                  ON pilot_allocations(
                    profile_id, execution_target, state, reserved, expires_at
                  );
                """
            )

    def _event(
        self,
        connection: sqlite3.Connection,
        *,
        pilot_id: str,
        event_type: str,
        reservation_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        now = _timestamp(self.clock())
        connection.execute(
            """
            INSERT INTO pilot_events
              (id, pilot_id, reservation_id, event_type, occurred_at,
               recorded_at, details)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "pilot-event-" + uuid.uuid4().hex,
                pilot_id,
                reservation_id,
                event_type,
                now,
                now,
                _json(details or {}),
            ),
        )

    @staticmethod
    def _active_profile(profile: dict[str, Any]) -> None:
        validate_contract_data("pilot-profile", profile)
        if profile["metadata"]["status"] != "active":
            raise PilotUnavailable("pilot profile is not active")

    def request_allocation(
        self,
        profile: dict[str, Any],
        *,
        created_by: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._active_profile(profile)
        now = self.clock()
        profile_metadata = profile["metadata"]
        allocation = profile["spec"]["allocation"]
        pilot_id = "pilot-" + uuid.uuid4().hex
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO pilot_allocations
                  (id, profile_id, profile_version, profile_digest,
                   execution_target, state, capacity, requested_at,
                   expires_at, last_activity_at, created_by, metadata)
                VALUES (?, ?, ?, ?, ?, 'requested', ?, ?, ?, ?, ?, ?)
                """,
                (
                    pilot_id,
                    profile_metadata["id"],
                    profile_metadata["version"],
                    document_digest(profile),
                    profile_metadata["execution_target"],
                    allocation["capacity"],
                    _timestamp(now),
                    _timestamp(
                        now + timedelta(seconds=allocation["max_lifetime_seconds"])
                    ),
                    _timestamp(now),
                    created_by,
                    _json(metadata or {}),
                ),
            )
            self._event(
                connection,
                pilot_id=pilot_id,
                event_type="pilot.requested",
                details={
                    "profile_id": profile_metadata["id"],
                    "capacity": allocation["capacity"],
                },
            )
        return self.get(pilot_id)

    def assign_scheduler_handle(self, pilot_id: str, handle: str) -> dict[str, Any]:
        if not re.fullmatch(r"[0-9]+(?:_[0-9]+)?", handle):
            raise ValueError("invalid pilot scheduler handle")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            pilot = self._get(connection, pilot_id)
            if pilot["state"] not in {"requested", "starting"}:
                raise RuntimeError(f"pilot cannot be submitted from {pilot['state']}")
            connection.execute(
                """
                UPDATE pilot_allocations
                SET state='starting', scheduler_handle=?
                WHERE id=?
                """,
                (handle, pilot_id),
            )
            self._event(
                connection,
                pilot_id=pilot_id,
                event_type="pilot.submitted",
                details={"scheduler_handle": handle},
            )
        return self.get(pilot_id)

    def mark_ready(self, pilot_id: str) -> dict[str, Any]:
        now = _timestamp(self.clock())
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            pilot = self._get(connection, pilot_id)
            if pilot["state"] != "starting" or not pilot["scheduler_handle"]:
                raise RuntimeError("only a submitted pilot can become ready")
            connection.execute(
                """
                UPDATE pilot_allocations
                SET state='ready', ready_at=?, last_heartbeat_at=?,
                    last_activity_at=?
                WHERE id=?
                """,
                (now, now, now, pilot_id),
            )
            self._event(connection, pilot_id=pilot_id, event_type="pilot.ready")
        return self.get(pilot_id)

    def heartbeat(self, pilot_id: str) -> dict[str, Any]:
        now = _timestamp(self.clock())
        with self._connect() as connection:
            pilot = self._get(connection, pilot_id)
            if pilot["state"] not in {"ready", "draining"}:
                raise RuntimeError(f"pilot cannot heartbeat while {pilot['state']}")
            connection.execute(
                """
                UPDATE pilot_allocations SET last_heartbeat_at=? WHERE id=?
                """,
                (now, pilot_id),
            )
        return self.get(pilot_id)

    @staticmethod
    def _operation(request: TaskRequest) -> str:
        return (
            f"{request.capability_id}@{request.capability_version}/"
            f"{request.operation_id}"
        )

    @staticmethod
    def _eligible(profile: dict[str, Any], request: TaskRequest) -> tuple[bool, str]:
        spec = profile["spec"]
        operation = PilotStore._operation(request)
        if operation not in spec["allowed_operations"]:
            return False, "operation-not-allowlisted"
        if request.runtime_digest not in spec["runtime_digests"]:
            return False, "runtime-not-prewarmed"
        eligibility = spec["eligibility"]
        resource_fields = {
            "cpu": "max_cpu",
            "memory_mb": "max_memory_mb",
            "gpu": "max_gpu",
            "walltime_seconds": "max_walltime_seconds",
        }
        defaults = {
            "cpu": 1,
            "memory_mb": 1024,
            "gpu": 0,
            "walltime_seconds": 600,
        }
        for resource, maximum_field in resource_fields.items():
            value = int(request.resources.get(resource, defaults[resource]))
            if value > eligibility[maximum_field]:
                return False, f"{resource}-exceeds-pilot-limit"
        return True, "eligible"

    def _fallback(
        self,
        profile: dict[str, Any],
        reason: str,
        require_pilot: bool,
    ) -> PilotDecision:
        if require_pilot or profile["spec"]["fallback"] == "reject":
            raise PilotUnavailable(f"warm pilot unavailable: {reason}")
        return PilotDecision("batch-hpc", reason)

    def reserve(
        self,
        profile: dict[str, Any],
        request: TaskRequest,
        *,
        require_pilot: bool = False,
    ) -> PilotDecision:
        self._active_profile(profile)
        if request.execution_target != profile["metadata"]["execution_target"]:
            return self._fallback(profile, "execution-target-mismatch", require_pilot)
        eligible, reason = self._eligible(profile, request)
        if not eligible:
            return self._fallback(profile, reason, require_pilot)
        now = self.clock()
        allocation = profile["spec"]["allocation"]
        latest_usable_expiration = _timestamp(
            now + timedelta(seconds=allocation["drain_before_expiry_seconds"])
        )
        heartbeat_cutoff = _timestamp(
            now - timedelta(seconds=allocation["health_timeout_seconds"])
        )
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._reconcile(connection, profile, now)
            pilot = connection.execute(
                """
                SELECT * FROM pilot_allocations
                WHERE profile_id=? AND profile_version=?
                  AND profile_digest=? AND execution_target=?
                  AND state='ready' AND reserved < capacity
                  AND expires_at > ?
                  AND last_heartbeat_at >= ?
                ORDER BY ready_at, id
                LIMIT 1
                """,
                (
                    profile["metadata"]["id"],
                    profile["metadata"]["version"],
                    document_digest(profile),
                    request.execution_target,
                    latest_usable_expiration,
                    heartbeat_cutoff,
                ),
            ).fetchone()
            if pilot is None:
                return self._fallback(profile, "no-ready-capacity", require_pilot)
            cursor = connection.execute(
                """
                UPDATE pilot_allocations
                SET reserved=reserved+1, last_activity_at=?
                WHERE id=? AND state='ready' AND reserved < capacity
                """,
                (_timestamp(now), pilot["id"]),
            )
            if not cursor.rowcount:
                return self._fallback(profile, "capacity-race", require_pilot)
            reservation_id = "reservation-" + uuid.uuid4().hex
            connection.execute(
                """
                INSERT INTO pilot_reservations
                  (id, pilot_id, run_id, node_id, attempt_id, state, created_at)
                VALUES (?, ?, ?, ?, ?, 'active', ?)
                """,
                (
                    reservation_id,
                    pilot["id"],
                    request.run_id,
                    request.node_id,
                    request.attempt_id,
                    _timestamp(now),
                ),
            )
            self._event(
                connection,
                pilot_id=pilot["id"],
                reservation_id=reservation_id,
                event_type="pilot.capacity-reserved",
                details={"attempt_id": request.attempt_id},
            )
        return PilotDecision(
            "interactive-hpc-pilot",
            "ready-capacity",
            pilot["id"],
            reservation_id,
        )

    def release(self, reservation_id: str) -> dict[str, Any]:
        now = _timestamp(self.clock())
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            reservation = connection.execute(
                "SELECT * FROM pilot_reservations WHERE id=?",
                (reservation_id,),
            ).fetchone()
            if not reservation:
                raise KeyError(f"pilot reservation not found: {reservation_id}")
            if reservation["state"] == "released":
                return self.get(reservation["pilot_id"])
            connection.execute(
                """
                UPDATE pilot_reservations
                SET state='released', released_at=?
                WHERE id=?
                """,
                (now, reservation_id),
            )
            connection.execute(
                """
                UPDATE pilot_allocations
                SET reserved=MAX(0, reserved-1), last_activity_at=?
                WHERE id=?
                """,
                (now, reservation["pilot_id"]),
            )
            self._event(
                connection,
                pilot_id=reservation["pilot_id"],
                reservation_id=reservation_id,
                event_type="pilot.capacity-released",
            )
        return self.get(reservation["pilot_id"])

    def drain(self, pilot_id: str, *, reason: str) -> dict[str, Any]:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._set_draining(connection, self._get(connection, pilot_id), reason)
        return self.get(pilot_id)

    def _set_draining(
        self,
        connection: sqlite3.Connection,
        pilot: sqlite3.Row,
        reason: str,
    ) -> None:
        if pilot["state"] in {"draining", "termination-requested", "terminated"}:
            return
        connection.execute(
            "UPDATE pilot_allocations SET state='draining' WHERE id=?",
            (pilot["id"],),
        )
        self._event(
            connection,
            pilot_id=pilot["id"],
            event_type="pilot.draining",
            details={"reason": reason},
        )

    def _reconcile(
        self,
        connection: sqlite3.Connection,
        profile: dict[str, Any],
        now: datetime,
    ) -> None:
        allocation = profile["spec"]["allocation"]
        pilots = connection.execute(
            """
            SELECT * FROM pilot_allocations
            WHERE profile_id=? AND state IN ('ready','draining')
            """,
            (profile["metadata"]["id"],),
        ).fetchall()
        for pilot in pilots:
            if pilot["state"] == "ready":
                reason = None
                heartbeat = pilot["last_heartbeat_at"]
                if not heartbeat or now - _parse(heartbeat) > timedelta(
                    seconds=allocation["health_timeout_seconds"]
                ):
                    reason = "health-timeout"
                elif _parse(pilot["expires_at"]) - now <= timedelta(
                    seconds=allocation["drain_before_expiry_seconds"]
                ):
                    reason = "lifetime-expiry"
                elif pilot["reserved"] == 0 and now - _parse(
                    pilot["last_activity_at"]
                ) >= timedelta(seconds=allocation["idle_timeout_seconds"]):
                    reason = "idle-timeout"
                if reason:
                    self._set_draining(connection, pilot, reason)
                    pilot = self._get(connection, pilot["id"])
            if pilot["state"] == "draining" and pilot["reserved"] == 0:
                connection.execute(
                    """
                    UPDATE pilot_allocations
                    SET state='termination-requested'
                    WHERE id=?
                    """,
                    (pilot["id"],),
                )
                self._event(
                    connection,
                    pilot_id=pilot["id"],
                    event_type="pilot.termination-requested",
                )

    def reconcile(self, profile: dict[str, Any]) -> list[dict[str, Any]]:
        validate_contract_data("pilot-profile", profile)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._reconcile(connection, profile, self.clock())
        return self.list_allocations(profile_id=profile["metadata"]["id"])

    def mark_terminated(
        self, pilot_id: str, *, reason: str = "scheduler-confirmed"
    ) -> dict[str, Any]:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            pilot = self._get(connection, pilot_id)
            if pilot["reserved"]:
                raise RuntimeError("cannot terminate a pilot with active reservations")
            connection.execute(
                "UPDATE pilot_allocations SET state='terminated' WHERE id=?",
                (pilot_id,),
            )
            self._event(
                connection,
                pilot_id=pilot_id,
                event_type="pilot.terminated",
                details={"reason": reason},
            )
        return self.get(pilot_id)

    @staticmethod
    def _get(connection: sqlite3.Connection, pilot_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM pilot_allocations WHERE id=?", (pilot_id,)
        ).fetchone()
        if not row:
            raise KeyError(f"pilot allocation not found: {pilot_id}")
        return row

    @staticmethod
    def _row(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        result["metadata"] = json.loads(result["metadata"])
        return result

    def get(self, pilot_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = self._get(connection, pilot_id)
        return self._row(row)

    def list_allocations(
        self, *, profile_id: str | None = None
    ) -> list[dict[str, Any]]:
        with self._connect() as connection:
            if profile_id is None:
                rows = connection.execute(
                    "SELECT * FROM pilot_allocations ORDER BY requested_at, id"
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT * FROM pilot_allocations
                    WHERE profile_id=? ORDER BY requested_at, id
                    """,
                    (profile_id,),
                ).fetchall()
        return [self._row(row) for row in rows]

    def events(self, pilot_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            self._get(connection, pilot_id)
            rows = connection.execute(
                """
                SELECT * FROM pilot_events
                WHERE pilot_id=? ORDER BY sequence
                """,
                (pilot_id,),
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["details"] = json.loads(item["details"])
            result.append(item)
        return result
