# QHPC Target Architecture

- Status: Target design with local execution-plane implementation
- Last updated: 2026-07-27
- Scope: QHPC ecosystem integration, orchestration, execution, and data paths

## Architectural Position

QHPC is a contract-first scientific workflow platform. Software Thrust
repositories remain authoritative for scientific behavior. QHPC publishes
attributed capability releases, resolves typed workflows, coordinates approved
execution targets, and records artifacts and provenance.

The local implementation includes a verified vertical slice and a simulated
production-shaped Slurm/Apptainer execution path. The target deployment is a
modular monolith with separately deployable API, worker, and workbench
applications. This keeps one repository and one domain model while preventing
scientific execution from occurring in an HTTP request process.

## System Planes

```text
Project repositories and ecosystem overlays
                    |
                    v
       Integration and publication plane
  validate -> build -> attest -> registry snapshot
                    |
                    v
          deployment profile allowlist
                    |
                    v
Workbench | CLI | automation | approved agents
                    |
                    v
                  API
 identity -> authorization -> application services -> audit
                    |
          +---------+----------+
          |                    |
          v                    v
  Registry and workflow    Orchestration state
       resolution          runs, tasks, attempts
                               |
                               v
                         Worker leases task
                               |
                    operation adapter
                               |
                    execution-target runner
                 /        /       \          \
              local   warm pilot  batch    quantum
                               |
                               v
                        Target data plane
        image cache | parallel FS | node scratch | artifact store
```

### Integration And Publication Plane

This plane discovers descriptors from pinned project releases or
ecosystem-owned overlays, validates attribution and contracts, builds immutable
runtimes, records evidence, and produces a deterministic registry snapshot.
Scientific source is not copied into QHPC.

The repository catalog is an inventory, not an admission policy. Each deployed
service validates a versioned component allowlist and derives a filtered
registry snapshot before serving discovery or resolving workflows. Components
without a published registry record remain visible in deployment planning but
cannot be executed. Run submission re-resolves stored workflow definitions
against the active filtered registry so earlier workflow records do not bypass
a profile change.

### Control Plane

The API authenticates users, authorizes actions, validates requests, publishes
workflow versions, creates runs, and exposes state. It does not execute tasks or
import project libraries. CLI, Workbench, automation, and approved agents use
the same application services and versioned contracts.

### Execution Plane

Workers claim persistent task leases and invoke a target runner. A runner owns
transport and lifecycle operations such as submit, poll, cancel, and collect.
Local, Slurm, and quantum runners implement the same lifecycle without changing
the scientific operation definition.

The development database may use SQLite. Production persistence must support
multiple API and worker processes, transactional task claims, schema migrations,
and recovery after process or target failure.

### Execution Classes

An execution target advertises policy-controlled classes rather than exposing
raw scheduler choices:

| Class | Intended use | Dispatch behavior |
| --- | --- | --- |
| `interactive-local` | Approved low-resource development or service operation | Already-running controlled worker |
| `interactive-hpc-pilot` | Short, approved HPC operation needing responsive feedback | Worker inside a warm, site-approved Slurm allocation |
| `batch-hpc` | Ordinary, long, large, or tightly scheduled HPC operation | Independent scheduler submission |

Quantum backends retain their own asynchronous target class and queue model.
Operation resource limits, runtime digest, target policy, data locality, and
current capacity determine eligible classes. User intent may narrow eligible
classes but cannot bypass policy.

A warm pilot is not an unscheduled execution path. QHPC acquires it through
Slurm under an approved account, partition, QoS, node ceiling, lifetime, and
idle timeout. Worker agents inside the allocation execute only allowlisted
operations, maintain safe caches of verified immutable images, and isolate each
task workspace. Only the allocation, worker, and verified immutable cache are
reused: each operation starts in a fresh resource-isolated job step and clean
container process. Pilots are health-checked, capacity-limited, drain before
expiry or maintenance, and release idle resources. An eligible task falls back
to `batch-hpc` when warm capacity is unavailable unless an approved request
explicitly requires interactive service.

### Latency Telemetry

