from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from qhpc_ecosystem import cli
from qhpc_ecosystem.catalog import load_catalog
from qhpc_ecosystem.contract import load_document, validate_contract
from qhpc_ecosystem.registry import (
    RegistryError,
    build_registry,
    discover_capability_files,
    find_registry_entry,
    load_registry,
    registry_digest,
    registry_entries,
    write_registry,
)


ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "ecosystem.yaml"
EXAMPLE_CAPABILITY = ROOT / "examples" / "contracts" / "valid" / "capability.yaml"


def test_published_capabilities_separate_tool_and_integration_identity() -> None:
    descriptors = sorted(
        (ROOT / "capabilities").rglob("qhpc-capability.yaml")
    )

    assert len(descriptors) == 18
    for descriptor in descriptors:
        capability = validate_contract("capability", descriptor)
        assert capability["spec"]["component"]["name"]

    lightstim = validate_contract(
        "capability",
        ROOT / "capabilities/LightStim/simulation/qhpc-capability.yaml",
    )
    assert lightstim["spec"]["component"]["name"] == "LightStim"
    assert lightstim["metadata"]["name"] == "LightStim Logical Error Estimation"
    assert lightstim["spec"]["component"]["description"].startswith(
        "Modular QEC framework built on Stim"
    )


def write_capability(
    root: Path,
    *,
    capability_id: str = "openqevo-registry-test",
    version: str = "0.1.0",
    project: str = "cross-project",
    repository_url: str = "https://github.com/QSCSoftwareThrust/OpenQEvo",
    canonical_repository_url: str | None = None,
    revision: str = "v0.1.0",
    qappswiki: str | None = "packages/openqevo.md",
    nested: bool = True,
) -> Path:
    capability = copy.deepcopy(load_document(EXAMPLE_CAPABILITY))
    repository = {"url": repository_url, "revision": revision}
    if canonical_repository_url is not None:
        repository["canonical_url"] = canonical_repository_url
    capability["metadata"].update(
        {
            "id": capability_id,
            "name": "OpenQEvo registry test fixture",
            "version": version,
            "project": project,
            "owners": ["openqevo"],
            "repository": repository,
        }
    )
    if qappswiki is None:
        capability["spec"].pop("documentation", None)
    else:
        capability["spec"]["documentation"] = {"qappswiki": qappswiki}
    destination = (
        root / ".qhpc" / "capability.yaml" if nested else root / "qhpc-capability.yaml"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        yaml.safe_dump(capability, sort_keys=False), encoding="utf-8"
    )
    return destination


def test_registry_build_is_deterministic_and_round_trips(tmp_path: Path) -> None:
    source = tmp_path / "openqevo-release"
    descriptor = write_capability(source)
    catalog = load_catalog(CATALOG_PATH)

    first = build_registry([source], catalog)
    second = build_registry([descriptor], catalog)

    assert first == second
    assert first["metadata"]["entry_count"] == 1
    entry = registry_entries(first)[0]
    assert entry["catalog_repository"] == "OpenQEvo"
    assert entry["validation"] == {
        "contract": "valid",
        "attribution": "valid",
        "authority": "ecosystem",
        "curated_by": ["qhpc-ecosystem"],
        "project_reviewed": False,
        "runtime": "declared",
        "documentation": "linked",
        "status": "contract-valid",
        "evidence": ["tests/test_contract.py"],
    }

    registry_path = write_registry(tmp_path / "registry.yaml", first)
    assert load_registry(registry_path, catalog) == first
    assert registry_digest(load_registry(registry_path)) == registry_digest(first)


def test_discovery_uses_only_documented_locations(tmp_path: Path) -> None:
    expected = write_capability(tmp_path / "project", nested=False)
    ignored = tmp_path / "project" / "node_modules" / "qhpc-capability.yaml"
    ignored.parent.mkdir(parents=True)
    ignored.write_text(expected.read_text(encoding="utf-8"), encoding="utf-8")
    unrelated = tmp_path / "project" / "capability.yaml"
    unrelated.write_text(expected.read_text(encoding="utf-8"), encoding="utf-8")

    assert discover_capability_files([tmp_path / "project"]) == (expected.resolve(),)


