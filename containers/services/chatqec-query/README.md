# ChatQEC Read-Only Query Stack

This directory packages the actual pinned ChatQEC RAG pipeline behind an
EQO-owned HTTP/SSE adapter. It is not the bundled canonical extractor and it
does not package Streamlit.

The query container accepts only the versioned EQO request contract, creates a
fresh upstream `ChatQEC` object for each request, performs one `ask` call, and
emits text/citations/final metadata through the same request. It never passes
an MCP command to upstream ChatQEC. `CHATQEC_MCP_SERVER`, Tavily, web fallback,
image input, QAppsWiki, figures, and automatic provider selection are rejected
or disabled.

## Build boundary

Prepare the context from a clean checkout of the pinned upstream repository
and a reviewed offline wheelhouse:

```bash
eqo chatqec-query prepare-context ../ChatQEC /approved/chatqec-wheelhouse .qhpc/build/chatqec-query
docker build --network=none --file containers/services/chatqec-query/Containerfile --tag qhpc/chatqec-query:a1ddc2e-linux-amd64 .qhpc/build/chatqec-query
```

The context preparation verifies the Git revision, deterministic Git archive
digest, commit timestamp, and upstream `uv.lock` digest. It records every
wheel checksum in `build-metadata.json`; the Docker build has no dependency
download path. The image imports the admitted source archive directly rather
than invoking the upstream PEP 517 backend: upstream declares `hatchling`
without pinning it in `uv.lock`, and EQO does not introduce an implicit build
dependency at image-build time. Its runtime therefore consists only of the
verified source archive and the recorded locked wheels. An image digest, SBOM,
signature, provenance attestation, and approved registry destination are still
release gates.

## Wheelhouse collection and review

The source-controlled `Containerfile.wheelhouse` creates a **candidate**
Linux/amd64 wheelhouse from the pinned `uv.lock`; it does not make those
dependencies approved. Build it only from the exact sibling upstream checkout:

```bash
docker build --platform=linux/amd64 \
  --file containers/services/chatqec-query/Containerfile.wheelhouse \
  --tag qhpc/chatqec-wheelhouse:a1ddc2e-linux-amd64 ../ChatQEC
```

After an allowed dependency/license/vulnerability review, extract only the
regular `.whl` files to an approved directory and supply that directory to
`eqo chatqec-query prepare-context`. The query image itself still runs
`docker|podman build --network=none`; it cannot download, compile, or select
additional dependencies.

## Deployment boundary

`compose.yaml` has two networks. Qdrant uses only the internal private
network and has no host-published port. The query container is published only
to `127.0.0.1`; it joins a separately provisioned egress network solely for
the deployment-selected model endpoint.

The profile example is deliberately degraded: no provider, corpus, Qdrant, or
credentials are selected. A ready profile must select exactly one of
`anthropic`, `gemini`, or `huggingface`; name its standard credential
environment; point at the immutable corpus manifest; and agree with the
mounted upstream `config.yaml`. The profile and manifest contain no secrets.

Until those project/institutional inputs are accepted, keep using the clearly
labeled **ChatQEC canonical-corpus extractive fallback** for offline EQO Local
verification. Do not replace it with an ungoverned native ChatQEC process.
