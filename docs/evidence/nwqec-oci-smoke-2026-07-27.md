# NWQEC OCI Smoke Evidence

Date: 2026-07-27

This evidence covers the local immutable OCI build and constrained smoke test
for `nwqec-qec-transpilation@0.1.0/count-clifford-t`. It is not registry
publication, an accepted Apptainer SIF, supply-chain attestation, or DOE target
acceptance.

## Inputs

- Source: `https://github.com/pnnl/nwqec`
- Revision: `d93299c2a0fe47fb7758bff02b456acfb3ac4416`
- Git archive digest:
  `sha256:fe1b6185790329b864f58d05c43d49eb9f92e26f091d556c5426ec6f19d2d70e`
- Source date epoch: `1781758769`
- Platform: `linux/amd64`
- Runtime contract: `containers/operations/nwqec/runtime.yaml`

## Build

- Local tag: `qhpc/nwqec:d93299c-linux-amd64`
- OCI manifest and local image ID:
  `sha256:ec487f7735925388fb960ea3a0c97aca2298f51c05beb1b96f3d90a81f7b9e7b`
- Image size: `29,114,085` bytes
- Runtime user: `65532:65532`
- Entrypoint: `/opt/qhpc/bin/qhpc-nwqec-counts`
- A second no-cache build from the exact prepared context produced the same
  manifest and config digests.

The operation builds NWQEC's audited C++ CLI directly and does not depend on
the repository's Python/scikit-build packaging path. The repository's vendored
GMP 6.3.0 and MPFR 4.2.2 sources are built with networking disabled. GMP
assembly is disabled and the compiler uses the generic x86-64 baseline; this
avoids carrying host-detected instruction choices into the image.

## Constrained Verification

The smoke test used no network, a read-only root filesystem, all Linux
capabilities dropped, `no-new-privileges`, a small `noexec,nosuid` `/tmp`, one
read-only QASM input bind, one writable output bind, and only the three typed
operation parameters.

The Clifford-only Bell fixture completed in `485 ms` and produced
`/outputs/counts.json`, 139 bytes, with digest
`sha256:722b06d5ea13e7cf5615702ab3f9d8bfd6665c46c0c1fff68b564e9542ca1145`.
The output reports two source qubits and the selected total-error policy. An
additional constrained invocation with epsilon zero was rejected before input
access with exit status `64`.

## Remaining Gates

- Publish an immutable OCI registry reference.
- Generate and review an SBOM, signature, and build attestation.
- Convert the accepted OCI release to a digest-verified SIF.
- Replace planned storage and execution-target values with site-approved
  values.
- Run native/container equivalence and target performance tests, including
  representative non-Clifford synthesis workloads.
