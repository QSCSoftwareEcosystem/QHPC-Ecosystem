"""Persistent workflow orchestration and controlled local runner protocol."""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable, Protocol

from .contract import ContractError, document_digest
from .registry import registry_digest
from .workflow import resolve_workflow, topological_nodes


TERMINAL_STATES = {"succeeded", "failed", "canceled"}
ARTIFACT_TYPE = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*@[1-9][0-9]*$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class ArtifactResult:
    artifact_type: str
    uri: str
    checksum: str
    size_bytes: int

    @classmethod
    def from_path(cls, artifact_type: str, path: str | Path) -> ArtifactResult:
        resolved = Path(path).resolve()
        content = resolved.read_bytes()
        return cls(
            artifact_type=artifact_type,
            uri=resolved.as_uri(),
            checksum="sha256:" + sha256(content).hexdigest(),
            size_bytes=len(content),
        )


@dataclass(frozen=True)
class TaskRequest:
    run_id: str
    node_id: str
    capability_id: str
    capability_version: str
    operation_id: str
    runtime_reference: str
    runtime_digest: str
    parameters: dict[str, Any]
    inputs: dict[str, dict[str, Any]]
    output_types: dict[str, str]
    work_directory: Path


@dataclass(frozen=True)
class TaskResult:
    outputs: dict[str, ArtifactResult]
    log: str = ""


class Runner(Protocol):
    def execute(self, request: TaskRequest) -> TaskResult: ...


class TaskRejectedError(RuntimeError):
    """A worker policy rejected a task before scientific execution."""


class FunctionRunner:
    """Execute only explicitly registered Python callables, never arbitrary shell."""

    def __init__(self) -> None:
        self._operations: dict[
            tuple[str, str], Callable[[TaskRequest], TaskResult]
        ] = {}

    def register(
        self,
        capability_id: str,
        operation_id: str,
        function: Callable[[TaskRequest], TaskResult],
    ) -> None:
        self._operations[(capability_id, operation_id)] = function

    def execute(self, request: TaskRequest) -> TaskResult:
        key = (request.capability_id, request.operation_id)
        if key not in self._operations:
            raise TaskRejectedError(
                f"operation is not allowlisted by local runner: {key[0]}/{key[1]}"
            )
        return self._operations[key](request)