QHPC records an append-only execution event stream rather than only a total
duration. Events are scoped to a run, task attempt, or pilot allocation and
include the run ID, optional attempt or pilot ID, correlation ID, sequence,
source component, execution class, target handle when present, stage name,
`occurred_at`, and `recorded_at`. A completed stage also retains its duration
measured with a monotonic clock. Canonical run and task events are:

```text
request_received             authorized                 run_accepted
task_queued                  task_leased
image_stage_started          image_ready
input_stage_started          inputs_ready
target_submitted             target_started
operation_started            operation_finished
output_collection_started    outputs_ready
attempt_finished | attempt_failed | attempt_canceled | attempt_timed_out
```

Terminal events identify the active stage at failure, timeout, or cancellation.
Runners may order staging around target acquisition differently; the event
pairs remain stable. The read model derives API, dispatch, scheduler,
image-staging, input-staging, operation, output-collection, finalization, and
end-to-end latency. `pilot_requested`, `pilot_ready`, `pilot_draining`, and
`pilot_terminated` form a separate capacity lifecycle.

Cross-component timelines retain both occurrence and receipt time and require
target-approved clock synchronization. Metrics and traces must not expose
secrets, controlled paths, or uncontrolled high-cardinality values. The API and
Workbench expose the stages separately and never describe warm capacity as
queue-free execution.

### Data Plane

Artifact metadata and payload storage are separate. The metadata store records
identity, type, checksum, size, lineage, access scope, and producing attempt.
The payload store may be local files during development and an approved POSIX,
object, or parallel filesystem service in deployment.

Workers materialize inputs into a controlled task workspace, verify them before
execution, ingest outputs from declared relative paths, compute checksums, and
publish immutable artifact records. An adapter cannot publish an arbitrary host
URI as a trusted output.

The implemented worker lifecycle, planned execution-target, storage, and pilot
profiles, and site activation procedure are documented in
[hpc-execution.md](hpc-execution.md).

## Deployment Units

The project remains one monorepo while it has one primary maintainer. Logical
boundaries are independently testable and the following applications are
separately deployable:

| Unit | Responsibility |
| --- | --- |
| `api` | Identity boundary, policy, registry and workflow APIs, run submission, read models |
| `worker` | Task leases, staging, adapter invocation, runner lifecycle, output collection |
| `workbench` | Browser client that consumes only versioned APIs |
| `cli` | Local administration and automation client using the same application services |

A repository split is justified only when release cadence, deployment
ownership, or access controls require it.

## Resource Model

The target domain adds explicit resources around the existing contracts:

| Resource | Purpose |
| --- | --- |
| Registry snapshot | Immutable set of capability and runtime releases used for resolution |
| Deployment profile | Versioned allowlist that selects registry repositories and non-executable ecosystem resources for one deployment |
| Runtime release | Digest-pinned executable environment plus build and attestation evidence |
| Workspace | User or team scope for workflows, runs, artifacts, and access policy |
| Task attempt | Append-only record of one execution attempt for a workflow node |
| Execution handle | Target-owned identifier for a local process, Slurm job, or backend request |
| Execution class | Policy-controlled dispatch mode such as local interactive, warm pilot, or batch |
| Pilot allocation | Site-approved warm scheduler allocation with capacity, lifetime, and drain state |
| Execution event | Append-only run, attempt, or pilot event used for state, audit correlation, and latency |
| Storage profile | Approved image, input, scratch, output, and host-library mappings for a target |

`Task` represents the workflow node's current projection. Retries create new
`TaskAttempt` records and never erase prior errors, logs, outputs, or target
handles.

## Adapter And Runner Boundary

An operation adapter owns the mapping from a capability contract to a fixed
invocation and output manifest. It may render validated arguments, prepare
operation-specific files, and parse a declared result format. It does not
submit Slurm jobs, select host paths, implement identity policy, or control
artifact retention.

A runner owns execution transport. Its lifecycle is conceptually:

```text
prepare -> submit -> poll or heartbeat -> cancel -> collect
```

The default integration is a declarative command adapter using an argument
vector and declared relative inputs and outputs. A custom adapter is permitted
only when a project API or result format cannot use that contract. Custom
adapters are versioned, allowlisted, tested, and tied to a runtime digest.

