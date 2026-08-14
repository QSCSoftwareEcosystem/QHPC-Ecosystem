# ADR 0010: Django Workbench With A Typed Browser Composer

- Status: Accepted
- Date: 2026-07-28

## Context

The local Workbench can discover operations, run published templates, and
publish a one-operation workflow. It cannot persist an incomplete draft or let
a user place and connect arbitrary registered operations.

The ecosystem already has an authoritative workflow contract, registry-aware
validation, immutable workflow publication, asynchronous execution, and
artifact provenance. Reimplementing those rules in a web framework would create
two workflow engines and weaken the control-plane boundary.

OpenStack Horizon demonstrates a useful dashboard pattern: a server-side web
application manages identity, forms, navigation, and service API calls while
independent services remain authoritative. Horizon itself is coupled to
OpenStack and is not a QHPC dependency.

## Decision

QHPC will implement a separately deployable Django 5.2 LTS Workbench. Django
owns browser sessions, CSRF protection, page routing, server-rendered dashboard
structure, and a narrow client for the versioned QHPC API. It does not import
the workflow engine, access orchestration tables, or execute scientific work.

The Compose view will embed a TypeScript and React graph editor using React
Flow. Browser nodes are projections of deployment-admitted registry operations.
Named handles represent declared artifact ports, and browser connections
compile to the existing `qhpc/v1` workflow contract.

Draft workflow content and layout are persisted through QHPC control-plane
APIs. The canonical workflow and the canvas layout are stored separately.
Position, zoom, selection, and other presentation state do not participate in
the published workflow digest.

The first composer supports acyclic graphs, registered operation nodes,
workflow input and output boundary nodes, typed edges, declared parameters,
template forking, validation, immutable publication, and run submission. It
does not support arbitrary scripts, loops, conditional branches, parameter
sweeps, or collaborative editing.

Client validation exists for immediate feedback only. The API revalidates the
workflow schema, graph, operation versions, parameters, ports, deployment
admission, runtime identity, and worker readiness before publication or
execution.

## Consequences

- Existing CLI, automation, and worker behavior remains unchanged.
- The Workbench can evolve without becoming a second source of scientific
  truth.
- A Node-based frontend build and a Django application become reviewed
  dependencies of the monorepo.
- Draft persistence requires revision checks and a schema-managed database
  migration.
- The existing static Workbench remains an explicit local fallback until a
  separate retirement decision.
- Production identity and authorization must be enforced again at the QHPC API;
  hiding an action in Django is not authorization.

## Implementation Status

The local implementation is complete for this decision: Django is the default
supervised browser service, React Flow owns the Compose canvas, drafts use
optimistic revisions, canonical workflow round trips are covered by tests, and
artifact content is path-contained and checksum-verified. The static browser
remains available through the explicit development fallback.

Verification is recorded in
`docs/evidence/workbench-composer-smoke-2026-07-28.md`. Shared identity,
workspace authorization, production persistence, approved artifact storage,
and collaborative editing remain outside this decision's local acceptance.
