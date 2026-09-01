"""Versioned HTTP API and static workbench server."""

from __future__ import annotations

import json
import mimetypes
import re
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from .assistant import ChatQECGateway
from .contract import ContractError
from .engine import DEFAULT_WORKER_STALE_AFTER_SECONDS, WorkflowEngine
from .knowledge import KnowledgeGraphError, QAppsWikiKnowledge
from .registry import registry_entries
from .repository_updates import RepositoryUpdateError, RepositoryUpdateManager
from .s3_client import S3Client, S3ClientError
from .service_adapters import ServiceAdapterError


RUN_ROUTE = re.compile(r"^/api/v1/runs/([^/]+)$")
RUN_ACTION_ROUTE = re.compile(r"^/api/v1/runs/([^/]+)/(execute|cancel|export)$")
TASK_RETRY_ROUTE = re.compile(r"^/api/v1/runs/([^/]+)/tasks/([^/]+)/retry$")
WORKFLOW_ROUTE = re.compile(r"^/api/v1/workflows/([^/]+)/([^/]+)$")
DRAFT_ROUTE = re.compile(r"^/api/v1/workflow-drafts/([^/]+)$")
DRAFT_ACTION_ROUTE = re.compile(
    r"^/api/v1/workflow-drafts/([^/]+)/(validate|publish)$"
)
ARTIFACT_ROUTE = re.compile(r"^/api/v1/artifacts/([^/]+)$")
ARTIFACT_CONTENT_ROUTE = re.compile(r"^/api/v1/artifacts/([^/]+)/content$")
KNOWLEDGE_COMMUNITY_ROUTE = re.compile(r"^/api/v1/knowledge/communities/(\d+)$")
KNOWLEDGE_NEIGHBORHOOD_ROUTE = re.compile(
    r"^/api/v1/knowledge/neighborhood/(.+)$"
)
KNOWLEDGE_NODE_ROUTE = re.compile(r"^/api/v1/knowledge/nodes/(.+)$")
ASSISTANT_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@-]{0,127}$")


@dataclass(frozen=True)
class APIContext:
    engine: WorkflowEngine
    registry: dict[str, Any]
    static_root: Path = Path(__file__).parent / "workbench"
    worker_stale_after_seconds: float = DEFAULT_WORKER_STALE_AFTER_SECONDS
    chatqec: ChatQECGateway | None = None
    repository_updates: RepositoryUpdateManager | None = None
    knowledge: QAppsWikiKnowledge | None = None
    databucket: S3Client | None = None


def _capability_summary(entry: dict[str, Any]) -> dict[str, Any]:
    capability = entry["capability"]
    metadata = capability["metadata"]
    component = capability["spec"]["component"]
    return {
        "id": metadata["id"],
        "name": component.get("name", metadata["name"]),
        "capability_name": metadata["name"],
        "version": metadata["version"],
        "project": metadata["project"],
        "maturity": metadata["maturity"],
        "visibility": metadata["visibility"],
        "repository": metadata["repository"],
        "integration": metadata["integration"],
        "catalog_repository": entry["catalog_repository"],
        "validation": entry["validation"],
        "operations": capability["spec"].get("operations", []),
        "resources": capability["spec"].get("resources", []),
        "guidance": capability["spec"].get("guidance", {}),
        "documentation": capability["spec"].get("documentation", {}),
        "description": component["description"],
    }


