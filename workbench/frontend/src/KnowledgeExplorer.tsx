/*
THESIS: The corpus appears first as a navigable atlas, not an undifferentiated
node cloud. OWN-WORLD: QSC Force Blue plotting field, paper-white records,
Quark Red selections, and Open Sans controls extend the orchestration console.
STORY: Search or choose a community, inspect a focused graph, verify its
sources, then trace a connection. FIRST VIEWPORT: discovery rail left, dominant
graph center, provenance record right, with corpus measures in one continuous
header. FORM: an established-world Operate surface using a community-first
scientific atlas; precise scope replaces concept-seed staging.
*/

import cytoscape, {
  type Core,
  type ElementDefinition,
  type EventObject,
  type StylesheetJson,
} from "cytoscape";
import {
  ArrowLeft,
  BookOpenText,
  Check,
  ChevronRight,
  CircleAlert,
  Crosshair,
  Focus,
  GitBranch,
  Link2,
  LocateFixed,
  Network,
  Route,
  Search,
  ShieldCheck,
  X,
} from "lucide-react";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { knowledgeApi } from "./api";
import type {
  KnowledgeCommunity,
  KnowledgeGraphSlice,
  KnowledgeNodeRecord,
  KnowledgeNodeSummary,
  KnowledgePath,
  KnowledgeSearchResults,
  KnowledgeSummary,
} from "./types";


interface KnowledgeExplorerProps {
  initialNodeId: string | null;
}

interface GraphCanvasProps {
  summary: KnowledgeSummary;
  graph: KnowledgeGraphSlice | null;
  selectedNodeId: string | null;
  onSelectNode: (nodeId: string) => void;
  onSelectCommunity: (community: number) => void;
}

const COMMUNITY_COLORS = [
  "#AA1E2E",
  "#1668B3",
  "#0E7A4B",
  "#B26812",
  "#668391",
  "#C14953",
  "#3286A0",
  "#658C54",
  "#946E8A",
];

const TYPE_COLORS: Record<string, string> = {
  package: "#AA1E2E",
  concept: "#1668B3",
  "how-to": "#0E7A4B",
  integration: "#8A5A08",
  workflow: "#3286A0",
  source: "#CFD2D3",
  external: "#80919B",
  missing: "#D66570",
  untyped: "#93A4AC",
};


