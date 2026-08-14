"""Persistent workflow orchestration and controlled local runner protocol."""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable, Iterator, Protocol
from urllib.parse import unquote, urlparse

from .contract import (
    ContractError,
    ContractIssue,
    document_digest,
    validate_contract_data,
)
from .registry import registry_digest
from .workflow import resolve_workflow, topological_nodes


TERMINAL_STATES = {"succeeded", "failed", "canceled"}
ARTIFACT_TYPE = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*@[1-9][0-9]*$")
DATABASE_SCHEMA_VERSION = 4
DEFAULT_WORKER_STALE_AFTER_SECONDS = 15.0


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
    project: str = ""
    attempt_id: str = ""
    execution_target: str = ""
    execution_class: str = ""
    runtime_type: str = ""
    entrypoint: tuple[str, ...] = ()
    arguments: tuple[str, ...] = ()
    resources: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TaskLease:
    run_id: str
    node_id: str
    attempt_id: str
    attempt_number: int
    token: str
    worker_id: str
    expires_at: str
    state: str
    target_handle: str | None = None
    recovered: bool = False


@dataclass(frozen=True)
class TaskResult:
    outputs: dict[str, ArtifactResult]
    log: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class Runner(Protocol):
    def execute(self, request: TaskRequest) -> TaskResult: ...


class TaskRejectedError(RuntimeError):
    """A worker policy rejected a task before scientific execution."""


