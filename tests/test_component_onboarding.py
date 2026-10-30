from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from qhpc_ecosystem.component_onboarding import (
    ComponentOnboardingError,
    ComponentOnboardingManager,
    normalise_public_repository_url,
)


def git(*arguments: str, cwd: Path | None = None) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=cwd,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.stdout.strip()


def source_repository(tmp_path: Path) -> tuple[Path, str]:
    source = tmp_path / "source"
    git("init", "--initial-branch=main", str(source))
    git("config", "user.name", "QHPC Test", cwd=source)
    git("config", "user.email", "qhpc@example.invalid", cwd=source)
    (source / "pyproject.toml").write_text("[project]\nname = 'sample'\n", encoding="utf-8")
    (source / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    (source / "src").mkdir()
    (source / "src" / "qasm_transpiler.py").write_text(
        "raise RuntimeError('repository code must not run during inspection')\n",
        encoding="utf-8",
    )
    git("add", ".", cwd=source)
    git("commit", "-m", "add compiler source", cwd=source)
    return source, git("rev-parse", "HEAD", cwd=source)


def test_component_onboarding_resolves_an_immutable_public_source_without_execution(
    tmp_path: Path,
) -> None:
    source, revision = source_repository(tmp_path)
    manager = ComponentOnboardingManager(
        workspace_root=tmp_path,
        allow_local_sources=True,
        allowed_hosts=frozenset(),
    )

    draft = manager.inspect(
        str(source),
        ref="main",
        template="compiler-transpiler",
    )

    assert draft["status"] == "inspected"
    assert draft["source"]["resolved_revision"] == revision
    assert draft["source"]["requested_ref"] == "refs/heads/main"
    assert draft["inspection"]["executed_repository_code"] is False
    assert draft["inspection"]["host_credentials_exposed"] is False
    assert "compiler-transpiler" in draft["inspection"]["detected_templates"]
    assert draft["draft"]["template"] == "compiler-transpiler"
    assert draft["draft"]["build_recipe"]["state"] == "not-run"
    assert draft["activation"]["state"] == "blocked"
    assert manager.list()["items"][0]["id"] == draft["id"]
    assert (tmp_path / ".qhpc" / "component-onboarding" / "state.json").is_file()
    assert not list((tmp_path / ".qhpc" / "component-onboarding").glob("**/qasm_transpiler.py"))

    edited = manager.update_draft(
        draft["id"],
        {
            "template": "simulator",
            "capability_id": "qasm-simulator",
            "operation_id": "simulate",
            "input_artifact": "qhpc.quantum-circuit@1",
            "output_artifact": "qhpc.measurement-counts@1",
        },
    )
    assert edited["draft"]["template"] == "simulator"
    assert edited["draft"]["capability_interface"] == {
        "id": "qasm-simulator",
        "version": "0.1.0-draft",
        "operation_id": "simulate",
        "input_artifact": "qhpc.quantum-circuit@1",
        "output_artifact": "qhpc.measurement-counts@1",
    }
    with pytest.raises(ComponentOnboardingError, match="versioned artifact"):
        manager.update_draft(draft["id"], {"input_artifact": "not-versioned"})


def test_component_onboarding_rejects_credentialed_and_unadmitted_urls() -> None:
    with pytest.raises(ComponentOnboardingError, match="credentials"):
        normalise_public_repository_url("https://token@example.com/org/repo")
    with pytest.raises(ComponentOnboardingError, match="not admitted"):
        normalise_public_repository_url("https://example.invalid/org/repo")
    with pytest.raises(ComponentOnboardingError, match="exactly one owner"):
        normalise_public_repository_url("https://github.com/org/repo/tree/main")
