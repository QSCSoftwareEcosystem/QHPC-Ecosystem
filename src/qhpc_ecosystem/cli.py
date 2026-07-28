"""Command-line interface for QHPC ecosystem environments."""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path
from typing import Sequence

from . import __version__
from .catalog import (
    Catalog,
    CatalogError,
    Repository,
    default_catalog_path,
    load_catalog,
)
from .contract import (
    CONTRACT_SCHEMAS,
    ContractError,
    contract_kinds,
    load_schema,
    validate_contract,
)
from .operation_runtime import OperationRuntimeError
from .registry import (
    RegistryError,
    build_registry,
    find_registry_entry,
    load_registry,
    registry_digest,
    registry_entries,
    write_registry,
)
from .slurm_test_cluster import SlurmTestClusterError
from . import runtime
from .sync import read_manifest, synchronize


def _csv(values: Sequence[str]) -> str:
    return ", ".join(values) if values else "none"


def _assignments(values: Sequence[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values:
        name, separator, item = value.partition("=")
        if not separator or not name or not item:
            raise ContractError(f"expected NAME=VALUE, received: {value}")
        result[name] = item
    return result


def _print_table(catalog: Catalog) -> None:
    columns = ("SLUG", "ENVIRONMENT", "STATUS", "ACCESS")
    rows = [
        (repo.slug, repo.environment, repo.container_status, repo.visibility)
        for repo in catalog.repositories
    ]
    widths = [
        max(len(columns[index]), *(len(row[index]) for row in rows))
        for index in range(4)
    ]
    print("  ".join(value.ljust(widths[index]) for index, value in enumerate(columns)))
    print("  ".join("-" * width for width in widths))
    for row in rows:
        print("  ".join(value.ljust(widths[index]) for index, value in enumerate(row)))


def _print_repository(repository: Repository) -> None:
    source = repository.source_url or "unresolved"
    print(f"Name:              {repository.display_name}")
    print(f"Slug:              {repository.slug}")
    print(f"QSC project:       {repository.qsc_project}")
    print(f"Role:              {repository.package_role}")
    print(f"Environment:       {repository.environment}")
    print(f"Container status:  {repository.container_status}")
    print(f"Visibility:        {repository.visibility}")
    print(f"Canonical status:  {repository.canonical_status}")
    print(f"Source:            {source}")
    if repository.alternate_sources:
        print(f"Alternate sources: {_csv(repository.alternate_sources)}")
    print(f"Capabilities:      {_csv(repository.capabilities)}")
    print(f"Hardware targets:  {_csv(repository.hardware_targets)}")
    print(f"Interfaces:        {_csv(repository.interfaces)}")
    if repository.local_path:
        print(f"Local path:        {repository.local_path}")
    print(f"Notes:             {repository.notes}")


def _require_runnable(repository: Repository) -> None:
    if repository.container_status == "blocked":
        raise CatalogError(
            f"{repository.slug} is blocked: {repository.notes} Resolve its catalog metadata first."
        )


def _image_dir(value: str | None) -> Path:
    return Path(value).expanduser().resolve() if value else runtime.default_image_dir()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="qhpc-ecosystem",
        description="Discover and enter QSC quantum-HPC development environments.",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument(
        "--catalog", default=str(default_catalog_path()), help="ecosystem catalog path"
    )
    parser.add_argument("--runtime", help="explicit Apptainer executable")
    parser.add_argument("--image-dir", help="directory for shared environment images")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    contract = subparsers.add_parser(
        "contract", help="inspect and validate QHPC integration contracts"
    )
    contract_subparsers = contract.add_subparsers(
        dest="contract_command", required=True
    )
    contract_subparsers.add_parser("list", help="list packaged contract schemas")
    contract_schema = contract_subparsers.add_parser(
        "schema", help="print a packaged JSON Schema"
    )
    contract_schema.add_argument("kind", choices=contract_kinds())
    contract_validate = contract_subparsers.add_parser(
        "validate", help="validate a YAML or JSON contract document"
    )
    contract_validate.add_argument("kind", choices=contract_kinds())
    contract_validate.add_argument("document")

    integration_parser = subparsers.add_parser(
        "integration", help="inspect pre-runtime component integration scaffolds"
    )
    integration_commands = integration_parser.add_subparsers(
        dest="integration_command", required=True
    )
    integration_validate = integration_commands.add_parser(
        "validate", help="validate all scaffolds selected by a deployment profile"
    )
    integration_list = integration_commands.add_parser(
        "list", help="list integration readiness without requiring runtimes"
    )
    integration_info = integration_commands.add_parser(
        "info", help="show one component integration scaffold"
    )
    for command in (integration_validate, integration_list, integration_info):
        command.add_argument(
            "profile", help="deployment profile containing scaffold paths"
        )
        command.add_argument(
            "--workspace-root",
            help="root used to resolve scaffold paths; defaults to the profile's project root",
        )
    integration_info.add_argument("component_id")

    registry_parser = subparsers.add_parser(
        "registry", help="build and inspect the federated capability registry"
    )
    registry_subparsers = registry_parser.add_subparsers(
        dest="registry_command", required=True
    )
    registry_build = registry_subparsers.add_parser(
        "build", help="build a registry from checked-out capability descriptors"
    )
    registry_build.add_argument(
        "--source",
        action="append",
        required=True,
        help="descriptor file or repository/release directory; repeat as needed",
    )
    registry_build.add_argument("--output", required=True)
    registry_validate = registry_subparsers.add_parser(
        "validate", help="validate a registry and its catalog ownership"
    )
    registry_validate.add_argument("registry")
    registry_list = registry_subparsers.add_parser(
        "list", help="list capabilities in a registry"
    )
    registry_list.add_argument("registry")
    registry_info = registry_subparsers.add_parser(
        "info", help="show a capability from a registry"
    )
    registry_info.add_argument("registry")
    registry_info.add_argument("capability")
    registry_info.add_argument("--version")
    registry_hash = registry_subparsers.add_parser(
        "digest", help="print the deterministic registry digest"
    )
    registry_hash.add_argument("registry")

    serve_parser = subparsers.add_parser(
        "serve", help="serve the QHPC API and workbench"
    )
    serve_parser.add_argument("--registry", required=True)
    serve_parser.add_argument(
        "--deployment-profile",
        required=True,
        help="explicit component allowlist for this deployment",
    )
    serve_parser.add_argument("--database", default=".qhpc/workbench.sqlite")
    serve_parser.add_argument("--artifact-root", default=".qhpc/artifacts")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8080)

    worker_parser = subparsers.add_parser(
        "worker", help="run a separate controlled task worker"
    )
    worker_parser.add_argument("--registry", required=True)
    worker_parser.add_argument(
        "--deployment-profile",
        required=True,
        help="explicit component allowlist for this worker",
    )
    worker_parser.add_argument("--database", default=".qhpc/workbench.sqlite")
    worker_parser.add_argument("--artifact-root", default=".qhpc/artifacts")
    worker_parser.add_argument("--runtime-root", default=".qhpc/runtimes")
    worker_parser.add_argument("--poll-interval", type=float, default=1.0)
    worker_parser.add_argument("--lease-seconds", type=int, default=300)
    worker_parser.add_argument("--worker-id")
    worker_parser.add_argument(
        "--execution-target",
        dest="execution_targets",
        action="append",
        help="execution target admitted by this local worker; repeat as needed",
    )
    worker_parser.add_argument(
        "--execution-class",
        dest="execution_classes",
        action="append",
        help="execution class admitted by this local worker; repeat as needed",
    )
    worker_mode = worker_parser.add_mutually_exclusive_group()
    worker_mode.add_argument(
        "--once", action="store_true", help="process at most one ready task and exit"
    )
    worker_mode.add_argument(
        "--drain", action="store_true", help="process ready tasks until idle and exit"
    )

    target_worker = subparsers.add_parser(
        "target-worker",
        help="run a restart-safe asynchronous Slurm/Apptainer worker",
    )
    target_worker.add_argument("--registry", required=True)
    target_worker.add_argument("--deployment-profile", required=True)
    target_worker.add_argument("--execution-target", required=True)
    target_worker.add_argument("--storage-profile", required=True)
    target_worker.add_argument("--runtime-manifest", action="append", required=True)
    target_worker.add_argument("--database", default=".qhpc/workbench.sqlite")
    target_worker.add_argument("--artifact-root", default=".qhpc/artifacts")
    target_worker.add_argument("--poll-interval", type=float, default=1.0)
    target_worker.add_argument("--lease-seconds", type=int, default=300)
    target_worker.add_argument("--worker-id")
    target_worker.add_argument(
        "--once", action="store_true", help="perform at most one transition and exit"
    )

    slurm_test_cluster = subparsers.add_parser(
        "slurm-test-cluster",
        help="manage the pinned development-only Slurm Docker cluster",
    )
    slurm_test_cluster_commands = slurm_test_cluster.add_subparsers(
        dest="slurm_test_cluster_command", required=True
    )
    slurm_test_prepare = slurm_test_cluster_commands.add_parser(
        "prepare", help="clone and verify the pinned cluster source"
    )
    slurm_test_start = slurm_test_cluster_commands.add_parser(
        "start", help="build and start the core Slurm services"
    )
    slurm_test_status = slurm_test_cluster_commands.add_parser(
        "status", help="inspect Compose, controller, and worker state"
    )
    slurm_test_smoke = slurm_test_cluster_commands.add_parser(
        "smoke", help="verify real Slurm completion, accounting, and cancellation"
    )
    slurm_test_stop = slurm_test_cluster_commands.add_parser(
        "stop", help="stop the test cluster without deleting its named volumes"
    )
    for command in (
        slurm_test_prepare,
        slurm_test_start,
        slurm_test_status,
        slurm_test_smoke,
        slurm_test_stop,
    ):
        command.add_argument("manifest")
        command.add_argument(
            "--checkout",
            help="test-cluster source checkout; defaults to revision-pinned .qhpc state",
        )
    slurm_test_prepare.add_argument(
        "--build-ca",
        help="approved public CA PEM for intercepted development build traffic",
    )
    slurm_test_start.add_argument("--timeout", type=int)
    slurm_test_smoke.add_argument("--timeout", type=int)
    slurm_test_smoke.add_argument(
        "--skip-cancel",
        action="store_true",
        help="skip the second job used to verify scancel and accounting",
    )
    slurm_test_smoke.add_argument(
        "--keep-artifacts",
        action="store_true",
        help="retain generated scripts and Slurm output in the shared directory",
    )

    pilot_parser = subparsers.add_parser(
        "pilot", help="manage durable warm-pilot allocation state"
    )
    pilot_commands = pilot_parser.add_subparsers(dest="pilot_command", required=True)
    pilot_list = pilot_commands.add_parser("list")
    pilot_request = pilot_commands.add_parser("request")
    pilot_request.add_argument("profile")
    pilot_request.add_argument("--created-by", required=True)
    pilot_submit = pilot_commands.add_parser("submit")
    pilot_submit.add_argument("pilot_id")
    pilot_submit.add_argument("scheduler_handle")
    pilot_ready = pilot_commands.add_parser("ready")
    pilot_ready.add_argument("pilot_id")
    pilot_heartbeat = pilot_commands.add_parser("heartbeat")
    pilot_heartbeat.add_argument("pilot_id")
    pilot_drain = pilot_commands.add_parser("drain")
    pilot_drain.add_argument("pilot_id")
    pilot_drain.add_argument("--reason", required=True)
    pilot_reconcile = pilot_commands.add_parser("reconcile")
    pilot_reconcile.add_argument("profile")
    pilot_terminate = pilot_commands.add_parser("terminate")
    pilot_terminate.add_argument("pilot_id")
    pilot_terminate.add_argument("--reason", default="scheduler-confirmed")
    for command in (
        pilot_list,
        pilot_request,
        pilot_submit,
        pilot_ready,
        pilot_heartbeat,
        pilot_drain,
        pilot_reconcile,
        pilot_terminate,
    ):
        command.add_argument("--database", default=".qhpc/workbench.sqlite")

    local_runtime = subparsers.add_parser(
        "local-runtime", help="build immutable local development runtimes"
    )
    local_runtime_commands = local_runtime.add_subparsers(
        dest="local_runtime_command", required=True
    )
    wheel_build = local_runtime_commands.add_parser(
        "build-wheel", help="build a reproducible wheel from a pinned Git revision"
    )
    wheel_build.add_argument("source")
    wheel_build.add_argument("--revision", required=True)
    wheel_build.add_argument("--runtime-root", default=".qhpc/runtimes")
    native_build = local_runtime_commands.add_parser(
        "build-native", help="build a reproducible native CMake runtime"
    )
    native_build.add_argument("source")
    native_build.add_argument("--revision", required=True)
    native_build.add_argument("--name", required=True)
    native_build.add_argument("--target", required=True)
    native_build.add_argument("--executable", required=True)
    native_build.add_argument("--asset", action="append", default=[])
    native_build.add_argument("--source-subdirectory", default=".")
    native_build.add_argument("--runtime-root", default=".qhpc/runtimes")
    cpp_build = local_runtime_commands.add_parser(
        "build-cpp", help="build a reproducible standalone C++ runtime"
    )
    cpp_build.add_argument("source")
    cpp_build.add_argument("--revision", required=True)
    cpp_build.add_argument("--name", required=True)
    cpp_build.add_argument("--executable", required=True)
    cpp_build.add_argument("--source-file", action="append", required=True)
    cpp_build.add_argument("--include-directory", action="append", default=[])
    cpp_build.add_argument("--runtime-root", default=".qhpc/runtimes")

    operation_runtime = subparsers.add_parser(
        "operation-runtime",
        help="prepare and verify immutable Linux operation containers",
    )
    operation_runtime_commands = operation_runtime.add_subparsers(
        dest="operation_runtime_command", required=True
    )
    operation_runtime_verify = operation_runtime_commands.add_parser(
        "verify", help="verify a runtime contract and its pinned workspace files"
    )
    operation_runtime_prepare = operation_runtime_commands.add_parser(
        "prepare", help="prepare a deterministic OCI build context"
    )
    operation_runtime_build = operation_runtime_commands.add_parser(
        "build-oci", help="prepare and build a local OCI operation image"
    )
    operation_runtime_smoke = operation_runtime_commands.add_parser(
        "smoke-oci", help="run the contracted OCI smoke verification"
    )
    operation_runtime_apptainer = operation_runtime_commands.add_parser(
        "apptainer-command",
        help="render an Apptainer build command for an immutable OCI release",
    )
    for command in (
        operation_runtime_verify,
        operation_runtime_prepare,
        operation_runtime_build,
        operation_runtime_smoke,
        operation_runtime_apptainer,
    ):
        command.add_argument("manifest")
        command.add_argument(
            "--workspace-root",
            help="root used to resolve runtime recipe, context, and fixture paths",
        )
    for command in (operation_runtime_prepare, operation_runtime_build):
        command.add_argument("source", help="checkout containing the pinned revision")
        command.add_argument(
            "--dependency-cache",
            help="directory containing checksum-pinned external build archives",
        )
    operation_runtime_prepare.add_argument("--output", required=True)
    operation_runtime_build.add_argument("--context", required=True)
    operation_runtime_build.add_argument("--tag", required=True)
    operation_runtime_build.add_argument("--builder", choices=("docker", "podman"))
    operation_runtime_smoke.add_argument("--image", required=True)
    operation_runtime_smoke.add_argument("--builder", choices=("docker", "podman"))
    operation_runtime_apptainer.add_argument("--oci-reference", required=True)
    operation_runtime_apptainer.add_argument("--output", required=True)
    operation_runtime_apptainer.add_argument("--fakeroot", action="store_true")

    artifact_parser = subparsers.add_parser(
        "artifact", help="register and inspect workflow artifacts"
    )
    artifact_commands = artifact_parser.add_subparsers(
        dest="artifact_command", required=True
    )
    artifact_register = artifact_commands.add_parser(
        "register", help="register a local file as a checksummed workflow input"
    )
    artifact_register.add_argument("path")
    artifact_register.add_argument("--type", required=True, dest="artifact_type")
    artifact_register.add_argument("--created-by", default="cli-user")
    artifact_list = artifact_commands.add_parser("list")
    artifact_info = artifact_commands.add_parser("info")
    artifact_info.add_argument("artifact_id")
    for command in (artifact_register, artifact_list, artifact_info):
        command.add_argument("--database", default=".qhpc/workbench.sqlite")
        command.add_argument("--artifact-root", default=".qhpc/artifacts")

    workflow_parser = subparsers.add_parser(
        "workflow", help="validate and publish immutable workflows"
    )
    workflow_commands = workflow_parser.add_subparsers(
        dest="workflow_command", required=True
    )
    workflow_validate = workflow_commands.add_parser(
        "validate", help="validate a workflow against a registry"
    )
    workflow_validate.add_argument("document")
    workflow_validate.add_argument("--registry", required=True)
    workflow_publish = workflow_commands.add_parser(
        "publish", help="publish an immutable workflow version"
    )
    workflow_publish.add_argument("document")
    workflow_publish.add_argument("--registry", required=True)
    workflow_publish.add_argument("--database", default=".qhpc/workbench.sqlite")
    workflow_publish.add_argument("--artifact-root", default=".qhpc/artifacts")
    workflow_publish.add_argument("--created-by", default="cli-user")
    workflow_list = workflow_commands.add_parser("list", help="list workflows")
    workflow_list.add_argument("--database", default=".qhpc/workbench.sqlite")
    workflow_list.add_argument("--artifact-root", default=".qhpc/artifacts")
    workflow_info = workflow_commands.add_parser("info", help="show a workflow")
    workflow_info.add_argument("workflow_id")
    workflow_info.add_argument("version")
    workflow_info.add_argument("--database", default=".qhpc/workbench.sqlite")
    workflow_info.add_argument("--artifact-root", default=".qhpc/artifacts")

    run_parser = subparsers.add_parser("run-record", help="manage workflow runs")
    run_commands = run_parser.add_subparsers(dest="run_command", required=True)
    run_submit = run_commands.add_parser("submit", help="submit a workflow run")
    run_submit.add_argument("workflow_id")
    run_submit.add_argument("version")
    run_submit.add_argument("--input", action="append", default=[])
    run_submit.add_argument("--target", default="local-development")
    run_submit.add_argument("--created-by", default="cli-user")
    run_submit.add_argument("--database", default=".qhpc/workbench.sqlite")
    run_submit.add_argument("--artifact-root", default=".qhpc/artifacts")
    for name in ("list", "info", "cancel", "retry", "export"):
        command = run_commands.add_parser(name)
        if name != "list":
            command.add_argument("run_id")
        if name == "retry":
            command.add_argument("node_id")
        if name == "export":
            command.add_argument("--output")
        command.add_argument("--database", default=".qhpc/workbench.sqlite")
        command.add_argument("--artifact-root", default=".qhpc/artifacts")

    subparsers.add_parser("list", help="list cataloged repositories")

    info = subparsers.add_parser("info", help="show repository metadata")
    info.add_argument("slug")

    subparsers.add_parser("validate", help="validate catalog metadata and recipes")

    build = subparsers.add_parser(
        "build", help="build the environment used by a repository"
    )
    build.add_argument("slug")
    build.add_argument("--force", action="store_true", help="replace an existing image")
    build.add_argument(
        "--fakeroot", action="store_true", help="pass --fakeroot to Apptainer"
    )

    shell = subparsers.add_parser(
        "shell", help="open a shell with a repository at /workspace"
    )
    shell.add_argument("slug")
    shell.add_argument(
        "--workspace", help="directory to bind instead of the cataloged local path"
    )

    run = subparsers.add_parser(
        "run", help="run a command with a repository at /workspace"
    )
    run.add_argument("slug")
    run.add_argument(
        "--workspace", help="directory to bind instead of the cataloged local path"
    )
    run.add_argument(
        "command",
        nargs="+",
        help="command to execute; use '--' before commands that have options",
    )

    sync = subparsers.add_parser(
        "sync-manifest", help="update source fields from repositories.tsv"
    )
    sync.add_argument("--manifest", help="override the catalog's source_manifest")
    sync.add_argument(
        "--check", action="store_true", help="report drift without retaining changes"
    )
    return parser


def _validate(catalog: Catalog) -> None:
    missing = [
        str(env.recipe)
        for env in catalog.environments.values()
        if not env.recipe.is_file()
    ]
    if missing:
        raise CatalogError(f"missing environment recipes: {', '.join(missing)}")
    manifest_slugs = {row["slug"] for row in read_manifest(catalog.source_manifest)}
    catalog_slugs = {repository.slug for repository in catalog.repositories}
    missing_repositories = sorted(manifest_slugs - catalog_slugs)
    if missing_repositories:
        raise CatalogError(
            "repositories missing from catalog: " + ", ".join(missing_repositories)
        )
    print(
        f"Catalog valid: {len(catalog.repositories)} repositories, "
        f"{len(catalog.environments)} environments"
    )


def _require_image(catalog: Catalog, repository: Repository, image_dir: Path) -> Path:
    environment = catalog.environments[repository.environment]
    image = runtime.image_path(environment, image_dir)
    if not image.is_file():
        raise CatalogError(
            f"environment image not found: {image}. Run 'qhpc-ecosystem build {repository.slug}' first."
        )
    return image


def _print_registry(registry: dict) -> None:
    columns = ("CAPABILITY", "VERSION", "PROJECT", "OPERATIONS", "REPOSITORY")
    rows = []
    for entry in registry_entries(registry):
        capability = entry["capability"]
        metadata = capability["metadata"]
        rows.append(
            (
                metadata["id"],
                metadata["version"],
                metadata["project"],
                str(len(capability["spec"].get("operations", []))),
                entry["catalog_repository"],
            )
        )
    widths = [
        max(len(columns[index]), *(len(row[index]) for row in rows))
        for index in range(len(columns))
    ]
    print("  ".join(value.ljust(widths[index]) for index, value in enumerate(columns)))
    print("  ".join("-" * width for width in widths))
    for row in rows:
        print("  ".join(value.ljust(widths[index]) for index, value in enumerate(row)))


def _print_registry_entry(entry: dict) -> None:
    capability = entry["capability"]
    metadata = capability["metadata"]
    operations = capability["spec"].get("operations", [])
    resources = capability["spec"].get("resources", [])
    documentation = capability["spec"].get("documentation", {})
    print(f"Name:               {metadata['name']}")
    print(f"Capability:         {metadata['id']}")
    print(f"Version:            {metadata['version']}")
    print(f"Project:            {metadata['project']}")
    print(f"Owners:             {_csv(metadata['owners'])}")
    integration = metadata["integration"]
    print(f"Authority:          {integration['authority']}")
    print(f"Curated by:         {_csv(integration['maintainers'])}")
    print(f"Project reviewed:   {str(integration['project_reviewed']).lower()}")
    print(f"Validation status:  {integration['validation_status']}")
    print(f"Repository:         {metadata['repository']['url']}")
    print(f"Revision:           {metadata['repository']['revision']}")
    print(f"Catalog repository: {entry['catalog_repository']}")
    print(f"Descriptor digest:  {entry['descriptor_digest']}")
    print(f"Operations:         {_csv([item['id'] for item in operations])}")
    print(f"Resources:          {_csv([item['id'] for item in resources])}")
    print(f"QAppsWiki:          {documentation.get('qappswiki', 'none')}")


def _print_integration_scaffolds(scaffolds: Sequence[object]) -> None:
    columns = (
        "COMPONENT",
        "STATUS",
        "SCOPE",
        "CONTRACT",
        "ADAPTER",
        "TESTS",
        "RUNTIME",
    )
    rows = []
    for scaffold in scaffolds:
        document = scaffold.document
        metadata = document["metadata"]
        spec = document["spec"]
        deliverables = spec["deliverables"]
        rows.append(
            (
                metadata["id"],
                metadata["integration_status"],
                spec["scope"]["status"],
                deliverables["interface_contract"],
                deliverables["adapter"],
                deliverables["integration_tests"],
                spec["production_runtime"]["status"],
            )
        )
    widths = [
        max(len(columns[index]), *(len(row[index]) for row in rows))
        for index in range(len(columns))
    ]
    print("  ".join(value.ljust(widths[index]) for index, value in enumerate(columns)))
    print("  ".join("-" * width for width in widths))
    for row in rows:
        print("  ".join(value.ljust(widths[index]) for index, value in enumerate(row)))


def _print_integration_scaffold(scaffold: object) -> None:
    document = scaffold.document
    metadata = document["metadata"]
    spec = document["spec"]
    source = spec["source"]
    mirror = spec["mirror"]
    environment = spec["development_environment"]
    deliverables = spec["deliverables"]
    runtime_spec = spec["production_runtime"]
    print(f"Name:                 {metadata['name']}")
    print(f"Component:            {metadata['id']}")
    print(f"Integration status:   {metadata['integration_status']}")
    print(f"Source:               {source.get('url') or 'unresolved'}")
    print(f"GitLab mirror:        {mirror.get('url') or mirror['status']}")
    print(f"Mirror status:        {mirror['status']}")
    print(
        f"Developer environment:{' ' if environment.get('class') else ''}{environment.get('class') or environment['status']}"
    )
    print(f"Scope status:         {spec['scope']['status']}")
    print(f"Scope:                {spec['scope']['summary']}")
    print(f"Interface contract:   {deliverables['interface_contract']}")
    print(f"Adapter:              {deliverables['adapter']}")
    print(f"Fixtures:             {deliverables['fixtures']}")
    print(f"Integration tests:    {deliverables['integration_tests']}")
    print(f"Registry publication: {deliverables['registry_publication']}")
    technology = runtime_spec.get("technology", "none")
    print(f"Production runtime:   {runtime_spec['status']} ({technology})")
    print(f"Scaffold:             {scaffold.path}")
    print(f"Blockers:             {_csv(spec['blockers'])}")


def dispatch(args: argparse.Namespace) -> int:
    if args.subcommand == "integration":
        from .integration import (
            find_integration_scaffold,
            load_integration_scaffolds,
        )

        profile, scaffolds = load_integration_scaffolds(
            args.profile, args.workspace_root
        )
        if args.integration_command == "validate":
            metadata = profile["metadata"]
            print(
                f"Integration scaffolds valid: {metadata['id']}@{metadata['version']} "
                f"({len(scaffolds)} components)"
            )
            return 0
        if args.integration_command == "list":
            _print_integration_scaffolds(scaffolds)
            return 0
        if args.integration_command == "info":
            _print_integration_scaffold(
                find_integration_scaffold(scaffolds, args.component_id)
            )
            return 0
        raise ContractError(
            f"unsupported integration command: {args.integration_command}"
        )

    if args.subcommand == "serve":
        from .api import APIContext, serve
        from .deployment import load_deployment_profile, registry_for_deployment
        from .engine import WorkflowEngine

        catalog = load_catalog(args.catalog)
        profile = load_deployment_profile(args.deployment_profile, catalog)
        registry = registry_for_deployment(
            load_registry(args.registry, catalog), profile
        )
        engine = WorkflowEngine(args.database, args.artifact_root)
        metadata = profile["metadata"]
        print(
            f"Deployment profile: {metadata['id']}@{metadata['version']} "
            f"({len(profile['spec']['components'])} components, "
            f"{len(registry_entries(registry))} published capabilities)"
        )
        print(f"QHPC Workbench: http://{args.host}:{args.port}")
        serve(
            APIContext(engine=engine, registry=registry),
            args.host,
            args.port,
        )
        return 0

    if args.subcommand == "slurm-test-cluster":
        from .slurm_test_cluster import SlurmDockerCluster

        cluster = SlurmDockerCluster.from_manifest(args.manifest, args.checkout)
        if args.slurm_test_cluster_command == "prepare":
            checkout = cluster.prepare(args.build_ca)
            source = cluster.source
            print(f"Slurm test cluster prepared: {checkout}")
            print(f"Source: {source['repository']}")
            print(f"Revision: {source['revision']}")
            return 0
        if args.slurm_test_cluster_command == "start":
            status = cluster.start(args.timeout)
            print(f"Slurm test cluster ready: {str(status.ready).lower()}")
            if status.nodes.stdout.strip():
                print(status.nodes.stdout.strip())
            return 0
        if args.slurm_test_cluster_command == "status":
            status = cluster.status()
            print(f"Ready: {str(status.ready).lower()}")
            print("Compose:")
            print(
                status.compose.stdout.strip()
                or status.compose.stderr.strip()
                or "not running"
            )
            print("Controller:")
            print(
                status.controller.stdout.strip()
                or status.controller.stderr.strip()
                or "not responding"
            )
            print("Nodes:")
            print(
                status.nodes.stdout.strip()
                or status.nodes.stderr.strip()
                or "not responding"
            )
            return 0 if status.ready else 1
        if args.slurm_test_cluster_command == "smoke":
            result = cluster.smoke(
                timeout_seconds=args.timeout,
                verify_cancellation=not args.skip_cancel,
                keep_artifacts=args.keep_artifacts,
            )
            print(
                f"Slurm completion verified: {result.completed_job_id} "
                f"({result.completed_state})"
            )
            if result.canceled_job_id:
                print(
                    f"Slurm cancellation verified: {result.canceled_job_id} "
                    f"({result.canceled_state})"
                )
            print(f"Duration: {result.duration_ms} ms")
            return 0
        if args.slurm_test_cluster_command == "stop":
            cluster.stop()
            print("Slurm test cluster stopped")
            return 0
        raise ContractError(
            "unsupported Slurm test-cluster command: "
            + args.slurm_test_cluster_command
        )

    if args.subcommand == "worker":
        import signal
        from threading import Event

        from .deployment import load_deployment_profile, registry_for_deployment
        from .engine import WorkflowEngine
        from .local_adapters import build_local_runner
        from .worker import RegistryBoundRunner, Worker

        if args.poll_interval <= 0:
            raise ContractError("worker poll interval must be greater than zero")
        if args.lease_seconds <= 0:
            raise ContractError("worker lease duration must be greater than zero")
        catalog = load_catalog(args.catalog)
        profile = load_deployment_profile(args.deployment_profile, catalog)
        registry = registry_for_deployment(
            load_registry(args.registry, catalog), profile
        )
        engine = WorkflowEngine(args.database, args.artifact_root)
        runner = RegistryBoundRunner(build_local_runner(args.runtime_root), registry)
        worker = Worker(
            engine,
            runner,
            poll_interval_seconds=args.poll_interval,
            lease_seconds=args.lease_seconds,
            worker_id=args.worker_id,
            execution_targets=args.execution_targets or ("local-development",),
            execution_classes=args.execution_classes or ("interactive-local",),
        )
        metadata = profile["metadata"]
        print(
            f"QHPC Worker: {metadata['id']}@{metadata['version']} "
            f"({len(registry_entries(registry))} published capabilities)"
        )
        if args.once:
            processed = int(worker.run_once())
            engine.heartbeat_worker(worker.worker_id, state="offline")
        elif args.drain:
            processed = worker.drain()
            engine.heartbeat_worker(worker.worker_id, state="offline")
        else:
            stop_event = Event()

            def stop_worker(_signum: int, _frame: object) -> None:
                stop_event.set()

            signal.signal(signal.SIGINT, stop_worker)
            signal.signal(signal.SIGTERM, stop_worker)
            print(
                f"Worker polling every {args.poll_interval:g}s "
                f"with {args.lease_seconds}s leases"
            )
            processed = worker.run_forever(stop_event)
        print(f"Worker stopped: {processed} tasks processed")
        return 0

    if args.subcommand == "target-worker":
        import signal
        from threading import Event

        from .deployment import load_deployment_profile, registry_for_deployment
        from .engine import WorkflowEngine
        from .operation_runtime import load_operation_runtime
        from .slurm_runner import (
            SlurmApptainerRunner,
            load_execution_target,
            load_storage_profile,
        )
        from .worker import AsyncWorker, RegistryBoundAsyncRunner

        if args.poll_interval <= 0:
            raise ContractError("worker poll interval must be greater than zero")
        if args.lease_seconds <= 0:
            raise ContractError("worker lease duration must be greater than zero")
        catalog = load_catalog(args.catalog)
        profile = load_deployment_profile(args.deployment_profile, catalog)
        registry = registry_for_deployment(
            load_registry(args.registry, catalog), profile
        )
        target = load_execution_target(args.execution_target)
        storage = load_storage_profile(args.storage_profile)
        runtimes = [load_operation_runtime(path) for path in args.runtime_manifest]
        engine = WorkflowEngine(args.database, args.artifact_root)
        runner = RegistryBoundAsyncRunner(
            SlurmApptainerRunner(target, storage, runtimes), registry
        )
        worker = AsyncWorker(
            engine,
            runner,
            poll_interval_seconds=args.poll_interval,
            lease_seconds=args.lease_seconds,
            worker_id=args.worker_id,
        )
        metadata = target["metadata"]
        print(
            f"QHPC Target Worker: {metadata['id']} ({len(runtimes)} accepted runtimes)"
        )
        if args.once:
            transitions = int(worker.run_once())
            engine.heartbeat_worker(worker.worker_id, state="offline")
        else:
            stop_event = Event()

            def stop_target_worker(_signum: int, _frame: object) -> None:
                stop_event.set()

            signal.signal(signal.SIGINT, stop_target_worker)
            signal.signal(signal.SIGTERM, stop_target_worker)
            print(
                f"Target worker polling every {args.poll_interval:g}s "
                f"with {args.lease_seconds}s leases"
            )
            transitions = worker.run_forever(stop_event)
        print(f"Target worker stopped: {transitions} transitions processed")
        return 0

    if args.subcommand == "pilot":
        from .pilot import PilotStore

        store = PilotStore(args.database)
        if args.pilot_command == "list":
            result = store.list_allocations()
        elif args.pilot_command == "request":
            profile = validate_contract("pilot-profile", args.profile)
            result = store.request_allocation(profile, created_by=args.created_by)
        elif args.pilot_command == "submit":
            result = store.assign_scheduler_handle(args.pilot_id, args.scheduler_handle)
        elif args.pilot_command == "ready":
            result = store.mark_ready(args.pilot_id)
        elif args.pilot_command == "heartbeat":
            result = store.heartbeat(args.pilot_id)
        elif args.pilot_command == "drain":
            result = store.drain(args.pilot_id, reason=args.reason)
        elif args.pilot_command == "reconcile":
            profile = validate_contract("pilot-profile", args.profile)
            result = store.reconcile(profile)
        else:
            result = store.mark_terminated(args.pilot_id, reason=args.reason)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    if args.subcommand == "local-runtime":
        from .local_runtime import (
            build_cmake_runtime,
            build_cpp_runtime,
            build_wheel_runtime,
        )

        root = Path(args.runtime_root).expanduser().resolve()
        if args.local_runtime_command == "build-wheel":
            runtime_artifact = build_wheel_runtime(
                args.source, root / "wheels", revision=args.revision
            )
        elif args.local_runtime_command == "build-native":
            runtime_artifact = build_cmake_runtime(
                args.source,
                root / "native",
                revision=args.revision,
                name=args.name,
                target=args.target,
                executable=args.executable,
                assets=tuple(args.asset),
                source_subdirectory=args.source_subdirectory,
            )
        else:
            runtime_artifact = build_cpp_runtime(
                args.source,
                root / "native",
                revision=args.revision,
                name=args.name,
                executable=args.executable,
                source_files=tuple(args.source_file),
                include_directories=tuple(args.include_directory),
            )
        print(f"Runtime built: {runtime_artifact.path}")
        print(f"Reference: {runtime_artifact.reference}")
        print(f"Digest: {runtime_artifact.digest}")
        return 0

    if args.subcommand == "operation-runtime":
        from .operation_runtime import (
            apptainer_build_command,
            build_oci_image,
            load_operation_runtime,
            prepare_build_context,
            smoke_oci_image,
            verify_runtime_definition,
        )

        if args.operation_runtime_command == "verify":
            document = verify_runtime_definition(args.manifest, args.workspace_root)
            metadata = document["metadata"]
            print(
                f"Operation runtime valid: {metadata['id']}@{metadata['version']} "
                f"({metadata['status']})"
            )
            return 0
        if args.operation_runtime_command == "prepare":
            context = prepare_build_context(
                args.manifest,
                args.source,
                args.output,
                workspace_root=args.workspace_root,
                dependency_cache=args.dependency_cache,
            )
            print(f"Build context prepared: {context.path}")
            print(f"Platform: {context.platform}")
            print(f"Source revision: {context.source_revision}")
            print(f"Source archive: {context.source_archive_digest}")
            return 0
        if args.operation_runtime_command == "build-oci":
            context = prepare_build_context(
                args.manifest,
                args.source,
                args.context,
                workspace_root=args.workspace_root,
                dependency_cache=args.dependency_cache,
            )
            image = build_oci_image(
                load_operation_runtime(args.manifest),
                context.path,
                args.tag,
                builder=args.builder,
            )
            print(f"OCI image built: {image.reference}")
            print(f"Local image ID: {image.local_id}")
            return 0
        if args.operation_runtime_command == "smoke-oci":
            result = smoke_oci_image(
                args.manifest,
                args.image,
                workspace_root=args.workspace_root,
                builder=args.builder,
            )
            print(
                f"OCI smoke verification passed: {result.image} "
                f"({result.duration_ms} ms)"
            )
            for output in result.outputs:
                print(
                    f"Output: {output.container_path} "
                    f"({output.size} bytes, {output.digest})"
                )
            return 0
        if args.operation_runtime_command == "apptainer-command":
            verify_runtime_definition(args.manifest, args.workspace_root)
            command = apptainer_build_command(
                args.oci_reference,
                args.output,
                executable=args.runtime or "apptainer",
                fakeroot=args.fakeroot,
            )
            print(shlex.join(command))
            return 0
        raise OperationRuntimeError(
            f"unsupported operation-runtime command: {args.operation_runtime_command}"
        )

    if args.subcommand == "artifact":
        from .engine import WorkflowEngine

        engine = WorkflowEngine(args.database, args.artifact_root)
        if args.artifact_command == "register":
            artifact = engine.register_input_file(
                args.path,
                artifact_type=args.artifact_type,
                created_by=args.created_by,
            )
            print(
                f"Artifact registered: {artifact['id']} "
                f"({artifact['artifact_type']}, {artifact['checksum']})"
            )
            return 0
        if args.artifact_command == "list":
            for artifact in engine.list_artifacts():
                print(
                    f"{artifact['id']}\t{artifact['artifact_type']}\t"
                    f"{artifact['provenance']}\t{artifact['checksum']}"
                )
            return 0
        json.dump(
            engine.get_artifact(args.artifact_id),
            sys.stdout,
            indent=2,
            sort_keys=True,
        )
        print()
        return 0

    if args.subcommand == "workflow":
        from .engine import WorkflowEngine
        from .workflow import resolve_workflow

        if args.workflow_command == "validate":
            workflow = validate_contract("workflow", args.document)
            registry = load_registry(args.registry)
            resolved = resolve_workflow(workflow, registry)
            print(
                f"Workflow valid: {workflow['metadata']['id']}@{workflow['metadata']['version']} ({resolved.digest})"
            )
            return 0
        engine = WorkflowEngine(args.database, args.artifact_root)
        if args.workflow_command == "publish":
            workflow = validate_contract("workflow", args.document)
            result = engine.register_workflow(
                workflow,
                load_registry(args.registry),
                created_by=args.created_by,
            )
            print(
                f"Workflow published: {result['id']}@{result['version']} ({result['digest']})"
            )
            return 0
        if args.workflow_command == "list":
            for workflow in engine.list_workflows():
                print(f"{workflow['id']}\t{workflow['version']}\t{workflow['digest']}")
            return 0
        result = engine.get_workflow(args.workflow_id, args.version)
        json.dump(result, sys.stdout, indent=2, sort_keys=True)
        print()
        return 0

    if args.subcommand == "run-record":
        from .engine import WorkflowEngine

        engine = WorkflowEngine(args.database, args.artifact_root)
        if args.run_command == "submit":
            result = engine.submit_run(
                args.workflow_id,
                args.version,
                inputs=_assignments(args.input),
                execution_target=args.target,
                created_by=args.created_by,
            )
            print(f"Run submitted: {result['id']} ({result['state']})")
            return 0
        if args.run_command == "list":
            for run in engine.list_runs():
                print(
                    f"{run['id']}\t{run['workflow_id']}@{run['workflow_version']}\t{run['state']}"
                )
            return 0
        if args.run_command == "cancel":
            result = engine.cancel_run(args.run_id)
            print(f"Run canceled: {result['id']} ({result['state']})")
            return 0
        if args.run_command == "retry":
            result = engine.retry_task(args.run_id, args.node_id)
            print(f"Task queued: {args.node_id} ({result['state']})")
            return 0
        result = (
            engine.export_run(args.run_id)
            if args.run_command == "export"
            else engine.get_run(args.run_id)
        )
        serialized = json.dumps(result, indent=2, sort_keys=True) + "\n"
        if args.run_command == "export" and args.output:
            destination = Path(args.output).expanduser().resolve()
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(serialized, encoding="utf-8")
            print(f"Run exported: {destination}")
        else:
            print(serialized, end="")
        return 0

    if args.subcommand == "contract":
        if args.contract_command == "list":
            for kind in contract_kinds():
                print(f"{kind}\t{CONTRACT_SCHEMAS[kind]}")
            return 0
        if args.contract_command == "schema":
            json.dump(load_schema(args.kind), sys.stdout, indent=2, sort_keys=True)
            print()
            return 0
        if args.contract_command == "validate":
            path = Path(args.document).expanduser().resolve()
            validate_contract(args.kind, path)
            print(f"Contract valid: {args.kind} ({path})")
            return 0
        raise ContractError(f"unsupported contract command: {args.contract_command}")

    if args.subcommand == "registry":
        if args.registry_command == "build":
            catalog = load_catalog(args.catalog)
            registry = build_registry(args.source, catalog)
            destination = write_registry(args.output, registry)
            print(
                f"Registry built: {destination} "
                f"({len(registry_entries(registry))} capabilities, "
                f"{registry_digest(registry)})"
            )
            return 0
        if args.registry_command == "validate":
            catalog = load_catalog(args.catalog)
            path = Path(args.registry).expanduser().resolve()
            registry = load_registry(path, catalog)
            print(
                f"Registry valid: {path} "
                f"({len(registry_entries(registry))} capabilities)"
            )
            return 0
        if args.registry_command == "list":
            _print_registry(load_registry(args.registry))
            return 0
        if args.registry_command == "info":
            registry = load_registry(args.registry)
            _print_registry_entry(
                find_registry_entry(registry, args.capability, args.version)
            )
            return 0
        if args.registry_command == "digest":
            print(registry_digest(load_registry(args.registry)))
            return 0
        raise RegistryError(f"unsupported registry command: {args.registry_command}")

    catalog = load_catalog(args.catalog)
    if args.subcommand == "list":
        _print_table(catalog)
        return 0
    if args.subcommand == "info":
        _print_repository(catalog.repository(args.slug))
        return 0
    if args.subcommand == "validate":
        _validate(catalog)
        return 0
    if args.subcommand == "sync-manifest":
        manifest = (
            Path(args.manifest).expanduser().resolve()
            if args.manifest
            else catalog.source_manifest
        )
        changed = synchronize(catalog.path, manifest, write=not args.check)
        if args.check and changed:
            print("Catalog is out of sync with the mirror manifest.", file=sys.stderr)
            return 1
        print(
            "Catalog is synchronized."
            if not changed
            else "Catalog updated from mirror manifest."
        )
        return 0

    repository = catalog.repository(args.slug)
    _require_runnable(repository)
    environment = catalog.environments[repository.environment]
    image_dir = _image_dir(args.image_dir)

    if args.subcommand == "build":
        if not environment.recipe.is_file():
            raise CatalogError(f"environment recipe not found: {environment.recipe}")
        image = runtime.image_path(environment, image_dir)
        if image.exists() and not args.force:
            print(f"Environment already built: {image}")
            return 0
        executable = runtime.find_runtime(args.runtime)
        image.parent.mkdir(parents=True, exist_ok=True)
        print(f"Building {repository.environment} for {repository.slug}: {image}")
        command = runtime.build_command(
            executable,
            environment,
            image,
            force=args.force,
            fakeroot=args.fakeroot,
        )
        return runtime.execute(command)

    executable = runtime.find_runtime(args.runtime)
    image = _require_image(catalog, repository, image_dir)
    workspace = runtime.resolve_workspace(repository, args.workspace)
    if args.subcommand == "shell":
        return runtime.execute(
            runtime.workspace_command(executable, "shell", image, workspace)
        )
    if args.subcommand == "run":
        command = list(args.command)
        if command and command[0] == "--":
            command.pop(0)
        if not command:
            raise CatalogError("run requires a command after '--'")
        return runtime.execute(
            runtime.workspace_command(executable, "exec", image, workspace, command)
        )
    raise CatalogError(f"unsupported command: {args.subcommand}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return dispatch(args)
    except (
        CatalogError,
        ContractError,
        OperationRuntimeError,
        RegistryError,
        SlurmTestClusterError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
