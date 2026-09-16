# QAppsWiki Read-Only Knowledge Interface

EQO-QSC consumes a compiled QAppsWiki `qappswiki-graph-0` artifact. The
QAppsWiki repository remains authoritative for corpus parsing, validation,
community detection, provenance, and graph construction. The ecosystem adapter
indexes that immutable JSON artifact without modifying the source corpus.

The API publishes these read-only routes:

| Route | Purpose |
| --- | --- |
| `GET /api/v1/knowledge` | Corpus identity, counts, thematic communities, and aggregated community connections |
| `GET /api/v1/knowledge/nodes` | Search and filter authored nodes by term, type, domain, or community |
| `GET /api/v1/knowledge/nodes/{id}` | Node record with incoming and outgoing relationships plus citations |
| `GET /api/v1/knowledge/communities/{index}` | Degree-ranked graph slice for one thematic community |
| `GET /api/v1/knowledge/neighborhood/{id}` | One- or two-hop focused graph around a node |
| `GET /api/v1/knowledge/path` | Shortest undirected connection between two nodes |

EQO Local packages the graph compiled from its pinned QAppsWiki revision and
passes that immutable asset to the API explicitly, so a first-time installation
does not need a sibling checkout or graph compiler. Deployments may supply a
different immutable artifact with `eqo local up --qappswiki-graph` or
`eqo serve --qappswiki-graph`. The lower-level `eqo serve` command otherwise
discovers `<QAppsWiki catalog local_path>/wiki-out/graph.json` for source-workspace
development.

The Workbench deliberately starts at the community level and requests focused
subgraphs on demand. Synthetic missing and external nodes remain available in
relationships and provenance but are excluded from ordinary search results.

This interface does not expose QAppsWiki ingest, extraction, promotion, corpus
editing, or online freshness mutation. Those actions remain in the
project-owned CLI and its curator workflow.
