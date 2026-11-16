"""Presentation views and a fixed-origin QHPC API proxy."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods

from qhpc_ecosystem.iqm_credentials import (
    IQMCredentialVault,
    IQMCredentialVaultError,
    validate_iqm_principal,
)


_SOURCE_ROOT = Path(__file__).resolve().parents[1]
_WORKBENCH_ASSETS = (
    _SOURCE_ROOT / "qhpc_ecosystem" / "workbench" / "styles.css",
    _SOURCE_ROOT / "qhpc_ecosystem" / "workbench" / "app.js",
    _SOURCE_ROOT / "qhpc_ecosystem" / "workbench" / "nebula.js",
    Path(__file__).resolve().parent / "static" / "qhpc_workbench" / "composer.css",
    Path(__file__).resolve().parent / "static" / "qhpc_workbench" / "composer.js",
)


def _asset_revision() -> str:
    """Return a compact revision that changes whenever a UI asset changes."""
    fingerprints = []
    for path in _WORKBENCH_ASSETS:
        try:
            stat = path.stat()
        except FileNotFoundError:
            continue
        fingerprints.append(f"{path.name}:{stat.st_mtime_ns}:{stat.st_size}")
    source = "|".join(fingerprints).encode("utf-8")
    return hashlib.sha256(source).hexdigest()[:12]


def _api_base() -> str:
    value = os.environ.get("QHPC_API_BASE", "http://127.0.0.1:8081").rstrip("/")
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise RuntimeError("QHPC_API_BASE must be an absolute HTTP(S) URL")
    return value


def _principal(request: HttpRequest) -> str | None:
    """Return the proxy-injected pilot identity, never a browser-supplied alias."""
    header = os.environ.get("QHPC_WORKBENCH_PRINCIPAL_HEADER", "X-EQO-Pilot-User")
    value = request.headers.get(header, "")
    if not value:
        return None
    try:
        return validate_iqm_principal(value)
    except IQMCredentialVaultError as error:
        raise PermissionError("pilot identity is invalid") from error


def _credential_vault() -> IQMCredentialVault | None:
    path = os.environ.get("QHPC_IQM_CREDENTIAL_VAULT", "")
    key = os.environ.get("QHPC_IQM_CREDENTIAL_VAULT_KEY", "")
    if not path and not key:
        return None
    if not path or not key:
        raise IQMCredentialVaultError("IQM credential vault is unavailable")
    return IQMCredentialVault(path, key)


def _credential_response(request: HttpRequest) -> JsonResponse:
    try:
        principal = _principal(request)
    except PermissionError:
        return JsonResponse({"error": "pilot identity is invalid"}, status=403)
    if principal is None:
        return JsonResponse({"error": "a pilot identity is required"}, status=403)
    try:
        vault = _credential_vault()
    except IQMCredentialVaultError:
        return JsonResponse({"error": "IQM credential service is unavailable"}, status=503)
    if vault is None:
        if request.method == "GET":
            response = JsonResponse({"enabled": False, "configured": False})
            response["Cache-Control"] = "no-store"
            return response
        return JsonResponse(
            {"error": "per-user IQM credentials are not enabled for this EQO instance"},
            status=409,
        )
    if request.method == "GET":
        response = JsonResponse(
            {"enabled": True, "principal": principal, **vault.status(principal)}
        )
    elif request.method == "DELETE":
        vault.delete(principal)
        response = JsonResponse(
            {"enabled": True, "principal": principal, "configured": False}
        )
    elif request.method == "PUT":
        try:
            body = json.loads(request.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return JsonResponse({"error": "IQM credential request must be JSON"}, status=400)
        if not isinstance(body, dict) or set(body) != {"token"}:
            return JsonResponse({"error": "supply only an IQM token"}, status=400)
        try:
            status = vault.put(principal, body["token"])
        except IQMCredentialVaultError:
            return JsonResponse({"error": "IQM token could not be stored"}, status=400)
        response = JsonResponse({"enabled": True, "principal": principal, **status})
    else:
        response = JsonResponse({"error": "method not allowed"}, status=405)
        response["Allow"] = "GET, PUT, DELETE"
    response["Cache-Control"] = "no-store"
    return response


@ensure_csrf_cookie
@require_GET
def index(request: HttpRequest) -> HttpResponse:
    response = render(
        request,
        "qhpc_workbench/index.html",
        {"asset_revision": _asset_revision()},
    )
    response["Cache-Control"] = "no-store"
    return response


@require_GET
def health(request: HttpRequest) -> JsonResponse:
    del request
    return JsonResponse(
        {
            "status": "ok",
            "service": "qhpc-workbench",
            "api_base_configured": True,
        }
    )


@require_http_methods(["GET", "POST", "PUT", "DELETE"])
def api_proxy(request: HttpRequest, api_path: str) -> HttpResponse:
    if api_path == "credentials/iqm":
        return _credential_response(request)
    try:
        principal = _principal(request)
    except PermissionError:
        return JsonResponse({"error": "pilot identity is invalid"}, status=403)
    target = f"{_api_base()}/api/v1/{api_path}"
    if request.META.get("QUERY_STRING"):
        target += "?" + request.META["QUERY_STRING"]
    headers = {
        "Accept": "application/json, application/octet-stream",
        "X-QHPC-Correlation-ID": request.headers.get(
            "X-QHPC-Correlation-ID",
            "workbench-" + uuid.uuid4().hex,
        ),
    }
    content_type = request.headers.get("Content-Type")
    if content_type:
        headers["Content-Type"] = content_type
    body = request.body
    if api_path == "runs" and request.method == "POST" and principal:
        try:
            run_request = json.loads(body.decode("utf-8"))
            if isinstance(run_request, dict):
                run_request["created_by"] = principal
                body = json.dumps(run_request, separators=(",", ":")).encode("utf-8")
        except (UnicodeDecodeError, json.JSONDecodeError):
            pass
    upstream = Request(
        target,
        data=body if request.method in {"POST", "PUT", "DELETE"} else None,
        headers=headers,
        method=request.method,
    )
    try:
        response = urlopen(upstream, timeout=30)
    except HTTPError as error:
        response = error
    except URLError:
        return JsonResponse(
            {"error": "QHPC control API is unavailable"},
            status=503,
        )

    payload = response.read()
    response_type = response.headers.get(
        "Content-Type",
        "application/octet-stream",
    )
    result = HttpResponse(
        payload,
        status=response.status,
        content_type=response_type,
    )
    result["Cache-Control"] = "no-store"
    for name in ("Content-Disposition", "ETag", "X-QHPC-Correlation-ID"):
        if response.headers.get(name):
            result[name] = response.headers[name]
    return result
