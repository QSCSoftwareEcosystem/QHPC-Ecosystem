# HPC and DOE Deployment Readiness

- Last updated: 2026-07-20
- Local MVP status: implemented and verified as a vertical-slice prototype
- Production deployment status: blocked on architecture integration,
  institutional services, target evidence, and review

The target system design is defined in [architecture.md](architecture.md).
[ADR 0006](adr/0006-dual-container-storage-aware-execution.md) records the
dual-container and storage-aware execution decision, and
[ADR 0007](adr/0007-warm-pilot-and-latency-telemetry.md) records warm-pilot
execution and latency telemetry.

## Implemented Local Primitives

- Immutable OCI, Apptainer, reproducible Python-wheel, and native-bundle
  reference contracts.
- Controlled local runner with an explicit operation allowlist.
- Slurm submission, state classification, accounting fallback, cancellation,
  and controlled Apptainer script-rendering primitives.
- Default-deny role/action definitions and secret-reference validation.
- Append-only SHA-256 chained audit records for future deployment integration.
- Persistent local workflow, run, task, artifact, checksum, log, retry,
  cancellation, lease, and export behavior.
- Verified local OpenQEvo and QASMTrans-to-STABSim vertical slices.

These are development foundations. The API does not yet enforce identity or
authorization, the engine does not use a separate worker, Slurm is not connected
to task leases, retries are not append-only attempts, and the local artifact
store is not an approved production storage service.

## Required Production Boundaries

### Control And Execution

- Separately deployable API and worker processes.
- Authoritative identity at the API boundary and policy enforcement in API and
  worker use cases.
- Persistent asynchronous target handles, heartbeats, reconciliation,
  cancellation, timeout, and recovery.
- Policy-controlled dispatch among local interactive, warm HPC pilot, ordinary
  HPC batch, and target-specific asynchronous execution classes.
- Append-only task-stage events and derived latency metrics spanning the API,
  worker, runner, scheduler, storage, operation, and artifact collector.
- Append-only task attempts and schema-managed production persistence.
- Central audit forwarding with independently protected retention or anchoring.

### Runtime Supply Chain

- Tool-specific immutable Linux operation images rather than shared developer
  environments, Python wheels, or Darwin native bundles.
- Approved internal OCI registry or Apptainer image cache.
- Digest and signature verification before execution.
- Source revision, build recipe, dependency inventory, SBOM, vulnerability
  result, attestation, retention, and revocation policy as required.
- Images built or pulled before job execution; target jobs do not build or pull
  mutable images.

### Storage And RDMA

Each execution target requires an administrator-owned storage profile defining:

- image source, shared cache, and optional node-local staging;
- read-only input binds or staging;
- node-local working, temporary, and cache directories;
- result collection and immutable artifact publication;
- parallel-filesystem and object-store locations;
- capacity, quota, retention, purge, backup, and recovery behavior;
- host MPI, UCX, libfabric, RDMA, GPU, and GPUDirect libraries and devices; and
- allowed logical binds, with no user-supplied arbitrary host paths.

A host-mounted Lustre or GPFS path should normally be exposed through a direct
bind so the host kernel storage client retains its native path. User-space RDMA
or GPUDirect workloads require additional site-approved devices, libraries, and
ABI validation.

### Interactive Capacity And Latency

A warm HPC service is a site-approved Slurm pilot allocation, not a scheduler
bypass. Its target profile must define account, partition, QoS, maximum nodes,
resource envelope, lifetime, idle timeout, cache policy, capacity ownership,
drain behavior, maintenance behavior, and ordinary-batch fallback. Pilot
workers accept only authorized operations and immutable runtime digests, use an
isolated workspace for every task, and apply the same storage, artifact, secret,
and audit controls as batch jobs. Only the allocation, worker, and verified
immutable cache are reused; every operation runs in a fresh resource-isolated
job step and clean container process.

