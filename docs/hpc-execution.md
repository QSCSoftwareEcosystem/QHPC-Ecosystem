# HPC Execution Operations

- Status: implementation complete for local simulation; site activation pending
- Last updated: 2026-07-27

This document describes the boundary between QHPC's durable control plane and a
site-owned Slurm/Apptainer execution target.

## Implemented Lifecycle

The API persists a run and append-only task attempt. A target worker:

1. registers a stable worker identity and heartbeats its admitted target and
   execution classes;
2. leases one ready attempt transactionally;
3. validates the deployment registry, target, storage profile, project,
   operation, immutable runtime, parameters, ports, and resources;
4. verifies and stages the SIF and checksum-verified inputs through controlled
   paths;
5. writes the submission intent before calling Slurm and persists the returned
   job ID;
6. reconciles queued, running, succeeded, failed, canceled, and unknown states;
7. propagates cancellation through `scancel`;
8. collects only declared output files and verifies their boundaries; and
9. records correlated dispatch, staging, scheduler, execution, collection, and
   finalization events.

A worker restart adopts an existing scheduler handle. A crash between `sbatch`
and database persistence recovers through the atomic submission receipt or the
deterministic Slurm job name, preventing duplicate submission.

The generated Apptainer command uses `--containall`, `--cleanenv`, `--no-home`,
`--net --network none`, a fixed entrypoint, controlled binds, and no
caller-provided shell. Site acceptance must verify that the target's Apptainer
configuration permits the required unprivileged `none` network namespace.

## Planned Manifests

The repository includes non-deployable placeholders:

- `infrastructure/execution-targets/doe-slurm-apptainer.yaml`
- `infrastructure/storage-profiles/doe-slurm-project.yaml`
- `infrastructure/pilot-profiles/doe-short-interactive.yaml`

Their `planned` status is intentional. The contract validator rejects
activation until required scheduler account, partition, resource limits,
storage roots, immutable runtime digests, and evidence are supplied. Placeholder
paths and all-zero digests must never be activated.

## Site Activation

A site owner must:

1. choose the cluster, partition, account, QoS, Apptainer executable, worker
   placement, and resource ceilings;
2. assign the image cache and task-staging roots and approve node-local image
   and input staging;
3. publish and sign operation images, build SIF files, and record their exact
   digests and acceptance evidence in each runtime manifest;
4. replace placeholder pilot values with an approved allocation envelope,
   operation allowlist, runtime digests, lifetime, idle timeout, and fallback;
5. validate native and container correctness and representative storage,
   startup, queue, and application performance; and
6. change profiles to `active` only after security and operations approval.

The active cold-batch worker is then started with explicit inputs:

```bash
qhpc-ecosystem target-worker \
  --registry /approved/qhpc/registry.yaml \
  --deployment-profile deployments/initial.yaml \
  --execution-target /approved/qhpc/execution-target.yaml \
  --storage-profile /approved/qhpc/storage-profile.yaml \
  --runtime-manifest /approved/qhpc/qasmtrans-runtime.yaml \
  --database /approved/qhpc/control.sqlite \
  --artifact-root /approved/qhpc/artifacts
```

SQLite is suitable only for the single-host acceptance slice. The shared
service still requires PostgreSQL and an approved artifact store.

## Warm Pilots

The durable pilot controller implements requested, submitted, ready, draining,
termination-requested, and terminated states; heartbeats; capacity
reservations; operation, runtime, and resource eligibility; idle, lifetime, and
health draining; and policy-selected batch fallback.

It does not submit the site allocation or launch worker job steps by itself.
Those two adapters depend on the approved account, partition, reservation,
launcher, and in-allocation worker command. Until they are implemented and
accepted on the target, warm pilots remain a control model and short operations
use ordinary batch execution.

Pilot state can be inspected without activating a target:

```bash
qhpc-ecosystem pilot list --database .qhpc/workbench.sqlite
qhpc-ecosystem pilot reconcile \
  infrastructure/pilot-profiles/doe-short-interactive.yaml \
  --database .qhpc/workbench.sqlite
```

## Acceptance Evidence

The simulated tests cover successful execution, staging, collection, restart
adoption, cancellation, and the crash window after scheduler submission. They
do not claim access to a DOE scheduler or validate real storage and RDMA
behavior. Target evidence must include cold and warm dispatch, cached and
uncached SIF staging, native comparison, complete stage telemetry, cleanup,
failure recovery, and the required parallel-filesystem, MPI, RDMA, GPU, or
GPUDirect paths.
