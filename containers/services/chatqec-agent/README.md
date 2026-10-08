# ChatQEC contained circuit-tool service

This is the EQO Local service boundary for explicit ChatQEC circuit tools. It
runs the pinned `chatqec-mcp-tools` source in one unprivileged container. The
service never starts a tool on the host and never receives a Docker socket.

It accepts explicitly supplied Stim/Tsim circuits and invokes the real
contained tool. It also retrieves concise excerpts from the immutable bundled
canonical corpus, returns page-and-line source-ledger citations, and provides a
deterministic extractive answer when those sources are sufficient. When
`eqo local up` is explicitly configured with an OpenAI model and scoped API
key, the Responses API receives that same bounded evidence to explain an actual
result or answer a general QEC question. Raw measurements remain measurement
data, not detector-event output, and the model does not create simulation
evidence.

The full vector-retrieval/model-directed-MCP loop remains a separately governed
`chatqec-query` deployment. It requires an approved model provider, an
immutable Qdrant corpus, restricted provider egress, and an image that bundles
the exact MCP tool server; it is not silently substituted by the local source
ledger or optional model path.

The local lifecycle builds this image offline from the already-admitted
`qhpc/chatqec-tsim:dd19a85-linux-amd64` image.