The append-only execution event stream must correlate run-level request receipt,
authorization, and acceptance with each attempt's queueing, worker lease, image
staging, input staging, target submission and start, operation execution,
output collection, and finalization. Events retain monotonic stage durations,
occurrence and receipt timestamps, and correlation and target identifiers.
Cross-system analysis requires the facility's approved clock-synchronization
and monitoring services.

## External Decisions Required

The following cannot be selected or certified from this development workspace:

1. Approved institutional identity provider and trusted authentication token or
   header validation boundary.
2. Group-to-role mappings, workspace ownership, and controlled-resource policy.
3. Internal OCI registry or Apptainer cache, signing, retention, and revocation.
4. Artifact metadata and payload stores, encryption, quotas, retention, purge,
   backup, and recovery.
5. Target Slurm clusters, partitions, accounts, QoS, modules, launch policy,
   and worker placement.
6. Warm-pilot accounts, partitions or reservations, resource ceilings, idle
   timeout, maximum lifetime, operating cost, capacity owner, and service SLOs.
7. Parallel-filesystem topology, node-local storage, image-staging mechanism,
   and approved logical bind mappings.
8. Required RDMA, MPI, UCX, libfabric, GPU, and GPUDirect data paths and ABI
   compatibility policy.
9. Native-versus-container performance thresholds and representative workload
   profiles.
10. Allowed egress, proxy, repository, package-index, and quantum-backend routes.
11. Secrets provider and workload identity mechanism.
12. Central audit sink, retention period, access controls, and incident process.
13. SBOM, vulnerability, attestation, export-control, and release gates.
14. Availability, restore, clock synchronization, monitoring, maintenance, and
    operations ownership.

These decisions block `production-approved` status. They do not block local
contract, workflow, API, workbench, or controlled-runner development.

## Target Acceptance Matrix

Every production target must retain an evidence bundle for the following
comparisons using representative operation workloads:

| Test | Required comparison |
| --- | --- |
| Startup | Native, shared SIF, and node-local SIF |
| Interactive dispatch | Cold batch, warm pilot, saturated pilot, and batch fallback |
| Runtime cache | Cached and uncached immutable image preparation |
| Metadata | Dependency loading and representative small-file behavior |
| Data throughput | Native and container reads and writes on approved storage |
| Workspace | Shared workspace and node-local scratch |
| Scaling | Single node and representative multi-node task counts |
| Communication | Required MPI, UCX, libfabric, and RDMA paths |
| GPU storage | Required GPU and GPUDirect Storage path, or explicit not-applicable evidence |
| Application | Native and container wall time and result equivalence |
| Telemetry | Complete correlated stage events, component durations, and clock-offset handling |

The facility selects acceptable regression thresholds. QHPC does not claim
native-equivalent performance until those measurements are approved.

## Functional And Security Acceptance

- Submit, poll, reconcile, cancel, timeout, and classify a controlled Slurm job
  through a worker.
- Acquire, health-check, constrain, drain, expire, and release a pilot allocation
  through approved Slurm policy.
- Verify pilot saturation, loss, or unavailability causes authorized fallback
  to ordinary batch without duplicate execution.
- Verify every successful, failed, canceled, retried, and timed-out attempt has
  correlated stage telemetry and identifies the stage where it terminated.
- Verify pilot tasks remain isolated and cannot reuse another task's workspace,
  credentials, artifacts, or mutable process state.
- Run the same pinned operation locally and through Slurm without changing its
  scientific operation contract.
- Verify image digest and signature before staging and execution.
- Demonstrate denied publication and execution for unauthorized identities.
- Verify workflows cannot request arbitrary host binds, partitions, accounts,
  devices, images, networks, or secret values.
- Verify secret values never appear in workflows, logs, exports, or images.
- Verify only declared outputs are collected and their checksums are computed
  after execution.
- Recover API, worker, registry, workflow, attempt, and artifact state after
  process and target failures.
- Forward and verify audit events in the approved central sink.
- Restore registry, orchestration state, and artifact metadata from backup.
