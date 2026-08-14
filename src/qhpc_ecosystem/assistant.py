"""QHPC-side gateway for the separately deployed ChatQEC service."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from uuid import uuid4

from .service_adapters import (
    ServiceAdapterError,
    ask_chatqec,
    build_chatqec_request,
)


_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@-]{0,127}$")
_CORPUS_REVISION = re.compile(r"^sha256:[0-9a-f]{64}$")
_SOURCE_REVISION = re.compile(r"^[0-9a-f]{40,64}$")
_HEALTH_FIELDS = {
    "status",
    "service",
    "mode",
    "source_revision",
    "corpus_revision",
    "pages",
    "tool_execution",
}


@dataclass(frozen=True)
class AuthenticatedServiceTransport:
    """Map the logical HTTPS service origin to one controlled deployment origin."""

    service_origin: str
    identity_token: str

    def __post_init__(self) -> None:
        parsed = urlsplit(self.service_origin)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ServiceAdapterError(
                "ChatQEC service origin must be an absolute HTTP(S) origin"
            )
        if parsed.username is not None or parsed.password is not None:
            raise ServiceAdapterError(
                "ChatQEC service origin cannot contain credentials"
            )
        if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
            raise ServiceAdapterError(
                "ChatQEC service origin cannot contain a path, query, or fragment"
            )
        if parsed.scheme == "http" and parsed.hostname not in {
            "127.0.0.1",
            "::1",
            "localhost",
        }:
            raise ServiceAdapterError(
                "unencrypted ChatQEC transport is allowed only on loopback"
            )
        if len(self.identity_token) < 32:
            raise ServiceAdapterError(
                "ChatQEC workload identity must be at least 32 characters"
            )

    def request(
        self,
        path: str,
        *,
        method: str,
        body: bytes | None = None,
        headers: Mapping[str, str] | None = None,
        timeout_seconds: float = 60.0,
        max_response_bytes: int = 2_000_000,
    ) -> tuple[int, Mapping[str, str], bytes]:
        if not path.startswith("/v1/") or ".." in path:
            raise ServiceAdapterError("ChatQEC request path is not allowed")
        request_headers = {
            **dict(headers or {}),
            "Authorization": f"Bearer {self.identity_token}",
        }
        request = Request(
            self.service_origin.rstrip("/") + path,
            data=body,
            headers=request_headers,
            method=method,
        )
        try:
            response = urlopen(request, timeout=timeout_seconds)
        except HTTPError as error:
            response = error
        except URLError as error:
            raise ServiceAdapterError(
                f"ChatQEC service is unavailable: {error.reason}"
            ) from error
        try:
            response_body = response.read(max_response_bytes + 1)
            if len(response_body) > max_response_bytes:
                raise ServiceAdapterError("ChatQEC service response is too large")
            return response.status, dict(response.headers.items()), response_body
        finally:
            response.close()

    def __call__(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        body: bytes,
        timeout_seconds: float,
    ) -> tuple[int, Mapping[str, str], bytes]:
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.netloc != "chatqec.internal":
            raise ServiceAdapterError("unexpected logical ChatQEC service origin")
        return self.request(
            parsed.path,
            method="POST",
            body=body,
            headers=headers,
            timeout_seconds=timeout_seconds,
        )


class ChatQECGateway:
    """Authorize, correlate, and validate browser requests at the QHPC boundary."""

    def __init__(
        self,
        service_origin: str,
        identity_token: str,
        *,
        authorized_subject: str = "workbench-user",
        workspace_id: str = "local-development",
        policy_class: str = "public-qec",
    ) -> None:
        self.transport = AuthenticatedServiceTransport(
            service_origin,
            identity_token,
        )
        self.authorized_subject = authorized_subject
        self.workspace_id = workspace_id
        self.policy_class = policy_class

    def status(self) -> dict[str, Any]:
        status, headers, body = self.transport.request(
            "/v1/health",
            method="GET",
            timeout_seconds=5,
            max_response_bytes=64_000,
        )
        content_type = next(
            (
                value
                for name, value in headers.items()
                if name.lower() == "content-type"
            ),
            "",
        )
        if (
            status != 200
            or content_type.split(";", 1)[0] != "application/json"
        ):
            raise ServiceAdapterError(
                f"ChatQEC health check returned HTTP status {status}"
            )
        try:
            value = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ServiceAdapterError("ChatQEC health response is invalid") from error
        if not isinstance(value, dict) or set(value) != _HEALTH_FIELDS:
            raise ServiceAdapterError("ChatQEC health response fields are invalid")
        if value.get("status") != "ok":
            raise ServiceAdapterError("ChatQEC health response is not ready")
        if value.get("service") != "chatqec":
            raise ServiceAdapterError("ChatQEC health response service is invalid")
        mode = value.get("mode")
        if not isinstance(mode, str) or not mode or len(mode) > 128:
            raise ServiceAdapterError("ChatQEC health response mode is invalid")
        source_revision = value.get("source_revision")
        if (
            not isinstance(source_revision, str)
            or _SOURCE_REVISION.fullmatch(source_revision) is None
        ):
            raise ServiceAdapterError(
                "ChatQEC health response source revision is invalid"
            )
        revision = value.get("corpus_revision")
        if (
            not isinstance(revision, str)
            or _CORPUS_REVISION.fullmatch(revision) is None
        ):
            raise ServiceAdapterError("ChatQEC health response lacks a corpus revision")
        pages = value.get("pages")
        if isinstance(pages, bool) or not isinstance(pages, int) or pages <= 0:
            raise ServiceAdapterError("ChatQEC health response pages is invalid")
        if value.get("tool_execution") is not False:
            raise ServiceAdapterError(
                "ChatQEC health response enables prohibited tool execution"
            )
        return {
            "status": "ok",
            "service": "chatqec",
            "mode": mode,
            "source_revision": source_revision,
            "corpus_revision": revision,
            "pages": pages,
            "tool_execution": False,
        }

    def ask(
        self,
        question: str,
        *,
        conversation_id: str,
        history: Sequence[Mapping[str, str]] = (),
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        if not isinstance(conversation_id, str) or _IDENTIFIER.fullmatch(
            conversation_id
        ) is None:
            raise ServiceAdapterError("conversation_id has an invalid format")
        correlation = correlation_id or f"corr-{uuid4().hex}"
        if _IDENTIFIER.fullmatch(correlation) is None:
            correlation = f"corr-{uuid4().hex}"
        status = self.status()
        request = build_chatqec_request(
            request_id=f"req-{uuid4().hex}",
            correlation_id=correlation,
            conversation_id=conversation_id,
            authorized_subject=self.authorized_subject,
            workspace_id=self.workspace_id,
            policy_class=self.policy_class,
            corpus_revision=status["corpus_revision"],
            question=question,
            history=history,
        )
        return ask_chatqec(
            "https://chatqec.internal",
            request,
            transport=self.transport,
        )
