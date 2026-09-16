# NWQ-Sim CPU OCI Smoke Evidence

Date: 2026-09-16

This evidence covers the local immutable OCI build and constrained smoke test
for `nwqsim-cpu-simulation@0.1.0/simulate-qasm`, plus publication of that
validated artifact to GHCR. It does not establish supply-chain attestation,
an Apptainer SIF, a facility-HPC target, or a QFw workflow runtime.

## Inputs and build

- Source revision: `b35763d846e6512ed817d3f88ac8ce79a7e82a7e`
- Git archive digest: `sha256:87ece7adc6b991eb8f1b5fb35a1825be77abdfb9cdf0f83f9ccd460a9f383589`
- Platform: `linux/amd64`
- Runtime contract: `containers/operations/nwqsim/runtime.yaml`
- Local tag: `qhpc/nwqsim:0.1.0-linux-amd64`
- Local OCI config/image ID: `sha256:9e0dfb6168bd03d98165315144150a386314e855c4aacf206da76116a0b8c5bc`
- Image size: `76,237,538` bytes
- Public Linux/AMD64 OCI manifest:
  `ghcr.io/qscsoftwareecosystem/eqo-nwqsim:0.1.0-linux-amd64@sha256:80200dfd967c5575b6ca8cf1a71a071ff6aaa03500564d0b412f71d3671f6bbf`

The image was built from the prepared sealed context with build networking
disabled. A second no-cache build from that same context produced the identical
local image ID and image size.

## Constrained verification

The two-qubit OpenQASM Bell fixture ran with 128 shots, seed 42, and a
16-qubit admission maximum. The harness used no network, a read-only root
filesystem, all Linux capabilities dropped, `no-new-privileges`, a small
`noexec,nosuid` `/tmp`, a read-only circuit bind, and a writable output bind.

The operation completed in 126 ms and produced
`/outputs/measurements.json` (215 bytes,
`sha256:e53f0a14ce70bef5d30d044979373b05bad66d42c943d451cb769ad1be6cd696`).
The normalized result declares CPU state-vector simulation, two qubits, and
counts only for the Bell outcomes. The wrapper rejects unrecognized argument
vectors and does not expose the upstream runner's MPI, GPU, noise, Qobj,
benchmark, or state-file flags.

## Remaining gates

- Generate and review SBOM, signature, and provenance attestation for that
  published image.
- Convert the accepted image to a digest-verified SIF and complete target
  acceptance before any facility-HPC use.