function displayLabel(value: string): string {
  return value
    .replaceAll("-", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}


function compactLabel(value: string, maximum = 30): string {
  return value.length > maximum
    ? `${value.slice(0, maximum - 1)}…`
    : value;
}


function graphStyles(): StylesheetJson {
  return [
    {
      selector: "node",
      style: {
        "background-color": "data(color)",
        "border-color": "#E8EEF0",
        "border-width": 1,
        color: "#F5F8F9",
        label: "data(label)",
        "font-family": "Open Sans, sans-serif",
        "font-size": 11,
        "font-weight": 600,
        height: "mapData(weight, 1, 40, 22, 48)",
        width: "mapData(weight, 1, 40, 22, 48)",
        "min-zoomed-font-size": 8,
        "text-background-color": "#131E29",
        "text-background-opacity": 0.78,
        "text-background-padding": "3px",
        "text-margin-y": 8,
        "text-valign": "bottom",
        "text-wrap": "wrap",
        "text-max-width": "112px",
      },
    },
    {
      selector: "node:selected",
      style: {
        "border-color": "#FFFFFF",
        "border-width": 4,
        "overlay-color": "#AA1E2E",
        "overlay-opacity": 0.18,
        "overlay-padding": 8,
      },
    },
    {
      selector: 'node[kind = "community"]',
      style: {
        height: "mapData(weight, 1, 180, 44, 92)",
        width: "mapData(weight, 1, 180, 44, 92)",
        "font-size": 12,
        "font-weight": 700,
        "text-margin-y": 11,
      },
    },
    {
      selector: "edge",
      style: {
        "curve-style": "bezier",
        "line-color": "#64808D",
        opacity: 0.58,
        width: "mapData(weight, 1, 50, 1, 5)",
        "target-arrow-color": "#809AA5",
        "target-arrow-shape": "triangle",
        "arrow-scale": 0.65,
      },
    },
    {
      selector: 'edge[confidence = "INFERRED"]',
      style: {
        "line-style": "dashed",
      },
    },
    {
      selector: 'edge[confidence = "AMBIGUOUS"]',
      style: {
        "line-color": "#D66570",
        "target-arrow-color": "#D66570",
        "line-style": "dashed",
      },
    },
  ];
}


function GraphCanvas({
  summary,
  graph,
  selectedNodeId,
  onSelectNode,
  onSelectCommunity,
}: GraphCanvasProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const coreRef = useRef<Core | null>(null);

  const elements = useMemo<ElementDefinition[]>(() => {
    if (!graph) {
      const nodes = (summary.communities ?? []).map((community) => ({
        data: {
          id: `community:${community.index}`,
          label: `${displayLabel(community.label)} · ${community.size}`,
          kind: "community",
          community: community.index,
          weight: Math.max(community.size, 1),
          color: COMMUNITY_COLORS[
            community.index % COMMUNITY_COLORS.length
          ],
        },
      }));
      const edges = (summary.community_edges ?? []).map((edge, index) => ({
        data: {
          id: `community-edge:${index}`,
          source: `community:${edge.source}`,
          target: `community:${edge.target}`,
          weight: edge.count,
          confidence: "EXTRACTED",
        },
      }));
      return [...nodes, ...edges];
    }
    const nodes = graph.nodes.map((node) => ({
      data: {
        id: node.id,
        label: compactLabel(node.title),
        kind: "knowledge-node",
        weight: Math.max(node.degree, 1),
        color: TYPE_COLORS[node.type] ?? TYPE_COLORS.untyped,
      },
    }));
    const edges = graph.edges.map((edge, index) => ({
      data: {
        id: `knowledge-edge:${index}`,
        source: edge.source,
        target: edge.target,
        weight: 1,
        confidence: edge.confidence,
      },
    }));
    return [...nodes, ...edges];
  }, [graph, summary]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const core = cytoscape({
      container,
      elements,
      style: graphStyles(),
      minZoom: 0.18,
      maxZoom: 2.6,
      wheelSensitivity: 0.22,
      boxSelectionEnabled: false,
      autoungrabify: false,
      layout: graph
        ? {
            name: graph.nodes.length < 5 ? "circle" : "cose",
            animate: false,
            fit: true,
            padding: 36,
            nodeRepulsion: () => 160_000,
            idealEdgeLength: () => 118,
            gravity: 0.3,
            numIter: 900,
          }
        : {
            name: "circle",
            animate: false,
            fit: true,
            padding: 54,
            spacingFactor: 1.25,
          },
    });
    coreRef.current = core;
    core.on("tap", "node", (event: EventObject) => {
      const data = event.target.data();
      if (data.kind === "community") {
        onSelectCommunity(Number(data.community));
      } else {
        onSelectNode(String(data.id));
      }
    });
    const observer = new ResizeObserver(() => {
      core.resize();
      core.fit(undefined, 36);
    });
    observer.observe(container);
    return () => {
      observer.disconnect();
      core.destroy();
      coreRef.current = null;
    };
  }, [elements, graph, onSelectCommunity, onSelectNode]);

  useEffect(() => {
    const core = coreRef.current;
    if (!core || !selectedNodeId) return;
    const selected = core.getElementById(selectedNodeId);
    if (selected.empty()) return;
    core.elements().unselect();
    selected.select();
    core.animate(
      {
        center: { eles: selected },
        zoom: Math.max(core.zoom(), 1.15),
      },
      { duration: 180 },
    );
  }, [selectedNodeId]);

  return (
    <div className="knowledge-plot-wrap">
      <div
        className="knowledge-plot"
        ref={containerRef}
        role="img"
        aria-label={
          graph
            ? `Focused QAppsWiki graph with ${graph.nodes.length} nodes`
            : `QAppsWiki atlas with ${summary.communities?.length ?? 0} thematic communities`
        }
      />
      <div className="knowledge-plot-controls" aria-label="Graph controls">
        <button
          type="button"
          onClick={() => coreRef.current?.fit(undefined, 36)}
          title="Fit graph"
        >
          <LocateFixed aria-hidden="true" size={16} />
          <span>Fit</span>
        </button>
        <button
          type="button"
          onClick={() => {
            const core = coreRef.current;
            if (!core) return;
            core.animate({ zoom: core.zoom() * 1.18 }, { duration: 150 });
          }}
          title="Zoom in"
        >
          <Focus aria-hidden="true" size={16} />
          <span>Zoom</span>
        </button>
      </div>
      <div className="knowledge-legend" aria-label="Graph legend">
        <span><i className="is-package" />Package</span>
        <span><i className="is-concept" />Concept</span>
        <span><i className="is-integration" />Integration</span>
        <span><i className="is-how-to" />How-to</span>
      </div>
    </div>
  );
}


