from __future__ import annotations

import json
import os
from email.message import Message
from pathlib import Path

import django
from cryptography.fernet import Fernet
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
    assert b'data-view="showcases"' in response.content
    assert b'data-view="tools"' in response.content
    assert b'data-view="knowledge"' in response.content
    assert b'data-view="openqse"' in response.content
    assert b'data-view="engagement"' in response.content
    assert b'data-view="assistant"' in response.content
    assert b'data-view="updates"' in response.content
    assert b">Projects<" not in response.content
    assert b"Software Thrust projects" not in response.content
    assert b'href="static/styles.css?v=' in response.content
    assert b'href="static/qhpc_workbench/composer.css?v=' in response.content
    assert b'src="static/qhpc_workbench/composer.js?v=' in response.content
    assert b'src="static/nebula.js?v=' in response.content
    assert b'src="static/app.js?v=' in response.content
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


def test_django_iqm_credential_vault_is_private_to_the_proxy_principal(
    tmp_path: Path, monkeypatch
) -> None:
    vault_path = tmp_path / "iqm-user-credentials.sqlite"
    token = "nqx-private-token"
    monkeypatch.setenv("QHPC_IQM_CREDENTIAL_VAULT", str(vault_path))
    monkeypatch.setenv(
        "QHPC_IQM_CREDENTIAL_VAULT_KEY", Fernet.generate_key().decode("ascii")
    )
    client = Client()

    anonymous = client.get("/api/v1/credentials/iqm")
    assert anonymous.status_code == 403

    nqx_headers = {"HTTP_X_EQO_PILOT_USER": "nqx"}
    initial = client.get("/api/v1/credentials/iqm", **nqx_headers)
    assert initial.status_code == 200
    assert initial.json() == {
        "enabled": True,
        "principal": "nqx",
        "configured": False,
        "updated_at": "",
    }
    assert initial["Cache-Control"] == "no-store"

    saved = client.put(
        "/api/v1/credentials/iqm",
        data=json.dumps({"token": token}),
        content_type="application/json",
        **nqx_headers,
    )
    assert saved.status_code == 200
    assert saved.json()["configured"] is True
    assert token.encode("utf-8") not in saved.content
    raw = vault_path.read_bytes()
    assert token.encode("utf-8") not in raw

    nk8 = client.get("/api/v1/credentials/iqm", HTTP_X_EQO_PILOT_USER="nk8")
    assert nk8.status_code == 200
    assert nk8.json()["configured"] is False

    deleted = client.delete("/api/v1/credentials/iqm", **nqx_headers)
    assert deleted.status_code == 200
    assert deleted.json()["configured"] is False
    assert client.post("/api/v1/credentials/iqm", **nqx_headers).status_code == 405


def test_django_proxy_binds_runs_to_the_injected_pilot_principal(monkeypatch) -> None:
    from qhpc_workbench import views

    requests = []

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return FakeUpstream({"status": "accepted"})

    monkeypatch.setattr(views, "urlopen", fake_urlopen)
    client = Client()
    response = client.post(
        "/api/v1/runs",
        data=json.dumps({"workflow_id": "demo", "created_by": "forged-user"}),
        content_type="application/json",
        HTTP_X_EQO_PILOT_USER="nqx",
    )

    assert response.status_code == 200
    upstream, _timeout = requests[-1]
    assert json.loads(upstream.data) == {"workflow_id": "demo", "created_by": "nqx"}


def test_django_proxy_preserves_encoded_slashes_in_query_values(monkeypatch) -> None:
    # Django's path("api/v1/<path:api_path>", ...) decodes %2F in the PATH
    # before api_proxy ever sees it, so a route that packs a slash-bearing
    # value (like a databucket object key) into the path segment breaks once
    # requests actually go through this proxy — the query string, by
    # contrast, is forwarded raw via request.META["QUERY_STRING"], so a key
    # with slashes must travel as a query parameter, not a path segment.
    from qhpc_workbench import views

    requests = []

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return FakeUpstream({"available": True, "objects": []})

    monkeypatch.setattr(views, "urlopen", fake_urlopen)
    client = Client()

    response = client.get(
        "/api/v1/data/objects/content?key=materials-db%2Fschema%2Fx.yaml"
    )

    assert response.status_code == 200
    upstream, _timeout = requests[-1]
    assert upstream.full_url == (
        "http://127.0.0.1:8999/api/v1/data/objects/content"
        "?key=materials-db%2Fschema%2Fx.yaml"
    )


def test_django_workbench_does_not_import_engine_or_database_modules() -> None:
    package = ROOT / "src" / "qhpc_workbench"
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in package.glob("*.py")
    )

    assert "qhpc_ecosystem.engine" not in source
    assert "sqlite3" not in source
