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
from urllib.parse import unquote, urlparse

from .contract import ContractError
from .engine import WorkflowEngine
from .registry import registry_entries


RUN_ROUTE = re.compile(r"^/api/v1/runs/([^/]+)$")
RUN_ACTION_ROUTE = re.compile(r"^/api/v1/runs/([^/]+)/(execute|cancel|export)$")
TASK_RETRY_ROUTE = re.compile(r"^/api/v1/runs/([^/]+)/tasks/([^/]+)/retry$")
WORKFLOW_ROUTE = re.compile(r"^/api/v1/workflows/([^/]+)/([^/]+)$")
ARTIFACT_ROUTE = re.compile(r"^/api/v1/artifacts/([^/]+)$")


@dataclass(frozen=True)
class APIContext:
    engine: WorkflowEngine
    registry: dict[str, Any]
    static_root: Path = Path(__file__).parent / "workbench"


def _capability_summary(entry: dict[str, Any]) -> dict[str, Any]:
    capability = entry["capability"]
    metadata = capability["metadata"]
    return {
        "id": metadata["id"],
        "name": metadata["name"],
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
        "documentation": capability["spec"].get("documentation", {}),
        "description": capability["spec"]["component"]["description"],
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
            elif isinstance(error, (ValueError, json.JSONDecodeError)):
                self._error(HTTPStatus.BAD_REQUEST, str(error))
            else:
                self._error(HTTPStatus.CONFLICT, str(error))

        def do_GET(self) -> None:  # noqa: N802
            try:
                path = urlparse(self.path).path
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
                if path == "/api/v1/workflows":
                    self._json_response(HTTPStatus.OK, context.engine.list_workflows())
                    return
                if path == "/api/v1/workers":
                    self._json_response(HTTPStatus.OK, context.engine.list_workers())
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
                if path == "/api/v1/workflows":
                    workflow = body.get("workflow", body)
                    created_by = body.get("created_by", "workbench-user")
                    result = context.engine.register_workflow(
                        workflow, context.registry, created_by=created_by
                    )
                    self._json_response(HTTPStatus.CREATED, result)
                    return
                if path == "/api/v1/runs":
                    result = context.engine.submit_run(
                        body["workflow_id"],
                        body["version"],
                        registry=context.registry,
                        inputs=body.get("inputs", {}),
                        execution_target=body.get(
                            "execution_target", "local-development"
                        ),
                        execution_class=body.get("execution_class"),
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
