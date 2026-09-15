# ChatQEC QEC Tools OCI Smoke — 2026-09-14

- Scope: local candidate for four governed `chatqec-mcp-tools` operations
- Source: `QSCSoftwareEcosystem/chatqec-mcp-tools`
- Source revision: `dd19a85b08637a61dc1afc124d2f4b32745b527b`
- Source archive digest:
  `sha256:7fb55933bdcf668b141358b45ab0940e2b1904d2c0ba49431421af0aff274692`
- Platform: `linux/amd64`
- Builder: Docker 29.7.2 on an ARM64 development host, with the declared
  `--platform linux/amd64` build and execution target
- Local image: `qhpc/chatqec-qec-tools:dd19a85-linux-amd64`
- Local image identity:
  `sha256:2d8fa49503f219a9b95178eedfca96a2648d186f76397ac9beee5a7668abb2dc`

## Procedure

EQO prepared the deterministic context using the revision-pinned source archive
and twenty checksum-verified Python wheels. The Docker build was run with
`--network none`. The resulting image runs as a non-root user, with a
read-only root filesystem, no Linux capabilities, a `no-new-privileges`
setting, a bounded temporary filesystem, and network access disabled.

The container imports the exact upstream `code_params`, `stim_simulate`,
`stim_diagram`, and `pymatching_decode` modules directly. It does not start the
MCP server or accept an MCP command. The EQO-owned entrypoint admits only four
reviewed subcommands: bounded code family/distance parameters, a mounted Stim
circuit plus bounded shot count, a validated Stim SVG diagram, or a bounded
PyMatching decoder result. It writes versioned `qhpc.qec-code-parameters@1`,
`qhpc.stim-simulation-samples@1`, `qhpc.stim-diagram@1`, and
`qhpc.qec-decoder-result@1` artifacts.

The contracted OCI smoke invoked the rotated surface-code calculation at
distance three. It produced `/outputs/parameters.json` with digest
`sha256:9443b1fc0bfde8e65d49d4c25f54740319e2f7c6a76155200d7ee1428ccba23c`
and verified the reported graphlike distance of three.

The second smoke mounted the checked-in Bell Stim circuit with four shots. It
produced `/outputs/samples.json` with digest
`sha256:978f3252beb3de92fbeadee9d4965c5a6e4258bb49b2c6339f5e8beb49a6ce62`
and verified the shot count and versioned sample-artifact schema.

The third smoke rendered the same checked-in circuit as a validated SVG. It
produced `/outputs/diagram.svg` with digest
`sha256:159a3f91a525940723289ed2a444ab9d983370511110d59e3f23517526733f89`
and verified its SVG root element. Before persistence, the EQO adapter rejects
active SVG elements and external references and caps the artifact at 10 MiB.

The fourth smoke decoded the checked-in detector-annotated repetition circuit
with 64 shots through upstream PyMatching 2.4.0. It produced
`/outputs/result.json` with digest
`sha256:bba8deb047a4b3d7d9f425c3d243d5fd25f5756cd5203502abf332393ff430c7`
and verified its schema and exact shot count.

## Boundary

This is local candidate evidence only. The image is neither published nor an
accepted HPC runtime. Promotion still requires source-authority and project
review, dependency/license/vulnerability and provenance review, immutable
registry publication, SIF conversion, and target-worker acceptance. It does
not authorize the remaining ChatQEC MCP tools.