function StatusMark({
  value,
  fallback = "untracked",
}: {
  value?: string | null;
  fallback?: string;
}) {
  const label = value || fallback;
  const verified = ["verified", "fresh", "active"].includes(label);
  return (
    <span className={`knowledge-state ${verified ? "is-verified" : ""}`}>
      {verified
        ? <Check size={12} aria-hidden="true" />
        : <CircleAlert size={12} aria-hidden="true" />}
      {displayLabel(label)}
    </span>
  );
}


function NodeRecord({
  record,
  pathSource,
  onExplore,
  onSelectRelated,
  onSetPathSource,
  onSetPathTarget,
  onClear,
}: {
  record: KnowledgeNodeRecord | null;
  pathSource: KnowledgeNodeSummary | null;
  onExplore: (nodeId: string) => void;
  onSelectRelated: (nodeId: string) => void;
  onSetPathSource: (node: KnowledgeNodeSummary) => void;
  onSetPathTarget: (node: KnowledgeNodeSummary) => void;
  onClear: () => void;
}) {
  if (!record) {
    return (
      <div className="knowledge-record-empty">
        <Crosshair aria-hidden="true" size={28} />
        <strong>Select a knowledge node</strong>
        <p>
          Its relationships, provenance, citations, and version context will
          appear here.
        </p>
      </div>
    );
  }
  const relations = [...record.outgoing, ...record.incoming]
    .filter((edge) => edge.relation !== "cites")
    .slice(0, 14);
  return (
    <article className="knowledge-record">
      <header>
        <div>
          <span className="knowledge-record-type">
            {displayLabel(record.type)}
          </span>
          <h2>{record.title}</h2>
          <code>{record.id}</code>
        </div>
        <button
          className="knowledge-icon-button"
          type="button"
          onClick={onClear}
          aria-label="Close knowledge record"
        >
          <X aria-hidden="true" size={18} />
        </button>
      </header>

      <div className="knowledge-record-states">
        <StatusMark value={record.provenance_status} />
        {record.freshness || record.freshness_rollup
          ? <StatusMark value={record.freshness || record.freshness_rollup} />
          : null}
      </div>

      <dl className="knowledge-record-facts">
        {record.status
          ? <div><dt>Maturity</dt><dd>{displayLabel(record.status)}</dd></div>
          : null}
        <div>
          <dt>Community</dt>
          <dd>{displayLabel(record.community_label || "unassigned")}</dd>
        </div>
        <div>
          <dt>Connections</dt>
          <dd>{record.degree}</dd>
        </div>
        {record.version_built
          ? <div><dt>Version built</dt><dd>{record.version_built}</dd></div>
          : null}
        {record.rel_path
          ? <div><dt>Corpus page</dt><dd>{record.rel_path}</dd></div>
          : null}
      </dl>

      <div className="knowledge-record-actions">
        <button type="button" onClick={() => onExplore(record.id)}>
          <Network aria-hidden="true" size={15} />
          Explore neighbors
        </button>
        {!pathSource || pathSource.id === record.id
          ? (
              <button type="button" onClick={() => onSetPathSource(record)}>
                <GitBranch aria-hidden="true" size={15} />
                Set path start
              </button>
            )
          : (
              <button type="button" onClick={() => onSetPathTarget(record)}>
                <Route aria-hidden="true" size={15} />
                Connect from {compactLabel(pathSource.title, 18)}
              </button>
            )}
      </div>

      <section className="knowledge-record-section">
        <div className="knowledge-section-title">
          <Link2 aria-hidden="true" size={15} />
          <h3>Relationships</h3>
          <span>{record.outgoing.length + record.incoming.length}</span>
        </div>
        {relations.length
          ? (
              <ul className="knowledge-relation-list">
                {relations.map((edge, index) => (
                  <li key={`${edge.source}:${edge.target}:${edge.relation}:${index}`}>
                    <button
                      type="button"
                      onClick={() => onSelectRelated(edge.node.id)}
                    >
                      <span>
                        <strong>{edge.node.title}</strong>
                        <small>
                          {edge.relation} · {edge.confidence.toLowerCase()}
                        </small>
                      </span>
                      <ChevronRight aria-hidden="true" size={15} />
                    </button>
                  </li>
                ))}
              </ul>
            )
          : <p className="knowledge-record-note">No content relationships are published.</p>}
      </section>

      <section className="knowledge-record-section">
        <div className="knowledge-section-title">
          <ShieldCheck aria-hidden="true" size={15} />
          <h3>Why trust this?</h3>
          <span>{record.citations.length}</span>
        </div>
        {record.citations.length
          ? (
              <ul className="knowledge-citation-list">
                {record.citations.map((citation, index) => (
                  <li key={`${citation.source}:${index}`}>
                    <span>{index + 1}</span>
                    <div>
                      <strong>{citation.title}</strong>
                      <small>
                        {citation.origin === "inline-citation"
                          ? "Claim-level citation"
                          : "Page-level source"}
                      </small>
                      <code>{citation.source}</code>
                    </div>
                  </li>
                ))}
              </ul>
            )
          : (
              <p className="knowledge-record-note">
                No citation edge is compiled for this node. Treat it as a
                provenance gap.
              </p>
            )}
      </section>
    </article>
  );
}


