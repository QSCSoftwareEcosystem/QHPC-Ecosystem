#!/usr/bin/env python3
"""Create or verify the populated state bundle used by the cross-OS release gate."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from qhpc_ecosystem.contract import document_digest, load_document
from qhpc_ecosystem.engine import (
    ArtifactResult,
    FunctionRunner,
    TaskRequest,
    TaskResult,
    WorkflowEngine,
)
from qhpc_ecosystem.local_bundle import export_local_state, import_local_state
from qhpc_ecosystem.local_release import LocalPaths


ROOT = Path(__file__).resolve().parents[1]


def _registry() -> dict:
    capability = load_document(ROOT / "examples/contracts/valid/capability.yaml")
    return {
        "api_version": "qhpc/v1",
        "kind": "Registry",
        "metadata": {
            "entry_count": 1,
            "catalog_digest": "sha256:" + "a" * 64,
        },
        "spec": {
            "entries": [
                {
                    "descriptor_digest": document_digest(capability),
                    "catalog_repository": "cross-platform-release-gate",
                    "validation": {
                        "contract": "valid",
                        "attribution": "valid",
                        "authority": "ecosystem",
                        "curated_by": ["qhpc-ecosystem"],
                        "project_reviewed": False,
                        "runtime": "declared",
                        "documentation": "linked",
                        "status": "contract-valid",
                        "evidence": ["tools/verify_cross_platform_bundle.py"],
                    },
                    "capability": capability,
                }
            ]
        },
    }


def _runner() -> FunctionRunner:
    runner = FunctionRunner()

    def generate(request: TaskRequest) -> TaskResult:
        output = request.work_directory / "circuit.qasm"
        output.write_text(
            f"OPENQASM 2.0;\nqreg q[{request.parameters['qubits']}];\n",
            encoding="utf-8",
        )
        return TaskResult(
            {
                "circuit": ArtifactResult.from_path(
                    request.output_types["circuit"], output
                )
            },
            "generated cross-platform circuit",
        )

    def simulate(request: TaskRequest) -> TaskResult:
        output = request.work_directory / "results.json"
        output.write_text(
            json.dumps(
                {
                    "input_checksum": request.inputs["circuit"]["checksum"],
                    "shots": request.parameters["shots"],
                    "counts": {"0": request.parameters["shots"]},
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        return TaskResult(
            {
                "results": ArtifactResult.from_path(
                    request.output_types["results"], output
                )
            },
            "simulated cross-platform circuit",
        )

    runner.register("example-toolkit", "generate", generate)
    runner.register("example-toolkit", "simulate", simulate)
    return runner


def create_bundle(destination: Path) -> dict:
    destination = destination.expanduser().resolve()
    with tempfile.TemporaryDirectory(prefix="eqo-cross-platform-export-") as name:
        paths = LocalPaths.discover(Path(name) / "home")
        engine = WorkflowEngine(paths.database, paths.artifact_root)
        workflow = load_document(ROOT / "examples/contracts/valid/workflow.yaml")
        engine.create_workflow_draft(workflow, created_by="release-gate")
        registered = engine.register_workflow(
            workflow,
            _registry(),
            created_by="release-gate",
        )
        run = engine.submit_run(
            registered["id"],
            registered["version"],
            inputs={},
            execution_target="local-development",
            created_by="release-gate",
        )
        if engine.run_until_idle(_runner()) != 2:
            raise RuntimeError("cross-platform fixture did not execute both tasks")
        if engine.get_run(run["id"])["state"] != "succeeded":
            raise RuntimeError("cross-platform fixture run did not succeed")
        return export_local_state(
            paths,
            release_version="0.1.0",
            destination=destination,
            overwrite=True,
        )


def verify_bundle(bundle: Path) -> dict:
    bundle = bundle.expanduser().resolve()
    with tempfile.TemporaryDirectory(prefix="eqo-cross-platform-import-") as name:
        paths = LocalPaths.discover(Path(name) / "home")
        report = import_local_state(paths, bundle)
        engine = WorkflowEngine(paths.database, paths.artifact_root)
        state = engine.export_portable_state()
        expected_counts = {
            "workflow_versions": 1,
            "workflow_drafts": 1,
            "runs": 1,
            "tasks": 2,
            "task_attempts": 2,
            "input_artifacts": 0,
            "output_artifacts": 2,
            "artifact_payloads": 2,
        }
        for key, expected in expected_counts.items():
            if report["counts"].get(key) != expected:
                raise RuntimeError(
                    f"cross-platform import count mismatch for {key}: "
                    f"{report['counts'].get(key)} != {expected}"
                )
        if state["runs"][0]["state"] != "succeeded":
            raise RuntimeError("cross-platform imported run is not succeeded")
        for artifact in engine.list_artifacts():
            metadata, content, _name = engine.read_artifact_content(artifact["id"])
            if not metadata["checksum"].startswith("sha256:") or not content:
                raise RuntimeError("cross-platform artifact verification failed")
        return report


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export")
    export.add_argument("bundle", type=Path)
    import_command = commands.add_parser("import")
    import_command.add_argument("bundle", type=Path)
    args = parser.parse_args()

    if args.command == "export":
        report = create_bundle(args.bundle)
        print(
            "Cross-platform EQO state exported: "
            f"{report['counts']['runs']} run, "
            f"{report['counts']['artifact_payloads']} artifacts, "
            f"{report['checksum']}"
        )
    else:
        report = verify_bundle(args.bundle)
        print(
            "Cross-platform EQO state imported and verified: "
            f"{report['counts']['runs']} run, "
            f"{report['counts']['artifact_payloads']} artifacts"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