def test_registry_rejects_duplicate_capability_version(tmp_path: Path) -> None:
    first = write_capability(tmp_path / "first")
    second = write_capability(tmp_path / "second")

    with pytest.raises(RegistryError, match="duplicate capability versions"):
        build_registry([first, second], load_catalog(CATALOG_PATH))


@pytest.mark.parametrize(
    ("project", "repository_url", "expected"),
    [
        (
            "data-schema",
            "https://github.com/QSCSoftwareThrust/OpenQEvo",
            "must be cross-project",
        ),
        (
            "cross-project",
            "https://example.invalid/not-cataloged",
            "does not match a repository",
        ),
    ],
)
def test_registry_rejects_catalog_ownership_problems(
    tmp_path: Path, project: str, repository_url: str, expected: str
) -> None:
    descriptor = write_capability(
        tmp_path / "project",
        project=project,
        repository_url=repository_url,
    )

    with pytest.raises(RegistryError, match=expected):
        build_registry([descriptor], load_catalog(CATALOG_PATH))


def test_registry_requires_pinned_revision_and_qappswiki(tmp_path: Path) -> None:
    mutable = write_capability(tmp_path / "mutable", revision="main")
    undocumented = write_capability(tmp_path / "undocumented", qappswiki=None)
    catalog = load_catalog(CATALOG_PATH)

    with pytest.raises(RegistryError, match="full commit hash or semantic release"):
        build_registry([mutable], catalog)
    with pytest.raises(RegistryError, match="required for registry publication"):
        build_registry([undocumented], catalog)


@pytest.mark.parametrize(
    ("project", "repository_url", "catalog_repository"),
    [
        (
            "data-schema",
            "https://github.com/QSCSoftwareThrust/DataSchema",
            "DataSchema",
        ),
        (
            "hybrid-workflows",
            "https://github.com/QSCSoftwareThrust/STABSim",
            "STABSim",
        ),
        (
            "compilation-tools",
            "https://github.com/QSCSoftwareThrust/FTQC",
            "ftqc",
        ),
    ],
)
def test_registry_maps_legacy_catalog_project_names(
    tmp_path: Path, project: str, repository_url: str, catalog_repository: str
) -> None:
    descriptor = write_capability(
        tmp_path / project,
        capability_id=f"{project}-test",
        project=project,
        repository_url=repository_url,
    )

    registry = build_registry([descriptor], load_catalog(CATALOG_PATH))
    assert registry_entries(registry)[0]["catalog_repository"] == catalog_repository


def test_registry_maps_admitted_release_source_to_canonical_repository(
    tmp_path: Path,
) -> None:
    descriptor = write_capability(
        tmp_path / "lightstim",
        capability_id="lightstim-registry-test",
        project="hybrid-workflows",
        repository_url="https://github.com/QuTone/LightStim",
        canonical_repository_url="https://github.com/QSCSoftwareThrust/LightStim",
        revision="b08d4c2f9cd69531a51b658e6f88089be69f16c0",
    )

    registry = build_registry([descriptor], load_catalog(CATALOG_PATH))
    entry = registry_entries(registry)[0]
    assert entry["catalog_repository"] == "LightStim"
    assert entry["capability"]["metadata"]["repository"] == {
        "url": "https://github.com/QuTone/LightStim",
        "canonical_url": "https://github.com/QSCSoftwareThrust/LightStim",
        "revision": "b08d4c2f9cd69531a51b658e6f88089be69f16c0",
    }


def test_registry_rejects_unadmitted_release_source_for_canonical_repository(
    tmp_path: Path,
) -> None:
    descriptor = write_capability(
        tmp_path / "invalid-source",
        repository_url="https://example.invalid/unadmitted-release",
        canonical_repository_url="https://github.com/QSCSoftwareThrust/OpenQEvo",
    )

    with pytest.raises(RegistryError, match="release source must match"):
        build_registry([descriptor], load_catalog(CATALOG_PATH))


