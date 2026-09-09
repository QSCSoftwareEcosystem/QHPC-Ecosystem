from __future__ import annotations

from pathlib import Path

import pytest

from qhpc_ecosystem import materials_db_ingest


class FakeS3Client:
    def __init__(self) -> None:
        self.put_calls: list[tuple[str, bytes, str]] = []

    def put_object(self, key: str, body: bytes, *, content_type: str) -> None:
        self.put_calls.append((key, body, content_type))


def _workspace_with_resources(tmp_path: Path) -> Path:
    for relative_path, _key in materials_db_ingest._RESOURCES:
        source = tmp_path / relative_path
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(f"# {relative_path}\n", encoding="utf-8")
    return tmp_path


def test_publish_uploads_both_static_resources(tmp_path: Path) -> None:
    workspace = _workspace_with_resources(tmp_path)
    client = FakeS3Client()

    written = materials_db_ingest.publish(client, workspace)

    assert written == (
        "materials-db/schema/materials-schema-v0.1.yaml",
        "materials-db/schema/provenance-v0.1.yaml",
    )
    assert [call[0] for call in client.put_calls] == list(written)
    assert all(call[2] == "application/yaml" for call in client.put_calls)
    for (relative_path, key), (put_key, body, _content_type) in zip(
        materials_db_ingest._RESOURCES, client.put_calls
    ):
        assert put_key == key
        assert body == (workspace / relative_path).read_bytes()


def test_publish_raises_when_resource_missing(tmp_path: Path) -> None:
    client = FakeS3Client()
    with pytest.raises(FileNotFoundError, match="materials-schema-v0.1.yaml"):
        materials_db_ingest.publish(client, tmp_path)


def test_publish_uses_real_repository_resources() -> None:
    workspace_root = Path(__file__).resolve().parents[1]
    client = FakeS3Client()

    written = materials_db_ingest.publish(client, workspace_root)

    assert len(written) == 2
    assert all(body for _key, body, _content_type in client.put_calls)
