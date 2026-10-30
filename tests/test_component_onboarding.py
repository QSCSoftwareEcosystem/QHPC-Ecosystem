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


def test_component_onboarding_records_isolated_build_and_smoke_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, revision = source_repository(tmp_path)
    manager = ComponentOnboardingManager(
        workspace_root=tmp_path,
        allow_local_sources=True,
        allowed_hosts=frozenset(),
    )
    draft = manager.inspect(str(source), template="container-cli")
    observed: dict[str, object] = {}

    def fake_isolated_build(
        received_draft: dict,
        checkout: Path,
    ) -> dict:
        observed["draft_id"] = received_draft["id"]
        observed["checkout_revision"] = git("rev-parse", "HEAD", cwd=checkout)
        observed["repository_code"] = (checkout / "src" / "qasm_transpiler.py").read_text(
            encoding="utf-8"
        )
        return {
            "state": "succeeded",
            "finished_at": "2026-10-30T12:00:00Z",
            "isolation": "network-disabled container build; no host credentials",
            "logs": "isolated build completed",
            "detected_entrypoints": ["Dockerfile"],
            "image_digest": "sha256:" + "a" * 64,
            "produced_artifacts": [
                {
                    "kind": "oci-image",
                    "reference": "eqo-onboarding/example:abcdef123456",
                    "digest": "sha256:" + "a" * 64,
                }
            ],
            "smoke_test": {"state": "passed", "command": ["--help"], "exit_code": 0},
        }

    monkeypatch.setattr(manager, "_run_isolated_build", fake_isolated_build)
    built = manager.build(draft["id"])

    assert observed["draft_id"] == draft["id"]
    assert observed["checkout_revision"] == revision
    assert "repository code must not run" in str(observed["repository_code"])
    assert built["status"] == "built"
    assert built["build"]["smoke_test"]["state"] == "passed"
    assert built["draft"]["build_recipe"]["image_digest"] == "sha256:" + "a" * 64
    assert built["activation"]["state"] == "ready-for-admission"
    assert not list((tmp_path / ".qhpc" / "component-onboarding" / "builds").glob("**/qasm_transpiler.py"))

    activated = manager.activate(draft["id"])

    assert activated["status"] == "active"
    assert activated["activation"]["state"] == "active-local"
    event = activated["lifecycle"][-1]
    assert event["at"].endswith("Z")
    assert {key: value for key, value in event.items() if key != "at"} == {
        "action": "activated",
        "source_revision": revision,
        "image_digest": "sha256:" + "a" * 64,
        "replaces": None,
    }
    listing = manager.list()
    assert listing["active_components"]["source"]["draft_id"] == draft["id"]
    assert listing["active_components"]["source"]["source_revision"] == revision
    with pytest.raises(ComponentOnboardingError, match="active component revision is immutable"):
        manager.update_draft(draft["id"], {"operation_id": "different"})

    git("commit", "--allow-empty", "-m", "new candidate", cwd=source)
    successor = manager.inspect(str(source), template="container-cli")
    manager.build(successor["id"])
    manager.activate(successor["id"])
    assert next(
        item for item in manager.list()["items"] if item["id"] == draft["id"]
    )["activation"]["state"] == "retained"

    rolled_back = manager.activate(draft["id"])
    assert rolled_back["status"] == "active"
    assert rolled_back["lifecycle"][-1]["action"] == "rolled-back"
    assert manager.list()["active_components"]["source"]["draft_id"] == draft["id"]


def test_component_onboarding_refreshes_to_a_separate_immutable_candidate(
    tmp_path: Path,
) -> None:
    source, current_revision = source_repository(tmp_path)
    manager = ComponentOnboardingManager(
        workspace_root=tmp_path,
        allow_local_sources=True,
        allowed_hosts=frozenset(),
    )
    draft = manager.inspect(str(source), ref="main", template="compiler-transpiler")

    assert manager.refresh(draft["id"])["refresh"]["state"] == "up-to-date"
    git("commit", "--allow-empty", "-m", "next candidate", cwd=source)
    next_revision = git("rev-parse", "HEAD", cwd=source)
    candidate = manager.refresh(draft["id"])

    assert candidate["id"] != draft["id"]
    assert candidate["source"]["resolved_revision"] == next_revision
    assert candidate["supersedes"] == {
        "draft_id": draft["id"],
        "resolved_revision": current_revision,
    }
    original = next(item for item in manager.list()["items"] if item["id"] == draft["id"])
    assert original["refresh"]["state"] == "update-available"
    assert original["superseded_by"] == candidate["id"]
