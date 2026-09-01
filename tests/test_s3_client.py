from __future__ import annotations

from io import BytesIO

import pytest

from qhpc_ecosystem import s3_client
from qhpc_ecosystem.s3_client import ObjectSummary, S3Client, S3ClientError


LIST_RESPONSE = b"""<?xml version="1.0" encoding="UTF-8"?>
<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">
  <Name>proj-materials-db</Name>
  <Contents>
    <Key>materials-db/schema/materials-schema-v0.1.yaml</Key>
    <LastModified>2026-08-31T00:00:00.000Z</LastModified>
    <ETag>"abc123"</ETag>
    <Size>512</Size>
  </Contents>
  <Contents>
    <Key>materials-db/schema/provenance-v0.1.yaml</Key>
    <LastModified>2026-08-31T00:00:01.000Z</LastModified>
    <ETag>"def456"</ETag>
    <Size>256</Size>
  </Contents>
</ListBucketResult>
"""


class FakeResponse:
    def __init__(self, status: int, body: bytes) -> None:
        self.status = status
        self._buffer = BytesIO(body)

    def read(self, size: int) -> bytes:
        return self._buffer.read(size)

    def close(self) -> None:
        pass


def _client() -> S3Client:
    return S3Client(
        endpoint="http://127.0.0.1:3900",
        region="garage",
        bucket="proj-materials-db",
        access_key_id="access",
        secret_access_key="secret",
    )


def test_rejects_non_http_endpoint() -> None:
    with pytest.raises(S3ClientError, match="absolute HTTP"):
        S3Client(
            endpoint="not-a-url",
            region="garage",
            bucket="b",
            access_key_id="a",
            secret_access_key="s",
        )


def test_list_objects_parses_response(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["method"] = request.get_method()
        return FakeResponse(200, LIST_RESPONSE)

    monkeypatch.setattr(s3_client, "urlopen", fake_urlopen)

    objects = _client().list_objects("materials-db/")

    assert objects == [
        ObjectSummary(
            key="materials-db/schema/materials-schema-v0.1.yaml",
            size=512,
            last_modified="2026-08-31T00:00:00.000Z",
            etag="abc123",
        ),
        ObjectSummary(
            key="materials-db/schema/provenance-v0.1.yaml",
            size=256,
            last_modified="2026-08-31T00:00:01.000Z",
            etag="def456",
        ),
    ]
    assert captured["method"] == "GET"
    assert "list-type=2" in captured["url"]
    assert "prefix=materials-db" in captured["url"]
    assert "Authorization" in captured["headers"]


def test_list_objects_raises_on_error_status(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        s3_client, "urlopen", lambda request, timeout: FakeResponse(403, b"denied")
    )
    with pytest.raises(S3ClientError, match="LIST"):
        _client().list_objects()


def test_put_object_sends_body_and_content_type(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["data"] = request.data
        captured["headers"] = dict(request.header_items())
        return FakeResponse(200, b"")

    monkeypatch.setattr(s3_client, "urlopen", fake_urlopen)

    _client().put_object(
        "materials-db/schema/materials-schema-v0.1.yaml",
        b"schema: {}\n",
        content_type="application/yaml",
    )

    assert captured["method"] == "PUT"
    assert captured["data"] == b"schema: {}\n"
    assert captured["url"].endswith(
        "/proj-materials-db/materials-db/schema/materials-schema-v0.1.yaml"
    )
    assert captured["headers"]["Content-type"] == "application/yaml"


def test_put_object_rejects_unsafe_key() -> None:
    with pytest.raises(S3ClientError, match="invalid object key"):
        _client().put_object("../escape", b"x")


def test_put_object_raises_on_error_status(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        s3_client, "urlopen", lambda request, timeout: FakeResponse(500, b"boom")
    )
    with pytest.raises(S3ClientError, match="PUT"):
        _client().put_object("k", b"x")
