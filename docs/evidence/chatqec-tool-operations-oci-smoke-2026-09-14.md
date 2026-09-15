# ChatQEC Tool Operations OCI Smoke Evidence — 2026-09-14

## Scope

All eight tools registered by the canonical `chatqec-mcp-tools` source at
`dd19a85b08637a61dc1afc124d2f4b32745b527b` were run through EQO-owned,
network-disabled Linux/amd64 adapters. The MCP server was not started.

## Candidate images and results

| Image | Local immutable image ID | Operations smoke-tested |
| --- | --- | --- |
| `qhpc/chatqec-qec-tools:dd19a85-linux-amd64-v2` | `sha256:b3b7a84fd409ef979df26e37dad4ef45f946782238ec6c085a345a154ef125e2` | `code-params`, `stim-simulate`, `stim-diagram`, `pymatching-decode`, `threshold-sweep`, `glcb-visualize-url` |
| `qhpc/chatqec-lightstim:dd19a85-linux-amd64-v3` | `sha256:476e66c70130e8f413827a3264659581d92a80fbc4e5ec9113e67f596d760d21` | `qec-circuit-build` with LightStim `47dd74976780192ae901d91958863cced1165354` |
| `qhpc/chatqec-tsim:dd19a85-linux-amd64` | `sha256:05524a6a1cb04618fc0797c46f071ac5447cd2f89aa7fe36598c2fa550538db0` | `tsim-simulate` using `bloqade-tsim` `0.1.5` |

Each smoke run used a read-only root filesystem, no network, all Linux
capabilities dropped, a non-root runtime user, declared input/output mounts,
and a bounded fixture or parameter set.

## Limits of this evidence

This is local candidate evidence only. It does not publish the images, create
an Apptainer/SIF release, approve the wheel sets, establish named project
release ownership, verify a target HPC worker, or certify scientific results.
