from __future__ import annotations

import json
import os
from email.message import Message
from pathlib import Path

import django
from django.contrib.staticfiles import finders
from django.test import Client


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "qhpc_workbench.settings")
os.environ.setdefault("QHPC_API_BASE", "http://127.0.0.1:8999")
django.setup()


ROOT = Path(__file__).resolve().parents[1]


class FakeUpstream:
    def __init__(
        self,
        body: dict,
        *,
        status: int = 200,
        content_type: str = "application/json",
    ) -> None:
        self._payload = json.dumps(body).encode("utf-8")
        self.status = status
        self.headers = Message()
        self.headers["Content-Type"] = content_type

    def read(self) -> bytes:
        return self._payload


def test_django_workbench_serves_existing_design_and_health() -> None:
    client = Client()

    response = client.get("/")
    assert response.status_code == 200
    assert b"QHPC Workbench" in response.content
    assert b'data-view="overview"' in response.content
    assert b'data-view="tools"' in response.content
    assert b'data-view="knowledge"' in response.content
    assert b'data-view="assistant"' in response.content
    assert b'data-view="updates"' in response.content
    assert b">Projects<" not in response.content
    assert b"Software Thrust projects" not in response.content
    assert b"/static/styles.css?v=" in response.content
    assert b"/static/qhpc_workbench/composer.css?v=" in response.content
    assert b"/static/qhpc_workbench/composer.js?v=" in response.content
    assert b"/static/nebula.js?v=" in response.content
    assert b"/static/app.js?v=" in response.content
    assert response["Cache-Control"] == "no-store"
    assert "csrftoken" in response.cookies

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["service"] == "qhpc-workbench"


def test_django_staticfiles_finds_composer_build() -> None:
    assert finders.find("qhpc_workbench/composer.css")
    assert finders.find("qhpc_workbench/composer.js")


def test_django_proxy_uses_fixed_api_origin_and_enforces_csrf(monkeypatch) -> None:
    from qhpc_workbench import views

    requests = []

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return FakeUpstream({"status": "ok"})

    monkeypatch.setattr(views, "urlopen", fake_urlopen)
    client = Client(enforce_csrf_checks=True)
    client.get("/")
    token = client.cookies["csrftoken"].value

    rejected = client.post(
        "/api/v1/workflow-drafts",
        data=json.dumps({"workflow": {}}),
        content_type="application/json",
    )
    assert rejected.status_code == 403

    accepted = client.post(
        "/api/v1/workflow-drafts?owner=test",
        data=json.dumps({"workflow": {}}),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=token,
    )
    assert accepted.status_code == 200
    assert accepted.json() == {"status": "ok"}
    upstream, timeout = requests[-1]
    assert (
        upstream.full_url
        == "http://127.0.0.1:8999/api/v1/workflow-drafts?owner=test"
    )
    assert upstream.method == "POST"
    assert timeout == 30


def test_django_workbench_does_not_import_engine_or_database_modules() -> None:
    package = ROOT / "src" / "qhpc_workbench"
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in package.glob("*.py")
    )

    assert "qhpc_ecosystem.engine" not in source
    assert "sqlite3" not in source
