# ADR 0004: Modular Monolith With Separate API And Worker

- Status: Accepted
- Date: 2026-07-14

## Context

The local vertical slice combines HTTP handling, orchestration, persistence,
and controlled execution in one Python package. The API currently starts local
execution synchronously. That is useful for an MVP but cannot represent
long-running Slurm jobs, independent worker recovery, or multiple users safely.

The ecosystem has one primary maintainer. Splitting every boundary into a
separate repository or network service would add release and operational cost
without improving scientific isolation.

## Decision

QHPC will remain a modular monorepo with one domain model and separately
deployable API, worker, and workbench applications.

The API is a control-plane process. It authenticates, authorizes, validates,
persists workflow and run requests, and returns without executing scientific
tasks. Workers claim persistent task leases and manage target execution.

Local development may run the applications together and use SQLite. Production
deployment uses persistence and artifact-store adapters suitable for multiple
processes, transactional task claims, migrations, and recovery.

## Consequences

- HTTP request lifetime is independent of workflow execution time.
- Local, Slurm, and quantum targets can use asynchronous execution handles.
- A worker failure does not require the API to restart, and leases permit task
  recovery.
- Workbench, CLI, automation, and agents use the same application services.
- Module boundaries must be enforced by tests even while packages share a
  repository.
- A future repository or service split remains possible when ownership,
  deployment cadence, or security boundaries justify it.
