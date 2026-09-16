# ADR 0012: Independent Stim and Tsim operation images

## Status

Proposed — local build design underway.

## Context

EQO now publishes `stim-simulation` and `tsim-simulation` as independent
capabilities, but their initial operations deliberately reuse the verified
ChatQEC wrapper images. Those images are appropriate for the first capability
release because their source inputs, Linux/AMD64 behavior, network-disabled
execution boundary, and smoke fixtures are already pinned and tested.

They are not independent simulator image releases: their OCI labels, runtime
contract identities, and release evidence still identify ChatQEC operations.
Relabeling or rebuilding them changes the image digest and invalidates the
previous local smoke evidence for the new image.

## Decision

Create two new, narrowly scoped Linux/AMD64 OCI operation images:

| Capability | Operation | Proposed local image | Proposed GHCR package |
| --- | --- | --- | --- |
| `stim-simulation` | `simulate`, `render-diagram` | `qhpc/stim:0.1.0-linux-amd64` | `ghcr.io/qscsoftwareecosystem/eqo-stim` |
| `tsim-simulation` | `simulate` | `qhpc/tsim:0.1.0-linux-amd64` | `ghcr.io/qscsoftwareecosystem/eqo-tsim` |

The first split images retain the exact bounded adapter behavior presently
used by the validated wrappers. Their OCI labels must state that the image is
an EQO operation image built from the pinned `chatqec-mcp-tools` wrapper
source; they must not claim an upstream-native Stim or Tsim build. A later
native-image design may replace that adapter source only with separate review
and equivalence evidence.

Each image receives an independent `OperationRuntime` contract, dedicated
recipe and entrypoint files, a pinned source archive, exact wheel set,
network-disabled build and execution policy, fixture, output assertions, and
new digest. Existing `chatqec-*` contracts and images remain unchanged as
historical wrapper evidence.

## Release requirements

Before a new image replaces a wrapper reference in a capability record:

1. Verify runtime-contract and deterministic build-context digests.
2. Build the exact Linux/AMD64 image with build-step networking disabled.
3. Run the declared OCI smoke fixture plus direct EQO operation tests.
4. Produce and review a license inventory and SPDX SBOM.
5. Produce source-to-image provenance and sign the immutable image digest.
6. Publish by immutable digest to the proposed GHCR package; do not publish a
   floating `latest` tag.
7. Verify an anonymous pull by immutable digest after logging out.
8. Update the capability runtime reference, public-image inventory, registry,
   release evidence, and Tool Record only with the resulting digest.

These releases remain development-only. They neither approve a hardware
backend nor establish facility-HPC acceptance.

## Consequences

The existing first-class capabilities are usable immediately through their
validated wrappers. New standalone image work cannot reuse their signatures,
SBOMs, attestation, or smoke results: every changed image receives new
evidence. GHCR publication and public visibility are intentionally deferred
until the local build and supply-chain evidence are reviewed.