class WorkflowDraftRevisionError(RuntimeError):
    """A workflow draft changed after the client loaded it."""


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
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                );
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
                CREATE TABLE IF NOT EXISTS workflow_drafts (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    owner TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    workflow TEXT NOT NULL,
                    layout TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
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
                    attempt_id TEXT,
                    port TEXT NOT NULL,
                    artifact_type TEXT NOT NULL,
                    uri TEXT NOT NULL,
                    checksum TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE (attempt_id, port),
                    FOREIGN KEY (run_id) REFERENCES runs(id),
                    FOREIGN KEY (attempt_id) REFERENCES task_attempts(id)
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
                CREATE TABLE IF NOT EXISTS workers (
                    id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    state TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    last_heartbeat_at TEXT NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}'
                );
                CREATE TABLE IF NOT EXISTS task_attempts (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    number INTEGER NOT NULL,
                    state TEXT NOT NULL,
                    worker_id TEXT,
                    lease_token TEXT,
                    lease_expires_at TEXT,
                    target_handle TEXT,
                    target_state TEXT,
                    target_metadata TEXT NOT NULL DEFAULT '{}',
                    started_at TEXT NOT NULL,
                    submitted_at TEXT,
                    finished_at TEXT,
                    error TEXT,
                    outputs TEXT NOT NULL DEFAULT '{}',
                    log TEXT NOT NULL DEFAULT '',
                    UNIQUE (run_id, node_id, number),
                    FOREIGN KEY (run_id, node_id)
                      REFERENCES tasks(run_id, node_id),
                    FOREIGN KEY (worker_id) REFERENCES workers(id)
                );
                CREATE TABLE IF NOT EXISTS execution_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    id TEXT NOT NULL UNIQUE,
                    run_id TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    attempt_id TEXT,
                    correlation_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    source TEXT NOT NULL,
                    execution_class TEXT,
                    target_handle TEXT,
                    stage TEXT,
                    state TEXT,
                    occurred_at TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    duration_ms INTEGER,
                    details TEXT NOT NULL DEFAULT '{}',
                    FOREIGN KEY (run_id, node_id)
                      REFERENCES tasks(run_id, node_id),
                    FOREIGN KEY (attempt_id) REFERENCES task_attempts(id)
                );
                CREATE INDEX IF NOT EXISTS task_state_index
                  ON tasks(state, run_id, sequence);
                CREATE INDEX IF NOT EXISTS attempt_reconcile_index
                  ON task_attempts(state, lease_expires_at, run_id, node_id);
                CREATE INDEX IF NOT EXISTS execution_event_run_index
                  ON execution_events(run_id, sequence);
                """
            )
            self._migrate(connection)

    @staticmethod
    def _migrate(connection: sqlite3.Connection) -> None:
        artifact_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(artifacts)").fetchall()
        }
        if "attempt_id" not in artifact_columns:
            connection.execute("ALTER TABLE artifacts ADD COLUMN attempt_id TEXT")
        artifact_unique_indexes = [
            row["name"]
            for row in connection.execute("PRAGMA index_list(artifacts)").fetchall()
            if row["origin"] == "u"
        ]
        has_legacy_artifact_identity = any(
            [
                column["name"]
                for column in connection.execute(
                    f"PRAGMA index_info({index_name})"
                ).fetchall()
            ]
            == ["run_id", "task_id", "port", "checksum"]
            for index_name in artifact_unique_indexes
        )
        if has_legacy_artifact_identity:
            connection.executescript(
                """
                CREATE TABLE artifacts_v3 (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    task_id TEXT,
                    attempt_id TEXT,
                    port TEXT NOT NULL,
                    artifact_type TEXT NOT NULL,
                    uri TEXT NOT NULL,
                    checksum TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE (attempt_id, port),
                    FOREIGN KEY (run_id) REFERENCES runs(id),
                    FOREIGN KEY (attempt_id) REFERENCES task_attempts(id)
                );
                INSERT INTO artifacts_v3
                  (id, run_id, task_id, attempt_id, port, artifact_type, uri,
                   checksum, size_bytes, created_at)
                SELECT id, run_id, task_id, attempt_id, port, artifact_type,
                       uri, checksum, size_bytes, created_at
                FROM artifacts;
                DROP TABLE artifacts;
                ALTER TABLE artifacts_v3 RENAME TO artifacts;
                """
            )
        attempt_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(task_attempts)").fetchall()
        }
        if "outputs" not in attempt_columns:
            connection.execute(
                "ALTER TABLE task_attempts "
                "ADD COLUMN outputs TEXT NOT NULL DEFAULT '{}'"
            )
        event_columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(execution_events)"
            ).fetchall()
        }
        additions = {
            "correlation_id": "TEXT NOT NULL DEFAULT ''",
            "source": "TEXT NOT NULL DEFAULT 'workflow-engine'",
            "execution_class": "TEXT",
            "target_handle": "TEXT",
            "recorded_at": "TEXT NOT NULL DEFAULT ''",
        }
        for name, declaration in additions.items():
            if name not in event_columns:
                connection.execute(
                    f"ALTER TABLE execution_events ADD COLUMN {name} {declaration}"
                )
        connection.execute(
            """
            UPDATE execution_events
            SET correlation_id=CASE
                  WHEN correlation_id='' THEN COALESCE(attempt_id, run_id)
                  ELSE correlation_id
                END,
                recorded_at=CASE
                  WHEN recorded_at='' THEN occurred_at
                  ELSE recorded_at
                END
            """
        )
        connection.execute(
            """
            INSERT OR IGNORE INTO schema_migrations(version, applied_at)
            VALUES (?, ?)
            """,
            (DATABASE_SCHEMA_VERSION, _now()),
        )

    def schema_version(self) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT MAX(version) AS version FROM schema_migrations"
            ).fetchone()
        return int(row["version"] or 0)

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

    def read_artifact_content(
        self,
        artifact_id: str,
    ) -> tuple[dict[str, Any], bytes, str]:
        artifact = self.get_artifact(artifact_id)
        parsed = urlparse(artifact["uri"])
        if parsed.scheme != "file" or parsed.netloc not in {"", "localhost"}:
            raise ContractError("only local file artifacts can be read")
        path = Path(unquote(parsed.path)).resolve()
        if path != self.artifact_root and self.artifact_root not in path.parents:
            raise ContractError("artifact path is outside the configured artifact root")
        if not path.is_file():
            raise FileNotFoundError(f"artifact content not found: {artifact_id}")
        content = path.read_bytes()
        checksum = "sha256:" + sha256(content).hexdigest()
        if checksum != artifact["checksum"]:
            raise ContractError(f"artifact checksum mismatch: {artifact_id}")
        if len(content) != artifact["size_bytes"]:
            raise ContractError(f"artifact size mismatch: {artifact_id}")
        name = artifact.get("name") or path.name or f"{artifact_id}.bin"
        return artifact, content, Path(name).name

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

    @staticmethod
    def _default_draft_layout() -> dict[str, Any]:
        return {
            "nodes": [],
            "viewport": {"x": 0, "y": 0, "zoom": 1},
        }

    @staticmethod
    def _draft_name(workflow: dict[str, Any]) -> str:
        metadata = workflow.get("metadata")
        if isinstance(metadata, dict):
            name = metadata.get("name")
            if isinstance(name, str) and name.strip():
                return name.strip()
        return "Untitled workflow"

    @staticmethod
    def _draft_row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "api_version": "qhpc/v1",
            "kind": "WorkflowDraft",
            "metadata": {
                "id": row["id"],
                "name": row["name"],
                "owner": row["owner"],
                "revision": row["revision"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            },
            "spec": {
                "workflow": json.loads(row["workflow"]),
                "layout": json.loads(row["layout"]),
            },
        }

    def create_workflow_draft(
        self,
        workflow: dict[str, Any],
        *,
        layout: dict[str, Any] | None = None,
        created_by: str,
    ) -> dict[str, Any]:
        draft_id = "draft-" + uuid.uuid4().hex
        now = _now()
        draft = {
            "api_version": "qhpc/v1",
            "kind": "WorkflowDraft",
            "metadata": {
                "id": draft_id,
                "name": self._draft_name(workflow),
                "owner": created_by,
                "revision": 1,
                "created_at": now,
                "updated_at": now,
            },
            "spec": {
                "workflow": workflow,
                "layout": layout or self._default_draft_layout(),
            },
        }
        validate_contract_data("workflow-draft", draft)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO workflow_drafts
                  (id, name, owner, revision, workflow, layout, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    draft_id,
                    draft["metadata"]["name"],
                    created_by,
                    1,
                    _json(workflow),
                    _json(draft["spec"]["layout"]),
                    now,
                    now,
                ),
            )
        return self.get_workflow_draft(draft_id)

    def list_workflow_drafts(self, *, owner: str | None = None) -> list[dict[str, Any]]:
        with self._connect() as connection:
            if owner is None:
                rows = connection.execute(
                    "SELECT * FROM workflow_drafts ORDER BY updated_at DESC, id"
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT * FROM workflow_drafts
                    WHERE owner=?
                    ORDER BY updated_at DESC, id
                    """,
                    (owner,),
                ).fetchall()
        return [self._draft_row(row) for row in rows]

    def get_workflow_draft(self, draft_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM workflow_drafts WHERE id=?",
                (draft_id,),
            ).fetchone()
        if not row:
            raise KeyError(f"workflow draft not found: {draft_id}")
        return self._draft_row(row)

    def update_workflow_draft(
        self,
        draft_id: str,
        workflow: dict[str, Any],
        *,
        layout: dict[str, Any],
        expected_revision: int,
    ) -> dict[str, Any]:
        if not isinstance(expected_revision, int) or isinstance(
            expected_revision, bool
        ):
            raise ValueError("expected_revision must be an integer")
        current = self.get_workflow_draft(draft_id)
        if current["metadata"]["revision"] != expected_revision:
            raise WorkflowDraftRevisionError(
                f"workflow draft revision conflict: expected {expected_revision}, "
                f"current {current['metadata']['revision']}"
            )
        updated_at = _now()
        next_revision = expected_revision + 1
        candidate = {
            "api_version": "qhpc/v1",
            "kind": "WorkflowDraft",
            "metadata": {
                **current["metadata"],
                "name": self._draft_name(workflow),
                "revision": next_revision,
                "updated_at": updated_at,
            },
            "spec": {"workflow": workflow, "layout": layout},
        }
        validate_contract_data("workflow-draft", candidate)
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE workflow_drafts
                SET name=?, revision=?, workflow=?, layout=?, updated_at=?
                WHERE id=? AND revision=?
                """,
                (
                    candidate["metadata"]["name"],
                    next_revision,
                    _json(workflow),
                    _json(layout),
                    updated_at,
                    draft_id,
                    expected_revision,
                ),
            )
            if cursor.rowcount != 1:
                raise WorkflowDraftRevisionError(
                    "workflow draft changed while it was being saved"
                )
        return self.get_workflow_draft(draft_id)

    def delete_workflow_draft(
        self,
        draft_id: str,
        *,
        expected_revision: int,
    ) -> dict[str, Any]:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM workflow_drafts WHERE id=? AND revision=?",
                (draft_id, expected_revision),
            )
            if cursor.rowcount == 1:
                return {"deleted": draft_id, "revision": expected_revision}
            existing = connection.execute(
                "SELECT revision FROM workflow_drafts WHERE id=?",
                (draft_id,),
            ).fetchone()
        if not existing:
            raise KeyError(f"workflow draft not found: {draft_id}")
        raise WorkflowDraftRevisionError(
            f"workflow draft revision conflict: expected {expected_revision}, "
            f"current {existing['revision']}"
        )

    def validate_workflow_draft(
        self,
        draft_id: str,
        registry: dict[str, Any],
        *,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        draft = self.get_workflow_draft(draft_id)
        revision = draft["metadata"]["revision"]
        if expected_revision is not None and revision != expected_revision:
            raise WorkflowDraftRevisionError(
                f"workflow draft revision conflict: expected {expected_revision}, "
                f"current {revision}"
            )
        try:
            resolved = resolve_workflow(draft["spec"]["workflow"], registry)
        except ContractError as error:
            return {
                "draft_id": draft_id,
                "revision": revision,
                "valid": False,
                "issues": [
                    {"path": issue.path, "message": issue.message}
                    for issue in error.issues
                ],
                "message": str(error),
            }
        return {
            "draft_id": draft_id,
            "revision": revision,
            "valid": True,
            "digest": resolved.digest,
            "node_ids": sorted(resolved.operations),
            "issues": [],
        }

    def publish_workflow_draft(
        self,
        draft_id: str,
        registry: dict[str, Any],
        *,
        expected_revision: int,
        created_by: str,
    ) -> dict[str, Any]:
        validation = self.validate_workflow_draft(
            draft_id,
            registry,
            expected_revision=expected_revision,
        )
        if not validation["valid"]:
            raise ContractError(
                "workflow draft is not publishable",
                [
                    ContractIssue(issue["path"], issue["message"])
                    for issue in validation["issues"]
                ],
            )
        draft = self.get_workflow_draft(draft_id)
        workflow = self.register_workflow(
            draft["spec"]["workflow"],
            registry,
            created_by=created_by,
        )
        return {
            "draft_id": draft_id,
            "revision": expected_revision,
            "workflow": workflow,
        }

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
        execution_class: str | None = None,
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
            default_execution_class = execution_class or (
                "interactive-local"
                if execution_target == "local-development"
                else "batch-hpc"
            )
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
                                "execution_target": target,
                                "execution_class": nodes[node_id].get(
                                    "execution_class", default_execution_class
                                ),
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
            attempts = connection.execute(
                """
                SELECT * FROM task_attempts
                WHERE run_id=?
                ORDER BY node_id, number
                """,
                (run_id,),
            ).fetchall()
            events = connection.execute(
                """
                SELECT * FROM execution_events
                WHERE run_id=?
                ORDER BY sequence
                """,
                (run_id,),
            ).fetchall()
        result = dict(run)
        result["inputs"] = json.loads(result["inputs"])
        result["outputs"] = json.loads(result["outputs"])
        attempts_by_node: dict[str, list[dict[str, Any]]] = {}
        for attempt in attempts:
            decoded = self._attempt_row(attempt)
            attempts_by_node.setdefault(decoded["node_id"], []).append(decoded)
        result["tasks"] = []
        for task in tasks:
            decoded = self._task_row(task)
            decoded["attempts"] = attempts_by_node.get(decoded["node_id"], [])
            result["tasks"].append(decoded)
        result["events"] = [self._event_row(event) for event in events]
        return result

    @staticmethod
    def _task_row(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        result["operation"] = json.loads(result["operation"])
        result["outputs"] = json.loads(result["outputs"])
        result["error"] = json.loads(result["error"]) if result["error"] else None
        return result

    @staticmethod
    def _attempt_row(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        result["target_metadata"] = json.loads(result["target_metadata"])
        result["outputs"] = json.loads(result["outputs"])
        result["error"] = json.loads(result["error"]) if result["error"] else None
        return result

    @staticmethod
    def _event_row(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        result["details"] = json.loads(result["details"])
        return result

    @staticmethod
    def _append_event(
        connection: sqlite3.Connection,
        *,
        run_id: str,
        node_id: str,
        attempt_id: str | None,
        event_type: str,
        stage: str | None = None,
        state: str | None = None,
        duration_ms: int | None = None,
        details: dict[str, Any] | None = None,
        source: str = "workflow-engine",
        occurred_at: str | None = None,
    ) -> None:
        if duration_ms is not None and duration_ms < 0:
            raise ValueError("event duration cannot be negative")
        task = connection.execute(
            "SELECT operation FROM tasks WHERE run_id=? AND node_id=?",
            (run_id, node_id),
        ).fetchone()
        operation = json.loads(task["operation"]) if task else {}
        target_handle = None
        if attempt_id:
            attempt = connection.execute(
                "SELECT target_handle FROM task_attempts WHERE id=?",
                (attempt_id,),
            ).fetchone()
            target_handle = attempt["target_handle"] if attempt else None
        recorded_at = _now()
        connection.execute(
            """
            INSERT INTO execution_events
              (id, run_id, node_id, attempt_id, correlation_id, event_type,
               source, execution_class, target_handle, stage, state,
               occurred_at, recorded_at, duration_ms, details)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "event-" + uuid.uuid4().hex,
                run_id,
                node_id,
                attempt_id,
                attempt_id or run_id,
                event_type,
                source,
                operation.get("execution_class"),
                target_handle,
                stage,
                state,
                occurred_at or recorded_at,
                recorded_at,
                duration_ms,
                _json(details or {}),
            ),
        )

    def register_worker(
        self,
        worker_id: str,
        *,
        kind: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", worker_id):
            raise ValueError("invalid worker ID")
        if not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", kind):
            raise ValueError("invalid worker kind")
        now = _now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO workers
                  (id, kind, state, started_at, last_heartbeat_at, metadata)
                VALUES (?, ?, 'online', ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  kind=excluded.kind,
                  state='online',
                  started_at=excluded.started_at,
                  last_heartbeat_at=excluded.last_heartbeat_at,
                  metadata=excluded.metadata
                """,
                (worker_id, kind, now, now, _json(metadata or {})),
            )
            row = connection.execute(
                "SELECT * FROM workers WHERE id=?", (worker_id,)
            ).fetchone()
        return self._worker_row(row)

    def heartbeat_worker(
        self, worker_id: str, *, state: str = "online"
    ) -> dict[str, Any]:
        if state not in {"online", "draining", "offline"}:
            raise ValueError("invalid worker state")
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE workers SET state=?, last_heartbeat_at=?
                WHERE id=?
                """,
                (state, _now(), worker_id),
            )
            if not cursor.rowcount:
                raise KeyError(f"worker not found: {worker_id}")
            row = connection.execute(
                "SELECT * FROM workers WHERE id=?", (worker_id,)
            ).fetchone()
        return self._worker_row(row)

    def list_workers(self) -> list[dict[str, Any]]:
        return self.worker_health()

    def worker_health(
        self,
        *,
        stale_after_seconds: float = DEFAULT_WORKER_STALE_AFTER_SECONDS,
    ) -> list[dict[str, Any]]:
        if stale_after_seconds <= 0:
            raise ValueError("worker stale threshold must be greater than zero")
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM workers ORDER BY id").fetchall()
        now = datetime.now(timezone.utc)
        return [
            self._worker_row(
                row,
                now=now,
                stale_after_seconds=stale_after_seconds,
            )
            for row in rows
        ]

    @staticmethod
    def _worker_row(
        row: sqlite3.Row,
        *,
        now: datetime | None = None,
        stale_after_seconds: float = DEFAULT_WORKER_STALE_AFTER_SECONDS,
    ) -> dict[str, Any]:
        result = dict(row)
        result["metadata"] = json.loads(result["metadata"])
        current = now or datetime.now(timezone.utc)
        heartbeat = datetime.fromisoformat(
            result["last_heartbeat_at"].replace("Z", "+00:00")
        )
        age_seconds = max(0.0, (current - heartbeat).total_seconds())
        stale = result["state"] == "online" and age_seconds > stale_after_seconds
        result["heartbeat_age_seconds"] = round(age_seconds, 3)
        result["stale"] = stale
        result["effective_state"] = "stale" if stale else result["state"]
        result["available"] = result["state"] == "online" and not stale
        return result

    @staticmethod
    def _worker_supports(
        worker: dict[str, Any],
        requirement: dict[str, str],
    ) -> bool:
        if not worker["available"]:
            return False
        metadata = worker["metadata"]
        targets = set(metadata.get("execution_targets", ()))
        classes = set(metadata.get("execution_classes", ()))
        digests = set(metadata.get("runtime_digests", ()))
        return (
            requirement["execution_target"] in targets
            and requirement["execution_class"] in classes
            and requirement["runtime_digest"] in digests
        )

    def worker_readiness(
        self,
        requirements: list[dict[str, str]],
        *,
        stale_after_seconds: float = DEFAULT_WORKER_STALE_AFTER_SECONDS,
    ) -> dict[str, Any]:
        workers = self.worker_health(stale_after_seconds=stale_after_seconds)
        checked: list[dict[str, Any]] = []
        for requirement in requirements:
            compatible = [
                worker["id"]
                for worker in workers
                if self._worker_supports(worker, requirement)
            ]
            checked.append(
                {
                    **requirement,
                    "ready": bool(compatible),
                    "compatible_workers": compatible,
                }
            )
        ready = bool(checked) and all(item["ready"] for item in checked)
        missing = [
            f"{item.get('node_id', 'operation')} "
            f"({item['execution_target']}/{item['execution_class']})"
            for item in checked
            if not item["ready"]
        ]
        if ready:
            reason = "compatible worker available"
        elif missing:
            reason = "no healthy compatible worker for " + ", ".join(missing)
        else:
            reason = "no execution requirements supplied"
        return {
            "ready": ready,
            "reason": reason,
            "stale_after_seconds": stale_after_seconds,
            "requirements": checked,
            "workers": workers,
        }

    def workflow_execution_requirements(
        self,
        workflow_id: str,
        version: str,
        *,
        execution_target: str,
        execution_class: str | None = None,
    ) -> list[dict[str, str]]:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT definition, resolution FROM workflow_versions
                WHERE workflow_id=? AND version=?
                """,
                (workflow_id, version),
            ).fetchone()
        if not row:
            raise KeyError(f"workflow not found: {workflow_id}@{version}")
        definition = json.loads(row["definition"])
        resolution = json.loads(row["resolution"])
        nodes = {node["id"]: node for node in definition["spec"]["nodes"]}
        default_execution_class = execution_class or (
            "interactive-local"
            if execution_target == "local-development"
            else "batch-hpc"
        )
        requirements: list[dict[str, str]] = []
        for node_id in topological_nodes(definition):
            node = nodes[node_id]
            operation = resolution[node_id]["operation"]
            target = node.get("execution_target", execution_target)
            if target not in operation["execution_targets"]:
                raise ContractError(
                    f"node {node_id} does not support execution target {target}"
                )
            requirements.append(
                {
                    "node_id": node_id,
                    "execution_target": target,
                    "execution_class": node.get(
                        "execution_class", default_execution_class
                    ),
                    "runtime_digest": operation["runtime"]["digest"],
                }
            )
        return requirements

    def _reset_expired_leases(self, connection: sqlite3.Connection) -> None:
        now = _now()
        expired = connection.execute(
            """
            SELECT t.run_id, t.node_id, t.attempt, r.state AS run_state,
                   a.id AS attempt_id, a.target_handle,
                   a.state AS attempt_state
            FROM tasks t JOIN runs r ON r.id=t.run_id
            LEFT JOIN task_attempts a
              ON a.run_id=t.run_id AND a.node_id=t.node_id
             AND a.number=t.attempt
            WHERE (t.lease_expires_at < ? OR a.lease_expires_at < ?)
              AND (t.state='running' OR a.state='cancel_requested')
            """,
            (now, now),
        ).fetchall()
        failure = {
            "code": "lease-expired",
            "message": "task lease expired before target submission",
            "retryable": True,
        }
        for row in expired:
            if row["run_state"] == "canceled" and not row["target_handle"]:
                if row["attempt_id"]:
                    connection.execute(
                        """
                        UPDATE task_attempts
                        SET state='canceled', worker_id=NULL, lease_token=NULL,
                            lease_expires_at=NULL, finished_at=?
                        WHERE id=?
                        """,
                        (now, row["attempt_id"]),
                    )
                    self._append_event(
                        connection,
                        run_id=row["run_id"],
                        node_id=row["node_id"],
                        attempt_id=row["attempt_id"],
                        event_type="task.canceled",
                        state="canceled",
                        details={"reason": "canceled-submission-lease-expired"},
                    )
                connection.execute(
                    """
                    UPDATE tasks SET lease_token=NULL, lease_expires_at=NULL
                    WHERE run_id=? AND node_id=?
                    """,
                    (row["run_id"], row["node_id"]),
                )
                continue
            if row["attempt_id"] and (
                row["target_handle"] or row["attempt_state"] == "submitting"
            ):
                connection.execute(
                    """
                    UPDATE task_attempts
                    SET worker_id=NULL, lease_token=NULL, lease_expires_at=NULL
                    WHERE id=?
                    """,
                    (row["attempt_id"],),
                )
                connection.execute(
                    """
                    UPDATE tasks SET lease_token=NULL, lease_expires_at=NULL
                    WHERE run_id=? AND node_id=?
                    """,
                    (row["run_id"], row["node_id"]),
                )
                self._append_event(
                    connection,
                    run_id=row["run_id"],
                    node_id=row["node_id"],
                    attempt_id=row["attempt_id"],
                    event_type="lease.expired",
                    state=row["attempt_state"],
                    details={
                        "recovery": (
                            "target-handle-preserved"
                            if row["target_handle"]
                            else "submission-intent-preserved"
                        )
                    },
                )
                continue
            if row["attempt_id"]:
                connection.execute(
                    """
                    UPDATE task_attempts
                    SET state='abandoned', worker_id=NULL, lease_token=NULL,
                        lease_expires_at=NULL, finished_at=?, error=?
                    WHERE id=?
                    """,
                    (now, _json(failure), row["attempt_id"]),
                )
                self._append_event(
                    connection,
                    run_id=row["run_id"],
                    node_id=row["node_id"],
                    attempt_id=row["attempt_id"],
                    event_type="lease.expired",
                    state="abandoned",
                    details={"recovery": "new-attempt-required"},
                )
            connection.execute(
                """
                UPDATE tasks SET state='pending', lease_token=NULL,
                    lease_expires_at=NULL, error=?
                WHERE run_id=? AND node_id=?
                """,
                (_json(failure), row["run_id"], row["node_id"]),
            )

    @staticmethod
    def _parents(definition: dict[str, Any], node_id: str) -> set[str]:
        return {
            edge["from"]["node"]
            for edge in definition["spec"]["edges"]
            if edge["to"]["node"] == node_id
        }

    @staticmethod
    def _lease_expiration(lease_seconds: int) -> str:
        return (
            (datetime.now(timezone.utc) + timedelta(seconds=lease_seconds))
            .isoformat()
            .replace("+00:00", "Z")
        )

    def claim_task(
        self,
        worker_id: str,
        *,
        lease_seconds: int = 300,
        execution_targets: set[str] | frozenset[str] | None = None,
        execution_classes: set[str] | frozenset[str] | None = None,
    ) -> TaskLease | None:
        if lease_seconds <= 0:
            raise ValueError("task lease duration must be greater than zero")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._reset_expired_leases(connection)
            now = _now()
            recoverable = connection.execute(
                """
                SELECT a.*, t.sequence, t.operation,
                       r.execution_target AS run_target
                FROM task_attempts a JOIN tasks t
                  ON t.run_id=a.run_id AND t.node_id=a.node_id
                JOIN runs r ON r.id=t.run_id
                WHERE (
                    (a.target_handle IS NOT NULL AND a.state IN
                      ('submitted','running','collecting','cancel_requested'))
                    OR (a.target_handle IS NULL AND a.state='submitting')
                  )
                  AND a.lease_token IS NULL
                ORDER BY
                  CASE WHEN a.state='cancel_requested' THEN 0 ELSE 1 END,
                  a.started_at, t.sequence
                """
            ).fetchall()
            recovered = next(
                (
                    row
                    for row in recoverable
                    if execution_targets is None
                    or (
                        json.loads(row["operation"]).get(
                            "execution_target", row["run_target"]
                        )
                        in execution_targets
                    )
                    if execution_classes is None
                    or json.loads(row["operation"]).get(
                        "execution_class", "interactive-local"
                    )
                    in execution_classes
                ),
                None,
            )
            if recovered:
                token = uuid.uuid4().hex
                expires = self._lease_expiration(lease_seconds)
                connection.execute(
                    """
                    UPDATE task_attempts
                    SET worker_id=?, lease_token=?, lease_expires_at=?
                    WHERE id=? AND lease_token IS NULL
                    """,
                    (worker_id, token, expires, recovered["id"]),
                )
                connection.execute(
                    """
                    UPDATE tasks SET lease_token=?, lease_expires_at=?
                    WHERE run_id=? AND node_id=?
                    """,
                    (
                        token,
                        expires,
                        recovered["run_id"],
                        recovered["node_id"],
                    ),
                )
                self._append_event(
                    connection,
                    run_id=recovered["run_id"],
                    node_id=recovered["node_id"],
                    attempt_id=recovered["id"],
                    event_type="lease.acquired",
                    state=recovered["state"],
                    details={"worker_id": worker_id, "recovered": True},
                )
                return TaskLease(
                    run_id=recovered["run_id"],
                    node_id=recovered["node_id"],
                    attempt_id=recovered["id"],
                    attempt_number=recovered["number"],
                    token=token,
                    worker_id=worker_id,
                    expires_at=expires,
                    state=recovered["state"],
                    target_handle=recovered["target_handle"],
                    recovered=True,
                )

            candidates = connection.execute(
                """
                SELECT t.run_id, t.node_id, t.attempt, t.operation,
                       r.execution_target AS run_target
                FROM tasks t JOIN runs r ON r.id=t.run_id
                WHERE t.state='pending' AND r.state IN ('queued','running')
                ORDER BY r.created_at, t.sequence
                """
            ).fetchall()
            for candidate in candidates:
                target = json.loads(candidate["operation"]).get(
                    "execution_target", candidate["run_target"]
                )
                if execution_targets is not None and target not in execution_targets:
                    continue
                task_execution_class = json.loads(candidate["operation"]).get(
                    "execution_class", "interactive-local"
                )
                if (
                    execution_classes is not None
                    and task_execution_class not in execution_classes
                ):
                    continue
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
                expires = self._lease_expiration(lease_seconds)
                attempt_number = candidate["attempt"] + 1
                attempt_id = "attempt-" + uuid.uuid4().hex
                cursor = connection.execute(
                    """
                    UPDATE tasks SET state='running', attempt=attempt+1,
                      lease_token=?, lease_expires_at=?, started_at=COALESCE(started_at, ?),
                      finished_at=NULL, error=NULL
                    WHERE run_id=? AND node_id=? AND state='pending'
                    """,
                    (token, expires, now, candidate["run_id"], candidate["node_id"]),
                )
                if not cursor.rowcount:
                    continue
                connection.execute(
                    """
                    INSERT INTO task_attempts
                      (id, run_id, node_id, number, state, worker_id,
                       lease_token, lease_expires_at, started_at)
                    VALUES (?, ?, ?, ?, 'leased', ?, ?, ?, ?)
                    """,
                    (
                        attempt_id,
                        candidate["run_id"],
                        candidate["node_id"],
                        attempt_number,
                        worker_id,
                        token,
                        expires,
                        now,
                    ),
                )
                connection.execute(
                    "UPDATE runs SET state='running', started_at=COALESCE(started_at, ?) WHERE id=?",
                    (now, candidate["run_id"]),
                )
                self._append_event(
                    connection,
                    run_id=candidate["run_id"],
                    node_id=candidate["node_id"],
                    attempt_id=attempt_id,
                    event_type="task.leased",
                    state="leased",
                    details={"worker_id": worker_id, "recovered": False},
                )
                return TaskLease(
                    run_id=candidate["run_id"],
                    node_id=candidate["node_id"],
                    attempt_id=attempt_id,
                    attempt_number=attempt_number,
                    token=token,
                    worker_id=worker_id,
                    expires_at=expires,
                    state="leased",
                )
        return None

    def _claim_ready_task(
        self,
        lease_seconds: int,
        worker_id: str = "embedded-local",
        execution_targets: set[str] | frozenset[str] | None = None,
        execution_classes: set[str] | frozenset[str] | None = None,
    ) -> TaskLease | None:
        return self.claim_task(
            worker_id,
            lease_seconds=lease_seconds,
            execution_targets=execution_targets,
            execution_classes=execution_classes,
        )

    def _task_request(
        self, run_id: str, node_id: str, attempt_id: str = ""
    ) -> TaskRequest:
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
        target = operation.get("execution_target", run["execution_target"])
        work_directory = self.artifact_root / run_id / node_id
        if attempt_id:
            work_directory /= attempt_id
        work_directory.mkdir(parents=True, exist_ok=True)
        definition = operation["definition"]
        invocation = definition.get("invocation", {})
        return TaskRequest(
            run_id=run_id,
            node_id=node_id,
            capability_id=operation["capability"],
            capability_version=operation["version"],
            operation_id=operation["operation"],
            runtime_reference=definition["runtime"]["reference"],
            runtime_digest=definition["runtime"]["digest"],
            parameters=parameters,
            inputs=input_artifacts,
            output_types={
                name: value["artifact_type"]
                for name, value in definition["outputs"].items()
            },
            work_directory=work_directory,
            project=operation["project"],
            attempt_id=attempt_id,
            execution_target=target,
            execution_class=operation.get("execution_class", "interactive-local"),
            runtime_type=definition["runtime"]["type"],
            entrypoint=tuple(invocation.get("entrypoint", ())),
            arguments=tuple(invocation.get("arguments", ())),
            resources=dict(definition.get("resources", {})),
        )

    def task_request(self, lease: TaskLease) -> TaskRequest:
        self._assert_lease(lease)
        return self._task_request(
            lease.run_id, lease.node_id, attempt_id=lease.attempt_id
        )

    def _assert_lease(
        self, lease: TaskLease, connection: sqlite3.Connection | None = None
    ) -> sqlite3.Row:
        if connection is None:
            with self._connect() as active_connection:
                return self._assert_lease(lease, active_connection)
        row = connection.execute(
            """
            SELECT * FROM task_attempts
            WHERE id=? AND run_id=? AND node_id=? AND worker_id=?
              AND lease_token=?
            """,
            (
                lease.attempt_id,
                lease.run_id,
                lease.node_id,
                lease.worker_id,
                lease.token,
            ),
        ).fetchone()
        if not row:
            raise RuntimeError("stale or invalid task lease")
        return row

    def renew_lease(self, lease: TaskLease, *, lease_seconds: int) -> TaskLease:
        if lease_seconds <= 0:
            raise ValueError("task lease duration must be greater than zero")
        expires = self._lease_expiration(lease_seconds)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = self._assert_lease(lease, connection)
            connection.execute(
                """
                UPDATE task_attempts SET lease_expires_at=? WHERE id=?
                """,
                (expires, lease.attempt_id),
            )
            connection.execute(
                """
                UPDATE tasks SET lease_expires_at=?
                WHERE run_id=? AND node_id=? AND lease_token=?
                """,
                (expires, lease.run_id, lease.node_id, lease.token),
            )
        return TaskLease(
            run_id=lease.run_id,
            node_id=lease.node_id,
            attempt_id=lease.attempt_id,
            attempt_number=lease.attempt_number,
            token=lease.token,
            worker_id=lease.worker_id,
            expires_at=expires,
            state=row["state"],
            target_handle=row["target_handle"],
            recovered=lease.recovered,
        )

    def record_stage(
        self,
        lease: TaskLease,
        stage: str,
        duration_ms: int,
        *,
        details: dict[str, Any] | None = None,
        source: str = "worker",
    ) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*", stage):
            raise ValueError("invalid execution stage")
        with self._connect() as connection:
            self._assert_lease(lease, connection)
            self._append_event(
                connection,
                run_id=lease.run_id,
                node_id=lease.node_id,
                attempt_id=lease.attempt_id,
                event_type="stage.completed",
                stage=stage,
                duration_ms=duration_ms,
                details=details,
                source=source,
            )

    def _record_reported_stages(
        self,
        connection: sqlite3.Connection,
        lease: TaskLease,
        metadata: dict[str, Any],
    ) -> None:
        durations = metadata.get("stage_durations_ms", {})
        if not isinstance(durations, dict):
            return
        for stage, duration in sorted(durations.items()):
            if not isinstance(stage, str) or not re.fullmatch(
                r"[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*", stage
            ):
                continue
            if isinstance(duration, bool) or not isinstance(duration, int):
                continue
            if duration < 0:
                continue
            self._append_event(
                connection,
                run_id=lease.run_id,
                node_id=lease.node_id,
                attempt_id=lease.attempt_id,
                event_type="stage.completed",
                stage=stage,
                duration_ms=duration,
                details={"reported_by": "target-runner"},
                source="target-runner",
            )

    def record_reported_stages(
        self, lease: TaskLease, metadata: dict[str, Any]
    ) -> None:
        with self._connect() as connection:
            self._assert_lease(lease, connection)
            self._record_reported_stages(connection, lease, metadata)

    def record_submission(
        self,
        lease: TaskLease,
        *,
        target_handle: str,
        target_state: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        if not target_handle or any(character.isspace() for character in target_handle):
            raise ValueError("invalid target handle")
        if target_state not in {
            "queued",
            "running",
            "succeeded",
            "failed",
            "canceled",
            "unknown",
        }:
            raise ValueError("invalid submitted target state")
        attempt_state = {
            "queued": "submitted",
            "running": "running",
            "succeeded": "collecting",
            "failed": "submitted",
            "canceled": "submitted",
            "unknown": "submitted",
        }[target_state]
        target_metadata = dict(metadata or {})
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = self._assert_lease(lease, connection)
            if current["state"] == "cancel_requested":
                attempt_state = "cancel_requested"
            connection.execute(
                """
                UPDATE task_attempts
                SET state=?, target_handle=?, target_state=?,
                    target_metadata=?, submitted_at=COALESCE(submitted_at, ?)
                WHERE id=?
                """,
                (
                    attempt_state,
                    target_handle,
                    target_state,
                    _json(target_metadata),
                    _now(),
                    lease.attempt_id,
                ),
            )
            self._append_event(
                connection,
                run_id=lease.run_id,
                node_id=lease.node_id,
                attempt_id=lease.attempt_id,
                event_type="target.submitted",
                state=target_state,
                details={"target_handle": target_handle},
                source="target-runner",
            )
            self._record_reported_stages(connection, lease, target_metadata)
        return attempt_state

    def attempt_state(self, lease: TaskLease) -> str:
        return self._assert_lease(lease)["state"]

    def mark_submitting(self, lease: TaskLease) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = self._assert_lease(lease, connection)
            if current["state"] == "cancel_requested":
                return
            if current["state"] not in {"leased", "submitting"}:
                raise RuntimeError(
                    f"attempt cannot enter submitting from {current['state']}"
                )
            connection.execute(
                "UPDATE task_attempts SET state='submitting' WHERE id=?",
                (lease.attempt_id,),
            )
            if current["state"] != "submitting":
                self._append_event(
                    connection,
                    run_id=lease.run_id,
                    node_id=lease.node_id,
                    attempt_id=lease.attempt_id,
                    event_type="target.submit-intent",
                    state="submitting",
                    details={"idempotency_key": lease.attempt_id},
                )

    def record_target_status(
        self,
        lease: TaskLease,
        *,
        target_state: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if target_state not in {
            "queued",
            "running",
            "succeeded",
            "failed",
            "canceled",
            "unknown",
        }:
            raise ValueError("invalid target state")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            attempt = self._assert_lease(lease, connection)
            merged = json.loads(attempt["target_metadata"])
            merged.update(metadata or {})
            attempt_state = attempt["state"]
            if target_state == "queued":
                attempt_state = "submitted"
            elif target_state == "running":
                attempt_state = "running"
            elif target_state == "succeeded":
                attempt_state = "collecting"
            connection.execute(
                """
                UPDATE task_attempts
                SET state=?, target_state=?, target_metadata=?
                WHERE id=?
                """,
                (
                    attempt_state,
                    target_state,
                    _json(merged),
                    lease.attempt_id,
                ),
            )
            self._append_event(
                connection,
                run_id=lease.run_id,
                node_id=lease.node_id,
                attempt_id=lease.attempt_id,
                event_type="target.state",
                state=target_state,
                details=metadata,
                source="target-runner",
            )
            self._record_reported_stages(connection, lease, metadata or {})

    def release_lease(self, lease: TaskLease) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._assert_lease(lease, connection)
            connection.execute(
                """
                UPDATE task_attempts
                SET worker_id=NULL, lease_token=NULL, lease_expires_at=NULL
                WHERE id=?
                """,
                (lease.attempt_id,),
            )
            connection.execute(
                """
                UPDATE tasks SET lease_token=NULL, lease_expires_at=NULL
                WHERE run_id=? AND node_id=? AND lease_token=?
                """,
                (lease.run_id, lease.node_id, lease.token),
            )

    def mark_attempt_canceled(
        self,
        lease: TaskLease,
        *,
        log: str = "",
        details: dict[str, Any] | None = None,
    ) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._assert_lease(lease, connection)
            now = _now()
            connection.execute(
                """
                UPDATE task_attempts
                SET state='canceled', target_state='canceled', finished_at=?,
                    log=?, worker_id=NULL, lease_token=NULL,
                    lease_expires_at=NULL
                WHERE id=?
                """,
                (now, log, lease.attempt_id),
            )
            connection.execute(
                """
                UPDATE tasks SET state='canceled', finished_at=?,
                    lease_token=NULL, lease_expires_at=NULL
                WHERE run_id=? AND node_id=?
                """,
                (now, lease.run_id, lease.node_id),
            )
            self._append_event(
                connection,
                run_id=lease.run_id,
                node_id=lease.node_id,
                attempt_id=lease.attempt_id,
                event_type="task.canceled",
                state="canceled",
                details=details,
            )

    def _complete(
        self,
        run_id: str,
        node_id: str,
        lease_token: str,
        result: TaskResult,
        attempt_id: str | None = None,
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
            attempt = connection.execute(
                """
                SELECT * FROM task_attempts
                WHERE run_id=? AND node_id=? AND lease_token=?
                """,
                (run_id, node_id, lease_token),
            ).fetchone()
            if not attempt or (attempt_id and attempt["id"] != attempt_id):
                raise RuntimeError("stale or invalid task attempt")
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
                      (id, run_id, task_id, attempt_id, port, artifact_type,
                       uri, checksum, size_bytes, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        artifact_id,
                        run_id,
                        node_id,
                        attempt["id"],
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
            now = _now()
            connection.execute(
                """
                UPDATE task_attempts
                SET state='succeeded', target_state=COALESCE(target_state, 'succeeded'),
                    finished_at=?, outputs=?, log=?, worker_id=NULL,
                    lease_token=NULL, lease_expires_at=NULL
                WHERE id=?
                """,
                (now, _json(output_ids), result.log, attempt["id"]),
            )
            self._append_event(
                connection,
                run_id=run_id,
                node_id=node_id,
                attempt_id=attempt["id"],
                event_type="task.succeeded",
                state="succeeded",
                details={"outputs": output_ids},
            )
            self._finish_run_if_terminal(connection, run_id)

    def _fail(
        self,
        run_id: str,
        node_id: str,
        lease_token: str,
        error: Exception,
        attempt_id: str | None = None,
    ) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            task = connection.execute(
                "SELECT state, lease_token FROM tasks WHERE run_id=? AND node_id=?",
                (run_id, node_id),
            ).fetchone()
            if task["state"] != "running" or task["lease_token"] != lease_token:
                return
            attempt = connection.execute(
                """
                SELECT * FROM task_attempts
                WHERE run_id=? AND node_id=? AND lease_token=?
                """,
                (run_id, node_id, lease_token),
            ).fetchone()
            if not attempt or (attempt_id and attempt["id"] != attempt_id):
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
            connection.execute(
                """
                UPDATE task_attempts
                SET state='failed', finished_at=?, error=?, worker_id=NULL,
                    lease_token=NULL, lease_expires_at=NULL
                WHERE id=?
                """,
                (now, _json(failure), attempt["id"]),
            )
            self._append_event(
                connection,
                run_id=run_id,
                node_id=node_id,
                attempt_id=attempt["id"],
                event_type="task.failed",
                state="failed",
                details={"error": failure},
            )

    def complete_task(self, lease: TaskLease, result: TaskResult) -> None:
        self._complete(
            lease.run_id,
            lease.node_id,
            lease.token,
            result,
            attempt_id=lease.attempt_id,
        )

    def fail_task(self, lease: TaskLease, error: Exception) -> None:
        self._fail(
            lease.run_id,
            lease.node_id,
            lease.token,
            error,
            attempt_id=lease.attempt_id,
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

    def run_once(
        self,
        runner: Runner,
        *,
        lease_seconds: int = 300,
        worker_id: str = "embedded-local",
        execution_targets: set[str] | frozenset[str] | None = None,
        execution_classes: set[str] | frozenset[str] | None = None,
    ) -> bool:
        if not any(worker["id"] == worker_id for worker in self.list_workers()):
            self.register_worker(worker_id, kind="local")
        else:
            self.heartbeat_worker(worker_id)
        claim = self._claim_ready_task(
            lease_seconds,
            worker_id,
            execution_targets,
            execution_classes,
        )
        if not claim:
            return False
        try:
            result = runner.execute(self.task_request(claim))
            self.complete_task(claim, result)
        except Exception as error:
            self.fail_task(claim, error)
        return True

    def run_until_idle(
        self,
        runner: Runner,
        *,
        lease_seconds: int = 300,
        worker_id: str = "embedded-local",
        execution_targets: set[str] | frozenset[str] | None = None,
        execution_classes: set[str] | frozenset[str] | None = None,
    ) -> int:
        completed = 0
        while self.run_once(
            runner,
            lease_seconds=lease_seconds,
            worker_id=worker_id,
            execution_targets=execution_targets,
            execution_classes=execution_classes,
        ):
            completed += 1
        return completed

    def cancel_run(self, run_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            run = connection.execute(
                "SELECT state FROM runs WHERE id=?", (run_id,)
            ).fetchone()
            if not run:
                raise KeyError(f"run not found: {run_id}")
            if run["state"] in TERMINAL_STATES:
                return self.get_run(run_id)
            now = _now()
            active_attempts = connection.execute(
                """
                SELECT * FROM task_attempts
                WHERE run_id=? AND state IN
                  ('leased','submitted','running','collecting','cancel_requested')
                """,
                (run_id,),
            ).fetchall()
            for attempt in active_attempts:
                target_handle = attempt["target_handle"]
                connection.execute(
                    """
                    UPDATE task_attempts
                    SET state='cancel_requested'
                    WHERE id=?
                    """,
                    (attempt["id"],),
                )
                if target_handle:
                    connection.execute(
                        """
                        UPDATE task_attempts
                        SET worker_id=NULL, lease_token=NULL, lease_expires_at=NULL
                        WHERE id=?
                        """,
                        (attempt["id"],),
                    )
                self._append_event(
                    connection,
                    run_id=attempt["run_id"],
                    node_id=attempt["node_id"],
                    attempt_id=attempt["id"],
                    event_type=(
                        "target.cancel-requested"
                        if target_handle
                        else "task.cancel-requested"
                    ),
                    state="cancel_requested",
                    details=(
                        {"target_handle": target_handle}
                        if target_handle
                        else {"reason": "run-canceled-during-task-lease"}
                    ),
                )
            connection.execute(
                """
                UPDATE tasks SET state='canceled', finished_at=?,
                    lease_token=NULL, lease_expires_at=NULL
                WHERE run_id=? AND state IN ('pending','running')
                """,
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
            for descendant in sorted(descendants):
                task = connection.execute(
                    """
                    SELECT attempt FROM tasks WHERE run_id=? AND node_id=?
                    """,
                    (run_id, descendant),
                ).fetchone()
                self._append_event(
                    connection,
                    run_id=run_id,
                    node_id=descendant,
                    attempt_id=None,
                    event_type="task.retry-requested",
                    state="pending",
                    details={"completed_attempts": task["attempt"]},
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
            "attempts": [
                attempt for task in run["tasks"] for attempt in task["attempts"]
            ],
            "events": run["events"],
        }
        bundle["digest"] = document_digest(bundle)
        return bundle
