"""A small, dependency-free client for the versioned EQO HTTP control plane."""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from http.cookiejar import CookieJar
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit, urlunsplit
from urllib.request import HTTPCookieProcessor, Request, build_opener


API_VERSION = "qhpc/v1"
_MAX_RESPONSE_BYTES = 16 * 1024 * 1024
_TERMINAL_RUN_STATES = frozenset({"succeeded", "failed", "canceled"})


class EQOError(RuntimeError):
    """Base class for SDK failures."""


class EQOConnectionError(EQOError):
    """Raised when the EQO control plane cannot be contacted."""


class EQOProtocolError(EQOError):
    """Raised when a response does not satisfy the public SDK contract."""


class EQOTimeoutError(EQOError):
    """Raised when waiting for a nonterminal run exceeds the requested limit."""


class EQOAPIError(EQOError):
    """A sanitized error response returned by the EQO control plane."""

    def __init__(self, status: int, message: str, details: Any = None) -> None:
        self.status = status
        self.message = message
        self.details = details
        super().__init__(f"EQO API {status}: {message}")


def _as_mapping(value: Any, description: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise EQOProtocolError(f"EQO {description} must be a JSON object")
    return value


def _as_list(value: Any, description: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise EQOProtocolError(f"EQO {description} must be a JSON object array")
    return value


@dataclass(frozen=True)
class Artifact:
    """A typed artifact metadata record with verified content helpers."""

    client: "EQOClient"
    metadata: dict[str, Any]

    @property
    def id(self) -> str:
        value = self.metadata.get("id")
        if not isinstance(value, str) or not value:
            raise EQOProtocolError("EQO artifact has no valid ID")
        return value

    @property
    def artifact_type(self) -> str:
        value = self.metadata.get("artifact_type")
        if not isinstance(value, str) or not value:
            raise EQOProtocolError("EQO artifact has no valid type")
        return value

    def read_bytes(self) -> bytes:
        content, headers = self.client._request_bytes(
            "GET", f"/api/v1/artifacts/{quote(self.id, safe='')}/content"
        )
        expected = self.metadata.get("checksum")
        observed = hashlib.sha256(content).hexdigest()
        expected_digest = f"sha256:{observed}"
        if isinstance(expected, str) and expected and expected != expected_digest:
            raise EQOProtocolError("EQO artifact content checksum does not match metadata")
        etag = headers.get("ETag", "").strip('"')
        if etag and etag != expected_digest:
            raise EQOProtocolError("EQO artifact content checksum does not match ETag")
        return content

    def read_text(self, encoding: str = "utf-8") -> str:
        try:
            return self.read_bytes().decode(encoding)
        except UnicodeDecodeError as error:
            raise EQOProtocolError("EQO artifact content is not text in the requested encoding") from error

    def read_json(self) -> Any:
        try:
            return json.loads(self.read_text())
        except json.JSONDecodeError as error:
            raise EQOProtocolError("EQO artifact content is not valid JSON") from error

    def download(self, destination: str | Path, *, overwrite: bool = False) -> Path:
        target = Path(destination).expanduser().resolve()
        if target.exists() and not overwrite:
            raise FileExistsError(f"refusing to overwrite existing artifact destination: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(self.read_bytes())
        return target


@dataclass(frozen=True)
class ArtifactCollection(Sequence[Artifact]):
    """Read-only artifact collection returned by a run or the control plane."""

    values: tuple[Artifact, ...]

    def __getitem__(self, index: int) -> Artifact:
        return self.values[index]

    def __len__(self) -> int:
        return len(self.values)

    def by_type(self, artifact_type: str) -> Artifact:
        matches = [item for item in self if item.artifact_type == artifact_type]
        if len(matches) != 1:
            raise KeyError(f"expected exactly one EQO artifact of type {artifact_type!r}")
        return matches[0]


@dataclass(frozen=True)
class Run:
    """A workflow run submitted through the ordinary EQO run API."""

    client: "EQOClient"
    metadata: dict[str, Any]

    @property
    def id(self) -> str:
        value = self.metadata.get("id")
        if not isinstance(value, str) or not value:
            raise EQOProtocolError("EQO run has no valid ID")
        return value

    @property
    def state(self) -> str:
        value = self.metadata.get("state")
        if not isinstance(value, str) or not value:
            raise EQOProtocolError("EQO run has no valid state")
        return value

    def refresh(self) -> "Run":
        return self.client.runs.get(self.id)

    def wait(self, *, timeout: float | None = None, poll_interval: float = 0.5) -> "Run":
        if poll_interval <= 0:
            raise ValueError("poll_interval must be positive")
        deadline = None if timeout is None else time.monotonic() + timeout
        current = self
        while current.state not in _TERMINAL_RUN_STATES:
            if deadline is not None and time.monotonic() >= deadline:
                raise EQOTimeoutError(f"EQO run {current.id} did not reach a terminal state")
            time.sleep(poll_interval)
            current = current.refresh()
        return current

    def cancel(self) -> "Run":
        return self.client.runs.cancel(self.id)

    def export(self) -> dict[str, Any]:
        return self.client.runs.export(self.id)

    @property
    def artifacts(self) -> ArtifactCollection:
        return self.client.artifacts.for_run(self.id)


class _Capabilities:
    def __init__(self, client: "EQOClient") -> None:
        self._client = client

    def list(self) -> list[dict[str, Any]]:
        return self._client._request_object_list("GET", "/api/v1/capabilities")


class _Workflows:
    def __init__(self, client: "EQOClient") -> None:
        self._client = client

    def list(self) -> list[dict[str, Any]]:
        return self._client._request_object_list("GET", "/api/v1/workflows")

    def latest(self, workflow_id: str) -> dict[str, Any]:
        """Return the highest published numeric semantic version of one workflow."""

        if not isinstance(workflow_id, str) or not workflow_id:
            raise ValueError("workflow_id must be a non-empty string")
        matches = [item for item in self.list() if item.get("id") == workflow_id]
        if not matches:
            raise KeyError(f"EQO workflow is not published: {workflow_id}")

        def version_key(item: Mapping[str, Any]) -> tuple[int, int, int]:
            version = item.get("version")
            if not isinstance(version, str):
                raise EQOProtocolError("EQO workflow has no valid version")
            fields = version.split(".")
            if len(fields) != 3 or any(not field.isdecimal() for field in fields):
                raise EQOProtocolError("EQO workflow version is not numeric semantic versioning")
            return int(fields[0]), int(fields[1]), int(fields[2])

        return max(matches, key=version_key)

    def get(self, workflow_id: str, version: str) -> dict[str, Any]:
        return self._client._request_object(
            "GET",
            f"/api/v1/workflows/{quote(workflow_id, safe='')}/{quote(version, safe='')}",
        )

    def submit(
        self,
        workflow_id: str,
        version: str,
        *,
        inputs: Mapping[str, str] | None = None,
        execution_target: str = "local-development",
        execution_class: str | None = None,
        queue_if_unavailable: bool = False,
        created_by: str | None = None,
    ) -> Run:
        return self._client.runs.submit(
            workflow_id,
            version,
            inputs=inputs,
            execution_target=execution_target,
            execution_class=execution_class,
            queue_if_unavailable=queue_if_unavailable,
            created_by=created_by,
        )


class _Runs:
    def __init__(self, client: "EQOClient") -> None:
        self._client = client

    def list(self) -> list[Run]:
        return [Run(self._client, item) for item in self._client._request_object_list("GET", "/api/v1/runs")]

    def get(self, run_id: str) -> Run:
        return Run(
            self._client,
            self._client._request_object("GET", f"/api/v1/runs/{quote(run_id, safe='')}")
        )

    def submit(
        self,
        workflow_id: str,
        version: str,
        *,
        inputs: Mapping[str, str] | None = None,
        execution_target: str = "local-development",
        execution_class: str | None = None,
        queue_if_unavailable: bool = False,
        created_by: str | None = None,
    ) -> Run:
        if not isinstance(workflow_id, str) or not workflow_id:
            raise ValueError("workflow_id must be a non-empty string")
        if not isinstance(version, str) or not version:
            raise ValueError("version must be a non-empty string")
        if not isinstance(execution_target, str) or not execution_target:
            raise ValueError("execution_target must be a non-empty string")
        if not isinstance(queue_if_unavailable, bool):
            raise ValueError("queue_if_unavailable must be a boolean")
        payload: dict[str, Any] = {
            "workflow_id": workflow_id,
            "version": version,
            "inputs": dict(inputs or {}),
            "execution_target": execution_target,
            "queue_if_unavailable": queue_if_unavailable,
        }
        if execution_class is not None:
            payload["execution_class"] = execution_class
        if created_by is not None:
            payload["created_by"] = created_by
        return Run(self._client, self._client._request_object("POST", "/api/v1/runs", payload))

    def cancel(self, run_id: str) -> Run:
        return Run(
            self._client,
            self._client._request_object("POST", f"/api/v1/runs/{quote(run_id, safe='')}/cancel", {}),
        )

    def export(self, run_id: str) -> dict[str, Any]:
        return self._client._request_object("GET", f"/api/v1/runs/{quote(run_id, safe='')}/export")


class _Artifacts:
    def __init__(self, client: "EQOClient") -> None:
        self._client = client

    def list(self) -> ArtifactCollection:
        return ArtifactCollection(
            tuple(Artifact(self._client, item) for item in self._client._request_object_list("GET", "/api/v1/artifacts"))
        )

    def get(self, artifact_id: str) -> Artifact:
        return Artifact(
            self._client,
            self._client._request_object("GET", f"/api/v1/artifacts/{quote(artifact_id, safe='')}")
        )

    def for_run(self, run_id: str) -> ArtifactCollection:
        return ArtifactCollection(tuple(item for item in self.list() if item.metadata.get("run_id") == run_id))

    def create_input(
        self,
        artifact_type: str,
        content: str,
        *,
        name: str = "input.txt",
        created_by: str | None = None,
        labels: Mapping[str, str] | None = None,
    ) -> Artifact:
        payload: dict[str, Any] = {
            "artifact_type": artifact_type,
            "content": content,
            "name": name,
            "labels": dict(labels or {}),
        }
        if created_by is not None:
            payload["created_by"] = created_by
        return Artifact(self._client, self._client._request_object("POST", "/api/v1/artifacts", payload))


class _Assistant:
    def __init__(self, client: "EQOClient") -> None:
        self._client = client

    def status(self) -> dict[str, Any]:
        return self._client._request_object("GET", "/api/v1/assistant/chatqec/status")

    def ask(
        self,
        question: str,
        *,
        conversation_id: str | None = None,
        history: Sequence[Mapping[str, str]] | None = None,
    ) -> dict[str, Any]:
        if conversation_id is None:
            conversation_id = f"notebook-{uuid.uuid4().hex}"
        return self._client._request_object(
            "POST",
            "/api/v1/assistant/chatqec/answers",
            {
                "question": question,
                "conversation_id": conversation_id,
                "history": [dict(item) for item in (history or ())],
            },
        )


class _Data:
    def __init__(self, client: "EQOClient") -> None:
        self._client = client

    def list(self, prefix: str = "") -> dict[str, Any]:
        return self._client._request_object(
            "GET", "/api/v1/data/objects?" + urlencode({"prefix": prefix})
        )

    def read_bytes(self, key: str) -> bytes:
        return self._client._request_bytes(
            "GET", "/api/v1/data/objects/content?" + urlencode({"key": key})
        )[0]


class _Engagement:
    """Read-only public learning and community resources."""

    def __init__(self, client: "EQOClient") -> None:
        self._client = client

    def list(self) -> list[dict[str, Any]]:
        """List external Engagement resources without provisioning anything."""

        catalog = self._client._request_object("GET", "/api/v1/engagement-resources")
        if catalog.get("kind") != "EngagementResources":
            raise EQOProtocolError("EQO Engagement response has an invalid kind")
        if catalog.get("read_only") is not True:
            raise EQOProtocolError("EQO Engagement response is not read-only")
        return _as_list(catalog.get("resources"), "Engagement resources")


class EQOClient:
    """Client for a running EQO control-plane endpoint.

    Constructing a client is side-effect free: it does not pull an image, start
    a container, launch a service, or resolve a target credential.
    """

    def __init__(self, endpoint: str, *, access_token: str | None = None, timeout: float = 15.0) -> None:
        parsed = urlsplit(endpoint)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("EQO endpoint must be an absolute HTTP(S) URL")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("EQO endpoint must not include credentials, a query, or a fragment")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.endpoint = urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))
        self._access_token = access_token
        self.timeout = timeout
        self._cookies = CookieJar()
        self._opener = build_opener(HTTPCookieProcessor(self._cookies))
        self.capabilities = _Capabilities(self)
        self.workflows = _Workflows(self)
        self.runs = _Runs(self)
        self.artifacts = _Artifacts(self)
        self.assistant = _Assistant(self)
        self.data = _Data(self)
        self.engagement = _Engagement(self)

    @classmethod
    def connect(cls, endpoint: str, *, access_token: str | None = None, timeout: float = 15.0) -> "EQOClient":
        """Create a client and validate the supported EQO API version."""

        client = cls(endpoint, access_token=access_token, timeout=timeout)
        client.health()
        return client

    def health(self) -> dict[str, Any]:
        response = self._request_object("GET", "/api/v1/health")
        if response.get("api") != API_VERSION:
            raise EQOProtocolError(
                f"EQO API version is incompatible: expected {API_VERSION!r}, got {response.get('api')!r}"
            )
        return response

    def workers(self) -> list[dict[str, Any]]:
        return self._request_object_list("GET", "/api/v1/workers")

    def readiness(
        self,
        *,
        execution_target: str,
        runtime_digests: Sequence[str],
        execution_class: str | None = None,
    ) -> dict[str, Any]:
        pairs: list[tuple[str, str]] = [("execution_target", execution_target)]
        pairs.extend(("runtime_digest", item) for item in runtime_digests)
        if execution_class is not None:
            pairs.append(("execution_class", execution_class))
        return self._request_object("GET", "/api/v1/readiness?" + urlencode(pairs))

    def _csrf_token(self) -> str | None:
        for cookie in self._cookies:
            if cookie.name == "csrftoken":
                return cookie.value
        return None

    def _ensure_csrf_cookie(self) -> None:
        """Establish a Workbench CSRF cookie when this is a proxied endpoint.

        Direct QHPC API endpoints do not provide Django's landing page and
        legitimately return 404 here; in that case the SDK continues without
        a CSRF header. The request never leaves the validated EQO endpoint.
        """

        if self._csrf_token() is not None:
            return
        request = Request(
            self.endpoint + "/",
            headers={"Accept": "text/html,application/xhtml+xml"},
            method="GET",
        )
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                self._read_bounded(response)
        except HTTPError:
            return
        except URLError as error:
            raise EQOConnectionError("unable to connect to the EQO control plane") from error

    def _headers(self, *, content_type: str | None = None) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "X-QHPC-Correlation-ID": f"sdk-{uuid.uuid4().hex}",
        }
        if content_type is not None:
            headers["Content-Type"] = content_type
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        csrf_token = self._csrf_token()
        if csrf_token is not None:
            headers["X-CSRFToken"] = csrf_token
        return headers

    def _request_object_list(self, method: str, path: str, body: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
        return _as_list(self._request_json(method, path, body), "response")

    def _request_object(self, method: str, path: str, body: Mapping[str, Any] | None = None) -> dict[str, Any]:
        return _as_mapping(self._request_json(method, path, body), "response")

    def _request_json(self, method: str, path: str, body: Mapping[str, Any] | None = None) -> Any:
        if method in {"POST", "PUT", "DELETE"}:
            self._ensure_csrf_cookie()
        data = None if body is None else json.dumps(dict(body), separators=(",", ":")).encode("utf-8")
        request = Request(
            self.endpoint + path,
            data=data,
            headers=self._headers(content_type="application/json" if data is not None else None),
            method=method,
        )
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                payload = self._read_bounded(response)
        except HTTPError as error:
            self._raise_api_error(error)
        except URLError as error:
            raise EQOConnectionError("unable to connect to the EQO control plane") from error
        try:
            return json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise EQOProtocolError("EQO response is not valid JSON") from error

    def _request_bytes(self, method: str, path: str) -> tuple[bytes, Mapping[str, str]]:
        request = Request(self.endpoint + path, headers=self._headers(), method=method)
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                return self._read_bounded(response), dict(response.headers.items())
        except HTTPError as error:
            self._raise_api_error(error)
        except URLError as error:
            raise EQOConnectionError("unable to connect to the EQO control plane") from error
        raise AssertionError("unreachable")

    @staticmethod
    def _read_bounded(response: Any) -> bytes:
        length = response.headers.get("Content-Length")
        if length is not None:
            try:
                if int(length) > _MAX_RESPONSE_BYTES:
                    raise EQOProtocolError("EQO response exceeds the SDK size limit")
            except ValueError as error:
                raise EQOProtocolError("EQO response has an invalid Content-Length") from error
        payload = response.read(_MAX_RESPONSE_BYTES + 1)
        if len(payload) > _MAX_RESPONSE_BYTES:
            raise EQOProtocolError("EQO response exceeds the SDK size limit")
        return payload

    @staticmethod
    def _raise_api_error(error: HTTPError) -> None:
        try:
            payload = error.read(_MAX_RESPONSE_BYTES + 1)
            decoded = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError):
            decoded = {}
        if isinstance(decoded, dict):
            message = decoded.get("error")
            details = decoded.get("details")
            if isinstance(message, str) and message:
                raise EQOAPIError(error.code, message, details) from None
        raise EQOAPIError(error.code, "EQO returned an invalid error response") from None
