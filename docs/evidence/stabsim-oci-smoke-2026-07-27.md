# STABSim OCI Smoke Evidence

Date: 2026-07-27

This evidence covers only the local immutable OCI build and constrained smoke
test for `stabsim-simulator@0.1.0/analyze-metrics`. It is not registry
publication, an accepted Apptainer SIF, supply-chain attestation, or DOE target
acceptance.

## Inputs

- Source: `https://github.com/seangarn32/STABSim`
- Revision: `a0d8d2e2a9fdec9785857104220b8e7f0346c761`
- Git archive digest:
  `sha256:760bcd2908389ea85071b743dec65ba8b1270aaf4fa7fc9e4e870fbc93c326f6`
- Source date epoch: `1779411961`
- Platform: `linux/amd64`
- Runtime contract: `containers/operations/stabsim/runtime.yaml`

## Build

- Local tag: `qhpc/stabsim:a0d8d2e-linux-amd64`
- OCI manifest and local image ID:
  `sha256:4ee1a6deae715be6c22d44447b6f6a655a81c0ee1be63c67ab601431c44a904b`
- Image size: `28,761,421` bytes
- Runtime user: `65532:65532`
- Entrypoint: `/opt/qhpc/bin/qhpc-stabsim-metrics`
- A second no-cache build from the exact prepared context produced the same
  manifest and config digests.

The C++17 binary is linked with static GCC and C++ runtimes, stripped, and
built with source-path remapping. Both build and runtime bases are pinned by
digest. The prepared context verifies exact file names, digests, modes, and
`SOURCE_DATE_EPOCH` timestamps before Docker is invoked.

## Constrained Verification

The smoke test used no network, a read-only root filesystem, all Linux
capabilities dropped, `no-new-privileges`, a small `noexec,nosuid` `/tmp`, one
read-only input bind, one writable output bind, and the controlled argument
vector `--random-seed 42`.

The Bell-circuit fixture completed in 310 ms and produced
`/outputs/metrics.json`, 199 bytes, with digest
`sha256:01bef538a137c218f0d1f42591ca819a0450baac1dbdb19eb08add9947145c26`.
The output reported circuit depth 2 and one two-qubit gate. An arbitrary
`--help` argument was rejected with exit status 64.

## Remaining Gates

- Obtain explicit upstream license terms before distributing the image.
- Publish an immutable OCI registry reference.
- Generate and review an SBOM, signature, and build attestation.
- Convert the accepted OCI release to a digest-verified SIF.
- Replace the planned storage and execution-target values with site-approved
  values.
- Run native/container equivalence, I/O, latency, and target acceptance tests.
