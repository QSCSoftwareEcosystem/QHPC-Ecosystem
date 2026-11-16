from __future__ import annotations

import sqlite3

import pytest
from cryptography.fernet import Fernet

from qhpc_ecosystem.iqm_credentials import (
    IQMCredentialVault,
    IQMCredentialVaultError,
    principal_from_user_iqm_secret_reference,
    user_iqm_secret_reference,
)


def test_iqm_credential_vault_encrypts_and_isolates_user_tokens(tmp_path) -> None:
    vault_path = tmp_path / "credentials.sqlite"
    vault = IQMCredentialVault(vault_path, Fernet.generate_key().decode("ascii"))

    nqx = vault.put("nqx", "nqx-private-token")
    nk8 = vault.put("nk8", "nk8-private-token")

    assert nqx["configured"] is True
    assert nk8["configured"] is True
    assert vault.get("nqx") == "nqx-private-token"
    assert vault.get("nk8") == "nk8-private-token"
    assert vault.status("z7w") == {"configured": False, "updated_at": ""}
    raw = sqlite3.connect(vault_path).execute(
        "SELECT encrypted_token FROM iqm_user_credentials ORDER BY principal"
    ).fetchall()
    assert b"nqx-private-token" not in b"".join(row[0] for row in raw)
    assert b"nk8-private-token" not in b"".join(row[0] for row in raw)

    assert vault.delete("nqx") is True
    with pytest.raises(IQMCredentialVaultError, match="unavailable"):
        vault.get("nqx")
    assert vault.get("nk8") == "nk8-private-token"


def test_iqm_user_secret_references_admit_only_stable_principals() -> None:
    reference = user_iqm_secret_reference("nqx.user-1")

    assert reference == "secret://iqm-user/nqx.user-1"
    assert principal_from_user_iqm_secret_reference(reference) == "nqx.user-1"
    with pytest.raises(IQMCredentialVaultError, match="identity is invalid"):
        user_iqm_secret_reference("nqx/user")
    with pytest.raises(IQMCredentialVaultError, match="not admitted"):
        principal_from_user_iqm_secret_reference("secret://env/IQM_TOKEN")
