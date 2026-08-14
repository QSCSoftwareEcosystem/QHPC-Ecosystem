# HPC Execution Operations

- Status: implementation complete for local simulation; site activation pending
- Last updated: 2026-07-29

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

## Initial-Package Acceptance

`infrastructure/hpc-acceptance/initial.yaml` is the machine-readable HPC
acceptance inventory for the fourteen initial components. Inspect it with:

```bash
eqo hpc-acceptance status \
  infrastructure/hpc-acceptance/initial.yaml
```

The profile currently identifies seven intended batch operations. STABSim,
NWQEC, FTPrimitiveBench, LightStim, and QASMTrans have OCI-verified runtime
contracts; TN-Sim and FTQC still need reproducible runtimes. OpenQEvo is
currently a library resource, OpenQSE an integration standard, QAppsWiki a
knowledge resource, and ChatQEC a separately deployed service, so they do not
enter the Slurm batch gate.

The gate command returns nonzero until every required runtime is
`target-accepted` and the execution target, storage profile, and acceptance
profile are active:

```bash
eqo hpc-acceptance gate \
  infrastructure/hpc-acceptance/initial.yaml
```

All five current runtime contracts traverse simulated Slurm/Apptainer
admission, input staging, job rendering, polling, output collection, telemetry,
and cleanup tests. Scheduler-visible image, bind, log, and telemetry paths are
translated through an injected mapper, allowing the same runner contract to
use host-local or Compose-backed Slurm command transports. This remains
contract evidence, not scientific execution evidence.

## Development Slurm Fixture

The development fixture is layered test infrastructure. It is not an execution
target, operation runtime, or deployment-registry entry, and it cannot produce
DOE acceptance evidence.

Thomas Naughton's
[`slurm-docker-cluster`](https://github.com/naughtont3/slurm-docker-cluster)
fork is integrated as an optional local scheduler test provider. QHPC pins the
fork's `tjn-main` branch at revision
`8c8065cbebb475a512a66cabff9aceda5f2c57b0` in:

```text
infrastructure/test-clusters/slurm-docker-cluster/cluster.yaml
```

The source is cloned on demand under ignored `.qhpc/` state. It is not vendored
into this repository:

```bash
eqo slurm-test-cluster prepare \
  infrastructure/test-clusters/slurm-docker-cluster/cluster.yaml \
  --build-ca /approved/path/development-build-ca.pem
eqo slurm-test-cluster start \
  infrastructure/test-clusters/slurm-docker-cluster/cluster.yaml
eqo slurm-test-cluster smoke \
  infrastructure/test-clusters/slurm-docker-cluster/cluster.yaml
eqo slurm-test-cluster status \
  infrastructure/test-clusters/slurm-docker-cluster/cluster.yaml
eqo slurm-test-cluster stop \
  infrastructure/test-clusters/slurm-docker-cluster/cluster.yaml
```

The harness starts MariaDB, `slurmdbd`, `slurmctld`, and workers `c1` and `c2`.
It deliberately does not start `slurmrestd` or expose its host port. The smoke
test submits through the shared `/mnt` path, waits through `squeue` and `sacct`,
checks worker output, then submits and cancels a second job through `scancel`.
The QHPC override also persists `/var/lib/slurmd`; `stop` preserves that named
volume, and the recorded restart test confirms scheduler job IDs continue
across full Compose replacement. It replaces the source's global container
names and image tag with QHPC-scoped identities, allowing the fixture to run
without taking ownership of an unrelated Slurm Compose stack.

The public build CA is optional on networks that do not intercept TLS. QHPC
rejects CA inputs containing a private key, never commits the local CA, and
uses a tracked compatibility Dockerfile instead of the source's insecure,
obsolete build steps.

This is scheduler-contract evidence only. The cluster uses development
credentials and requires an isolated development host and non-sensitive test
data. It does not provide Apptainer, SIF
distribution, facility identity, parallel filesystems, MPI, RDMA, GPU,
GPUDirect, representative queue behavior, or representative performance. See
[ADR 0009](adr/0009-development-slurm-test-cluster.md).

The first live verification passed on 2026-07-27; the exact source, build,
image, node, completion, accounting, and cancellation record is in
[the scheduler smoke evidence](evidence/slurm-docker-cluster-smoke-2026-07-27.md).

The external OpenQSE QFw Slurm stack is reference material only. QHPC may use
its design ideas when defining future multi-node or synthetic-resource tests,
but it is not a provider, dependency, runtime, or deployment component.

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
eqo target-worker \
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
eqo pilot list --database .qhpc/workbench.sqlite
eqo pilot reconcile \
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
