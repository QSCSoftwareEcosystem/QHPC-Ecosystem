# ChatQEC Query Container Scaffold

- Date: 2026-09-11
- EQO scope: container-only adapter and readiness scaffold
- Upstream source revision: `a1ddc2e4916b1f4152fba4c94c9c7512eea0d977`
- Upstream Git archive digest:
  `sha256:1af97636073b031a2e859bd56e544ea2064c3b7af1ebf6af827202177a472718`
- Upstream `uv.lock` digest:
  `sha256:214fff8b9ffc463ecea2667a15436b6beb8cb8a20173667941003b891508a511`
- Python 3.11 Linux/amd64 base:
  `docker.io/library/python:3.11.13-slim-bookworm@sha256:cec9aa7aa96eea4fa036e9b82be1e6b325f2e3707f462d885868df51ec0a4b47`
- Qdrant Linux/amd64 base:
  `docker.io/qdrant/qdrant:v1.12.0@sha256:d8cd4bb56e737c78d7e06e364584eb2b58097977aa12e0a9324b18bffddc17ec`

## Implemented boundary

`chatqec_query_service.py` is a project-owned HTTP/SSE boundary around the
actual upstream `ChatQEC` Python API. It does not copy Streamlit and creates a
fresh upstream object for each accepted EQO request, preserving the
subject/workspace/conversation history supplied by the QHPC boundary without
retaining process-global memory.

The adapter calls upstream `ask` once, then emits bounded token events,
governed citations, and one final response event. This avoids the upstream
Streamlit pattern that reruns a non-tool query to recover citations after a
stream. It rejects MCP subprocess configuration, Tavily, web fallback,
QAppsWiki, image input, figure paths, and automatic provider selection.

The query image is prepared only by `eqo chatqec-query prepare-context`; that
command verifies the pinned Git archive and lockfile, copies a reviewed
wheelhouse, and records checksums before a `docker|podman build --network=none`.
The Compose template joins Qdrant only to an internal network and publishes the
query adapter only on a loopback host port. A separate externally provisioned
egress network is required for the one future approved provider endpoint.

## Validation performed

```text
.venv/bin/pytest -q tests/test_chatqec_query_service.py tests/test_chatqec_service.py tests/test_service_adapters.py
22 passed

.venv/bin/python -m py_compile src/qhpc_ecosystem/chatqec_query_container.py src/qhpc_ecosystem/cli.py
.venv/bin/eqo chatqec-query --help
```

The query-adapter tests cover degraded readiness, governed citation mapping,
one upstream invocation per SSE request, fallback labeling, provider-auto
rejection, and deterministic context preparation/verification.

## Not performed and still blocked

No upstream image was built, no Qdrant container was started, no model endpoint
or provider credential was contacted, and no corpus snapshot was imported. A
full smoke requires a complete reviewed wheelhouse, an immutable corpus
manifest/snapshot, one approved provider/model and secret injection path, and
a model-egress network approved by the responsible institution.
