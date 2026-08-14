"""Presentation views and a fixed-origin QHPC API proxy."""

from __future__ import annotations

import hashlib
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
    upstream = Request(
        target,
        data=request.body if request.method in {"POST", "PUT", "DELETE"} else None,
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
