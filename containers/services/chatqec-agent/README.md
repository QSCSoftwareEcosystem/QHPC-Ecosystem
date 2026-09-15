# ChatQEC contained circuit-tool service

This is the EQO Local service boundary for explicit ChatQEC circuit tools. It
runs the pinned `chatqec-mcp-tools` source in one unprivileged container. The
service never starts a tool on the host and never receives a Docker socket.

It accepts explicitly supplied Stim/Tsim circuits and invokes the real
contained tool; it does not fabricate a model answer. The full model/RAG/MCP
loop is a separately governed `chatqec-query` deployment. It requires an
approved model provider, an immutable Qdrant corpus, restricted provider
egress, and an image that bundles the exact MCP tool server; it is not silently
substituted by this local direct path.

The local lifecycle builds this image offline from the already-admitted
`qhpc/chatqec-tsim:dd19a85-linux-amd64` image.