## Container Models

QHPC has two intentionally different container uses:

| Model | Purpose | Properties |
| --- | --- | --- |
| Developer environment | Distrobox-like shell and command access for repository development | Shared by environment class, source bind at `/workspace`, not a production runtime |
| Operation runtime | Reproducible workflow and HPC execution | Tool-specific Linux image, immutable digest, approved entrypoint, SBOM and attestation as required |

Developer environments may later export convenience launchers to the host.
They are never substituted for an approved operation runtime. Production jobs
do not pull or build an image during execution.

The versioned `OperationRuntime` contract records build-ready, local OCI smoke,
and target-accepted states without treating them as equivalent. Its reference
implementation and OCI-to-Apptainer flow are documented in
[operation-runtimes.md](operation-runtimes.md).

The image contains application user-space dependencies. Kernel drivers,
parallel-filesystem clients, RDMA devices, site MPI, UCX, libfabric, GPU
libraries, and storage policy remain controlled by the execution target.

## Storage-Aware HPC Execution

Storage topology is part of an execution target contract. A target profile
must define logical mappings rather than accepting user-supplied host paths:

```text
image source and node-local cache policy
read-only input staging or bind
node-local task workspace and temporary/cache paths
result collection destination
parallel-filesystem and object-store access
RDMA, MPI, UCX, libfabric, and GPU library policy
GPUDirect Storage support when required
capacity, quota, retention, and purge behavior
```

The preferred Slurm sequence is:

1. Resolve and authorize the operation, target, image digest, and resources.
2. Stage or verify the immutable SIF in a target-approved cache, using
   node-local storage when startup measurements justify it.
3. Stage or bind inputs from approved storage as read-only.
4. Run in node-local scratch when the workload permits, with only controlled
   host libraries, devices, and paths exposed.
5. Collect declared outputs, compute checksums, and commit artifact metadata.
6. Remove temporary data according to target policy.

A host-mounted Lustre or GPFS path should normally be bind-mounted directly so
the host kernel storage client retains its native data path. User-space RDMA or
GPUDirect workloads additionally require target-approved devices and compatible
host libraries. Writable overlays and dependency trees containing many small
files must not be placed on shared performance filesystems without measured
acceptance.

## Security Boundary

Identity is established at the API boundary and propagated as signed or
deployment-trusted workload identity. `created_by` is not accepted as an
authoritative client field in production. Policy is evaluated when publishing,
submitting, leasing, canceling, collecting outputs, and reading controlled
artifacts.

Only target administrators define host binds, partitions, accounts, image
sources, network access, and secret providers. Workflows reference logical
target and secret identifiers, never credentials or unrestricted host paths.

## Acceptance Strategy

Each production target requires an evidence bundle containing:

- native and container baselines for startup, metadata, throughput, and
  application wall time;
- cold batch, warm pilot, and unavailable-pilot fallback measurements for
  eligible short operations;
- cached and uncached runtime staging measurements plus complete stage-event
  correlation;
- shared-image versus node-local-image measurements;
- shared-workspace versus node-local-workspace measurements;
- multi-node scaling and representative small-file or file-per-rank behavior;
- verification of parallel-filesystem, RDMA, MPI, GPU, and GPUDirect paths that
  the operation requires;
- restart, cancellation, timeout, output collection, and provenance tests; and
- image digest, signature, SBOM, vulnerability, and policy results required by
  the deployment.

Performance thresholds are selected with the target facility. QHPC does not
claim native-equivalent performance until the measured target acceptance is
approved.

## Current Implementation Boundary

The current local API and worker are separate processes connected through
transactional SQLite task leases. The API queues work and never invokes an
operation adapter; the worker applies deployment-registry and local-adapter
allowlists before using the synchronous runner protocol. This verifies the
process boundary but is not production PostgreSQL persistence, durable worker
heartbeats, Linux operation containers, asynchronous Slurm handles and
reconciliation, a warm pilot service, stage latency telemetry, approved
artifact storage, or storage-aware target integration.