def handler_for(context: APIContext) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "QHPCWorkbench/0.1"

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _json_response(self, status: int, value: Any) -> None:
            payload = json.dumps(value, sort_keys=True).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)

        def _bytes_response(
            self,
            status: int,
            content: bytes,
            *,
            content_type: str,
            disposition: str,
            filename: str,
            checksum: str,
        ) -> None:
            safe_filename = (
                filename.replace('"', "")
                .replace("\\", "_")
                .replace("\r", "_")
                .replace("\n", "_")
            )
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header(
                "Content-Disposition",
                f'{disposition}; filename="{safe_filename}"',
            )
            self.send_header("ETag", f'"{checksum}"')
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(content)

        def _error(self, status: int, message: str, details: Any = None) -> None:
            body: dict[str, Any] = {"error": message}
            if details is not None:
                body["details"] = details
            self._json_response(status, body)

        def _body(self) -> dict[str, Any]:
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError as error:
                raise ValueError("invalid Content-Length") from error
            if length <= 0:
                return {}
            if length > 2_000_000:
                raise ValueError("request body exceeds 2 MB")
            value = json.loads(self.rfile.read(length))
            if not isinstance(value, dict):
                raise ValueError("JSON body must be an object")
            return value

        def _dispatch_error(self, error: Exception) -> None:
            if isinstance(error, KeyError):
                self._error(HTTPStatus.NOT_FOUND, str(error).strip("'"))
            elif isinstance(error, ContractError):
                self._error(
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                    str(error),
                    [
                        {"path": issue.path, "message": issue.message}
                        for issue in error.issues
                    ],
                )
            elif isinstance(error, ServiceAdapterError):
                self._error(HTTPStatus.BAD_GATEWAY, str(error))
            elif isinstance(error, RepositoryUpdateError):
                self._error(HTTPStatus.CONFLICT, str(error))
            elif isinstance(error, KnowledgeGraphError):
                self._error(HTTPStatus.BAD_GATEWAY, str(error))
            elif isinstance(error, S3ClientError):
                self._error(HTTPStatus.BAD_GATEWAY, str(error))
            elif isinstance(error, (ValueError, json.JSONDecodeError)):
                self._error(HTTPStatus.BAD_REQUEST, str(error))
            else:
                self._error(HTTPStatus.CONFLICT, str(error))

        def do_GET(self) -> None:  # noqa: N802
            try:
                request_url = urlparse(self.path)
                path = request_url.path
                if path == "/api/v1/health":
                    self._json_response(
                        HTTPStatus.OK,
                        {
                            "status": "ok",
                            "api": "qhpc/v1",
                            "execution": "external-worker",
                        },
                    )
                    return
                if path == "/api/v1/capabilities":
                    self._json_response(
                        HTTPStatus.OK,
                        [
                            _capability_summary(entry)
                            for entry in registry_entries(context.registry)
                        ],
                    )
                    return
                if path == "/api/v1/data/objects":
                    if context.databucket is None:
                        self._json_response(
                            HTTPStatus.OK,
                            {
                                "available": False,
                                "reason": "databucket/Garage is not configured",
                            },
                        )
                        return
                    query = parse_qs(request_url.query)
                    prefix = query.get("prefix", [""])[-1]
                    objects = context.databucket.list_objects(prefix)
                    self._json_response(
                        HTTPStatus.OK,
                        {
                            "available": True,
                            "bucket": context.databucket.bucket,
                            "prefix": prefix,
                            "objects": [
                                {
                                    "key": item.key,
                                    "size": item.size,
                                    "last_modified": item.last_modified,
                                    "etag": item.etag,
                                }
                                for item in objects
                            ],
                        },
                    )
                    return
                if path == "/api/v1/knowledge":
                    if context.knowledge is None:
                        self._json_response(
                            HTTPStatus.OK,
                            {
                                "available": False,
                                "reason": "QAppsWiki graph is not configured",
                            },
                        )
                        return
                    self._json_response(
                        HTTPStatus.OK,
                        context.knowledge.summary(),
                    )
                    return
                if path == "/api/v1/knowledge/nodes":
                    if context.knowledge is None:
                        self._error(
                            HTTPStatus.SERVICE_UNAVAILABLE,
                            "QAppsWiki graph is not configured",
                        )
                        return
                    query = parse_qs(request_url.query)
                    community_value = query.get("community", [None])[-1]
                    include_synthetic = query.get(
                        "include_synthetic", ["false"]
                    )[-1].lower() in {"1", "true", "yes"}
                    self._json_response(
                        HTTPStatus.OK,
                        context.knowledge.search(
                            query.get("query", [""])[-1],
                            node_type=query.get("type", [None])[-1],
                            domain=query.get("domain", [None])[-1],
                            community=(
                                int(community_value)
                                if community_value is not None
                                else None
                            ),
                            limit=int(query.get("limit", ["60"])[-1]),
                            include_synthetic=include_synthetic,
                        ),
                    )
                    return
                if path == "/api/v1/knowledge/path":
                    if context.knowledge is None:
                        self._error(
                            HTTPStatus.SERVICE_UNAVAILABLE,
                            "QAppsWiki graph is not configured",
                        )
                        return
                    query = parse_qs(request_url.query)
                    source = query.get("source", [None])[-1]
                    target = query.get("target", [None])[-1]
                    if not source or not target:
                        raise ValueError(
                            "source and target query parameters are required"
                        )
                    self._json_response(
                        HTTPStatus.OK,
                        context.knowledge.shortest_path(source, target),
                    )
                    return
                community_match = KNOWLEDGE_COMMUNITY_ROUTE.fullmatch(path)
                if community_match:
                    if context.knowledge is None:
                        self._error(
                            HTTPStatus.SERVICE_UNAVAILABLE,
                            "QAppsWiki graph is not configured",
                        )
                        return
                    query = parse_qs(request_url.query)
                    self._json_response(
                        HTTPStatus.OK,
                        context.knowledge.community(
                            int(community_match.group(1)),
                            limit=int(query.get("limit", ["120"])[-1]),
                        ),
                    )
                    return
                neighborhood_match = KNOWLEDGE_NEIGHBORHOOD_ROUTE.fullmatch(path)
                if neighborhood_match:
                    if context.knowledge is None:
                        self._error(
                            HTTPStatus.SERVICE_UNAVAILABLE,
                            "QAppsWiki graph is not configured",
                        )
                        return
                    query = parse_qs(request_url.query)
                    self._json_response(
                        HTTPStatus.OK,
                        context.knowledge.neighborhood(
                            unquote(neighborhood_match.group(1)),
                            depth=int(query.get("depth", ["1"])[-1]),
                            limit=int(query.get("limit", ["100"])[-1]),
                        ),
                    )
                    return
                knowledge_node_match = KNOWLEDGE_NODE_ROUTE.fullmatch(path)
                if knowledge_node_match:
                    if context.knowledge is None:
                        self._error(
                            HTTPStatus.SERVICE_UNAVAILABLE,
                            "QAppsWiki graph is not configured",
                        )
                        return
                    self._json_response(
                        HTTPStatus.OK,
                        context.knowledge.node(
                            unquote(knowledge_node_match.group(1))
                        ),
                    )
                    return
                if path == "/api/v1/repository-updates":
                    if context.repository_updates is None:
                        self._json_response(
                            HTTPStatus.OK,
                            {"enabled": False, "items": []},
                        )
                        return
                    self._json_response(
                        HTTPStatus.OK,
                        context.repository_updates.list(),
                    )
                    return
                if path == "/api/v1/assistant/chatqec/status":
                    if context.chatqec is None:
                        self._json_response(
                            HTTPStatus.OK,
                            {
                                "status": "unconfigured",
                                "available": False,
                            },
                        )
                        return
                    status = context.chatqec.status()
                    self._json_response(
                        HTTPStatus.OK,
                        {
                            **status,
                            "available": True,
                        },
                    )
                    return
                if path == "/api/v1/workflows":
                    self._json_response(HTTPStatus.OK, context.engine.list_workflows())
                    return
                if path == "/api/v1/workflow-drafts":
                    query = parse_qs(request_url.query)
                    owner = query.get("owner", [None])[-1]
                    self._json_response(
                        HTTPStatus.OK,
                        context.engine.list_workflow_drafts(owner=owner),
                    )
                    return
                draft_match = DRAFT_ROUTE.fullmatch(path)
                if draft_match:
                    self._json_response(
                        HTTPStatus.OK,
                        context.engine.get_workflow_draft(
                            unquote(draft_match.group(1))
                        ),
                    )
                    return
                if path == "/api/v1/workers":
                    self._json_response(
                        HTTPStatus.OK,
                        context.engine.worker_health(
                            stale_after_seconds=context.worker_stale_after_seconds
                        ),
                    )
                    return
                if path == "/api/v1/readiness":
                    query = parse_qs(request_url.query)
                    target = query.get("execution_target", [None])[-1]
                    runtime_digests = query.get("runtime_digest", [])
                    if not target:
                        raise ValueError("execution_target query parameter is required")
                    execution_class = query.get(
                        "execution_class",
                        [
                            "interactive-local"
                            if target == "local-development"
                            else "batch-hpc"
                        ],
                    )[-1]
                    if not runtime_digests:
                        raise ValueError(
                            "at least one runtime_digest query parameter is required"
                        )
                    requirements = [
                        {
                            "node_id": f"requested-{index + 1}",
                            "execution_target": target,
                            "execution_class": execution_class,
                            "runtime_digest": digest,
                        }
                        for index, digest in enumerate(runtime_digests)
                    ]
                    self._json_response(
                        HTTPStatus.OK,
                        context.engine.worker_readiness(
                            requirements,
                            stale_after_seconds=context.worker_stale_after_seconds,
                        ),
                    )
                    return
                workflow_match = WORKFLOW_ROUTE.fullmatch(path)
                if workflow_match:
                    self._json_response(
                        HTTPStatus.OK,
                        context.engine.get_workflow(
                            *map(unquote, workflow_match.groups())
                        ),
                    )
                    return
                if path == "/api/v1/runs":
                    self._json_response(HTTPStatus.OK, context.engine.list_runs())
                    return
                if path == "/api/v1/artifacts":
                    self._json_response(HTTPStatus.OK, context.engine.list_artifacts())
                    return
                content_match = ARTIFACT_CONTENT_ROUTE.fullmatch(path)
                if content_match:
                    artifact, content, filename = context.engine.read_artifact_content(
                        unquote(content_match.group(1))
                    )
                    media_type = (
                        {
                            ".qasm": "text/plain",
                            ".stim": "text/plain",
                        }.get(Path(filename).suffix.lower())
                        or mimetypes.guess_type(filename)[0]
                        or "application/octet-stream"
                    )
                    safe_inline_types = {
                        "application/json",
                        "text/csv",
                        "text/plain",
                    }
                    query = parse_qs(request_url.query)
                    download = query.get("download", ["0"])[-1] in {
                        "1",
                        "true",
                        "yes",
                    }
                    disposition = (
                        "attachment"
                        if download or media_type not in safe_inline_types
                        else "inline"
                    )
                    self._bytes_response(
                        HTTPStatus.OK,
                        content,
                        content_type=media_type,
                        disposition=disposition,
                        filename=filename,
                        checksum=artifact["checksum"],
                    )
                    return
                artifact_match = ARTIFACT_ROUTE.fullmatch(path)
                if artifact_match:
                    self._json_response(
                        HTTPStatus.OK,
                        context.engine.get_artifact(unquote(artifact_match.group(1))),
                    )
                    return
                run_match = RUN_ROUTE.fullmatch(path)
                if run_match:
                    self._json_response(
                        HTTPStatus.OK,
                        context.engine.get_run(unquote(run_match.group(1))),
                    )
                    return
                action_match = RUN_ACTION_ROUTE.fullmatch(path)
                if action_match and action_match.group(2) == "export":
                    self._json_response(
                        HTTPStatus.OK,
                        context.engine.export_run(unquote(action_match.group(1))),
                    )
                    return
                if path.startswith("/api/"):
                    self._error(HTTPStatus.NOT_FOUND, "API route not found")
                    return
                self._serve_static(path)
            except Exception as error:
                self._dispatch_error(error)

        def do_POST(self) -> None:  # noqa: N802
            try:
                path = urlparse(self.path).path
                body = self._body()
                if path == "/api/v1/repository-updates/check":
                    if context.repository_updates is None:
                        self._error(
                            HTTPStatus.SERVICE_UNAVAILABLE,
                            "repository updates are not enabled",
                        )
                        return
                    unexpected = sorted(set(body) - {"component_ids"})
                    if unexpected:
                        raise ValueError(
                            "unsupported repository update check fields: "
                            + ", ".join(unexpected)
                        )
                    component_ids = body.get("component_ids")
                    if component_ids is not None:
                        if (
                            not isinstance(component_ids, list)
                            or len(component_ids) > 100
                            or any(
                                not isinstance(component_id, str)
                                or not component_id
                                for component_id in component_ids
                            )
                        ):
                            raise ValueError(
                                "component_ids must be an array of component identifiers"
                            )
                    self._json_response(
                        HTTPStatus.OK,
                        context.repository_updates.check(component_ids),
                    )
                    return
                if path == "/api/v1/repository-updates/stage":
                    if context.repository_updates is None:
                        self._error(
                            HTTPStatus.SERVICE_UNAVAILABLE,
                            "repository updates are not enabled",
                        )
                        return
                    unexpected = sorted(
                        set(body) - {"component_id", "candidate_revision"}
                    )
                    if unexpected:
                        raise ValueError(
                            "unsupported repository update stage fields: "
                            + ", ".join(unexpected)
                        )
                    component_id = body.get("component_id")
                    candidate_revision = body.get("candidate_revision")
                    if not isinstance(component_id, str) or not component_id:
                        raise ValueError("component_id must be a string")
                    if (
                        candidate_revision is not None
                        and not isinstance(candidate_revision, str)
                    ):
                        raise ValueError("candidate_revision must be a string")
                    result = context.repository_updates.stage(
                        component_id,
                        candidate_revision,
                    )
                    self._json_response(HTTPStatus.CREATED, result)
                    return
                if path == "/api/v1/repository-updates/discard":
                    if context.repository_updates is None:
                        self._error(
                            HTTPStatus.SERVICE_UNAVAILABLE,
                            "repository updates are not enabled",
                        )
                        return
                    unexpected = sorted(set(body) - {"component_id"})
                    if unexpected:
                        raise ValueError(
                            "unsupported repository update discard fields: "
                            + ", ".join(unexpected)
                        )
                    component_id = body.get("component_id")
                    if not isinstance(component_id, str) or not component_id:
                        raise ValueError("component_id must be a string")
                    self._json_response(
                        HTTPStatus.OK,
                        context.repository_updates.discard(component_id),
                    )
                    return
                if path == "/api/v1/assistant/chatqec/answers":
                    if context.chatqec is None:
                        self._error(
                            HTTPStatus.SERVICE_UNAVAILABLE,
                            "ChatQEC is not configured",
                        )
                        return
                    allowed_fields = {
                        "question",
                        "conversation_id",
                        "history",
                    }
                    unexpected = sorted(set(body) - allowed_fields)
                    if unexpected:
                        raise ValueError(
                            "unsupported ChatQEC request fields: "
                            + ", ".join(unexpected)
                        )
                    question = body.get("question")
                    conversation_id = body.get("conversation_id")
                    history = body.get("history", [])
                    if not isinstance(question, str):
                        raise ValueError("question must be a string")
                    if not question.strip() or len(question) > 8_000:
                        raise ValueError(
                            "question must contain 1 to 8000 characters"
                        )
                    if not isinstance(conversation_id, str):
                        raise ValueError("conversation_id must be a string")
                    if ASSISTANT_IDENTIFIER.fullmatch(conversation_id) is None:
                        raise ValueError("conversation_id has an invalid format")
                    if not isinstance(history, list):
                        raise ValueError("history must be an array")
                    if len(history) > 20:
                        raise ValueError("history exceeds 20 entries")
                    for index, message in enumerate(history):
                        if not isinstance(message, dict) or set(message) != {
                            "role",
                            "content",
                        }:
                            raise ValueError(
                                f"history[{index}] must contain only role and content"
                            )
                        if message["role"] not in {"user", "assistant"}:
                            raise ValueError(
                                f"history[{index}].role is invalid"
                            )
                        content = message["content"]
                        if (
                            not isinstance(content, str)
                            or not content.strip()
                            or len(content) > 8_000
                        ):
                            raise ValueError(
                                f"history[{index}].content must contain "
                                "1 to 8000 characters"
                            )
                    result = context.chatqec.ask(
                        question,
                        conversation_id=conversation_id,
                        history=history,
                        correlation_id=self.headers.get(
                            "X-QHPC-Correlation-ID"
                        ),
                    )
                    self._json_response(HTTPStatus.OK, result)
                    return
                if path == "/api/v1/workflow-drafts":
                    workflow = body.get("workflow")
                    if not isinstance(workflow, dict):
                        raise ValueError("workflow draft requires a workflow object")
                    layout = body.get("layout")
                    if layout is not None and not isinstance(layout, dict):
                        raise ValueError("workflow draft layout must be an object")
                    result = context.engine.create_workflow_draft(
                        workflow,
                        layout=layout,
                        created_by=body.get("created_by", "workbench-user"),
                    )
                    self._json_response(HTTPStatus.CREATED, result)
                    return
                draft_action_match = DRAFT_ACTION_ROUTE.fullmatch(path)
                if draft_action_match:
                    draft_id, action = map(unquote, draft_action_match.groups())
                    expected_revision = body.get("expected_revision")
                    if not isinstance(expected_revision, int) or isinstance(
                        expected_revision, bool
                    ):
                        raise ValueError("expected_revision must be an integer")
                    if action == "validate":
                        result = context.engine.validate_workflow_draft(
                            draft_id,
                            context.registry,
                            expected_revision=expected_revision,
                        )
                        status = HTTPStatus.OK
                    else:
                        result = context.engine.publish_workflow_draft(
                            draft_id,
                            context.registry,
                            expected_revision=expected_revision,
                            created_by=body.get("created_by", "workbench-user"),
                        )
                        status = HTTPStatus.CREATED
                    self._json_response(status, result)
                    return
                if path == "/api/v1/workflows":
                    workflow = body.get("workflow", body)
                    created_by = body.get("created_by", "workbench-user")
                    result = context.engine.register_workflow(
                        workflow, context.registry, created_by=created_by
                    )
                    self._json_response(HTTPStatus.CREATED, result)
                    return
                if path == "/api/v1/runs":
                    execution_target = body.get(
                        "execution_target", "local-development"
                    )
                    execution_class = body.get("execution_class")
                    requirements = context.engine.workflow_execution_requirements(
                        body["workflow_id"],
                        body["version"],
                        execution_target=execution_target,
                        execution_class=execution_class,
                    )
                    readiness = context.engine.worker_readiness(
                        requirements,
                        stale_after_seconds=context.worker_stale_after_seconds,
                    )
                    queue_if_unavailable = body.get("queue_if_unavailable", False)
                    if not isinstance(queue_if_unavailable, bool):
                        raise ValueError("queue_if_unavailable must be a boolean")
                    if not readiness["ready"] and not queue_if_unavailable:
                        self._error(
                            HTTPStatus.SERVICE_UNAVAILABLE,
                            readiness["reason"],
                            readiness,
                        )
                        return
                    result = context.engine.submit_run(
                        body["workflow_id"],
                        body["version"],
                        registry=context.registry,
                        inputs=body.get("inputs", {}),
                        execution_target=execution_target,
                        execution_class=execution_class,
                        created_by=body.get("created_by", "workbench-user"),
                    )
                    self._json_response(HTTPStatus.ACCEPTED, result)
                    return
                if path == "/api/v1/artifacts":
                    if "content" not in body:
                        raise ValueError("artifact content is required")
                    content = body["content"]
                    if not isinstance(content, str):
                        raise ValueError("artifact content must be text")
                    result = context.engine.register_input_artifact(
                        artifact_type=body["artifact_type"],
                        content=content.encode("utf-8"),
                        name=body.get("name", "input.txt"),
                        created_by=body.get("created_by", "workbench-user"),
                        labels=body.get("labels", {}),
                    )
                    self._json_response(HTTPStatus.CREATED, result)
                    return
                action_match = RUN_ACTION_ROUTE.fullmatch(path)
                if action_match:
                    run_id, action = map(unquote, action_match.groups())
                    if action == "execute":
                        self._error(
                            HTTPStatus.GONE,
                            "runs are executed asynchronously by worker processes",
                        )
                        return
                    elif action == "cancel":
                        result = context.engine.cancel_run(run_id)
                    else:
                        self._error(HTTPStatus.METHOD_NOT_ALLOWED, "use GET for export")
                        return
                    self._json_response(HTTPStatus.OK, result)
                    return
                retry_match = TASK_RETRY_ROUTE.fullmatch(path)
                if retry_match:
                    result = context.engine.retry_task(
                        *map(unquote, retry_match.groups())
                    )
                    self._json_response(HTTPStatus.ACCEPTED, result)
                    return
                self._error(HTTPStatus.NOT_FOUND, "API route not found")
            except Exception as error:
                self._dispatch_error(error)

        def do_PUT(self) -> None:  # noqa: N802
            try:
                path = urlparse(self.path).path
                body = self._body()
                draft_match = DRAFT_ROUTE.fullmatch(path)
                if draft_match:
                    workflow = body.get("workflow")
                    layout = body.get("layout")
                    if not isinstance(workflow, dict):
                        raise ValueError("workflow draft requires a workflow object")
                    if not isinstance(layout, dict):
                        raise ValueError("workflow draft layout must be an object")
                    result = context.engine.update_workflow_draft(
                        unquote(draft_match.group(1)),
                        workflow,
                        layout=layout,
                        expected_revision=body.get("expected_revision"),
                    )
                    self._json_response(HTTPStatus.OK, result)
                    return
                self._error(HTTPStatus.NOT_FOUND, "API route not found")
            except Exception as error:
                self._dispatch_error(error)

        def do_DELETE(self) -> None:  # noqa: N802
            try:
                path = urlparse(self.path).path
                body = self._body()
                draft_match = DRAFT_ROUTE.fullmatch(path)
                if draft_match:
                    expected_revision = body.get("expected_revision")
                    if not isinstance(expected_revision, int) or isinstance(
                        expected_revision, bool
                    ):
                        raise ValueError("expected_revision must be an integer")
                    result = context.engine.delete_workflow_draft(
                        unquote(draft_match.group(1)),
                        expected_revision=expected_revision,
                    )
                    self._json_response(HTTPStatus.OK, result)
                    return
                self._error(HTTPStatus.NOT_FOUND, "API route not found")
            except Exception as error:
                self._dispatch_error(error)

        def _serve_static(self, request_path: str) -> None:
            relative = (
                "index.html"
                if request_path in {"", "/"}
                else unquote(request_path.lstrip("/"))
            )
            root = context.static_root.resolve()
            candidate = (root / relative).resolve()
            if root not in candidate.parents and candidate != root:
                self._error(HTTPStatus.NOT_FOUND, "asset not found")
                return
            if not candidate.is_file():
                candidate = root / "index.html"
            if not candidate.is_file():
                self._error(HTTPStatus.NOT_FOUND, "workbench is not installed")
                return
            content = candidate.read_bytes()
            media_type = (
                mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
            )
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", media_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(content)

    return Handler


def serve(
    context: APIContext, host: str = "127.0.0.1", port: int = 8080
) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), handler_for(context))
    server.serve_forever()
    return server
