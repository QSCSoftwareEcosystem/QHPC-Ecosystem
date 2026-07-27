# FTPrimitiveBench OCI Smoke Evidence

Date: 2026-07-27

This evidence covers the local immutable OCI build and constrained smoke test
for `ftprimitivebench-primitives@0.1.0/build-memory`. It is not registry
publication, an accepted Apptainer SIF, supply-chain attestation, or DOE target
acceptance.

## Inputs

- Source: `https://github.com/ShuwenKan/FTPrimitiveBench`
- Revision: `ba15eba263ac6d641d225984fa074f4ee25bb462`
- Git archive digest:
  `sha256:3c9686257c7c4c27fe661c37525156d37b4457172e33ba256479cea70bf28076`
- Source date epoch: `1778037194`
- Platform: `linux/amd64`
- Runtime contract:
  `containers/operations/ftprimitivebench/runtime.yaml`
- Python base: `python:3.12.11-slim-bookworm` at the contract digest
- Offline dependencies: checksum-pinned NumPy 2.3.2 and Stim 1.15.0 wheels

## Build

- Local tag: `qhpc/ftprimitivebench:ba15eba-linux-amd64`
- OCI manifest and local image ID:
  `sha256:329c0f99e7fb2373323a5d3fae5f1f4266d290914ec6f6a8bdd60ef2326259c9`
- Image size: `67,240,094` bytes
- Runtime user: `65532:65532`
- Entrypoint: `/opt/qhpc/bin/qhpc-ftprimitivebench-memory`
- A second no-cache build from the exact prepared context produced the same
  manifest and config digests.

The operation build ran with networking disabled. The source archive, recipe,
wrapper, base image, dependency wheels, file modes, and timestamps are pinned
by the runtime contract.

## Constrained Verification

The smoke test used no network, a read-only root filesystem, all Linux
capabilities dropped, `no-new-privileges`, a small `noexec,nosuid` `/tmp`, no
input bind, and one writable declared output bind. The wrapper accepted only
the five typed operation parameters.

The distance-three, three-round memory fixture completed in `1,681 ms` and
produced `/outputs/circuit.stim`, 3,643 bytes, with digest
`sha256:565a0b234810359744d91540071491a2bf4c55761e957e0b4d52c649eda67832`.
The output contains detector and observable annotations.

## Remaining Gates

- Publish an immutable OCI registry reference.
- Generate and review an SBOM, signature, and build attestation.
- Convert the accepted OCI release to a digest-verified SIF.
- Replace planned storage and execution-target values with site-approved
  values.
- Run native/container equivalence, I/O, latency, and target acceptance tests.
