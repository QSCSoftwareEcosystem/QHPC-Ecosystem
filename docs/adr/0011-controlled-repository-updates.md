# ADR 0011: Controlled Repository Updates

- Status: Accepted
- Date: 2026-07-29

## Context

The ecosystem pins source revisions and immutable runtime digests so a workflow
can be reproduced. Pulling a repository inside a running image would make the
same runtime identity execute different code. Updating every integration
directly from an upstream default branch would also bypass deployment
admission, source review, runtime rebuilds, and HPC acceptance.

Users nevertheless need one simple mechanism to discover and prepare upstream
changes from either the CLI or Workbench.

## Decision

One repository-update controller serves the CLI and QHPC API. It derives its
targets exclusively from the active deployment profile and admitted registry:

1. **List** reports the active source pin and any persisted check or candidate.
2. **Check** resolves only the target's configured remote ref with
   non-interactive `git ls-remote`.
3. **Stage** rechecks that ref, requires the selected full commit hash to remain
   current, and prepares a clean detached checkout in a revision-addressed
   directory.
4. **Discard** releases the selected candidate but retains the immutable
   checkout as a local cache.
5. **Build** is available only where a reviewed operation-runtime contract
   declares an explicit candidate-rebuild policy. It derives a separate,
   unpublished build-ready contract from the verified detached commit, runs
   the existing no-network OCI build and constrained smoke test, and records
   bounded local evidence without changing the active release.

The deployment profile supplies the canonical repository to check. A capability
may separately retain the source URL of its admitted release when that commit
does not exist in the canonical repository. The controller exposes both values
and never rewrites release provenance merely because ownership moved.

The browser may select only a component ID and the exact candidate returned by
the controller. It cannot provide a repository URL, branch, credential, local
path, or Git option. Standalone API deployments must explicitly enable update
routes; the loopback development stack enables them by default.

Staging does not alter the active registry, runtime manifest, container image,
service revision, or worker cache. Operation providers require a reproducible
runtime rebuild and validation before activation. Services and resources
require their own review and registry republication or restart gate.

## Consequences

- Upstream changes are discoverable and easy to prepare without weakening
  immutable runtime identity.
- Private repositories use the Git credential helper available to the API or
  CLI process; credentials are never accepted in browser payloads or persisted
  in update state.
- A prepared candidate is not an active ecosystem release.
- Candidate build and smoke evidence are local review inputs, not publication
  or promotion. Digest publication, supply-chain evidence, registry repinning,
  and atomic promotion remain subsequent release-pipeline milestones.
- Old candidate directories may be retained as caches until a future explicit
  pruning policy is implemented.
