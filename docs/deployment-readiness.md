# HPC and DOE Deployment Readiness

- Last updated: 2026-07-29
- Local MVP status: implemented and verified as a vertical-slice prototype
- Production deployment status: blocked on architecture integration,
  institutional services, target evidence, and review

The target system design is defined in [architecture.md](architecture.md).
[ADR 0006](adr/0006-dual-container-storage-aware-execution.md) records the
dual-container and storage-aware execution decision, and
[ADR 0007](adr/0007-warm-pilot-and-latency-telemetry.md) records warm-pilot
execution and latency telemetry. [ADR 0008](adr/0008-chatqec-internal-service-boundary.md)
records the accepted ChatQEC identity, model, data, and API boundary, and
[ADR 0009](adr/0009-development-slurm-test-cluster.md) limits the contributed
Docker Compose Slurm cluster to development scheduler testing.
The implemented local lifecycle and the activation procedure for the planned
target, storage, and pilot profiles are described in
[hpc-execution.md](hpc-execution.md).

## Initial Scope Gates

The first-deployment component boundary is the versioned allowlist in
[`deployments/initial.yaml`](../deployments/initial.yaml), summarized in
[initial-deployment.md](initial-deployment.md). A catalog entry does not grant
deployment admission. The service filters its registry through this profile
before discovery and workflow resolution.

The initial pre-container integration gate is closed. OpenQSE is resolved to a
pinned `openqse-spec` revision and published only as glossary and architecture
resources. QAppsWiki's resource contract is integration-tested. ChatQEC's
GitHub working source is authenticated and audited at an exact revision, and
its provider-neutral HTTPS JSON/SSE contract, bounded client adapter, fixtures,
and tests are complete. A loopback-only service and QHPC gateway now expose
cited extractive answers from all 60 exact-revision canonical pages through
the same contract and supervised local lifecycle. The local verification is
recorded in
[ChatQEC service smoke evidence](evidence/chatqec-local-service-smoke-2026-07-28.md).

This does not make ChatQEC production-deployable. The local service deliberately
uses no generative model, Qdrant service, open-web fallback, or scientific tool
execution. A production model-backed server and the concrete institutional
model, embedding, identity, egress, retention, corpus, secrets, and telemetry
services still require implementation, selection, security testing, and
acceptance.

TN-Sim's exact public revision, CPU iTensor MPS operation contract, controlled
CLI adapter, and representative fixtures are now defined. Its external binary
has not been built or source-executed; reproducible build corrections,
immutable runtime evidence, and target acceptance remain required. Every
selected component has a validated pre-runtime scaffold. Source audits,
interface contracts, adapters, fixtures, and integration tests are completed
first; each executable operation still requires a pinned descriptor and
target-accepted immutable Linux runtime before production execution.

FTQC's private QSC ecosystem repository is admitted at an exact revision. Its
stable C API has been built locally on macOS arm64 and exercised through the EQO
worker for two Workbench workflows: a measured two-device-qubit Bell circuit
and one Steane logical-qubit preparation. Both produce typed FTQC MLIR, IQM
JSON, and an explicit preparation report. The preparation stops before
calibration-aware routing or IQM submission and makes no fault-tolerance or
hardware-execution claim. The source also contains the historical ORNL IQM path,
but its job receipt, exact device identity, counts, corrected logical histogram,
and acceptance comparison are not preserved. License clearance, a portable
reproducible LLVM/MLIR 22 Linux runtime, immutable release publication, and
target acceptance remain required.

Production-shaped containerization is locally complete for STABSim, QASMTrans,
NWQEC, FTPrimitiveBench, and LightStim. Their exact source revisions, source
archives, recipes, context wrappers, dependencies, smoke boundaries, and base
images are digest-pinned in `OperationRuntime` contracts. Each constrained
`linux/amd64` image passed a local network-disabled, read-only OCI smoke test
and reproduced the same image manifest in a second no-cache build. This is
local OCI evidence only; registry publication, SIF conversion, SBOM,
signature, attestation, site storage activation, and target acceptance remain
open.

The machine-readable initial HPC acceptance profile covers all fourteen
deployment components. It reports five OCI-verified batch runtimes, TN-Sim and
FTQC as production-runtime-pending, and OpenQEvo, OpenQSE, QAppsWiki, ChatQEC, plus the
three non-executable QFlow/QIRIS incubation records as outside the Slurm batch
gate in their current roles. Its gate remains closed
while the target and storage profiles are planned and no runtime is
target-accepted.

TN-Sim still needs a corrected reproducible iTensor/BLAS source build and
source-backed correctness evidence. FTQC still needs license clearance and a
reproducible, portable LLVM/MLIR 22 Linux build despite its verified local
macOS development bundle. STABSim's local image cannot be published
until its upstream project supplies explicit license terms. OpenQEvo packaging
is blocked because the audited source declares its license as `TBD` and
provides no license file. ChatQEC remains a separately governed service rather
than an operation image.

