"""Encrypted, per-user IQM credentials for the isolated hardware worker.

The vault stores ciphertext only.  It is deliberately independent of workflow,
run, and artifact records so a provider token cannot enter EQO provenance data.
"""

from __future__ import annotations

import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken


_PRINCIPAL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_USER_REFERENCE_PREFIX = "secret://iqm-user/"
_MAX_TOKEN_LENGTH = 16_384


class IQMCredentialVaultError(RuntimeError):
    """A credential-vault operation failed without disclosing a token."""


def validate_iqm_principal(value: str) -> str:
    """Return a stable pilot principal suitable for a credential lookup."""
    if not isinstance(value, str) or _PRINCIPAL.fullmatch(value) is None:
        raise IQMCredentialVaultError("IQM credential identity is invalid")
    return value


def user_iqm_secret_reference(principal: str) -> str:
    """Return the non-secret worker reference for one pilot principal."""
    return _USER_REFERENCE_PREFIX + validate_iqm_principal(principal)


def principal_from_user_iqm_secret_reference(reference: str) -> str:
    """Parse only the vault reference format owned by this implementation."""
    if not isinstance(reference, str) or not reference.startswith(_USER_REFERENCE_PREFIX):
        raise IQMCredentialVaultError("IQM credential reference is not admitted")
    return validate_iqm_principal(reference.removeprefix(_USER_REFERENCE_PREFIX))


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class IQMCredentialVault:
    """Small SQLite vault encrypted with a deployment-owned Fernet key."""

    def __init__(self, path: str | Path, key: str) -> None:
        self.path = Path(path).expanduser().resolve()
        if self.path.is_symlink():
            raise IQMCredentialVaultError("IQM credential vault cannot be a symlink")
        try:
            self._cipher = Fernet(key.encode("ascii"))
        except (AttributeError, UnicodeEncodeError, ValueError) as error:
            raise IQMCredentialVaultError("IQM credential vault key is invalid") from error
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(
            self.path,
            os.O_CREAT | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        os.close(descriptor)
        os.chmod(self.path, 0o600)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS iqm_user_credentials (
                    principal TEXT PRIMARY KEY,
                    encrypted_token BLOB NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def status(self, principal: str) -> dict[str, str | bool]:
        principal = validate_iqm_principal(principal)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT updated_at FROM iqm_user_credentials WHERE principal=?",
                (principal,),
            ).fetchone()
        return {
            "configured": row is not None,
            "updated_at": row[0] if row is not None else "",
        }

    def put(self, principal: str, token: str) -> dict[str, str | bool]:
        principal = validate_iqm_principal(principal)
        if not isinstance(token, str) or not token or len(token) > _MAX_TOKEN_LENGTH:
            raise IQMCredentialVaultError("IQM token must be non-empty and within the size limit")
        now = _timestamp()
        encrypted = self._cipher.encrypt(token.encode("utf-8"))
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO iqm_user_credentials
                  (principal, encrypted_token, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(principal) DO UPDATE SET
                  encrypted_token=excluded.encrypted_token,
                  updated_at=excluded.updated_at
                """,
                (principal, encrypted, now, now),
            )
        return {"configured": True, "updated_at": now}

    def get(self, principal: str) -> str:
        principal = validate_iqm_principal(principal)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT encrypted_token FROM iqm_user_credentials WHERE principal=?",
                (principal,),
            ).fetchone()
        if row is None:
            raise IQMCredentialVaultError("IQM credential is unavailable for this user")
        try:
            token = self._cipher.decrypt(row[0]).decode("utf-8")
        except (InvalidToken, UnicodeDecodeError, TypeError) as error:
            raise IQMCredentialVaultError("IQM credential cannot be recovered") from error
        if not token or len(token) > _MAX_TOKEN_LENGTH:
            raise IQMCredentialVaultError("IQM credential cannot be recovered")
        return token

    def delete(self, principal: str) -> bool:
        principal = validate_iqm_principal(principal)
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM iqm_user_credentials WHERE principal=?", (principal,)
            )
        return bool(cursor.rowcount)
