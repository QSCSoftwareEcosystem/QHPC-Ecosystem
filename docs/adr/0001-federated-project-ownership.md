# ADR 0001: Federated Project Ownership

- Status: Superseded by ADR 0003
- Date: 2026-07-10

## Context

The Software Thrust contains independently developed SE, DS, AS, CT, and HW
projects plus the cross-project OpenQEvo prototype. The ecosystem must make
their developments usable together without copying scientific implementations
or transferring ownership into a central application repository.

## Decision

Project repositories remain authoritative for source, scientific behavior,
tests, documentation, releases, and capability descriptors. The QHPC Ecosystem
defines shared contracts, validates project releases, and builds a generated
registry from accepted immutable versions.

The workbench and workflow engine reference project operations through the
registry. They do not embed project implementations. A repository may publish
multiple operations or only non-executable resources.

## Consequences

- Project teams can release on their own cadence while preserving ownership.
- Cross-project workflows depend on explicit versioned interfaces instead of
  source-tree assumptions.
- Registry aggregation must handle compatibility, deprecation, provenance, and
  unavailable internal sources.
- Integration cannot be claimed until a project-owned release passes the
  contracts and participates in a verified workflow.
- Coordination with project owners was originally treated as a required
  delivery dependency. ADR 0003 replaces that gate with evidence-backed
  ecosystem curation when project participation is unavailable.
