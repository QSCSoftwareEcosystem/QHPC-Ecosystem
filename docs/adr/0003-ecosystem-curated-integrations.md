# ADR 0003: Ecosystem-Curated Integrations

- Status: Accepted
- Date: 2026-07-11

## Context

The ecosystem maintainer has legitimate access to Software Thrust repositories,
but project leaders cannot be assumed to author descriptors or perform reviews.
Making their participation a publication prerequisite prevents integration work
without improving the technical evidence behind an integration.

## Decision

QHPC supports both project-authored and ecosystem-curated capability
descriptors. Scientific attribution remains attached to the originating project,
repository, and immutable revision. Integration authority and maintenance are
recorded separately.

An ecosystem-curated descriptor may be stored under `capabilities/` in this
repository. It must identify its curators, declare whether project review has
occurred, link validation evidence, and use the validation ladder:

1. `discovered`
2. `contract-valid`
3. `smoke-tested`
4. `integration-tested`
5. `production-approved`

Project review can increase confidence but is not required for the first four
states. `production-approved` additionally depends on the applicable DOE
release, security, and deployment controls.

## Consequences

- Repository access is sufficient to audit and integrate supported behavior.
- QHPC never implies project endorsement when `project_reviewed` is false.
- Upstream source and scientific behavior are not copied into QHPC.
- Curators are responsible for keeping descriptors and evidence aligned with
  pinned upstream revisions.
- Missing project participation no longer blocks the local MVP.
