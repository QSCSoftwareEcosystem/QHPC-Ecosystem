from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from qhpc_ecosystem.repository_updates import (
    RepositoryUpdateError,
    RepositoryUpdateManager,
    split_repository_source,
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


def commit(source: Path, content: str) -> str:
    (source / "tool.txt").write_text(content, encoding="utf-8")
    git("add", "tool.txt", cwd=source)
    git("commit", "-m", content, cwd=source)
    return git("rev-parse", "HEAD", cwd=source)


def documents(
    repository: Path,
    revision: str,
    *,
    release_repository: Path | None = None,
) -> tuple[dict, dict]:
    repository_metadata = {
        "url": str(release_repository or repository),
        "revision": revision,
    }
    if release_repository is not None:
        repository_metadata["canonical_url"] = str(repository)
    registry = {
        "spec": {
            "entries": [
                {
                    "catalog_repository": "example-tool",
                    "capability": {
                        "metadata": {
                            "id": "example-capability",
                            "repository": repository_metadata,
                        },
                        "spec": {"operations": [{"id": "run"}]},
                    },
                }
            ]
        }
    }
    profile = {
        "spec": {
            "components": [
                {
                    "id": "example",
                    "name": "Example Tool",
                    "role": "operation-provider",
                    "catalog_repository": "example-tool",
                    "source": {"url": str(repository)},
                }
            ]
        }
    }
    return registry, profile


def test_repository_updates_check_and_stage_exact_revision(tmp_path: Path) -> None:
    source = tmp_path / "source"
    git("init", "--initial-branch=main", str(source))
    git("config", "user.name", "QHPC Test", cwd=source)
    git("config", "user.email", "qhpc@example.invalid", cwd=source)
    current = commit(source, "current")
    registry, profile = documents(source, current)
    manager = RepositoryUpdateManager(
        registry,
        profile,
        workspace_root=tmp_path,
        state_root=".qhpc/updates",
    )

    initial = manager.list()["items"][0]
    assert initial["status"] == "not-checked"
    assert initial["activation"] == "rebuild-required"

    candidate = commit(source, "candidate")
    checked = manager.check()["items"][0]
    assert checked["status"] == "update-available", checked["error"]
    assert checked["latest_revision"] == candidate

    staged = manager.stage("example", candidate)
    assert staged["status"] == "prepared"
    assert staged["staged_revision"] == candidate
    checkout = tmp_path / staged["checkout"]
    assert git("rev-parse", "HEAD", cwd=checkout) == candidate
    assert git("status", "--porcelain", cwd=checkout) == ""

    reloaded = RepositoryUpdateManager(
        registry,
        profile,
        workspace_root=tmp_path,
        state_root=".qhpc/updates",
    )
    assert reloaded.list()["items"][0]["status"] == "prepared"
    released = reloaded.discard("example")
    assert released["status"] == "update-available"
    assert released["staged_revision"] is None


def test_repository_updates_reject_stale_candidate(tmp_path: Path) -> None:
    source = tmp_path / "source"
    git("init", "--initial-branch=main", str(source))
    git("config", "user.name", "QHPC Test", cwd=source)
    git("config", "user.email", "qhpc@example.invalid", cwd=source)
    current = commit(source, "current")
    registry, profile = documents(source, current)
    candidate = commit(source, "candidate")
    manager = RepositoryUpdateManager(
        registry,
        profile,
        workspace_root=tmp_path,
    )

    with pytest.raises(
        RepositoryUpdateError,
        match="no longer the tracked remote revision",
    ):
        manager.stage("example", current)
    assert manager.check()["items"][0]["latest_revision"] == candidate


def test_repository_tree_url_tracks_explicit_branch() -> None:
    repository, tracked_ref = split_repository_source(
        "https://github.com/pnnl/NWQ-Sim/tree/tn_sim"
    )

    assert repository == "https://github.com/pnnl/NWQ-Sim"
    assert tracked_ref == "refs/heads/tn_sim"


def test_repository_updates_track_canonical_repo_from_older_release_source(
    tmp_path: Path,
) -> None:
    release = tmp_path / "release"
    canonical = tmp_path / "canonical"
    for source in (release, canonical):
        git("init", "--initial-branch=main", str(source))
        git("config", "user.name", "QHPC Test", cwd=source)
        git("config", "user.email", "qhpc@example.invalid", cwd=source)
    current = commit(release, "current release")
    candidate = commit(canonical, "canonical candidate")
    registry, profile = documents(
        canonical,
        current,
        release_repository=release,
    )
    manager = RepositoryUpdateManager(
        registry,
        profile,
        workspace_root=tmp_path,
    )

    initial = manager.list()["items"][0]
    assert initial["repository_url"] == str(canonical)
    assert initial["current_repository_url"] == str(release)
    checked = manager.check()["items"][0]
    assert checked["status"] == "update-available"
    assert checked["latest_revision"] == candidate
    staged = manager.stage("example", candidate)
    assert staged["status"] == "prepared"
    assert git("rev-parse", "HEAD", cwd=tmp_path / staged["checkout"]) == candidate
