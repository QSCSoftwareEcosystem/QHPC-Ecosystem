# QHPC Worker Processes

- Status: Durable local and asynchronous target workers implemented
- Last updated: 2026-07-27

The API is a control-plane process. It validates and stores workflows, queues
runs, exposes state, and never calls a scientific operation adapter. A separate
worker leases ready tasks from persistent orchestration state and invokes a
controlled runner. Workers register an identity, heartbeat their admitted
targets and execution classes, and write append-only attempt and execution
event records.

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

Use an explicit `--worker-id` when the process identity must remain stable
across restarts. `--execution-target` and `--execution-class` are repeatable
allowlists; a worker cannot lease a task outside those values. Expired leases
are recovered without rewriting prior attempt history.

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

## Asynchronous Target Worker

`target-worker` binds the same durable lifecycle to a versioned execution
target, storage profile, and one or more accepted runtime manifests:

```bash
qhpc-ecosystem target-worker \
  --registry /approved/qhpc/registry.yaml \
  --deployment-profile deployments/initial.yaml \
  --execution-target /approved/qhpc/execution-target.yaml \
  --storage-profile /approved/qhpc/storage-profile.yaml \
  --runtime-manifest /approved/qhpc/qasmtrans-runtime.yaml \
  --worker-id qhpc-target-worker-01
```

The asynchronous worker persists submission intent and scheduler handles,
polls target state, propagates cancellation, reconciles after restart, and
collects only declared outputs. A crash after `sbatch` but before handle
persistence is recovered from the submission receipt or deterministic job
name. The Slurm/Apptainer implementation additionally validates runtime,
parameter, port, resource, checksum, quota, staging, bind, and network policy.
See [hpc-execution.md](hpc-execution.md).

## Current Limits

SQLite WAL mode and filesystem artifacts support this local two-process slice.
They are not a multi-host production backend. The asynchronous target path is
covered by fake scheduler and Apptainer transports; it has not executed on a
DOE target. Production still requires PostgreSQL-backed transactional leases,
an approved shared artifact service, institutional identity and workspace
policy, active site-owned target and storage profiles, target-accepted SIFs,
and operational monitoring and recovery evidence.
