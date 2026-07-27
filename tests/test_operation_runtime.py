from __future__ import annotations

import copy
import json
import stat
import subprocess
from pathlib import Path

import pytest
import yaml

from qhpc_ecosystem import cli
from qhpc_ecosystem.contract import (
    ContractError,
    load_document,
    validate_contract_data,
)
from qhpc_ecosystem.operation_runtime import (
    OperationRuntimeError,
    apptainer_build_command,
    file_digest,
    oci_build_command,
    prepare_build_context,
    source_archive_digest,
    verify_runtime_definition,
)


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "containers/operations/qasmtrans/runtime.yaml"
RECIPE = ROOT / "containers/operations/qasmtrans/Containerfile"
ENTRYPOINT = ROOT / "containers/operations/qasmtrans/entrypoint.sh"
REPOSITORY_RUNTIMES = (
    ROOT / "containers/operations/qasmtrans/runtime.yaml",
    ROOT / "containers/operations/stabsim/runtime.yaml",
    ROOT / "containers/operations/nwqec/runtime.yaml",
    ROOT / "containers/operations/ftprimitivebench/runtime.yaml",
    ROOT / "containers/operations/lightstim/runtime.yaml",
)


def _commit_source(path: Path) -> str:
    path.mkdir()
    (path / "source.cpp").write_text("int main() { return 0; }\n", encoding="ascii")
    subprocess.run(["git", "-C", str(path), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(path), "add", "source.cpp"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(path),
            "-c",
            "user.name=QHPC Test",
            "-c",
            "user.email=qhpc@example.invalid",
            "commit",
            "-q",
            "-m",
            "runtime source",
        ],
        check=True,
    )
    return subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _runtime_fixture(tmp_path: Path) -> tuple[Path, Path]:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    source = tmp_path / "source"
    revision = _commit_source(source)
    source_date_epoch = int(
        subprocess.run(
            ["git", "-C", str(source), "show", "-s", "--format=%ct", revision],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    recipe = workspace / "Containerfile"
    entrypoint = workspace / "entrypoint.sh"
    fixture = workspace / "fixture.txt"
    builder_digest = "sha256:" + "a" * 64
    runtime_digest = "sha256:" + "b" * 64
    builder = f"docker.io/library/gcc:test@{builder_digest}"
    runtime = f"docker.io/library/debian:test@{runtime_digest}"
    recipe.write_text(
        f"FROM {builder} AS build\nFROM {runtime}\n",
        encoding="ascii",
    )
    entrypoint.write_text("#!/bin/sh\nexit 0\n", encoding="ascii")
    fixture.write_text("fixture\n", encoding="ascii")
    document = {
        "api_version": "qhpc/v1",
        "kind": "OperationRuntime",
        "metadata": {
            "id": "test-operation-linux-amd64",
            "name": "Test operation runtime",
            "version": "0.1.0",
            "component": "test-component",
            "capability": "test-capability",
            "operation": "execute",
            "project": "software-engineering",
            "owners": ["qhpc-ecosystem"],
            "source": {
                "url": "https://example.invalid/source.git",
                "revision": revision,
            },
            "status": "build-ready",
            "evidence": [],
        },
        "spec": {
            "packaging": "oci-to-apptainer",
            "platform": {"os": "linux", "architecture": "amd64"},
            "build": {
                "recipe": {
                    "path": "Containerfile",
                    "digest": file_digest(recipe),
                },
                "source_archive": {
                    "filename": "source.tar",
                    "format": "git-archive-tar",
                    "digest": source_archive_digest(source, revision),
                    "source_date_epoch": source_date_epoch,
                },
                "context_files": [
                    {
                        "source": "entrypoint.sh",
                        "destination": "entrypoint.sh",
                        "digest": file_digest(entrypoint),
                        "mode": "0755",
                    }
                ],
                "builder": {"reference": builder, "digest": builder_digest},
                "runtime_base": {
                    "reference": runtime,
                    "digest": runtime_digest,
                },
                "network": "disabled",
            },
            "execution": {
                "entrypoint": ["/opt/test"],
                "working_directory": "/work",
                "network": "disabled",
                "read_only_root": True,
                "mounts": [
                    {
                        "name": "test-input",
                        "kind": "input",
                        "path": "/inputs",
                        "mode": "ro",
                    },
                    {
                        "name": "test-output",
                        "kind": "output",
                        "path": "/outputs",
                        "mode": "rw",
                    },
                ],
                "ports": {
                    "inputs": {"input": "/inputs/fixture.txt"},
                    "outputs": {"result": "/outputs/result.txt"},
                },
                "parameters": {},
            },
            "verification": {
                "fixture": {
                    "path": "fixture.txt",
                    "digest": file_digest(fixture),
                    "mount_path": "/inputs/fixture.txt",
                },
                "arguments": [],
                "expected_outputs": [{"path": "/outputs/result.txt", "nonempty": True}],
                "timeout_seconds": 10,
            },
            "release": {"status": "unpublished"},
        },
    }
    manifest = workspace / "runtime.yaml"
    manifest.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    return manifest, source


def test_qasmtrans_runtime_definition_and_recipe_are_pinned() -> None:
    document = verify_runtime_definition(RUNTIME)
    assert document["metadata"]["status"] == "oci-smoke-tested"
    recipe = RECIPE.read_text(encoding="utf-8")
    entrypoint = ENTRYPOINT.read_text(encoding="utf-8")
    assert "apt-get" not in recipe
    assert "curl " not in recipe
    assert "git clone" not in recipe
    assert "USER 65532:65532" in recipe
    assert 'ENTRYPOINT ["/opt/qhpc/bin/qhpc-qasmtrans"]' in recipe
    assert 'if [ "$#" -ne 0 ]' in entrypoint
    assert "-m ibmq" in entrypoint
    assert "ibmq_toronto.json" in entrypoint


@pytest.mark.parametrize("runtime", REPOSITORY_RUNTIMES)
def test_repository_operation_runtime_definitions_are_pinned(
    runtime: Path,
) -> None:
    document = verify_runtime_definition(runtime)
    assert document["metadata"]["status"] in {
        "build-ready",
        "oci-smoke-tested",
    }
    assert document["spec"]["build"]["network"] == "disabled"
    assert document["spec"]["execution"]["network"] == "disabled"
    assert document["spec"]["execution"]["read_only_root"] is True
    assert document["spec"]["release"]["status"] == "unpublished"


def test_operation_runtime_rejects_mutable_or_incomplete_releases() -> None:
    document = copy.deepcopy(load_document(RUNTIME))
    document["spec"]["build"]["builder"]["reference"] = "docker.io/library/gcc:latest"
    with pytest.raises(ContractError) as error:
        validate_contract_data("operation-runtime", document)
    assert "base image reference must end with its digest" in str(error.value)
    assert "mutable ':latest' references are forbidden" in str(error.value)

    document = copy.deepcopy(load_document(RUNTIME))
    document["metadata"]["status"] = "target-accepted"
    document["metadata"]["evidence"] = ["docs/evidence/target.md"]
    document["spec"]["release"]["status"] = "target-accepted"
    with pytest.raises(ContractError, match="is required for a published runtime"):
        validate_contract_data("operation-runtime", document)

    document = copy.deepcopy(load_document(RUNTIME))
    document["spec"]["verification"]["expected_outputs"][0]["path"] = (
        "/outputs/../escape.qasm"
    )
    with pytest.raises(ContractError, match="normalized container path"):
        validate_contract_data("operation-runtime", document)


def test_prepare_build_context_is_pinned_and_deterministic(tmp_path: Path) -> None:
    manifest, source = _runtime_fixture(tmp_path)
    first = prepare_build_context(
        manifest,
        source,
        tmp_path / "context-one",
        workspace_root=manifest.parent,
    )
    second = prepare_build_context(
        manifest,
        source,
        tmp_path / "context-two",
        workspace_root=manifest.parent,
    )
    assert first.source_archive_digest == second.source_archive_digest
    assert (first.path / "source.tar").read_bytes() == (
        second.path / "source.tar"
    ).read_bytes()
    assert (
        json.loads((first.path / "qhpc-build.json").read_text())[
            "source_archive_digest"
        ]
        == first.source_archive_digest
    )
    assert stat.S_IMODE((first.path / "entrypoint.sh").stat().st_mode) == 0o755

    document = load_document(manifest)
    command = oci_build_command(
        document,
        first.path,
        "qhpc/test-operation:fixture",
        builder="/usr/bin/docker",
    )
    assert command[:5] == [
        "/usr/bin/docker",
        "build",
        "--platform",
        "linux/amd64",
        "--network",
    ]
    assert "none" in command
    assert "--provenance=false" in command
    assert f"SOURCE_DATE_EPOCH={first.source_date_epoch}" in command

    (first.path / "entrypoint.sh").write_text("#!/bin/sh\nexit 1\n", encoding="ascii")
    with pytest.raises(OperationRuntimeError, match="digest mismatch"):
        oci_build_command(
            document,
            first.path,
            "qhpc/test-operation:fixture",
            builder="/usr/bin/docker",
        )


def test_runtime_without_inputs_does_not_require_a_fixture(tmp_path: Path) -> None:
    manifest, source = _runtime_fixture(tmp_path)
    document = load_document(manifest)
    execution = document["spec"]["execution"]
    execution["mounts"] = [
        mount for mount in execution["mounts"] if mount["kind"] != "input"
    ]
    execution["ports"]["inputs"] = {}
    document["spec"]["verification"].pop("fixture")
    manifest.write_text(
        yaml.safe_dump(document, sort_keys=False),
        encoding="utf-8",
    )

    verified = verify_runtime_definition(manifest, manifest.parent)
    assert verified["spec"]["execution"]["ports"]["inputs"] == {}
    context = prepare_build_context(
        manifest,
        source,
        tmp_path / "no-input-context",
        workspace_root=manifest.parent,
    )
    assert context.path.is_dir()


def test_prepare_build_context_requires_exact_dependency_cache(
    tmp_path: Path,
) -> None:
    manifest, source = _runtime_fixture(tmp_path)
    cache = tmp_path / "dependency-cache"
    cache.mkdir()
    dependency = cache / "runtime-dependency.whl"
    dependency.write_bytes(b"pinned runtime wheel\n")
    document = load_document(manifest)
    document["spec"]["build"]["dependency_archives"] = [
        {
            "filename": dependency.name,
            "url": "https://packages.example.invalid/runtime-dependency.whl",
            "digest": file_digest(dependency),
        }
    ]
    manifest.write_text(
        yaml.safe_dump(document, sort_keys=False),
        encoding="utf-8",
    )

    with pytest.raises(OperationRuntimeError, match="dependency cache"):
        prepare_build_context(
            manifest,
            source,
            tmp_path / "missing-cache-context",
            workspace_root=manifest.parent,
        )

    prepared = prepare_build_context(
        manifest,
        source,
        tmp_path / "dependency-context",
        workspace_root=manifest.parent,
        dependency_cache=cache,
    )
    assert (prepared.path / dependency.name).read_bytes() == dependency.read_bytes()
    metadata = json.loads((prepared.path / "qhpc-build.json").read_text())
    assert metadata["dependency_archives"][0]["digest"] == file_digest(dependency)


def test_runtime_definition_detects_context_drift(tmp_path: Path) -> None:
    manifest, _source = _runtime_fixture(tmp_path)
    (manifest.parent / "entrypoint.sh").write_text(
        "#!/bin/sh\nexit 1\n", encoding="ascii"
    )
    with pytest.raises(OperationRuntimeError, match="digest mismatch"):
        verify_runtime_definition(manifest, manifest.parent)


def test_apptainer_command_requires_an_immutable_source(tmp_path: Path) -> None:
    digest = "sha256:" + "c" * 64
    command = apptainer_build_command(
        f"docker://registry.example/qhpc/test@{digest}",
        tmp_path / "test.sif",
        fakeroot=True,
    )
    assert command[:3] == ["apptainer", "build", "--fakeroot"]
    assert command[-1].endswith(digest)

    with pytest.raises(OperationRuntimeError, match="immutable"):
        apptainer_build_command(
            "docker://registry.example/qhpc/test:latest",
            tmp_path / "test.sif",
        )


def test_operation_runtime_cli_verifies_repository_manifest(capsys) -> None:
    assert cli.main(["operation-runtime", "verify", str(RUNTIME)]) == 0
    assert "qasmtrans-transpile-linux-amd64@0.1.0" in capsys.readouterr().out
