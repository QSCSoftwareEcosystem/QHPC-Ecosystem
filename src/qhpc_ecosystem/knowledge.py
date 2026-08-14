"""Read-only access to a compiled QAppsWiki knowledge graph."""

from __future__ import annotations

import json
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Iterable


class KnowledgeGraphError(ValueError):
    """Raised when a QAppsWiki graph artifact is missing or malformed."""


_SYNTHETIC_TYPES = {"external", "missing"}
_NAVIGATION_TYPES = {
    "activity-log",
    "index",
    "project-charter",
    "project-plan",
    "schema",
    "untyped",
}
_MAX_GRAPH_BYTES = 64 * 1024 * 1024
_MAX_NODES = 50_000
_MAX_EDGES = 250_000
_MAX_OVERLAY_BYTES = 2 * 1024 * 1024
_OVERLAY_SCHEMA = "qhpc-knowledge-overlay-0"


def _bounded_limit(value: int, *, default: int = 60, maximum: int = 200) -> int:
    if value <= 0:
        return default
    return min(value, maximum)


class QAppsWikiKnowledge:
    """Index and query one immutable ``qappswiki-graph-0`` artifact."""

    def __init__(
        self,
        graph_path: str | Path,
        *,
        source_revision: str | None = None,
        overlay_paths: Iterable[str | Path] = (),
    ) -> None:
        self.graph_path = Path(graph_path).expanduser().resolve()
        self.source_revision = source_revision
        self.overlay_paths = tuple(
            Path(path).expanduser().resolve() for path in overlay_paths
        )
        self._load()

    def _load_overlays(
        self,
        base_nodes: list[dict[str, Any]],
        base_edges: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        nodes = list(base_nodes)
        edges = list(base_edges)
        known_ids = {
            node.get("id")
            for node in nodes
            if isinstance(node, dict) and isinstance(node.get("id"), str)
        }
        overlay_nodes = 0
        overlay_edges = 0
        for path in self.overlay_paths:
            try:
                if path.stat().st_size > _MAX_OVERLAY_BYTES:
                    raise KnowledgeGraphError(
                        f"knowledge overlay exceeds the 2 MB limit: {path}"
                    )
                payload = json.loads(path.read_text(encoding="utf-8"))
            except FileNotFoundError as error:
                raise KnowledgeGraphError(
                    f"knowledge overlay not found: {path}"
                ) from error
            except json.JSONDecodeError as error:
                raise KnowledgeGraphError(
                    f"knowledge overlay is not valid JSON ({path}): {error}"
                ) from error
            if not isinstance(payload, dict):
                raise KnowledgeGraphError(
                    f"knowledge overlay root must be an object: {path}"
                )
            if payload.get("schema_version") != _OVERLAY_SCHEMA:
                raise KnowledgeGraphError(
                    f"knowledge overlay must use schema_version "
                    f"{_OVERLAY_SCHEMA}: {path}"
                )
            additions = payload.get("nodes")
            relationships = payload.get("edges")
            if not isinstance(additions, list) or not isinstance(
                relationships, list
            ):
                raise KnowledgeGraphError(
                    f"knowledge overlay requires node and edge lists: {path}"
                )
            for node in additions:
                node_id = node.get("id") if isinstance(node, dict) else None
                if not isinstance(node_id, str) or not node_id:
                    raise KnowledgeGraphError(
                        f"knowledge overlay contains an invalid node: {path}"
                    )
                if node_id in known_ids:
                    raise KnowledgeGraphError(
                        f"knowledge overlay cannot replace an existing node: "
                        f"{node_id}"
                    )
                known_ids.add(node_id)
                normalized = dict(node)
                normalized["overlay_source"] = str(path)
                nodes.append(normalized)
                overlay_nodes += 1
            for edge in relationships:
                if not isinstance(edge, dict):
                    raise KnowledgeGraphError(
                        f"knowledge overlay contains an invalid edge: {path}"
                    )
                normalized = dict(edge)
                normalized.setdefault("origin", "qhpc-registry-overlay")
                edges.append(normalized)
                overlay_edges += 1
        self.overlay_stats = {
            "files": len(self.overlay_paths),
            "nodes": overlay_nodes,
            "edges": overlay_edges,
        }
        return nodes, edges

    def _load(self) -> None:
        try:
            if self.graph_path.stat().st_size > _MAX_GRAPH_BYTES:
                raise KnowledgeGraphError("QAppsWiki graph exceeds the 64 MB limit")
            payload = json.loads(self.graph_path.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise KnowledgeGraphError(
                f"QAppsWiki graph not found: {self.graph_path}"
            ) from error
        except json.JSONDecodeError as error:
            raise KnowledgeGraphError(
                f"QAppsWiki graph is not valid JSON: {error}"
            ) from error

        if not isinstance(payload, dict):
            raise KnowledgeGraphError("QAppsWiki graph root must be an object")
        if payload.get("schema_version") != "qappswiki-graph-0":
            raise KnowledgeGraphError(
                "QAppsWiki graph must use schema_version qappswiki-graph-0"
            )
        nodes = payload.get("nodes")
        edges = payload.get("edges")
        communities = payload.get("communities")
        if not isinstance(nodes, list) or not isinstance(edges, list):
            raise KnowledgeGraphError("QAppsWiki graph requires node and edge lists")
        if not isinstance(communities, list):
            raise KnowledgeGraphError("QAppsWiki graph requires a community list")
        nodes, edges = self._load_overlays(nodes, edges)
        if len(nodes) > _MAX_NODES or len(edges) > _MAX_EDGES:
            raise KnowledgeGraphError("QAppsWiki graph exceeds supported dimensions")

        self.payload = payload
        self.nodes: dict[str, dict[str, Any]] = {}
        for node in nodes:
            if not isinstance(node, dict):
                raise KnowledgeGraphError("QAppsWiki graph contains an invalid node")
            node_id = node.get("id")
            if not isinstance(node_id, str) or not node_id:
                raise KnowledgeGraphError(
                    "QAppsWiki graph node identifiers must be non-empty strings"
                )
            if node_id in self.nodes:
                raise KnowledgeGraphError(
                    f"QAppsWiki graph contains duplicate node: {node_id}"
                )
            self.nodes[node_id] = node

        self.edges: list[dict[str, Any]] = []
        self.out_edges: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.in_edges: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for edge in edges:
            if not isinstance(edge, dict):
                raise KnowledgeGraphError("QAppsWiki graph contains an invalid edge")
            source = edge.get("source")
            target = edge.get("target")
            relation = edge.get("relation")
            confidence = edge.get("confidence")
            if (
                not isinstance(source, str)
                or source not in self.nodes
                or not isinstance(target, str)
                or target not in self.nodes
                or not isinstance(relation, str)
                or not relation
                or confidence not in {"EXTRACTED", "INFERRED", "AMBIGUOUS"}
            ):
                raise KnowledgeGraphError(
                    "QAppsWiki graph contains an unresolved or malformed edge"
                )
            normalized = {
                "source": source,
                "target": target,
                "relation": relation,
                "confidence": confidence,
                "origin": edge.get("origin"),
            }
            self.edges.append(normalized)
            self.out_edges[source].append(normalized)
            self.in_edges[target].append(normalized)

        self.communities: dict[int, dict[str, Any]] = {}
        for community in communities:
            if not isinstance(community, dict):
                raise KnowledgeGraphError(
                    "QAppsWiki graph contains an invalid community"
                )
            index = community.get("index")
            if not isinstance(index, int):
                raise KnowledgeGraphError(
                    "QAppsWiki community identifiers must be integers"
                )
            self.communities[index] = community

        self._degree = {
            node_id: len(self.out_edges[node_id]) + len(self.in_edges[node_id])
            for node_id in self.nodes
        }

    @classmethod
    def from_repository(
        cls,
        repository_root: str | Path,
        *,
        source_revision: str | None = None,
    ) -> QAppsWikiKnowledge:
        return cls(
            Path(repository_root) / "wiki-out" / "graph.json",
            source_revision=source_revision,
        )

    def _content_node(self, node: dict[str, Any]) -> bool:
        return node.get("type") not in _SYNTHETIC_TYPES

    def _node_summary(self, node_id: str) -> dict[str, Any]:
        node = self.nodes[node_id]
        return {
            "id": node_id,
            "title": node.get("title") or node_id,
            "type": node.get("type") or "untyped",
            "domains": node.get("domains") or [],
            "status": node.get("status"),
            "provenance_status": node.get("provenance_status"),
            "community": node.get("community"),
            "community_label": node.get("community_label"),
            "freshness": node.get("freshness"),
            "freshness_rollup": node.get("freshness_rollup"),
            "synthetic": node.get("type") in _SYNTHETIC_TYPES,
            "degree": self._degree[node_id],
        }

    def summary(self) -> dict[str, Any]:
        content_nodes = [
            node for node in self.nodes.values() if self._content_node(node)
        ]
        typed_counts: dict[str, int] = defaultdict(int)
        provenance_counts: dict[str, int] = defaultdict(int)
        for node in content_nodes:
            typed_counts[str(node.get("type") or "untyped")] += 1
            provenance_counts[
                str(node.get("provenance_status") or "untracked")
            ] += 1

        community_edges: dict[tuple[int, int], dict[str, Any]] = {}
        for edge in self.edges:
            source_community = self.nodes[edge["source"]].get("community")
            target_community = self.nodes[edge["target"]].get("community")
            if (
                not isinstance(source_community, int)
                or not isinstance(target_community, int)
                or source_community == target_community
            ):
                continue
            pair = tuple(sorted((source_community, target_community)))
            aggregate = community_edges.setdefault(
                pair,
                {
                    "source": pair[0],
                    "target": pair[1],
                    "count": 0,
                    "confidence": defaultdict(int),
                },
            )
            aggregate["count"] += 1
            aggregate["confidence"][edge["confidence"]] += 1

        overview_edges = []
        for aggregate in community_edges.values():
            overview_edges.append(
                {
                    **aggregate,
                    "confidence": dict(aggregate["confidence"]),
                }
            )

        return {
            "available": True,
            "schema_version": self.payload["schema_version"],
            "generated": self.payload.get("generated"),
            "source_revision": self.source_revision,
            "overlays": self.overlay_stats,
            "stats": {
                "content_nodes": len(content_nodes),
                "all_nodes": len(self.nodes),
                "edges": len(self.edges),
                "communities": len(self.communities),
                "by_type": dict(sorted(typed_counts.items())),
                "by_provenance": dict(sorted(provenance_counts.items())),
            },
            "communities": [
                {
                    "index": index,
                    "label": community.get("label") or f"Community {index + 1}",
                    "size": community.get("size", 0),
                    "god_node": community.get("god_node"),
                    "domains": community.get("domains") or [],
                    "internal_edges": community.get("internal_edges", 0),
                    "external_edges": community.get("external_edges", 0),
                    "cohesion": community.get("cohesion", 0),
                }
                for index, community in sorted(self.communities.items())
            ],
            "community_edges": sorted(
                overview_edges,
                key=lambda edge: (-edge["count"], edge["source"], edge["target"]),
            ),
        }

    def search(
        self,
        term: str = "",
        *,
        node_type: str | None = None,
        domain: str | None = None,
        community: int | None = None,
        limit: int = 60,
        include_synthetic: bool = False,
    ) -> dict[str, Any]:
        normalized_term = term.strip().lower()
        matches = []
        for node_id, node in self.nodes.items():
            if not include_synthetic and not self._content_node(node):
                continue
            if node_type and node.get("type") != node_type:
                continue
            domains = node.get("domains") or []
            if domain and domain not in domains:
                continue
            if community is not None and node.get("community") != community:
                continue
            title = str(node.get("title") or node_id)
            haystack = " ".join((node_id, title, " ".join(domains))).lower()
            if normalized_term and normalized_term not in haystack:
                continue
            exact = normalized_term in {node_id.lower(), title.lower()}
            prefix = bool(normalized_term) and title.lower().startswith(
                normalized_term
            )
            matches.append(
                (
                    0 if exact else 1 if prefix else 2,
                    1
                    if (node.get("type") or "untyped") in _NAVIGATION_TYPES
                    else 0,
                    -self._degree[node_id],
                    title.lower(),
                    node_id,
                )
            )
        matches.sort()
        bounded = _bounded_limit(limit)
        selected = [self._node_summary(item[4]) for item in matches[:bounded]]
        return {
            "query": term,
            "total": len(matches),
            "limit": bounded,
            "items": selected,
        }

    def node(self, node_id: str) -> dict[str, Any]:
        if node_id not in self.nodes:
            raise KeyError(f"unknown QAppsWiki node: {node_id}")
        node = self.nodes[node_id]

        def edge_detail(edge: dict[str, Any], adjacent_id: str) -> dict[str, Any]:
            return {
                **edge,
                "node": self._node_summary(adjacent_id),
            }

        outgoing = [
            edge_detail(edge, edge["target"]) for edge in self.out_edges[node_id]
        ]
        incoming = [
            edge_detail(edge, edge["source"]) for edge in self.in_edges[node_id]
        ]
        citations = [
            {
                "source": edge["target"],
                "title": self.nodes[edge["target"]].get("title")
                or edge["target"],
                "type": self.nodes[edge["target"]].get("type") or "untyped",
                "origin": edge.get("origin"),
                "confidence": edge["confidence"],
            }
            for edge in self.out_edges[node_id]
            if edge["relation"] == "cites"
        ]
        return {
            **self._node_summary(node_id),
            "rel_path": node.get("rel_path"),
            "version_built": node.get("version_built"),
            "version_scope": node.get("version_scope"),
            "version_source": node.get("version_source"),
            "outgoing": outgoing,
            "incoming": incoming,
            "citations": citations,
        }

    def _subgraph(self, node_ids: Iterable[str]) -> dict[str, Any]:
        selected = set(node_ids)
        return {
            "nodes": [
                self._node_summary(node_id)
                for node_id in sorted(
                    selected,
                    key=lambda item: (-self._degree[item], item),
                )
            ],
            "edges": [
                edge
                for edge in self.edges
                if edge["source"] in selected and edge["target"] in selected
            ],
        }

    def community(self, index: int, *, limit: int = 120) -> dict[str, Any]:
        if index not in self.communities:
            raise KeyError(f"unknown QAppsWiki community: {index}")
        community = self.communities[index]
        members = [
            member
            for member in community.get("members", [])
            if member in self.nodes and self._content_node(self.nodes[member])
        ]
        members.sort(key=lambda item: (-self._degree[item], item))
        bounded = _bounded_limit(limit, default=120)
        selected = members[:bounded]
        god_node = community.get("god_node")
        if (
            isinstance(god_node, str)
            and god_node in members
            and god_node not in selected
        ):
            selected[-1:] = [god_node]
        return {
            "community": {
                "index": index,
                "label": community.get("label") or f"Community {index + 1}",
                "size": len(members),
                "god_node": god_node,
                "domains": community.get("domains") or [],
                "cohesion": community.get("cohesion", 0),
            },
            "truncated": len(selected) < len(members),
            **self._subgraph(selected),
        }

    def neighborhood(
        self,
        node_id: str,
        *,
        depth: int = 1,
        limit: int = 100,
    ) -> dict[str, Any]:
        if node_id not in self.nodes:
            raise KeyError(f"unknown QAppsWiki node: {node_id}")
        bounded_depth = min(max(depth, 1), 2)
        bounded_limit = _bounded_limit(limit, default=100)
        seen = {node_id}
        queue = deque([(node_id, 0)])
        while queue and len(seen) < bounded_limit:
            current, distance = queue.popleft()
            if distance >= bounded_depth:
                continue
            adjacent = {
                edge["target"] for edge in self.out_edges[current]
            } | {edge["source"] for edge in self.in_edges[current]}
            ordered = sorted(
                adjacent,
                key=lambda item: (-self._degree[item], item),
            )
            for candidate in ordered:
                if candidate in seen:
                    continue
                seen.add(candidate)
                queue.append((candidate, distance + 1))
                if len(seen) >= bounded_limit:
                    break
        return {
            "center": node_id,
            "depth": bounded_depth,
            "truncated": len(seen) >= bounded_limit,
            **self._subgraph(seen),
        }

    def shortest_path(self, source: str, target: str) -> dict[str, Any]:
        if source not in self.nodes:
            raise KeyError(f"unknown QAppsWiki node: {source}")
        if target not in self.nodes:
            raise KeyError(f"unknown QAppsWiki node: {target}")
        previous: dict[str, str | None] = {source: None}
        queue = deque([source])
        while queue:
            current = queue.popleft()
            if current == target:
                break
            adjacent = {
                edge["target"] for edge in self.out_edges[current]
            } | {edge["source"] for edge in self.in_edges[current]}
            for candidate in sorted(adjacent):
                if candidate in previous:
                    continue
                previous[candidate] = current
                queue.append(candidate)
        if target not in previous:
            return {
                "found": False,
                "source": source,
                "target": target,
                "path": [],
                "nodes": [],
                "edges": [],
            }
        path = []
        cursor: str | None = target
        while cursor is not None:
            path.append(cursor)
            cursor = previous[cursor]
        path.reverse()
        selected_edges = []
        for left, right in zip(path, path[1:]):
            candidates = [
                edge
                for edge in self.edges
                if {edge["source"], edge["target"]} == {left, right}
            ]
            selected_edges.extend(candidates)
        return {
            "found": True,
            "source": source,
            "target": target,
            "path": path,
            "length": len(path) - 1,
            "nodes": [self._node_summary(node_id) for node_id in path],
            "edges": selected_edges,
        }
