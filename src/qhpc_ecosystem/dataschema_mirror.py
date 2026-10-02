"""Mirror registry-declared DataSchema resources into optional object storage."""

from __future__ import annotations

import hashlib
import mimetypes
from dataclasses import dataclass
from pathlib import Path

from .contract import validate_contract
from .s3_client import S3Client


class DataSchemaMirrorError(RuntimeError):
    """Raised when a local DataSchema resource does not match the registry."""


@dataclass(frozen=True)
class MirrorResource:
    resource_id: str
    source_path: str
    storage_key: str
    digest: str


def mirror_resources(capability_path: str | Path) -> tuple[MirrorResource, ...]:
    capability = validate_contract("capability", capability_path)
    resources: list[MirrorResource] = []
    for resource in capability["spec"]["resources"]:
        source_path = resource.get("source_path")
        storage_key = resource.get("storage_key")
        digest = resource.get("digest")
        if not (source_path and storage_key and digest):
            continue
        resources.append(
            MirrorResource(
                resource_id=resource["id"],
                source_path=source_path,
                storage_key=storage_key,
                digest=digest.removeprefix("sha256:"),
            )
        )
    return tuple(resources)


def publish(
    client: S3Client,
    capability_path: str | Path,
    source_root: str | Path,
) -> tuple[str, ...]:
    """Verify and upload the DataSchema resources declared by a capability."""
    root = Path(source_root).expanduser().resolve()
    if not root.is_dir():
        raise DataSchemaMirrorError(f"DataSchema checkout not found: {root}")
    written: list[str] = []
    for resource in mirror_resources(capability_path):
        source = (root / resource.source_path).resolve()
        if root not in source.parents or not source.is_file():
            raise DataSchemaMirrorError(
                f"DataSchema resource not found: {resource.source_path}"
            )
        body = source.read_bytes()
        actual = hashlib.sha256(body).hexdigest()
        if actual != resource.digest:
            raise DataSchemaMirrorError(
                f"digest mismatch for {resource.resource_id}: "
                f"expected {resource.digest}, got {actual}"
            )
        content_type = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
        client.put_object(resource.storage_key, body, content_type=content_type)
        written.append(resource.storage_key)
    return tuple(written)
