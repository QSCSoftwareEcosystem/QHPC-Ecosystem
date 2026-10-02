from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import yaml

from qhpc_ecosystem import dataschema_mirror
from qhpc_ecosystem.dataschema_mirror import DataSchemaMirrorError


class FakeS3Client:
    def __init__(self) -> None:
        self.put_calls: list[tuple[str, bytes, str]] = []

    def put_object(self, key: str, body: bytes, *, content_type: str) -> None:
        self.put_calls.append((key, body, content_type))


def _capability(tmp_path: Path, body: bytes, digest: str | None = None) -> Path:
    path = tmp_path / "capability.yaml"
    document = {
        "api_version": "qhpc/v1",
        "kind": "Capability",
        "metadata": {
            "id": "test-data",
            "name": "Test Data",
            "version": "0.1.0",
            "project": "data-schema",
            "owners": ["test-data"],
            "repository": {"url": "https://example.test/data", "revision": "a" * 40},
            "integration": {
                "authority": "ecosystem",
                "maintainers": ["test-data"],
                "project_reviewed": False,
                "runtime_status": "not-applicable",
                "validation_status": "contract-valid",
            },
            "visibility": "public",
            "maturity": "prototype",
        },
        "spec": {
            "component": {"name": "Test Data", "description": "Test data."},
            "guidance": {"use_when": ["Testing."], "quick_start": ["Open it."]},
            "resources": [
                {
                    "id": "record",
                    "kind": "dataset",
                    "version": "0.1.0",
                    "uri": "https://example.test/record.json",
                    "download_uri": "https://example.test/raw/record.json",
                    "source_path": "data/record.json",
                    "storage_key": "materials-db/v0.1.0/record.json",
                    "digest": "sha256:" + (digest or hashlib.sha256(body).hexdigest()),
                },
                {
                    "id": "developer-attribution",
                    "kind": "documentation",
                    "version": "1.0.0",
                    "uri": "docs/attribution.md",
                },
            ],
            "documentation": {"qappswiki": "docs/wiki.md"},
        },
    }
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    return path


def test_publish_verifies_and_uploads_declared_resources(tmp_path: Path) -> None:
    body = b'{"material":"KCuF3"}\n'
    capability = _capability(tmp_path, body)
    source_root = tmp_path / "DataSchema"
    source = source_root / "data/record.json"
    source.parent.mkdir(parents=True)
    source.write_bytes(body)
    client = FakeS3Client()

    written = dataschema_mirror.publish(client, capability, source_root)

    assert written == ("materials-db/v0.1.0/record.json",)
    assert client.put_calls == [
        ("materials-db/v0.1.0/record.json", body, "application/json")
    ]


def test_publish_rejects_digest_mismatch(tmp_path: Path) -> None:
    body = b"record\n"
    capability = _capability(tmp_path, body, digest="0" * 64)
    source_root = tmp_path / "DataSchema"
    source = source_root / "data/record.json"
    source.parent.mkdir(parents=True)
    source.write_bytes(body)

    with pytest.raises(DataSchemaMirrorError, match="digest mismatch"):
        dataschema_mirror.publish(FakeS3Client(), capability, source_root)


def test_materials_capability_matches_local_dataschema_clone() -> None:
    source_root = Path("/tmp/DataSchema")
    if not source_root.is_dir():
        pytest.skip("local DataSchema checkout is not available")
    capability = Path("capabilities/qsc-materials-db/schema/qhpc-capability.yaml")

    written = dataschema_mirror.publish(FakeS3Client(), capability, source_root)

    assert written == (
        "materials-db/v0.1.0/KCuF3_Hamiltonian.json",
        "materials-db/v0.1.0/KCuF3_Hamiltonian.yaml",
        "materials-db/v0.1.0/KCuF3_MAPS-SEQ_sqw.zip",
        "materials-db/v0.1.0/manifest.yaml",
        "materials-db/v0.1.0/README.md",
        "schema/spin_hamiltonian.yaml",
    )
