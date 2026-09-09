"""Publish the local qsc-materials-db static resources into databucket.

This is the only module that knows what "materials-db content" means; it
uses the generic s3_client.S3Client and has no knowledge of Garage/Compose
lifecycle details, which live in databucket_stack.py instead.
"""

from __future__ import annotations

from pathlib import Path

from .s3_client import S3Client

MATERIALS_DB_PREFIX = "materials-db/schema/"

# (repo-relative path, object key) — the two local static resources
# qhpc-capability.yaml points at (capabilities/qsc-materials-db/schema/qhpc-capability.yaml
# resources[].uri). The external ORNL-hosted dataset payloads (kcuf3-*) are
# not fetched here — that's live-SDL integration, explicitly out of scope
# for this static admission record.
_RESOURCES: tuple[tuple[str, str], ...] = (
    (
        "data-services/qsc-materials-db/materials-schema-v0.1.yaml",
        f"{MATERIALS_DB_PREFIX}materials-schema-v0.1.yaml",
    ),
    (
        "data-services/qsc-materials-db/provenance-v0.1.yaml",
        f"{MATERIALS_DB_PREFIX}provenance-v0.1.yaml",
    ),
)


def publish(client: S3Client, workspace_root: str | Path) -> tuple[str, ...]:
    """Upload the local materials-db static resources; return the keys written."""
    root = Path(workspace_root)
    written: list[str] = []
    for relative_path, key in _RESOURCES:
        source = root / relative_path
        if not source.is_file():
            raise FileNotFoundError(f"materials-db resource not found: {source}")
        client.put_object(key, source.read_bytes(), content_type="application/yaml")
        written.append(key)
    return tuple(written)
