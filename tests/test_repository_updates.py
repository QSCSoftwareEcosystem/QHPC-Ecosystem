from __future__ import annotations

import json
import subprocess
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from qhpc_ecosystem import repository_updates
from qhpc_ecosystem.operation_runtime import file_digest, source_archive_digest
from qhpc_ecosystem.repository_updates import (
    RepositoryUpdateError,
    RepositoryUpdateDetector,
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


def candidate_rebuild_documents(
    workspace: Path,
    repository: Path,
    revision: str,
) -> tuple[dict, dict]:
    """Create one reviewed, local-only candidate-rebuild runtime contract."""
    repository_url = repository.as_uri()
    runtime_directory = workspace / "runtime-contracts"
    integration_directory = workspace / "integrations" / "example"
    runtime_directory.mkdir(parents=True)
    integration_directory.mkdir(parents=True)
    recipe = workspace / "Containerfile"
    entrypoint = workspace / "entrypoint.sh"
    fixture = workspace / "fixture.txt"
    builder_digest = "sha256:" + "a" * 64
    runtime_digest = "sha256:" + "b" * 64
    builder = f"docker.io/library/gcc:test@{builder_digest}"
    runtime = f"docker.io/library/debian:test@{runtime_digest}"
    recipe.write_text(
        f"FROM {builder} AS build\nFROM {runtime}\nARG SOURCE_REVISION\n",
        encoding="ascii",
    )
    entrypoint.write_text("#!/bin/sh\nexit 0\n", encoding="ascii")
    fixture.write_text("fixture\n", encoding="ascii")
    timestamp = int(git("show", "-s", "--format=%ct", revision, cwd=repository))
    runtime_document = {
        "api_version": "qhpc/v1",
        "kind": "OperationRuntime",
        "metadata": {
            "id": "example-runtime-linux-amd64",
            "name": "Example runtime",
            "version": "0.1.0",
            "component": "example",
            "capability": "example-capability",
            "operation": "run",
            "project": "software-engineering",
            "owners": ["qhpc-ecosystem"],
            "source": {"url": repository_url, "revision": revision},
            "status": "build-ready",
            "evidence": [],
        },
        "spec": {
            "packaging": "oci-to-apptainer",
            "platform": {"os": "linux", "architecture": "amd64"},
            "build": {
                "recipe": {"path": "Containerfile", "digest": file_digest(recipe)},
                "source_archive": {
                    "filename": "source.tar",
                    "format": "git-archive-tar",
                    "digest": source_archive_digest(repository, revision),
                    "source_date_epoch": timestamp,
                },
                "context_files": [{
                    "source": "entrypoint.sh",
                    "destination": "entrypoint.sh",
                    "digest": file_digest(entrypoint),
                    "mode": "0755",
                }],
                "candidate_rebuild": {"source_revision_build_arg": "SOURCE_REVISION"},
                "builder": {"reference": builder, "digest": builder_digest},
                "runtime_base": {"reference": runtime, "digest": runtime_digest},
                "network": "disabled",
            },
            "execution": {
                "entrypoint": ["/opt/test"],
                "working_directory": "/work",
                "network": "disabled",
                "read_only_root": True,
                "mounts": [
                    {"name": "input", "kind": "input", "path": "/inputs", "mode": "ro"},
                    {"name": "output", "kind": "output", "path": "/outputs", "mode": "rw"},
                ],
                "ports": {"inputs": {"input": "/inputs/fixture.txt"}, "outputs": {"result": "/outputs/result.txt"}},
                "parameters": {},
            },
            "verification": {
                "fixture": {"path": "fixture.txt", "digest": file_digest(fixture), "mount_path": "/inputs/fixture.txt"},
                "arguments": [],
                "expected_outputs": [{"path": "/outputs/result.txt", "nonempty": True}],
                "timeout_seconds": 10,
            },
            "release": {"status": "unpublished"},
        },
    }
    (runtime_directory / "example.yaml").write_text(
        yaml.safe_dump(runtime_document, sort_keys=False), encoding="utf-8"
    )
    integration = {
        "api_version": "qhpc/v1",
        "kind": "IntegrationScaffold",
        "metadata": {"id": "example", "name": "Example", "version": "0.1.0", "project": "software-engineering", "role": "operation-provider", "owners": ["qhpc-ecosystem"], "visibility": "internal", "integration_status": "published"},
        "spec": {
            "source": {"kind": "repository", "url": repository_url, "catalog_repository": "example-tool"},
            "mirror": {"status": "not-applicable"},
            "development_environment": {"status": "assigned", "class": "hpc-build"},
            "interfaces": ["cli"],
            "scope": {"status": "defined", "summary": "Test candidate build."},
            "deliverables": {"source_audit": "complete", "interface_contract": "complete", "adapter": "complete", "fixtures": "complete", "integration_tests": "complete", "registry_publication": "complete"},
            "contract_refs": ["runtime-contracts/example.yaml"],
            "evidence": ["docs/evidence/test.md"],
            "production_runtime": {"status": "deferred", "technology": "oci", "reason": "Test fixture."},
            "blockers": [],
        },
    }
    (integration_directory / "integration.yaml").write_text(
        yaml.safe_dump(integration, sort_keys=False), encoding="utf-8"
    )
    registry, profile = documents(repository, revision)
    registry["spec"]["entries"][0]["capability"]["metadata"]["repository"]["url"] = repository_url
    profile["spec"]["components"][0]["source"]["url"] = repository_url
    profile["spec"]["components"][0]["integration_scaffold"] = "integrations/example/integration.yaml"
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
    assert initial["current_runtimes"] == []

    candidate = commit(source, "candidate")
    checked = manager.check()["items"][0]
    assert checked["status"] == "update-available", checked["error"]
    assert checked["latest_revision"] == candidate

    staged = manager.stage("example", candidate)
    assert staged["status"] == "prepared"
    assert staged["staged_revision"] == candidate
    assert staged["candidate_commit"] == {
        "revision": candidate,
        "committed_at": staged["candidate_commit"]["committed_at"],
        "subject": "candidate",
    }
    assert [event["action"] for event in staged["history"][:2]] == [
        "prepared",
        "checked",
    ]
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
    assert released["history"][0]["action"] == "discarded"


def test_repository_update_candidate_build_records_isolated_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source"
    git("init", "--initial-branch=main", str(source))
    git("config", "user.name", "QHPC Test", cwd=source)
    git("config", "user.email", "qhpc@example.invalid", cwd=source)
    current = commit(source, "current")
    registry, profile = candidate_rebuild_documents(tmp_path, source, current)
    candidate = commit(source, "candidate")
    manager = RepositoryUpdateManager(
        registry,
        profile,
        workspace_root=tmp_path,
        state_root=".qhpc/updates",
    )
    assert manager.stage("example", candidate)["status"] == "prepared"

    def fake_prepare(manifest, checkout, destination, *, workspace_root):
        document = json.loads(Path(manifest).read_text(encoding="utf-8"))
        assert document["metadata"]["source"]["revision"] == candidate
        assert Path(checkout).name == candidate
        path = Path(destination)
        path.mkdir()
        return SimpleNamespace(
            path=path,
            source_archive_digest=document["spec"]["build"]["source_archive"]["digest"],
            source_date_epoch=document["spec"]["build"]["source_archive"]["source_date_epoch"],
        )

    monkeypatch.setattr(repository_updates, "prepare_build_context", fake_prepare)
    monkeypatch.setattr(
        repository_updates,
        "build_oci_image",
        lambda _document, _context, tag: SimpleNamespace(
            reference=tag,
            local_id="sha256:" + "c" * 64,
        ),
    )
    monkeypatch.setattr(
        repository_updates,
        "smoke_oci_image",
        lambda _manifest, _image, *, workspace_root: SimpleNamespace(
            duration_ms=17,
            outputs=(
                SimpleNamespace(
                    container_path="/outputs/result.txt",
                    digest="sha256:" + "d" * 64,
                    size=7,
                ),
            ),
        ),
    )

    built = manager.build("example")

    assert built["status"] == "built"
    assert built["candidate_build"]["state"] == "succeeded"
    assert built["candidate_build"]["activation"] == "not-activated"
    assert built["candidate_build"]["image"]["local_id"] == "sha256:" + "c" * 64
    assert built["candidate_build"]["smoke"]["outputs"] == [{
        "path": "/outputs/result.txt",
        "digest": "sha256:" + "d" * 64,
        "size": 7,
    }]
    assert built["history"][0]["action"] == "build-succeeded"
    candidate_contract = tmp_path / built["candidate_build"]["candidate_contract"]["path"]
    assert candidate_contract.is_file()
    candidate_document = json.loads(candidate_contract.read_text(encoding="utf-8"))
    assert candidate_document["metadata"]["source"]["revision"] == candidate
    active_document = yaml.safe_load(
        (tmp_path / "runtime-contracts" / "example.yaml").read_text(encoding="utf-8")
    )
    assert active_document["metadata"]["source"]["revision"] == current


def test_repository_updates_report_active_runtime_identity(tmp_path: Path) -> None:
    source = tmp_path / "source"
    git("init", "--initial-branch=main", str(source))
    git("config", "user.name", "QHPC Test", cwd=source)
    git("config", "user.email", "qhpc@example.invalid", cwd=source)
    current = commit(source, "current")
    registry, profile = documents(source, current)
    registry["spec"]["entries"][0]["capability"]["spec"]["operations"] = [
        {
            "id": "run",
            "runtime": {
                "type": "oci",
                "reference": "docker://example/tool@sha256:" + "d" * 64,
                "digest": "sha256:" + "d" * 64,
            },
        }
    ]

    item = RepositoryUpdateManager(
        registry,
        profile,
        workspace_root=tmp_path,
    ).list()["items"][0]

    assert item["current_runtimes"] == [
        {
            "type": "oci",
            "reference": "docker://example/tool@sha256:" + "d" * 64,
            "digest": "sha256:" + "d" * 64,
        }
    ]


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


def test_repository_update_detector_only_runs_check_callbacks() -> None:
    completed = threading.Event()
    calls: list[str] = []

    detector = RepositoryUpdateDetector(
        [lambda: calls.append("checked") or completed.set()],
    )

    assert detector.trigger() is True
    assert completed.wait(timeout=1)
    assert calls == ["checked"]
    status = detector.status()
    assert status["last_started_at"] is not None
    assert status["last_completed_at"] is not None
    assert status["last_error"] is None
    detector.stop()

    with pytest.raises(RepositoryUpdateError, match="at least 30"):
        RepositoryUpdateDetector([lambda: None], interval_seconds=1)
