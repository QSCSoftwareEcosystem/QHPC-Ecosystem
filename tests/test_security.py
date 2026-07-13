from __future__ import annotations

import json
from pathlib import Path

import pytest

from qhpc_ecosystem.security import (
    AuditLog,
    AuthorizationError,
    authorize,
    validate_secret_reference,
)


def test_role_authorization_is_default_deny() -> None:
    authorize(["viewer"], "registry.read")
    with pytest.raises(AuthorizationError, match="not authorized"):
        authorize(["viewer"], "run.submit")
    authorize(["admin"], "policy.admin")


def test_secret_values_must_remain_references() -> None:
    assert validate_secret_reference("secret://vault/qhpc/gitlab-token")
    with pytest.raises(ValueError):
        validate_secret_reference("ghp_plaintext")
    with pytest.raises(ValueError):
        validate_secret_reference("secret://vault/../token")


def test_audit_log_detects_tampering(tmp_path: Path) -> None:
    audit = AuditLog(tmp_path / "audit.jsonl")
    audit.append(
        actor="user-1",
        action="run.submit",
        resource="run-1",
        outcome="allowed",
    )
    audit.append(
        actor="operator-1",
        action="run.cancel",
        resource="run-1",
        outcome="allowed",
    )
    assert audit.verify() == 2

    lines = audit.path.read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    first["actor"] = "changed"
    lines[0] = json.dumps(first, sort_keys=True)
    audit.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="digest mismatch"):
        audit.verify()