## Implemented Local Primitives

- Immutable OCI, Apptainer, reproducible Python-wheel, and native-bundle
  reference contracts.
- Versioned operation-runtime build contracts, deterministic context
  preparation, exact offline dependency archives, constrained local OCI smoke
  verification, and immutable OCI-to-Apptainer command rendering.
- Reproducible locally smoke-tested operation images for STABSim, QASMTrans,
  NWQEC, FTPrimitiveBench, and LightStim.
- A deployment-aligned HPC acceptance profile and CLI status/gate checks that
  reject component, role, integration, or runtime drift.
- Controlled local runner with an explicit operation allowlist.
- Separate local API and worker commands connected through transactional task
  leases, with deployment-registry admission enforced again at the worker.
- Durable worker identity and heartbeats, append-only task attempts and
  execution events, persisted asynchronous handles, restart reconciliation,
  cancellation, and declared-output collection.
- Slurm submission, state classification, accounting fallback, cancellation,
  scheduler-handle recovery, controlled staging, storage-policy validation,
  output collection, and controlled network-disabled Apptainer rendering.
- Versioned planned execution-target, storage-profile, and pilot-profile
  contracts plus an asynchronous Slurm runner exercised end to end with
  simulated scheduler and Apptainer transports. All five current operation
  runtime contracts pass runner admission, staging, job-rendering, polling,
  collection, and cleanup conformance tests.
- A revision-pinned, development-only Docker Compose Slurm provider and
  tokenized CLI transport for real `sbatch`, `squeue`, `sacct`, and `scancel`
  smoke testing without exposing the contributed REST service. Completion and
  cancellation passed against two live local workers on 2026-07-27.
- Durable pilot allocation and reservation state, capacity and eligibility
  policy, health, drain and expiry transitions, and batch fallback.
- Default-deny role/action definitions and secret-reference validation.
- Append-only SHA-256 chained audit records for future deployment integration.
- Persistent local workflow, run, task, attempt, event, worker, artifact,
  checksum, log, retry, cancellation, lease, and export behavior.
- Separately deployable Django Workbench with CSRF-protected fixed-origin API
  proxy, revisioned workflow drafts, typed React Flow composition, immutable
  publication, run submission, and checksum-verified artifact retrieval.
- A separately supervised, workload-authenticated ChatQEC development service
  over the pinned canonical corpus, with a server-side QHPC gateway, strict
  browser request allowlist, cited answers or explicit refusal, and no tool
  execution or retained conversation state.
- Verified local OpenQEvo and QASMTrans-to-STABSim vertical slices.

These are development foundations. The API does not yet enforce authoritative
institutional identity or workspace ownership; SQLite and the filesystem
artifact store are not approved production services; and the Slurm,
Apptainer, storage, and pilot paths have not run on a DOE target. The planned
profiles contain no claim of administrator approval.

The Docker Compose Slurm provider passed its local scheduler lifecycle smoke,
but it is not target acceptance. It does not run the
approved operation SIFs or model facility storage, networking, identity,
hardware, queueing, or performance, and its external source build has
development-only credentials. QHPC uses a tracked compatibility build and an
explicit local public CA instead of the source's global TLS-verification bypass.

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

Production containerization is the final executable onboarding gate. It begins
after the component's source, interface contract, adapter, fixtures, and
integration tests are stable. The local runtime matrix, immutable identifiers,
and evidence links are documented in
[operation-runtimes.md](operation-runtimes.md) and
[`containers/operations/README.md`](../containers/operations/README.md).

- Tool-specific immutable Linux operation images rather than shared developer
  environments, Python wheels, or Darwin native bundles.
- Approved internal OCI registry or Apptainer image cache.
- Digest and signature verification before execution.
- Source revision, build recipe, dependency inventory, SBOM, vulnerability
  result, attestation, retention, and revocation policy as required.
- Images built or pulled before job execution; target jobs do not build or pull
  mutable images.
- A target-accepted SIF and its digest for each admitted runtime; local Docker
  image IDs are never used as release identities.

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
   worker placement, and permitted Apptainer network namespaces.
6. Warm-pilot accounts, partitions or reservations, resource ceilings, idle
   timeout, maximum lifetime, operating cost, capacity owner, and service SLOs.
7. Parallel-filesystem topology, node-local storage, image-staging mechanism,
   and approved logical bind mappings.
8. Required RDMA, MPI, UCX, libfabric, GPU, and GPUDirect data paths and ABI
   compatibility policy.
9. Native-versus-container performance thresholds and representative workload
   profiles.
10. Allowed egress, proxy, repository, package-index, and quantum-backend
    routes, including enforcement for runtimes that require no network.
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