class WorkflowEngine:
    """SQLite-backed workflow engine with leases and idempotent task completion."""

    def __init__(self, database: str | Path, artifact_root: str | Path) -> None:
        self.database = Path(database).expanduser().resolve()
        self.artifact_root = Path(artifact_root).expanduser().resolve()
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self.artifact_root.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode = WAL;
                CREATE TABLE IF NOT EXISTS workflow_versions (
                    workflow_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    digest TEXT NOT NULL,
                    definition TEXT NOT NULL,
                    resolution TEXT NOT NULL,
                    registry_digest TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    PRIMARY KEY (workflow_id, version)
                );
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY,
                    workflow_id TEXT NOT NULL,
                    workflow_version TEXT NOT NULL,
                    workflow_digest TEXT NOT NULL,
                    execution_target TEXT NOT NULL,
                    state TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    inputs TEXT NOT NULL,
                    outputs TEXT NOT NULL DEFAULT '{}',
                    FOREIGN KEY (workflow_id, workflow_version)
                      REFERENCES workflow_versions(workflow_id, version)
                );
                CREATE TABLE IF NOT EXISTS tasks (
                    run_id TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    state TEXT NOT NULL,
                    attempt INTEGER NOT NULL DEFAULT 0,
                    operation TEXT NOT NULL,
                    runtime_digest TEXT NOT NULL,
                    lease_token TEXT,
                    lease_expires_at TEXT,
                    started_at TEXT,
                    finished_at TEXT,
                    error TEXT,
                    outputs TEXT NOT NULL DEFAULT '{}',
                    log TEXT NOT NULL DEFAULT '',
                    PRIMARY KEY (run_id, node_id),
                    FOREIGN KEY (run_id) REFERENCES runs(id)
                );
                CREATE TABLE IF NOT EXISTS artifacts (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    task_id TEXT,
                    port TEXT NOT NULL,
                    artifact_type TEXT NOT NULL,
                    uri TEXT NOT NULL,
                    checksum TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE (run_id, task_id, port, checksum),
                    FOREIGN KEY (run_id) REFERENCES runs(id)
                );
                CREATE TABLE IF NOT EXISTS input_artifacts (
                    id TEXT PRIMARY KEY,
                    artifact_type TEXT NOT NULL,
                    uri TEXT NOT NULL,
                    checksum TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    name TEXT NOT NULL,
                    labels TEXT NOT NULL DEFAULT '{}'
                );
                CREATE INDEX IF NOT EXISTS task_state_index
                  ON tasks(state, run_id, sequence);
                """
            )

    def register_input_artifact(
        self,
        *,
        artifact_type: str,
        content: bytes,
        name: str,
        created_by: str,
        labels: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        if not ARTIFACT_TYPE.fullmatch(artifact_type):
            raise ContractError(f"invalid artifact type: {artifact_type}")
        safe_name = Path(name).name
        if not safe_name or safe_name in {".", ".."}:
            raise ContractError("artifact name must be a file name")
        if len(content) > 10_000_000:
            raise ContractError("input artifact exceeds 10 MB local limit")
        artifact_id = "artifact-" + uuid.uuid4().hex
        destination = self.artifact_root / "inputs" / artifact_id / safe_name
        destination.parent.mkdir(parents=True, exist_ok=False)
        destination.write_bytes(content)
        checksum = "sha256:" + sha256(content).hexdigest()
        created_at = _now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO input_artifacts
                  (id, artifact_type, uri, checksum, size_bytes, created_at,
                   created_by, name, labels)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact_id,
                    artifact_type,
                    destination.resolve().as_uri(),
                    checksum,
                    len(content),
                    created_at,
                    created_by,
                    safe_name,
                    _json(labels or {}),
                ),
            )
        return self.get_artifact(artifact_id)

    def register_input_file(
        self,
        path: str | Path,
        *,
        artifact_type: str,
        created_by: str,
        labels: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        source = Path(path).expanduser().resolve()
        if not source.is_file():
            raise FileNotFoundError(f"artifact file not found: {source}")
        return self.register_input_artifact(
            artifact_type=artifact_type,
            content=source.read_bytes(),
            name=source.name,
            created_by=created_by,
            labels=labels,
        )

    def get_artifact(self, artifact_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT *, 'input' AS provenance FROM input_artifacts WHERE id=?",
                (artifact_id,),
            ).fetchone()
            if row:
                result = dict(row)
                result["labels"] = json.loads(result["labels"])
                return result
            row = connection.execute(
                "SELECT *, 'task-output' AS provenance FROM artifacts WHERE id=?",
                (artifact_id,),
            ).fetchone()
        if not row:
            raise KeyError(f"artifact not found: {artifact_id}")
        return dict(row)

    def list_artifacts(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            inputs = connection.execute(
                "SELECT id FROM input_artifacts ORDER BY created_at DESC"
            ).fetchall()
            outputs = connection.execute(
                "SELECT id FROM artifacts ORDER BY created_at DESC"
            ).fetchall()
        return [self.get_artifact(row["id"]) for row in (*inputs, *outputs)]

    def register_workflow(
        self,
        workflow: dict[str, Any],
        registry: dict[str, Any],
        *,
        created_by: str,
    ) -> dict[str, Any]:
        resolved = resolve_workflow(workflow, registry)
        metadata = workflow["metadata"]
        resolution = {
            node_id: {
                "capability_id": item.capability_id,
                "capability_version": item.capability_version,
                "project": item.project,
                "operation": item.operation,
            }
            for node_id, item in resolved.operations.items()
        }
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT digest FROM workflow_versions WHERE workflow_id=? AND version=?",
                (metadata["id"], metadata["version"]),
            ).fetchone()
            if existing and existing["digest"] != resolved.digest:
                raise ContractError(
                    "workflow version is immutable; publish a new semantic version"
                )
            connection.execute(
                """
                INSERT OR IGNORE INTO workflow_versions
                  (workflow_id, version, digest, definition, resolution,
                   registry_digest, created_at, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    metadata["id"],
                    metadata["version"],
                    resolved.digest,
                    _json(workflow),
                    _json(resolution),
                    registry_digest(registry),
                    _now(),
                    created_by,
                ),
            )
        return self.get_workflow(metadata["id"], metadata["version"])

    def list_workflows(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM workflow_versions ORDER BY workflow_id, version"
            ).fetchall()
        return [self._workflow_row(row) for row in rows]

    def get_workflow(self, workflow_id: str, version: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM workflow_versions WHERE workflow_id=? AND version=?",
                (workflow_id, version),
            ).fetchone()
        if not row:
            raise KeyError(f"workflow not found: {workflow_id}@{version}")
        return self._workflow_row(row)

    @staticmethod
    def _workflow_row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["workflow_id"],
            "version": row["version"],
            "digest": row["digest"],
            "registry_digest": row["registry_digest"],
            "created_at": row["created_at"],
            "created_by": row["created_by"],
            "definition": json.loads(row["definition"]),
        }

    def submit_run(
        self,
        workflow_id: str,
        version: str,
        *,
        registry: dict[str, Any] | None = None,
        inputs: dict[str, str],
        execution_target: str,
        created_by: str,
    ) -> dict[str, Any]:
        with self._connect() as connection:
            workflow_row = connection.execute(
                "SELECT * FROM workflow_versions WHERE workflow_id=? AND version=?",
                (workflow_id, version),
            ).fetchone()
            if not workflow_row:
                raise KeyError(f"workflow not found: {workflow_id}@{version}")
            definition = json.loads(workflow_row["definition"])
            if registry is not None:
                resolve_workflow(definition, registry)
            declared_inputs = definition["spec"]["inputs"]
            unknown = sorted(set(inputs) - set(declared_inputs))
            if unknown:
                raise ContractError("unknown workflow inputs: " + ", ".join(unknown))
            missing = sorted(
                name
                for name, value in declared_inputs.items()
                if value.get("required", True) and name not in inputs
            )
            if missing:
                raise ContractError("missing workflow inputs: " + ", ".join(missing))
            for name, artifact_id in inputs.items():
                artifact = self.get_artifact(artifact_id)
                expected = declared_inputs[name]["artifact_type"]
                if artifact["artifact_type"] != expected:
                    raise ContractError(
                        f"workflow input {name} requires {expected}; "
                        f"artifact {artifact_id} is {artifact['artifact_type']}"
                    )

            run_id = "run-" + uuid.uuid4().hex
            now = _now()
            connection.execute(
                """
                INSERT INTO runs
                  (id, workflow_id, workflow_version, workflow_digest,
                   execution_target, state, created_at, created_by, inputs, outputs)
                VALUES (?, ?, ?, ?, ?, 'queued', ?, ?, ?, '{}')
                """,
                (
                    run_id,
                    workflow_id,
                    version,
                    workflow_row["digest"],
                    execution_target,
                    now,
                    created_by,
                    _json(inputs),
                ),
            )
            resolution = json.loads(workflow_row["resolution"])
            nodes = {node["id"]: node for node in definition["spec"]["nodes"]}
            for sequence, node_id in enumerate(topological_nodes(definition)):
                item = resolution[node_id]
                operation = item["operation"]
                target = nodes[node_id].get("execution_target", execution_target)
                if target not in operation["execution_targets"]:
                    raise ContractError(
                        f"node {node_id} does not support execution target {target}"
                    )
                connection.execute(
                    """
                    INSERT INTO tasks
                      (run_id, node_id, sequence, state, operation, runtime_digest)
                    VALUES (?, ?, ?, 'pending', ?, ?)
                    """,
                    (
                        run_id,
                        node_id,
                        sequence,
                        _json(
                            {
                                "capability": item["capability_id"],
                                "version": item["capability_version"],
                                "operation": operation["id"],
                                "project": item["project"],
                                "definition": operation,
                                "parameters": nodes[node_id]["parameters"],
                            }
                        ),
                        operation["runtime"]["digest"],
                    ),
                )
        return self.get_run(run_id)

    def list_runs(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id FROM runs ORDER BY created_at DESC"
            ).fetchall()
        return [self.get_run(row["id"]) for row in rows]

    def get_run(self, run_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            run = connection.execute(
                "SELECT * FROM runs WHERE id=?", (run_id,)
            ).fetchone()
            if not run:
                raise KeyError(f"run not found: {run_id}")
            tasks = connection.execute(
                "SELECT * FROM tasks WHERE run_id=? ORDER BY sequence", (run_id,)
            ).fetchall()
        result = dict(run)
        result["inputs"] = json.loads(result["inputs"])
        result["outputs"] = json.loads(result["outputs"])
        result["tasks"] = [self._task_row(task) for task in tasks]
        return result

    @staticmethod
    def _task_row(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        result["operation"] = json.loads(result["operation"])
        result["outputs"] = json.loads(result["outputs"])
        result["error"] = json.loads(result["error"]) if result["error"] else None
        return result

    def _reset_expired_leases(self, connection: sqlite3.Connection) -> None:
        now = _now()
        connection.execute(
            """
            UPDATE tasks SET state='pending', lease_token=NULL, lease_expires_at=NULL,
              error=json_object('code','lease-expired','message','task lease expired',
                                'retryable',json('true'))
            WHERE state='running' AND lease_expires_at < ?
            """,
            (now,),
        )

    @staticmethod
    def _parents(definition: dict[str, Any], node_id: str) -> set[str]:
        return {
            edge["from"]["node"]
            for edge in definition["spec"]["edges"]
            if edge["to"]["node"] == node_id
        }

    def _claim_ready_task(self, lease_seconds: int) -> tuple[str, str, str] | None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._reset_expired_leases(connection)
            candidates = connection.execute(
                """
                SELECT t.run_id, t.node_id
                FROM tasks t JOIN runs r ON r.id=t.run_id
                WHERE t.state='pending' AND r.state IN ('queued','running')
                ORDER BY r.created_at, t.sequence
                """
            ).fetchall()
            for candidate in candidates:
                workflow_row = connection.execute(
                    """
                    SELECT w.definition FROM workflow_versions w JOIN runs r
                      ON w.workflow_id=r.workflow_id AND w.version=r.workflow_version
                    WHERE r.id=?
                    """,
                    (candidate["run_id"],),
                ).fetchone()
                definition = json.loads(workflow_row["definition"])
                parents = self._parents(definition, candidate["node_id"])
                if parents:
                    states = {
                        row["node_id"]: row["state"]
                        for row in connection.execute(
                            "SELECT node_id, state FROM tasks WHERE run_id=?",
                            (candidate["run_id"],),
                        )
                    }
                    if any(states[parent] != "succeeded" for parent in parents):
                        continue
                token = uuid.uuid4().hex
                expires = (
                    (datetime.now(timezone.utc) + timedelta(seconds=lease_seconds))
                    .isoformat()
                    .replace("+00:00", "Z")
                )
                now = _now()
                connection.execute(
                    """
                    UPDATE tasks SET state='running', attempt=attempt+1,
                      lease_token=?, lease_expires_at=?, started_at=COALESCE(started_at, ?),
                      finished_at=NULL, error=NULL
                    WHERE run_id=? AND node_id=? AND state='pending'
                    """,
                    (token, expires, now, candidate["run_id"], candidate["node_id"]),
                )
                connection.execute(
                    "UPDATE runs SET state='running', started_at=COALESCE(started_at, ?) WHERE id=?",
                    (now, candidate["run_id"]),
                )
                return candidate["run_id"], candidate["node_id"], token
        return None

    def _task_request(self, run_id: str, node_id: str) -> TaskRequest:
        with self._connect() as connection:
            task = connection.execute(
                "SELECT * FROM tasks WHERE run_id=? AND node_id=?", (run_id, node_id)
            ).fetchone()
            run = connection.execute(
                "SELECT * FROM runs WHERE id=?", (run_id,)
            ).fetchone()
            workflow = connection.execute(
                """
                SELECT w.definition FROM workflow_versions w
                WHERE w.workflow_id=? AND w.version=?
                """,
                (run["workflow_id"], run["workflow_version"]),
            ).fetchone()
            definition = json.loads(workflow["definition"])
            operation = json.loads(task["operation"])
            input_artifacts: dict[str, dict[str, Any]] = {}
            run_inputs = json.loads(run["inputs"])
            for name, item in definition["spec"]["inputs"].items():
                if item["to"]["node"] == node_id and name in run_inputs:
                    input_artifacts[item["to"]["port"]] = self.get_artifact(
                        run_inputs[name]
                    )
            for edge in definition["spec"]["edges"]:
                if edge["to"]["node"] != node_id:
                    continue
                parent = connection.execute(
                    "SELECT outputs FROM tasks WHERE run_id=? AND node_id=?",
                    (run_id, edge["from"]["node"]),
                ).fetchone()
                parent_outputs = json.loads(parent["outputs"])
                artifact_id = parent_outputs[edge["from"]["port"]]
                artifact = connection.execute(
                    "SELECT * FROM artifacts WHERE id=?", (artifact_id,)
                ).fetchone()
                input_artifacts[edge["to"]["port"]] = dict(artifact)

        parameters = {
            name: value["default"]
            for name, value in operation["definition"].get("parameters", {}).items()
            if "default" in value
        }
        parameters.update(operation["parameters"])
        work_directory = self.artifact_root / run_id / node_id
        work_directory.mkdir(parents=True, exist_ok=True)
        return TaskRequest(
            run_id=run_id,
            node_id=node_id,
            capability_id=operation["capability"],
            capability_version=operation["version"],
            operation_id=operation["operation"],
            runtime_reference=operation["definition"]["runtime"]["reference"],
            runtime_digest=operation["definition"]["runtime"]["digest"],
            parameters=parameters,
            inputs=input_artifacts,
            output_types={
                name: value["artifact_type"]
                for name, value in operation["definition"]["outputs"].items()
            },
            work_directory=work_directory,
        )

    def _complete(
        self,
        run_id: str,
        node_id: str,
        lease_token: str,
        result: TaskResult,
    ) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            task = connection.execute(
                "SELECT * FROM tasks WHERE run_id=? AND node_id=?", (run_id, node_id)
            ).fetchone()
            if task["state"] == "succeeded":
                return
            if task["state"] != "running" or task["lease_token"] != lease_token:
                raise RuntimeError("stale or invalid task lease")
            operation = json.loads(task["operation"])["definition"]
            declared = operation["outputs"]
            missing = sorted(
                name
                for name, value in declared.items()
                if value.get("required", True) and name not in result.outputs
            )
            if missing:
                raise RuntimeError(
                    "runner omitted required outputs: " + ", ".join(missing)
                )
            unknown = sorted(set(result.outputs) - set(declared))
            if unknown:
                raise RuntimeError(
                    "runner returned unknown outputs: " + ", ".join(unknown)
                )
            output_ids: dict[str, str] = {}
            for port, artifact in result.outputs.items():
                expected = declared[port]["artifact_type"]
                if artifact.artifact_type != expected:
                    raise RuntimeError(
                        f"output {port} has {artifact.artifact_type}; expected {expected}"
                    )
                artifact_id = "artifact-" + uuid.uuid4().hex
                connection.execute(
                    """
                    INSERT INTO artifacts
                      (id, run_id, task_id, port, artifact_type, uri, checksum,
                       size_bytes, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        artifact_id,
                        run_id,
                        node_id,
                        port,
                        artifact.artifact_type,
                        artifact.uri,
                        artifact.checksum,
                        artifact.size_bytes,
                        _now(),
                    ),
                )
                output_ids[port] = artifact_id
            connection.execute(
                """
                UPDATE tasks SET state='succeeded', finished_at=?, outputs=?, log=?,
                  lease_token=NULL, lease_expires_at=NULL
                WHERE run_id=? AND node_id=?
                """,
                (_now(), _json(output_ids), result.log, run_id, node_id),
            )
            self._finish_run_if_terminal(connection, run_id)

    def _fail(
        self, run_id: str, node_id: str, lease_token: str, error: Exception
    ) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            task = connection.execute(
                "SELECT state, lease_token FROM tasks WHERE run_id=? AND node_id=?",
                (run_id, node_id),
            ).fetchone()
            if task["state"] != "running" or task["lease_token"] != lease_token:
                return
            failure = {
                "code": error.__class__.__name__,
                "message": str(error),
                "retryable": not isinstance(error, TaskRejectedError),
            }
            now = _now()
            connection.execute(
                """
                UPDATE tasks SET state='failed', finished_at=?, error=?,
                  lease_token=NULL, lease_expires_at=NULL
                WHERE run_id=? AND node_id=?
                """,
                (now, _json(failure), run_id, node_id),
            )
            connection.execute(
                "UPDATE runs SET state='failed', finished_at=? WHERE id=?",
                (now, run_id),
            )

    def _finish_run_if_terminal(
        self, connection: sqlite3.Connection, run_id: str
    ) -> None:
        states = [
            row["state"]
            for row in connection.execute(
                "SELECT state FROM tasks WHERE run_id=?", (run_id,)
            )
        ]
        if not states or any(state != "succeeded" for state in states):
            return
        run = connection.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        workflow = connection.execute(
            """
            SELECT definition FROM workflow_versions
            WHERE workflow_id=? AND version=?
            """,
            (run["workflow_id"], run["workflow_version"]),
        ).fetchone()
        definition = json.loads(workflow["definition"])
        outputs: dict[str, str] = {}
        for name, value in definition["spec"]["outputs"].items():
            task = connection.execute(
                "SELECT outputs FROM tasks WHERE run_id=? AND node_id=?",
                (run_id, value["from"]["node"]),
            ).fetchone()
            outputs[name] = json.loads(task["outputs"])[value["from"]["port"]]
        connection.execute(
            "UPDATE runs SET state='succeeded', finished_at=?, outputs=? WHERE id=?",
            (_now(), _json(outputs), run_id),
        )

    def run_once(self, runner: Runner, *, lease_seconds: int = 300) -> bool:
        claim = self._claim_ready_task(lease_seconds)
        if not claim:
            return False
        run_id, node_id, token = claim
        try:
            result = runner.execute(self._task_request(run_id, node_id))
            self._complete(run_id, node_id, token, result)
        except Exception as error:
            self._fail(run_id, node_id, token, error)
        return True

    def run_until_idle(self, runner: Runner, *, lease_seconds: int = 300) -> int:
        completed = 0
        while self.run_once(runner, lease_seconds=lease_seconds):
            completed += 1
        return completed

    def cancel_run(self, run_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            run = connection.execute(
                "SELECT state FROM runs WHERE id=?", (run_id,)
            ).fetchone()
            if not run:
                raise KeyError(f"run not found: {run_id}")
            if run["state"] in TERMINAL_STATES:
                return self.get_run(run_id)
            now = _now()
            connection.execute(
                "UPDATE tasks SET state='canceled', finished_at=? WHERE run_id=? AND state IN ('pending','running')",
                (now, run_id),
            )
            connection.execute(
                "UPDATE runs SET state='canceled', finished_at=? WHERE id=?",
                (now, run_id),
            )
        return self.get_run(run_id)

    def retry_task(self, run_id: str, node_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            run = connection.execute(
                "SELECT * FROM runs WHERE id=?", (run_id,)
            ).fetchone()
            if not run:
                raise KeyError(f"run not found: {run_id}")
            workflow = connection.execute(
                "SELECT definition FROM workflow_versions WHERE workflow_id=? AND version=?",
                (run["workflow_id"], run["workflow_version"]),
            ).fetchone()
            definition = json.loads(workflow["definition"])
            descendants = {node_id}
            changed = True
            while changed:
                changed = False
                for edge in definition["spec"]["edges"]:
                    if (
                        edge["from"]["node"] in descendants
                        and edge["to"]["node"] not in descendants
                    ):
                        descendants.add(edge["to"]["node"])
                        changed = True
            placeholders = ",".join("?" for _ in descendants)
            connection.execute(
                f"""
                UPDATE tasks SET state='pending', finished_at=NULL, error=NULL,
                  outputs='{{}}', lease_token=NULL, lease_expires_at=NULL
                WHERE run_id=? AND node_id IN ({placeholders})
                """,
                (run_id, *sorted(descendants)),
            )
            connection.execute(
                "UPDATE runs SET state='queued', finished_at=NULL, outputs='{}' WHERE id=?",
                (run_id,),
            )
        return self.get_run(run_id)

    def export_run(self, run_id: str) -> dict[str, Any]:
        run = self.get_run(run_id)
        workflow = self.get_workflow(run["workflow_id"], run["workflow_version"])
        with self._connect() as connection:
            artifacts = [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM artifacts WHERE run_id=? ORDER BY created_at, id",
                    (run_id,),
                )
            ]
        input_artifacts = [
            self.get_artifact(artifact_id) for artifact_id in run["inputs"].values()
        ]
        bundle = {
            "api_version": "qhpc/v1",
            "kind": "RunBundle",
            "workflow": workflow,
            "run": run,
            "artifacts": [*input_artifacts, *artifacts],
        }
        bundle["digest"] = document_digest(bundle)
        return bundle
