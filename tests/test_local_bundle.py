from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from qhpc_ecosystem import cli
from qhpc_ecosystem.contract import load_document
from qhpc_ecosystem.engine import WorkflowEngine
from qhpc_ecosystem.local_bundle import export_local_state, import_local_state
from qhpc_ecosystem.local_release import LocalPaths, LocalReleaseError
from test_engine import make_runner
from test_workflow import example_registry


ROOT = Path(__file__).resolve().parents[1]


def populated_home(root: Path) -> tuple[LocalPaths, WorkflowEngine, str]:
    paths = LocalPaths.discover(root)
    engine = WorkflowEngine(paths.database, paths.artifact_root)
    workflow = load_document(ROOT / "examples/contracts/valid/workflow.yaml")
    engine.create_workflow_draft(workflow, created_by="test-user")
    registered = engine.register_workflow(
        workflow,
        example_registry(),
        created_by="test-user",
    )
    run = engine.submit_run(
        registered["id"],
        registered["version"],
        inputs={},
        execution_target="local-development",
        created_by="test-user",
    )
    assert engine.run_until_idle(make_runner()) == 2
    return paths, engine, run["id"]


def test_portable_bundle_round_trips_logical_state_and_artifacts(
    tmp_path: Path,
) -> None:
    source_paths, source_engine, run_id = populated_home(tmp_path / "source")
    bundle = tmp_path / "exports" / "research-state.eqo"

    export_report = export_local_state(
        source_paths,
        release_version="0.1.0",
        destination=bundle,
    )

    assert Path(export_report["path"]) == bundle
    assert export_report["checksum"].startswith("sha256:")
    assert export_report["counts"]["runs"] == 1
    assert export_report["counts"]["artifact_payloads"] == 2

    target_paths = LocalPaths.discover(tmp_path / "target")
    import_report = import_local_state(target_paths, bundle)
    target_engine = WorkflowEngine(target_paths.database, target_paths.artifact_root)

    assert import_report["backup"] is None
    assert target_engine.export_portable_state() == source_engine.export_portable_state()
    assert target_engine.get_run(run_id)["state"] == "succeeded"
    for artifact in target_engine.list_artifacts():
        metadata, content, _name = target_engine.read_artifact_content(artifact["id"])
        assert metadata["checksum"].startswith("sha256:")
        assert content
        assert str(target_paths.artifact_root) in metadata["uri"]


def test_import_rejects_tampered_artifact_payload(tmp_path: Path) -> None:
    source_paths, _engine, _run_id = populated_home(tmp_path / "source")
    original = Path(
        export_local_state(
            source_paths,
            release_version="0.1.0",
            destination=tmp_path / "original.eqo",
        )["path"]
    )
    tampered = tmp_path / "tampered.eqo"

    with zipfile.ZipFile(original, "r") as source, zipfile.ZipFile(
        tampered, "w", compression=zipfile.ZIP_DEFLATED
    ) as target:
        for info in source.infolist():
            content = source.read(info)
            if info.filename.startswith("artifacts/"):
                content += b"tampered"
            target.writestr(info.filename, content)

    with pytest.raises(LocalReleaseError, match="artifact (size|checksum) mismatch"):
        import_local_state(LocalPaths.discover(tmp_path / "target"), tampered)


def test_import_requires_replace_and_keeps_automatic_backup(tmp_path: Path) -> None:
    source_paths, source_engine, _run_id = populated_home(tmp_path / "source")
    bundle = Path(
        export_local_state(
            source_paths,
            release_version="0.1.0",
            destination=tmp_path / "state.eqo",
        )["path"]
    )
    target_paths = LocalPaths.discover(tmp_path / "target")
    target_engine = WorkflowEngine(target_paths.database, target_paths.artifact_root)
    previous = target_engine.register_input_artifact(
        artifact_type="qhpc.quantum-circuit@1",
        content=b"OPENQASM 2.0;\n",
        name="previous.qasm",
        created_by="test-user",
    )

    with pytest.raises(LocalReleaseError, match="--replace"):
        import_local_state(target_paths, bundle)
    assert target_engine.get_artifact(previous["id"])["name"] == "previous.qasm"

    report = import_local_state(target_paths, bundle, replace=True)
    backup = Path(report["backup"])
    restored = WorkflowEngine(target_paths.database, target_paths.artifact_root)

    assert (backup / "workbench.sqlite").is_file()
    assert (backup / "artifacts").is_dir()
    assert restored.export_portable_state() == source_engine.export_portable_state()


def test_export_refuses_nonterminal_runs(tmp_path: Path) -> None:
    paths = LocalPaths.discover(tmp_path / "source")
    engine = WorkflowEngine(paths.database, paths.artifact_root)
    workflow = load_document(ROOT / "examples/contracts/valid/workflow.yaml")
    registered = engine.register_workflow(
        workflow,
        example_registry(),
        created_by="test-user",
    )
    engine.submit_run(
        registered["id"],
        registered["version"],
        inputs={},
        execution_target="local-development",
        created_by="test-user",
    )

    with pytest.raises(LocalReleaseError, match="terminal runs"):
        export_local_state(
            paths,
            release_version="0.1.0",
            destination=tmp_path / "active.eqo",
        )


def test_cli_exposes_portable_export_and_import(tmp_path: Path, capsys) -> None:
    source = tmp_path / "source"
    paths = LocalPaths.discover(source)
    WorkflowEngine(paths.database, paths.artifact_root)
    bundle = tmp_path / "empty.eqo"

    assert (
        cli.main(
            [
                "local",
                "export",
                str(bundle),
                "--home",
                str(source),
            ]
        )
        == 0
    )
    assert "EQO Local export:" in capsys.readouterr().out

    assert (
        cli.main(
            [
                "local",
                "import",
                str(bundle),
                "--home",
                str(tmp_path / "target"),
            ]
        )
        == 0
    )
    assert "EQO Local import restored:" in capsys.readouterr().out