export function KnowledgeExplorer({
  initialNodeId,
}: KnowledgeExplorerProps) {
  const [summary, setSummary] = useState<KnowledgeSummary | null>(null);
  const [graph, setGraph] = useState<KnowledgeGraphSlice | null>(null);
  const [graphTitle, setGraphTitle] = useState("Knowledge communities");
  const [query, setQuery] = useState("");
  const [nodeType, setNodeType] = useState("");
  const [domain, setDomain] = useState("");
  const [results, setResults] = useState<KnowledgeSearchResults | null>(null);
  const [selected, setSelected] = useState<KnowledgeNodeRecord | null>(null);
  const [pathSource, setPathSource] = useState<KnowledgeNodeSummary | null>(null);
  const [pathTarget, setPathTarget] = useState<KnowledgeNodeSummary | null>(null);
  const [path, setPath] = useState<KnowledgePath | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const selectNode = useCallback(async (nodeId: string) => {
    try {
      setError(null);
      setSelected(await knowledgeApi.node(nodeId));
    } catch (requestError) {
      setError((requestError as Error).message);
    }
  }, []);

  const showNeighborhood = useCallback(async (nodeId: string) => {
    try {
      setBusy(true);
      setError(null);
      const [neighborhood, record] = await Promise.all([
        knowledgeApi.neighborhood(nodeId),
        knowledgeApi.node(nodeId),
      ]);
      setGraph(neighborhood);
      setGraphTitle(`Neighborhood · ${record.title}`);
      setSelected(record);
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      setBusy(false);
    }
  }, []);

  const showCommunity = useCallback(async (community: number) => {
    try {
      setBusy(true);
      setError(null);
      const communityGraph = await knowledgeApi.community(community);
      setGraph(communityGraph);
      setGraphTitle(
        `Community · ${displayLabel(
          communityGraph.community?.label || String(community + 1),
        )}`,
      );
      setSelected(null);
      setPath(null);
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      setBusy(false);
    }
  }, []);

  const showOverview = useCallback(() => {
    setGraph(null);
    setGraphTitle("Knowledge communities");
    setSelected(null);
    setPath(null);
  }, []);

  useEffect(() => {
    let active = true;
    knowledgeApi.summary()
      .then(async (payload) => {
        if (!active) return;
        setSummary(payload);
        if (payload.available) {
          setResults(await knowledgeApi.search(""));
          if (initialNodeId) await showNeighborhood(initialNodeId);
        }
      })
      .catch((requestError: Error) => {
        if (active) setError(requestError.message);
      })
      .finally(() => {
        if (active) setBusy(false);
      });
    return () => {
      active = false;
    };
  }, [initialNodeId, showNeighborhood]);

  useEffect(() => {
    if (!summary?.available) return;
    const timer = window.setTimeout(() => {
      knowledgeApi.search(query, {
        type: nodeType || undefined,
        domain: domain || undefined,
      })
        .then(setResults)
        .catch((requestError: Error) => setError(requestError.message));
    }, 180);
    return () => window.clearTimeout(timer);
  }, [domain, nodeType, query, summary?.available]);

  const connectPath = useCallback(async (target: KnowledgeNodeSummary) => {
    if (!pathSource) {
      setPathSource(target);
      return;
    }
    try {
      setBusy(true);
      setError(null);
      setPathTarget(target);
      const connection = await knowledgeApi.path(pathSource.id, target.id);
      setPath(connection);
      if (connection.found) {
        setGraph(connection);
        setGraphTitle(
          `Connection · ${pathSource.title} to ${target.title}`,
        );
      } else {
        setError("No connection exists between the selected knowledge nodes.");
      }
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      setBusy(false);
    }
  }, [pathSource]);

  const domains = useMemo(
    () => Array.from(
      new Set((summary?.communities ?? []).flatMap((item) => item.domains)),
    ).sort(),
    [summary],
  );
  const nodeTypes = Object.keys(summary?.stats?.by_type ?? {}).sort();

  if (!summary && busy) {
    return (
      <div className="knowledge-loading" aria-live="polite">
        <Network aria-hidden="true" />
        <strong>Loading the QAppsWiki knowledge graph</strong>
        <span>Indexing communities, provenance, and graph relationships</span>
      </div>
    );
  }

  if (!summary?.available) {
    return (
      <div className="knowledge-unavailable" role="status">
        <BookOpenText aria-hidden="true" size={34} />
        <h2>Knowledge graph unavailable</h2>
        <p>
          {summary?.reason || error || "This deployment has no compiled QAppsWiki graph."}
        </p>
        <code>qappswiki build --out wiki-out</code>
        <span>
          Build the pinned corpus artifact, then restart the EQO-QSC API.
        </span>
      </div>
    );
  }

  return (
    <section className="knowledge-explorer" aria-label="QAppsWiki Knowledge Explorer">
      <header className="knowledge-command">
        <div>
          <span><Network aria-hidden="true" size={15} />QAppsWiki knowledge layer</span>
          <h2>Navigate quantum computing as connected evidence</h2>
          <p>
            Search concepts, software, how-tos, and integrations; inspect their
            provenance; then trace how they connect.
          </p>
        </div>
        <dl>
          <div>
            <dt>Authored pages</dt>
            <dd>{summary.stats?.content_nodes ?? 0}</dd>
          </div>
          <div>
            <dt>Relations</dt>
            <dd>{summary.stats?.edges ?? 0}</dd>
          </div>
          <div>
            <dt>Communities</dt>
            <dd>{summary.stats?.communities ?? 0}</dd>
          </div>
          <div>
            <dt>Corpus revision</dt>
            <dd>{summary.source_revision?.slice(0, 8) || "unversioned"}</dd>
          </div>
        </dl>
      </header>

      {error
        ? (
            <div className="knowledge-error" role="alert">
              <CircleAlert aria-hidden="true" size={17} />
              <span>{error}</span>
              <button type="button" onClick={() => setError(null)}>Dismiss</button>
            </div>
          )
        : null}

      <div className="knowledge-layout">
        <aside className="knowledge-discovery" aria-label="Knowledge discovery">
          <div className="knowledge-search">
            <Search aria-hidden="true" size={17} />
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search the corpus"
              aria-label="Search QAppsWiki"
            />
          </div>
          <div className="knowledge-filters">
            <label>
              <span>Type</span>
              <select
                value={nodeType}
                onChange={(event) => setNodeType(event.target.value)}
              >
                <option value="">All types</option>
                {nodeTypes.map((type) => (
                  <option key={type} value={type}>{displayLabel(type)}</option>
                ))}
              </select>
            </label>
            <label>
              <span>Domain</span>
              <select
                value={domain}
                onChange={(event) => setDomain(event.target.value)}
              >
                <option value="">All domains</option>
                {domains.map((item) => (
                  <option key={item} value={item}>{displayLabel(item)}</option>
                ))}
              </select>
            </label>
          </div>

          <div className="knowledge-results-heading">
            <strong>{query || nodeType || domain ? "Search results" : "Connected pages"}</strong>
            <span>{results?.total ?? 0}</span>
          </div>
          <div className="knowledge-results">
            {(results?.items ?? []).map((node) => (
              <button
                className={selected?.id === node.id ? "is-selected" : ""}
                key={node.id}
                type="button"
                onClick={() => selectNode(node.id)}
              >
                <i style={{ background: TYPE_COLORS[node.type] ?? TYPE_COLORS.untyped }} />
                <span>
                  <strong>{node.title}</strong>
                  <small>{displayLabel(node.type)} · {node.degree} links</small>
                </span>
                <ChevronRight aria-hidden="true" size={15} />
              </button>
            ))}
          </div>

          <div className="knowledge-community-index">
            <div className="knowledge-results-heading">
              <strong>Communities</strong>
              <span>{summary.communities?.length ?? 0}</span>
            </div>
            {(summary.communities ?? []).map((community) => (
              <button
                key={community.index}
                type="button"
                onClick={() => showCommunity(community.index)}
              >
                <i style={{
                  background: COMMUNITY_COLORS[
                    community.index % COMMUNITY_COLORS.length
                  ],
                }} />
                <span>
                  <strong>{displayLabel(community.label)}</strong>
                  <small>{community.size} pages · hub {compactLabel(community.god_node || "—", 22)}</small>
                </span>
              </button>
            ))}
          </div>
        </aside>

        <main className="knowledge-map">
          <header>
            <div>
              {graph
                ? (
                    <button type="button" onClick={showOverview}>
                      <ArrowLeft aria-hidden="true" size={15} />
                      All communities
                    </button>
                  )
                : <span>Atlas overview</span>}
              <h3>{graphTitle}</h3>
            </div>
            <span>
              {graph
                ? `${graph.nodes.length} nodes · ${graph.edges.length} relations`
                : `${summary.communities?.length ?? 0} thematic communities`}
            </span>
          </header>
          <GraphCanvas
            summary={summary}
            graph={graph}
            selectedNodeId={selected?.id ?? null}
            onSelectNode={selectNode}
            onSelectCommunity={showCommunity}
          />
          {busy
            ? <div className="knowledge-map-busy" role="status">Updating graph view</div>
            : null}
          {graph?.truncated
            ? (
                <p className="knowledge-truncation">
                  Showing the most connected nodes in this graph slice.
                </p>
              )
            : null}
          {path
            ? (
                <div className="knowledge-path-strip">
                  <Route aria-hidden="true" size={16} />
                  <strong>{path.length} hops</strong>
                  <span>{path.path.map((id) => compactLabel(id, 22)).join(" → ")}</span>
                  <button
                    type="button"
                    onClick={() => {
                      setPath(null);
                      setPathSource(null);
                      setPathTarget(null);
                      showOverview();
                    }}
                  >
                    Clear
                  </button>
                </div>
              )
            : pathSource
              ? (
                  <div className="knowledge-path-strip">
                    <GitBranch aria-hidden="true" size={16} />
                    <strong>Path starts at {pathSource.title}</strong>
                    <span>Select another node, then choose “Connect from…”</span>
                    <button type="button" onClick={() => setPathSource(null)}>Clear</button>
                  </div>
                )
              : null}
        </main>

        <aside className="knowledge-details" aria-label="Knowledge record">
          <NodeRecord
            record={selected}
            pathSource={pathSource}
            onExplore={showNeighborhood}
            onSelectRelated={selectNode}
            onSetPathSource={(node) => {
              setPathSource(node);
              setPathTarget(null);
              setPath(null);
            }}
            onSetPathTarget={connectPath}
            onClear={() => setSelected(null)}
          />
        </aside>
      </div>
    </section>
  );
}