def test_registry_rejects_capability_ownership_change(tmp_path: Path) -> None:
    first = write_capability(tmp_path / "openqevo", version="1.0.0")
    second = write_capability(
        tmp_path / "data-schema",
        version="2.0.0",
        project="data-schema",
        repository_url="https://github.com/QSCSoftwareThrust/DataSchema",
    )

    with pytest.raises(RegistryError, match="changes ownership"):
        build_registry([first, second], load_catalog(CATALOG_PATH))


def test_registry_detects_catalog_drift(tmp_path: Path) -> None:
    descriptor = write_capability(tmp_path / "project")
    catalog = load_catalog(CATALOG_PATH)
    registry_path = write_registry(
        tmp_path / "registry.yaml", build_registry([descriptor], catalog)
    )
    changed_catalog_path = tmp_path / "ecosystem.yaml"
    changed_catalog_path.write_text(
        CATALOG_PATH.read_text(encoding="utf-8").replace(
            "QSC applications/wiki context repository.",
            "Changed catalog content.",
        ),
        encoding="utf-8",
    )

    with pytest.raises(RegistryError, match="does not match the current"):
        load_registry(registry_path, load_catalog(changed_catalog_path))


def test_find_registry_entry_uses_latest_semantic_version(tmp_path: Path) -> None:
    first = write_capability(tmp_path / "first", version="1.2.0")
    second = write_capability(tmp_path / "second", version="1.10.0")
    registry = build_registry([first, second], load_catalog(CATALOG_PATH))

    assert (
        find_registry_entry(registry, "openqevo-registry-test")["capability"][
            "metadata"
        ]["version"]
        == "1.10.0"
    )
    assert (
        find_registry_entry(registry, "openqevo-registry-test", "1.2.0")["capability"][
            "metadata"
        ]["version"]
        == "1.2.0"
    )


def test_registry_cli_build_validate_and_inspect(tmp_path: Path, capsys) -> None:
    source = tmp_path / "project"
    write_capability(source)
    registry_path = tmp_path / "registry.yaml"
    common = ["--catalog", str(CATALOG_PATH), "registry"]

    assert (
        cli.main(
            [
                *common,
                "build",
                "--source",
                str(source),
                "--output",
                str(registry_path),
            ]
        )
        == 0
    )
    assert "Registry built:" in capsys.readouterr().out

    assert cli.main([*common, "validate", str(registry_path)]) == 0
    assert "Registry valid:" in capsys.readouterr().out

    assert cli.main(["registry", "list", str(registry_path)]) == 0
    assert "openqevo-registry-test" in capsys.readouterr().out

    assert (
        cli.main(["registry", "info", str(registry_path), "openqevo-registry-test"])
        == 0
    )
    output = capsys.readouterr().out
    assert "Catalog repository: OpenQEvo" in output
    assert "Purpose:" in output
    assert "Use when:" in output
    assert "Quick start:" in output
    assert "generate: Generate example circuit" in output

    assert (
        cli.main(
            [
                "registry",
                "info",
                str(registry_path),
                "openqevo-registry-test",
                "--operation",
                "generate",
            ]
        )
        == 0
    )
    operation_output = capsys.readouterr().out
    assert "Operation:          Generate example circuit" in operation_output
    assert "circuit: qhpc.quantum-circuit@1" in operation_output
    assert "Number of qubits (qubits): integer; default=4" in operation_output

    assert (
        cli.main(
            [
                "registry",
                "info",
                str(registry_path),
                "openqevo-registry-test",
                "--operation",
                "generate",
                "--json",
            ]
        )
        == 0
    )
    operation_json = yaml.safe_load(capsys.readouterr().out)
    assert operation_json["operation"]["id"] == "generate"
    assert operation_json["capability"]["guidance"]["quick_start"]

    assert cli.main(["registry", "digest", str(registry_path)]) == 0
    assert capsys.readouterr().out.startswith("sha256:")


def test_contributor_template_passes_contract_validation() -> None:
    validate_contract("capability", ROOT / "templates" / "qhpc-capability.yaml")
