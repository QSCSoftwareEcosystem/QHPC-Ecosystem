# QHPC Worker Process

- Status: Local process boundary implemented
- Last updated: 2026-07-22

The API is a control-plane process. It validates and stores workflows, queues
runs, exposes state, and never calls a scientific operation adapter. A separate
worker leases ready tasks from persistent orchestration state and invokes a
controlled runner.

## Local Topology

Run the API and worker from the same checkout with the same registry,
deployment profile, database, and artifact root:

```bash
# Terminal 1: control plane and Workbench
qhpc-ecosystem serve \
  --registry examples/registry.yaml \
  --deployment-profile deployments/initial.yaml

# Terminal 2: local development worker
qhpc-ecosystem worker \
  --registry examples/registry.yaml \
  --deployment-profile deployments/initial.yaml \
  --runtime-root .qhpc/runtimes
```

The long-running worker polls for transactional SQLite task leases. `--once`
processes at most one ready task and exits; `--drain` processes ready tasks
until the queue is idle. These modes support testing and controlled local
administration, not production autoscaling.

The Workbench queues runs and polls their persistent state. The retired
`POST /api/v1/runs/{id}/execute` path returns `410 Gone`; execution cannot be
reintroduced into the HTTP request process through API configuration.

## Admission Boundary

Both processes validate the same deployment profile and derive the same
filtered registry. Before invoking an adapter, the worker verifies the exact
capability ID, capability version, operation ID, runtime reference, and runtime
digest against that registry snapshot. A missing operation or mismatched
runtime is recorded as a non-retryable `TaskRejectedError` without scientific
execution.

The local adapter remains a second allowlist. Registry admission therefore
cannot cause an arbitrary command to run when no corresponding controlled
adapter is installed.

## Current Limits

SQLite WAL mode and filesystem artifacts support this local two-process slice.
They are not a multi-host production backend. The production worker still
requires PostgreSQL-backed leases and migrations, durable worker identity and
heartbeats, asynchronous target handles and reconciliation, approved shared
artifact storage, institutional identity and policy, and Slurm integration.
