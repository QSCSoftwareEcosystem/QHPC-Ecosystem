# LightStim OCI Smoke Evidence

Date: 2026-07-27

This evidence covers the local immutable OCI build and constrained smoke test
for `lightstim-simulation@0.1.0/estimate-logical-error`. It is not registry
publication, an accepted Apptainer SIF, supply-chain attestation, or DOE target
acceptance.

## Inputs

- Source: `https://github.com/QuTone/LightStim`
- Revision: `b08d4c2f9cd69531a51b658e6f88089be69f16c0`
- Git archive digest:
  `sha256:9310d79639685697937dd971113030e33cbe2846a5918287c31c67b7f06ea8ac`
- Source date epoch: `1784655175`
- Platform: `linux/amd64`
- Runtime contract: `containers/operations/lightstim/runtime.yaml`
- Python base: `python:3.12.11-slim-bookworm` at the contract digest
- Dependencies: the complete Linux wheel set and every SHA-256 digest are
  recorded in the runtime contract; the operation build had no network access

## Build

- Local tag: `qhpc/lightstim:b08d4c2-linux-amd64`
- OCI manifest and local image ID:
  `sha256:0787bba8b32fe251dcc82ab8bf1e6ced21e78281bf350813dfe3426adb73984f`
- Image size: `141,610,197` bytes
- Runtime user: `65532:65532`
- Entrypoint: `/opt/qhpc/bin/qhpc-lightstim-estimate`
- A second no-cache build from the exact prepared context produced the same
  manifest and config digests.

The runtime includes only LightStim's CPU PyMatching operation boundary and
its declared Python dependencies. Optional GPU and additional decoder backends
are not installed or claimed.

## Constrained Verification

The smoke test used no network, a read-only root filesystem, all Linux
capabilities dropped, `no-new-privileges`, a small `noexec,nosuid` `/tmp`, one
read-only Stim input bind, one writable output bind, and one CPU worker.

The bounded 100-shot repetition fixture completed in `5,103 ms` and produced
`/outputs/estimate.json`, 174 bytes, with run-specific digest
`sha256:63e8ab36b47d6ec92b919aa805a15ff9e7a1846630336781ff058e8bdc28c049`.
The output identifies the `pymatching` decoder and reports the accepted shots,
errors, logical-error estimate, confidence width, and execution time. The
artifact checksum is run-specific because timing and stochastic statistics are
part of the result.

## Remaining Gates

- Publish an immutable OCI registry reference.
- Generate and review an SBOM, signature, and build attestation.
- Convert the accepted OCI release to a digest-verified SIF.
- Replace planned storage and execution-target values with site-approved
  values.
- Compare native and container statistics and performance on the target.
- Exercise worker counts and resource accounting beyond the one-worker smoke
  boundary.
