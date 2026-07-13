"""Deployment-neutral authorization, secret references, and audit chaining."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable


ROLE_ACTIONS = {
    "viewer": {"registry.read", "workflow.read", "run.read", "artifact.read"},
    "composer": {
        "registry.read",
        "workflow.read",
        "workflow.publish",
        "run.read",
        "run.submit",
        "run.cancel-own",
        "run.retry-own",
        "artifact.read",
    },
    "publisher": {"registry.read", "capability.publish", "capability.deprecate"},
    "operator": {
        "registry.read",
        "workflow.read",
        "run.read",
        "run.submit",
        "run.cancel",
        "run.retry",
        "artifact.read",
    },
}
ALL_ACTIONS = set().union(*ROLE_ACTIONS.values()) | {
    "policy.admin",
    "audit.read",
}
ROLE_ACTIONS["admin"] = ALL_ACTIONS
SECRET_REFERENCE = re.compile(r"^secret://[a-z][a-z0-9-]*/[A-Za-z0-9._/-]+$")


class AuthorizationError(PermissionError):
    pass


def authorize(roles: Iterable[str], action: str) -> None:
    granted: set[str] = set()
    for role in roles:
        if role not in ROLE_ACTIONS:
            raise AuthorizationError(f"unknown role: {role}")
        granted.update(ROLE_ACTIONS[role])
    if action not in granted:
        raise AuthorizationError(f"action not authorized: {action}")


def validate_secret_reference(value: str) -> str:
    if not SECRET_REFERENCE.fullmatch(value) or ".." in value:
        raise ValueError("secrets must use secret://PROVIDER/IDENTIFIER references")
    return value


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


@dataclass(frozen=True)
class AuditEvent:
    timestamp: str
    actor: str
    action: str
    resource: str
    outcome: str
    details: dict[str, Any]
    previous_digest: str
    digest: str


class AuditLog:
    """Append-only JSONL audit log with a verifiable SHA-256 hash chain."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _last_digest(self) -> str:
        if not self.path.is_file():
            return "sha256:" + "0" * 64
        last = ""
        with self.path.open(encoding="utf-8") as stream:
            for line in stream:
                if line.strip():
                    last = line
        if not last:
            return "sha256:" + "0" * 64
        return json.loads(last)["digest"]

    def append(
        self,
        *,
        actor: str,
        action: str,
        resource: str,
        outcome: str,
        details: dict[str, Any] | None = None,
    ) -> AuditEvent:
        previous = self._last_digest()
        body = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "actor": actor,
            "action": action,
            "resource": resource,
            "outcome": outcome,
            "details": details or {},
            "previous_digest": previous,
        }
        body["digest"] = (
            "sha256:" + sha256(previous.encode("ascii") + _canonical(body)).hexdigest()
        )
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(body, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        return AuditEvent(**body)

    def verify(self) -> int:
        previous = "sha256:" + "0" * 64
        count = 0
        if not self.path.is_file():
            return count
        with self.path.open(encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                if not line.strip():
                    continue
                event = json.loads(line)
                digest = event.pop("digest")
                if event.get("previous_digest") != previous:
                    raise ValueError(f"audit chain broken at line {line_number}")
                expected = (
                    "sha256:"
                    + sha256(previous.encode("ascii") + _canonical(event)).hexdigest()
                )
                if digest != expected:
                    raise ValueError(f"audit digest mismatch at line {line_number}")
                previous = digest
                count += 1
        return count
