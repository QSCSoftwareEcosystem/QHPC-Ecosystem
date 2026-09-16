# Stim and Tsim independent-image readiness — 2026-09-16

## Verified starting point

The current ChatQEC Stim and Tsim wrapper runtime contracts pin a Linux/AMD64
Python base image, a Git archive of `chatqec-mcp-tools` at
`dd19a85b08637a61dc1afc124d2f4b32745b527b`, every required wheel archive,
their SHA-256 digests, fixed entrypoints, non-root execution, no execution
network, read-only roots, typed mounts, and smoke fixtures. The existing
wrapper image IDs are retained as baseline evidence only.

## Current build-input audit

The repository worktree did not contain the pinned `chatqec-mcp-tools`
checkout or an approved wheel cache. A fresh detached checkout at the pinned
commit was acquired in the ignored development build area; its Git archive
matches the required
`sha256:7fb55933bdcf668b141358b45ab0940e2b1904d2c0ba49431421af0aff274692`.
The exact 57 wheel archives declared by the Stim and Tsim runtime contracts
were then acquired by filename and verified against their declared SHA-256
digests. Both deterministic build contexts now verify successfully.

The `.development/eqo-local-install-source` checkout remains an installation
source tree with unrelated local modifications and was not used as a build
input. No standalone image has been built, relabeled, signed, or published.

## Next build action

Create and verify new dedicated runtime contracts from these pinned inputs;
then build and smoke-test their images before generating new SBOM, provenance,
signature, or registry references.
