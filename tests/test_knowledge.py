from __future__ import annotations

import json
from pathlib import Path

import pytest

from qhpc_ecosystem.knowledge import KnowledgeGraphError, QAppsWikiKnowledge


def write_graph(path: Path) -> Path:
    payload = {
        "schema_version": "qappswiki-graph-0",
        "generated": "2026-07-29",
        "stats": {},
        "communities": [
            {
                "index": 0,
                "label": "quantum-software",
                "size": 3,
                "members": [
                    "packages/openqevo",
                    "how-to/openqevo-first-run",
                    "integrations/qiskit-to-openqevo",
                ],
                "god_node": "packages/openqevo",
                "domains": ["quantum-software"],
                "internal_edges": 2,
                "external_edges": 1,
                "cohesion": 0.667,
            },
            {
                "index": 1,
                "label": "quantum-error-correction",
                "size": 1,
                "members": ["concepts/qec/surface"],
                "god_node": "concepts/qec/surface",
                "domains": ["quantum-error-correction"],
                "internal_edges": 0,
                "external_edges": 1,
                "cohesion": 0,
            },
        ],
        "nodes": [
            {
                "id": "packages/openqevo",
                "title": "OpenQEvo",
                "type": "package",
                "domains": ["quantum-software"],
                "status": "active",
                "provenance_status": "verified",
                "community": 0,
                "community_label": "quantum-software",
                "rel_path": "packages/openqevo.md",
            },
            {
                "id": "how-to/openqevo-first-run",
                "title": "OpenQEvo first run",
                "type": "how-to",
                "domains": ["quantum-software"],
                "provenance_status": "verified",
                "community": 0,
                "community_label": "quantum-software",
            },
            {
                "id": "integrations/qiskit-to-openqevo",
                "title": "Qiskit to OpenQEvo",
                "type": "integration",
                "domains": ["quantum-software"],
                "provenance_status": "verified",
                "community": 0,
                "community_label": "quantum-software",
            },
            {
                "id": "concepts/qec/surface",
                "title": "Surface code",
                "type": "concept",
                "domains": ["quantum-error-correction"],
                "provenance_status": "needs-verification",
                "community": 1,
                "community_label": "quantum-error-correction",
            },
            {
                "id": "ext:openqevo-paper",
                "title": "OpenQEvo paper",
                "type": "external",
                "domains": [],
                "provenance_status": None,
                "community": None,
                "community_label": None,
            },
            {
                "id": "index",
                "title": "QAppsWiki Index",
                "type": "index",
                "domains": [],
                "provenance_status": "verified",
                "community": None,
                "community_label": None,
            },
        ],
        "edges": [
            {
                "source": "packages/openqevo",
                "target": "how-to/openqevo-first-run",
                "relation": "has-how-to",
                "confidence": "EXTRACTED",
                "origin": "wikilink",
            },
            {
                "source": "how-to/openqevo-first-run",
                "target": "integrations/qiskit-to-openqevo",
                "relation": "uses",
                "confidence": "INFERRED",
                "origin": "frontmatter",
            },
            {
                "source": "integrations/qiskit-to-openqevo",
                "target": "concepts/qec/surface",
                "relation": "related",
                "confidence": "EXTRACTED",
                "origin": "wikilink",
            },
            {
                "source": "packages/openqevo",
                "target": "ext:openqevo-paper",
                "relation": "cites",
                "confidence": "EXTRACTED",
                "origin": "inline-citation",
            },
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_qappswiki_knowledge_exposes_focused_graph_queries(tmp_path: Path) -> None:
    knowledge = QAppsWikiKnowledge(
        write_graph(tmp_path / "graph.json"),
        source_revision="a" * 40,
    )

    summary = knowledge.summary()
    assert summary["available"]
    assert summary["source_revision"] == "a" * 40
    assert summary["stats"]["content_nodes"] == 5
    assert summary["stats"]["all_nodes"] == 6
    assert summary["community_edges"][0]["count"] == 1

    browse = knowledge.search()
    assert browse["items"][-1]["id"] == "index"

    search = knowledge.search("openqevo")
    assert search["total"] == 3
    assert search["items"][0]["id"] == "packages/openqevo"
    assert not any(item["synthetic"] for item in search["items"])

    record = knowledge.node("packages/openqevo")
    assert record["citations"][0]["source"] == "ext:openqevo-paper"
    assert record["citations"][0]["origin"] == "inline-citation"

    community = knowledge.community(0)
    assert len(community["nodes"]) == 3
    assert len(community["edges"]) == 2

    neighborhood = knowledge.neighborhood("packages/openqevo")
    assert {node["id"] for node in neighborhood["nodes"]} == {
        "packages/openqevo",
        "how-to/openqevo-first-run",
        "ext:openqevo-paper",
    }

    path = knowledge.shortest_path(
        "packages/openqevo",
        "concepts/qec/surface",
    )
    assert path["found"]
    assert path["length"] == 3
    assert path["path"][-1] == "concepts/qec/surface"


def test_qappswiki_knowledge_rejects_wrong_schema(tmp_path: Path) -> None:
    graph_path = tmp_path / "graph.json"
    graph_path.write_text(
        json.dumps(
            {
                "schema_version": "other",
                "nodes": [],
                "edges": [],
                "communities": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(KnowledgeGraphError, match="schema_version"):
        QAppsWikiKnowledge(graph_path)


def test_qappswiki_knowledge_merges_registry_relationship_overlays(
    tmp_path: Path,
) -> None:
    overlay_path = tmp_path / "knowledge-overlay.json"
    overlay_path.write_text(
        json.dumps(
            {
                "schema_version": "qhpc-knowledge-overlay-0",
                "nodes": [
                    {
                        "id": "packages/exachem-qflow",
                        "title": "ExaChem QFlow",
                        "type": "package",
                        "domains": ["quantum-chemistry", "hybrid-workflows"],
                        "status": "prototype",
                        "provenance_status": "integration-tested",
                        "community": None,
                        "community_label": None,
                    },
                    {
                        "id": "packages/iris-qiris",
                        "title": "QIRIS Runtime",
                        "type": "package",
                        "domains": ["quantum-runtime", "hybrid-workflows"],
                        "status": "prototype",
                        "provenance_status": "contract-valid",
                        "community": None,
                        "community_label": None,
                    },
                ],
                "edges": [
                    {
                        "source": "packages/exachem-qflow",
                        "target": "packages/iris-qiris",
                        "relation": "delegates-taskset-to",
                        "confidence": "EXTRACTED",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    knowledge = QAppsWikiKnowledge(
        write_graph(tmp_path / "graph.json"),
        source_revision="a" * 40,
        overlay_paths=[overlay_path],
    )

    summary = knowledge.summary()
    assert summary["overlays"] == {"files": 1, "nodes": 2, "edges": 1}
    assert knowledge.search("qflow")["items"][0]["status"] == "prototype"
    path = knowledge.shortest_path(
        "packages/exachem-qflow",
        "packages/iris-qiris",
    )
    assert path["found"]
    assert path["edges"][0]["relation"] == "delegates-taskset-to"
    assert path["edges"][0]["origin"] == "qhpc-registry-overlay"


def test_qappswiki_knowledge_overlay_cannot_shadow_curated_nodes(
    tmp_path: Path,
) -> None:
    overlay_path = tmp_path / "knowledge-overlay.json"
    overlay_path.write_text(
        json.dumps(
            {
                "schema_version": "qhpc-knowledge-overlay-0",
                "nodes": [
                    {
                        "id": "packages/openqevo",
                        "title": "Replacement",
                    }
                ],
                "edges": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(KnowledgeGraphError, match="cannot replace"):
        QAppsWikiKnowledge(
            write_graph(tmp_path / "graph.json"),
            overlay_paths=[overlay_path],
        )
