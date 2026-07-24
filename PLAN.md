# QHPC Ecosystem Plan

- Status: Active
- Last updated: 2026-07-24
- Scope: QSC Software Thrust quantum-HPC software ecosystem

## Purpose

The QHPC Ecosystem will provide a DOE-controlled platform for discovering,
composing, executing, and reproducing quantum-HPC software workflows. Its
interaction model may be informed by successful scientific workflow systems,
including Galaxy, but the implementation, architecture, schemas, APIs, visual
design, and deployment will be independently developed for QSC requirements.

The ecosystem is not a replacement for the Software Thrust projects. It is the
integration layer through which project-owned software can be discovered and
used together.

The governing model is:

> Federated development, evidence-backed ecosystem curation, and centralized
> discovery and execution.

Each project remains authoritative for its scientific software and domain
behavior. When project maintainers do not participate, the ecosystem curator
may build descriptors and adapters from repository evidence without claiming
project endorsement. The ecosystem owns shared integration contracts, catalog
aggregation, workflow composition, execution coordination, provenance, and the
user workbench.

## Current Delivery Snapshot

As of 2026-07-24, the ecosystem is a working local orchestration MVP. It is not
yet a shared DOE service or an end-to-end HPC deployment. The plan uses the
following status distinctions:

| Capability area | Current state | Evidence and remaining gate |
| --- | --- | --- |
| Contracts, catalog, and deployment admission | Functional locally | Versioned schemas, catalog validation, and deny-by-default deployment-profile filtering are implemented |
| Registry, workflow engine, and control API | Functional locally | Discovery, workflow publication, run submission, state, cancellation, retry, logs, and export are implemented |
| Local execution and provenance | Functional locally | Separate API and worker processes execute controlled local operations and persist artifacts, checksums, logs, and provenance in SQLite and the filesystem |
| Browser Workbench | Partially functional | Discovery, templates, one-operation drafts, run polling, artifacts, and export work; arbitrary typed graph composition and durable workspaces remain pending |
| Initial component onboarding | Pre-container scope complete | Five components are registry-published; all ten have source, interface, adapter or not-applicable, fixture, and integration-test closure; executable runtimes and the ChatQEC server remain production gates |
| HPC execution | Foundations only | Slurm and Apptainer primitives exist, but task leases, asynchronous target handles, storage profiles, production images, and target acceptance are not connected end to end |
| DOE shared deployment | Not ready | Institutional identity, PostgreSQL, approved artifact storage, secrets, audit forwarding, monitoring, signed runtime supply chain, and security and operations acceptance remain pending |

The automated local suite reported 100 passed tests and one skipped test on
2026-07-24. Target-system acceptance, performance, RDMA, container, and
institutional security tests are separate and are not represented by that
local result.

The active delivery target is a production-shaped shared execution slice: a
durable asynchronous task lifecycle, one Slurm-backed operation using an
accepted immutable runtime and storage profile, and correlated stage latency
evidence from submission through artifact collection.

## Design Principles

1. Project repositories remain the source of truth for scientific behavior;
   capability descriptors may be project-authored or ecosystem-curated.
2. Scientific functionality is integrated, not copied into the ecosystem.
3. Repositories, executable operations, artifacts, and workflows are distinct
   resources.
4. Every executable operation has typed inputs and outputs, a version,
   originating-project attribution, integration authority, evidence, and an
   immutable runtime identity.
5. Workflow definitions are independent of the frontend canvas format.
6. The CLI, web workbench, automation, and agents use the same versioned APIs
   and schemas.
7. Runs preserve resolved versions, parameters, logs, artifacts, checksums, and
   state transitions for reproducibility.
8. Execution is performed by controlled runners. The web API does not execute
   arbitrary shell commands.
9. Local development is supported first, while the architecture preserves a
   direct path to Slurm, Apptainer, and quantum execution backends.
10. DOE identity, authorization, auditing, secrets, network, and software supply
    chain requirements are architectural inputs rather than deployment add-ons.
11. The API is a control-plane process; separately deployable workers lease and
    execute tasks asynchronously.
12. Operation adapters define scientific invocation while target runners own
    local, Slurm, or quantum transport and lifecycle behavior.
13. Shared developer environments and immutable operation runtimes are distinct
    container models with different release and security requirements.
14. Storage topology, staging, controlled binds, RDMA, MPI, GPU, and GPUDirect
    behavior are execution-target requirements that must be measured in situ.
15. SE and DS may contribute cross-cutting release and artifact contracts
    without being represented as artificial executable workflow nodes; AS
    assistance is optional unless it publishes a meaningful versioned output.
16. Short approved operations may use site-governed warm workers or pilot
    allocations, while every attempt records stage-by-stage latency and falls
    back to ordinary batch execution when policy permits.
17. Repository inventory and deployment admission are separate: every service
    starts from a versioned, deny-by-default component allowlist and filters
    registry discovery and workflow resolution through it.

## System Boundaries

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
             API control plane
 identity -> policy -> workflow and run application services
                    |
                    v
             Persistent task leases
                    |
                    v
              Worker processes
  class selection -> staging -> adapter -> target runner -> collection
                    |
       +------------+------------+--------------+
       |            |            |              |
       v            v            v              v
     Local     Warm pilot    Slurm batch   Quantum backend
                    |
                    v
       Target data and communication plane
 image cache | parallel FS | node scratch | artifact store | RDMA/GPU
```

`QHPC-Ecosystem` remains one modular monorepo while it has one primary
maintainer. The API, worker, workbench, and CLI are separate application or
deployment units that share versioned domain contracts. A repository split is
deferred until ownership, deployment cadence, or access controls justify it.
The Workbench consumes QHPC APIs and registry records and is never authoritative
for project software.

The complete target design is maintained in `docs/architecture.md`. ADRs 0004
through 0007 record the API-worker split, adapter-runner boundary, dual
container plus storage-aware execution, and warm-pilot latency decisions.

## Ecosystem Infrastructure

The browser Workbench is one client of the ecosystem, not the ecosystem
itself. It owns presentation and user interaction only. Authoritative state,
workflow validation, policy, execution, and provenance remain available through
the versioned API and CLI when the Workbench is unavailable or replaced. No
scientific invocation, credential, deployment policy, or durable orchestration
state is implemented only in browser code.

The infrastructure consists of the following layers:

| Layer | Responsibility | Initial implementation direction |
| --- | --- | --- |
| Source federation | Independent project repositories and ecosystem-owned integration overlays | GitHub and internal GitLab repositories remain authoritative |
| Integration and supply chain | Validate descriptors, run tests, build runtimes, scan, sign, attest, and publish releases | Repository or ecosystem CI with pinned source revisions |
| Registry and admission | Aggregate capabilities and apply the deployment-profile allowlist | Deterministic registry snapshot filtered by `deployments/initial.yaml` |
| Access clients | Discovery, composition, administration, and automation | Workbench, CLI, approved automation, and ChatQEC use the same API |
| Control plane | Identity, authorization, workflow publication, run submission, policy, and audit | API service behind an approved reverse proxy and authentication boundary |
| Persistence | Durable workflows, runs, attempts, leases, registry references, artifact metadata, and migrations | PostgreSQL for the first shared deployment; SQLite remains local-development only |
| Execution plane | Lease tasks, stage data, invoke adapters, submit targets, monitor, cancel, and collect | Separate worker service connected to local, Slurm, pilot, and later quantum runners |
| Runtime distribution | Store and deliver immutable operation environments | Approved internal OCI or ORAS registry and Apptainer image cache |
| Data plane | Artifact payloads, input staging, node scratch, results, checksums, and retention | Approved object or shared filesystem storage plus target-local scratch |
| Knowledge and services | Documentation, provenance context, assistance, and domain services | QAppsWiki as a knowledge resource and ChatQEC as a separately governed service |
| Operations | Secrets, telemetry, logs, audit forwarding, backup, recovery, and incident handling | Reuse approved institutional services wherever available |

### Initial Deployment Topology

The preferred first shared deployment minimizes infrastructure operated by the
single ecosystem maintainer:

```text
Users and approved automation
             |
             v
 institutional reverse proxy, TLS, and identity
             |
             v
 service host: static Workbench + QHPC API
             |
       +-----+-------------------+
       |                         |
       v                         v
 PostgreSQL              artifact metadata and payload store
       |
       v
 separate worker on an approved HPC service or edge node
       |
       v
 Slurm: warm pilot or batch allocation
       |
       v
 Apptainer runtime + node-local cache/scratch + parallel filesystem
```

An approved internal image registry supplies immutable operation images before
job execution. The worker submits and reconciles Slurm jobs; the API does not
execute scientific commands or import project libraries. QAppsWiki and ChatQEC
connect through versioned resource or service contracts rather than being
embedded into the Workbench process.

Kubernetes is not required for the initial deployment. A service VM or an
institutionally managed application platform with system-managed processes is
preferred while there is one primary maintainer. Kubernetes becomes reasonable
only if a managed institutional service, availability requirements, scaling,
or independent deployment ownership justifies its operational cost.

The infrastructure boundary is successful when a Workbench outage does not
invalidate registered workflows, stop API or CLI access, or interrupt workers
already executing approved tasks. Conversely, a static webpage without the
registry, control plane, persistence, workers, runtimes, data plane, and
operational controls is not considered a deployed ecosystem.

## Project Responsibilities

| Project | Ecosystem contribution | Ownership retained by project |
| --- | --- | --- |
| SE - Software Engineering | Packaging standards, CI/CD profiles, testing, versioning, containers, Spack, release validation | Build and release practices for Software Thrust components |
| DS - Data Schema | Artifact schemas, metadata contracts, validation, interoperability, provenance fields | Schema definitions and compatibility policy |
| AS - Agentic Software | Agents, RAG, recommendations, copilots, and workflow assistance | Agent behavior, models, prompts, evaluation, and service releases |
| CT - Compilation Tools | Compiler passes, IR transformations, QASM/QIR/MLIR operations, and resource estimation | Compiler behavior, IR compatibility, and transformation releases |
| HW - Hybrid Workflows | Hybrid workflow patterns, QEC integration, simulators, and execution backends | Workflow and backend implementations and hardware-facing behavior |
| OpenQEvo | Cross-project reference integration, algorithm registry, adapters, and structured context | Time-evolution methods, adapters, context, and library releases |

The ecosystem may also consume scientific implementations from other QSC
thrusts through an owning Software Thrust project. Such code must enter through
the same release and capability contracts as Software Thrust components.

These responsibilities do not imply one executable node per project. SE release
controls and DS artifact contracts apply across the graph. AS may assist users
through the same API or publish a versioned recommendation operation when its
output is part of the scientific record.

## Initial Deployment Scope

The authoritative first-deployment allowlist is
`deployments/initial.yaml`. It contains only STABSim, TN-Sim, NWQEC,
FTPrimitiveBench, LightStim, QASMTrans, OpenQEvo, OpenQSE, QAppsWiki, and
ChatQEC. `ecosystem.yaml` remains broader so future candidates can be audited
without becoming visible or executable in the deployed service.

STABSim, QASMTrans, OpenQEvo, OpenQSE, and QAppsWiki currently have published
registry records. OpenQSE resolves to a pinned `openQSE/openqse-spec` revision
and, like QAppsWiki, publishes non-executable resources. TN-Sim, NWQEC,
FTPrimitiveBench, and LightStim have completed pre-runtime contract and adapter
integration but still require immutable runtimes and executable capability
publication. TN-Sim uses the public `tn_sim` branch of `pnnl/NWQ-Sim` without a
QSC mirror; its CPU iTensor MPS adapter is fixture-tested, while the external
binary and source-backed correctness execution remain runtime gates.

ChatQEC has an authenticated exact-revision audit, accepted internal service
boundary, provider-neutral HTTPS JSON/SSE contract, bounded client adapter,
fixtures, and tests. A conforming server and the concrete institutional model,
egress, retention, corpus, and identity services still require implementation,
selection, and acceptance. Detailed status and admission rules are maintained
in `docs/initial-deployment.md`.

## Resource Model

The platform will distinguish the following resources:

| Resource | Definition |
| --- | --- |
| Repository | Source location, ownership, visibility, maturity, and project metadata |
| Component | Versioned software release produced by a repository |
| Operation | Executable capability exposed by a component |
| Runtime release | Immutable executable environment with digest, source, build, and attestation evidence |
| Registry snapshot | Immutable set of capability and runtime releases used to resolve a workflow |
| Deployment profile | Versioned component allowlist applied to discovery and workflow resolution for one deployment |
| Artifact type | Versioned contract for a workflow input or output |
| Artifact | Immutable or versioned data object with a URI, media type, checksum, and provenance |
| Workspace | User or team scope for workflows, runs, artifacts, and access policy |
| Workflow | User-authored directed acyclic graph of operation references and connections |
| Workflow version | Immutable workflow definition with resolved contract versions |
| Run | Execution of a workflow version with inputs, parameters, identity, and target |
| Task | Current execution projection for one workflow node |
| Task attempt | Append-only record of one node attempt, including logs, errors, outputs, and target handle |
| Execution target | Local, CPU, GPU, Slurm partition, simulator, or quantum backend destination |
| Execution class | Policy-controlled local interactive, warm HPC pilot, batch HPC, or backend dispatch mode |
| Pilot allocation | Site-approved warm scheduler capacity with limits, health, lifetime, and drain state |
| Execution event | Append-only run, attempt, or pilot event with source, duration, and occurrence/receipt time |
| Storage profile | Approved image, input, scratch, output, host-library, and RDMA mappings for a target |
| Developer environment | Shared toolchain image for repository development, not a production runtime |

One repository may publish multiple operations. A repository may also publish
only schemas, datasets, documentation, adapters, or other non-executable
resources. The workbench will display project attribution without forcing a
one-repository-to-one-tool mapping.

## Capability Contract

Each integration publishes a small, versioned capability descriptor alongside
its source or in an ecosystem-owned overlay. The descriptor separates
originating-project attribution from integration authority. The intended shape
is:

```yaml
api_version: qhpc/v1
project: compilation-tools
integration:
  authority: ecosystem
  maintainers: [qhpc-ecosystem]
  project_reviewed: false
  validation_status: smoke-tested
  evidence: [tests/evidence/qasmtrans-smoke.md]
component: qasmtrans
version: 0.3.0

operations:
  - id: compile
    title: Compile quantum circuit
    inputs:
      circuit: qasm
      target: hardware-profile
    outputs:
      circuit: qir
      report: compilation-report
    runtime:
      image: registry.example/qsc/qasmtrans@sha256:...
    resources:
      cpu: 4
      memory_gb: 8
    execution_targets: [local, hpc-cpu]

documentation:
  qappswiki: integrations/qasmtrans.md
```

The descriptor records an operation contract, not unrestricted command text.
Commands, adapters, and parameter rendering will be validated against the
capability schema and packaged implementation.

## Publication Flow

```text
Project source repository or ecosystem overlay
        |
        v
Attributed descriptor with explicit integration authority
        |
        v
Project or ecosystem CI: validate, test, build, and attest
        |
        v
Internal GitLab release and container registry
        |
        v
QHPC registry aggregation and compatibility validation
        |
        v
Workbench discovery and workflow composition
```

The aggregated registry is generated from pinned releases or commits. It does
not replace project manifests and must retain the originating repository,
revision, attribution, curator, review state, evidence, validation result, and
runtime digest.

## Target Architecture

The target implementation separates the API control plane from worker
execution. The API validates and persists a run request and returns without
executing scientific work. Workers lease tasks, stage inputs, invoke a versioned
operation adapter through a target runner, collect declared outputs, compute
checksums, and append attempt and provenance records.

Adapters define operation-specific invocation and result interpretation.
Runners define target-specific prepare, submit, poll, cancel, and collect
behavior. Storage and communication policy is supplied by an approved execution
target, not by user-provided shell text or host paths.

For eligible short operations, target policy may select a warm worker inside a
pre-acquired Slurm pilot allocation. The pilot remains scheduler-accounted,
capacity-limited, and restricted to allowlisted runtime digests. If suitable
capacity is unavailable, dispatch falls back to ordinary Slurm batch unless the
approved request requires interactive service. Append-only task-stage events
separate API, dispatch, scheduler, image, input, execution, collection, and
finalization latency.

The local SQLite engine, filesystem artifact store, separate worker process,
synchronous local runner protocol, Python wheel, and Darwin native bundles are
MVP implementations. The API-worker process boundary is implemented locally,
but this does not constitute production persistence, Linux operation
containers, asynchronous Slurm execution handles, worker heartbeats, a warm
pilot service, stage latency telemetry, or a storage-aware HPC target.

## Implementation Phases

### Phase 0 - Repository and Developer Environment Foundation

Status: Completed baseline

- [x] Create the top-level `QHPC-Ecosystem` project.
- [x] Import the GitLab mirror inventory into `ecosystem.yaml`.
- [x] Record unresolved HeteQSys and ambiguous FTQC source metadata.
- [x] Define five reusable development environment classes.
- [x] Add Apptainer definitions for Python, HPC, documentation, agentic, and
      packaging work.
- [x] Implement `list`, `info`, `validate`, `sync-manifest`, `build`, `shell`,
      and `run` CLI commands.
- [x] Keep catalog inspection and drift checking offline.
- [x] Add unit and static catalog tests.

Phase 0 is infrastructure, not the completed ecosystem. Its images are shared
developer environments. Production workflow operations will require immutable,
component-specific runtime images or validated mappings to approved images.
Optional host command launchers may make developer environments Distrobox-like,
but those launchers do not become workflow execution contracts.

### Phase 1 - Integration Contracts and Readiness

Status: Completed initial contract and readiness baseline

Deliverables:

- [x] Define the initial `capability-v1` schema.
- [x] Define a versioned deployment-profile schema with explicit component
      roles, sources, onboarding state, and allowlist semantics.
- [x] Define initial artifact-type and artifact-metadata schemas for DS review.
- [x] Define workflow, workflow-version, run, task, and execution-target
      schemas.
- [x] Define component versioning, compatibility, deprecation, and ownership
      rules.
- [x] Define the initial runtime reference format, including immutable image
      identity.
- [x] Add CLI validators and valid/invalid contract fixtures.
- [x] Produce a project readiness matrix containing repository, owner, initial
      component, initial operation, inputs, outputs, runtime, and status.
- [x] Record architecture decisions covering DOE constraints and the clean
      implementation boundary from Galaxy.

The initial contracts are implemented. Project-owner confirmation and DS review
are optional confidence signals rather than delivery gates. The curator records
review state honestly and advances validation status only with evidence.

Exit criteria:

- Each of SE, DS, AS, CT, HW, and OpenQEvo has an evidence-backed candidate or
  an explicit unavailable/deferred decision.
- The contract schemas can represent executable and non-executable project
  contributions without project-specific exceptions.
- Invalid operation connections and mutable runtime references are rejected.

### Phase 1A - Initial Component Integration Scaffolding

Status: Completed pre-container integration; production runtimes deferred

Integration is deliberately completed before production containerization. A
scaffold is non-executable and cannot enter a workflow registry as an operation.
It records enough structure to audit and integrate each project without a fake
runtime digest or speculative invocation command.

Delivery order for each selected component:

1. Confirm canonical source and GitLab mirror state.
2. Audit supported interfaces and define the initial integration scope.
3. Define versioned input, output, resource, or service contracts.
4. Implement the smallest controlled adapter required by that contract.
5. Add representative fixtures and integration tests.
6. Build, verify, and accept the production runtime container for executable
   operations after the interface and adapter stabilize.
7. Publish the evidence-backed capability or resource descriptor. Executable
   capability publication requires the accepted immutable runtime digest.

Deliverables:

- [x] Define a versioned `integration-scaffold-v1` contract that contains no
      executable runtime reference.
- [x] Link every component in `deployments/initial.yaml` to one validated
      scaffold.
- [x] Record source, expected GitLab mirror, reusable developer environment,
      interfaces, scope, deliverable status, deferred production runtime, and
      blockers for all ten initial components.
- [x] Add CLI validation, listing, and inspection for the selected scaffold set.
- [x] Complete exact-revision source audits for TN-Sim, NWQEC,
      FTPrimitiveBench, and LightStim.
- [x] Define runtime-free operation interfaces and artifact contracts for
      TN-Sim, NWQEC, FTPrimitiveBench, and LightStim without inventing
      unsupported scientific behavior.
- [x] Implement controlled adapters, representative fixtures, and integration
      tests for TN-Sim, NWQEC, FTPrimitiveBench, and LightStim, including the
      FTPrimitiveBench-to-LightStim artifact boundary. TN-Sim remains
      fixture-tested until its external iTensor binary is built.
- [x] Select `QSCSoftwareThrust/ChatQEC` as the GitHub working source, complete
      its authenticated exact-revision audit, and accept the restrictive
      internal service boundary.
- [x] Define and test the provider-neutral ChatQEC HTTPS JSON/SSE contract,
      bounded client adapter, provenance checks, and representative fixtures.
      Institutionally accepted services and the conforming server remain Phase
      6 deployment gates.
- [x] Select the concrete `openQSE/openqse-spec` repository at an exact revision
      and publish its glossary and architecture as non-executable resources.
- [x] Defer immutable operation-runtime builds and executable publication for
      TN-Sim, NWQEC, FTPrimitiveBench, and LightStim to the production-runtime
      work after interface stabilization.

Shared Apptainer developer environments remain available during this phase.
Tool-specific Linux operation images, image signing, and target acceptance stay
in Phase 6 so interface churn does not force repeated production image work.

### Phase 2 - Federated Registry and Contributor Workflow

Status: Completed local registry and curated onboarding baseline

Deliverables:

- [x] Keep `ecosystem.yaml` as the repository inventory.
- [x] Add a generated component and operation registry.
- [x] Implement capability discovery from checked-out repositories and approved
      local release staging directories. Authenticated GitLab retrieval remains
      a deployment integration.
- [x] Add duplicate-ID, incompatible-version, ownership, schema, and runtime
      validation.
- [x] Add CLI commands for capability validation, registry construction, and
      registry inspection.
- [x] Provide a minimal descriptor template, fixtures, and CI example for
      project teams and ecosystem overlays.
- [x] Separate originating-project attribution from integration authority,
      curator identity, review state, evidence, and validation maturity.
- [x] Require registry entries to link QAppsWiki documentation and retain source
      provenance.
- [x] Filter the service registry through an explicit deployment profile before
      API discovery or workflow resolution.

The Phase 2 registry foundation is implemented. A local registry may contain
ecosystem-curated entries. Production approval remains subject to DOE release,
security, and deployment controls.

The initial generated registry contains seven pinned overlays spanning SE, DS,
AS, CT, HW, and cross-project resources. QASMTrans has source-level smoke
evidence; OpenQEvo publishes the first verified executable local operation.

Exit criteria:

- A project can publish a capability without moving its source into the
  ecosystem repository.
- The registry can be rebuilt deterministically from pinned project releases.
- Every registry entry identifies its owning project, repository revision, and
  validation status.

### Phase 3 - Independent Workflow Engine

Status: Local API-worker process split implemented; production backend pending

Deliverables:

- [x] Implement workflow graph validation using typed operation ports.
- [x] Implement immutable workflow versions and resolved operation references.
- [x] Implement persistent run and task state machines.
- [x] Implement task leases, idempotent completion, cancellation, retry, and
      node-level restart.
- [x] Implement artifact metadata, checksums, storage URIs, and provenance.
- [x] Implement structured logs and failure records.
- [x] Define the runner protocol.
- [x] Implement a controlled local runner for the first vertical slice.
- [x] Expose a versioned API used by both CLI and workbench clients.

Production architecture deliverables:

- [x] Separate the API process from task-executing worker processes; the API
      queues runs and a registry-bound worker leases and executes tasks.
- [ ] Replace synchronous execution with persistent asynchronous execution
      handles and worker heartbeats.
- [ ] Persist append-only execution events scoped to runs, task attempts, and
      pilots with correlation IDs, occurrence and receipt timestamps, monotonic
      stage durations, execution class, source component, and target handle.
- [ ] Expose asynchronous state and derived API, dispatch, queue, staging,
      execution, collection, and end-to-end latency through versioned APIs.
- [ ] Store retries as append-only task attempts rather than rewriting prior
      execution facts.
- [ ] Introduce persistence and artifact-store interfaces with schema migration
      support.
- [ ] Ingest outputs only from declared task-relative paths and verify payloads
      during collection.
- [ ] Enforce workspace ownership, target policy, and authoritative identity in
      application services.

The orchestration domain owns workflow and execution state, not scientific
behavior. An adapter invokes a validated project operation through its runtime
contract, and a target runner owns execution transport.

Exit criteria:

- A workflow can be validated, submitted, canceled, inspected, and rerun
  without a web interface.
- Restarting the engine does not duplicate completed tasks.
- A run can be exported with the information required to understand and repeat
  it.

The local exit criteria are met. Production exit additionally requires that API
restart, worker restart, duplicate completion, retry history, and asynchronous
target recovery preserve all prior attempts and artifacts.

### Phase 4 - QHPC Workbench MVP

Status: Local browser baseline implemented; visual composition remains pending

The first screen will be the working application, not a marketing page.

Primary views:

- **Projects:** Software Thrust developments grouped by SE, DS, AS, CT, HW, and
  OpenQEvo.
- **Explore:** searchable components, operations, workflows, artifacts, and
  examples.
- **Compose:** node-based workflow editor with typed connections and a focused
  operation inspector.
- **Runs:** active and historical executions with task states, logs, failures,
  resource use, and retry controls.
- **Artifacts:** circuits, IR, schemas, context, results, logs, and provenance.
- **Environments:** runtime identities, validation status, supported hardware,
  and execution targets.

The visual design will be original and tailored to quantum-HPC work. It may use
the general product lessons of scientific workflow systems, but it will not
copy Galaxy source code, schemas, wrappers, API design, visual assets, or page
layouts.

The current browser can discover registry entries, queue published templates,
publish and queue a one-operation draft, poll basic run state, inspect runs and
artifacts, and export provenance. Arbitrary node placement, typed edge editing,
draft persistence, workspace ownership, stage-specific progress, and streaming
updates remain target work.

The target Runs view distinguishes authorization, dispatch, scheduler queue,
image and input staging, operation execution, output collection, and
finalization. It displays the selected execution class and warm-pilot fallback
without combining all delay into scientific wall time.

Exit criteria:

- A user can discover project-owned operations, compose a valid workflow,
  submit it locally, inspect progress, examine artifacts, and rerun it from
  history.
- Project ownership and resolved component versions remain visible throughout
  discovery, composition, and execution.
- The interface cannot create a workflow that the API contract rejects.

### Phase 5 - Cross-Project Vertical Slice

Status: In progress; CT-HW workflow verified

Cross-project integration uses scientific operations where they exist and
cross-cutting contracts where a project is not an executable tool:

```text
DS artifact schemas and validation apply to inputs, edges, and outputs
SE packaging, CI, runtime, SBOM, and release policy apply to every operation
AS assistance may produce a draft or a versioned recommendation artifact

Executable scientific path:
  project-owned input or OpenQEvo output
                    |
                    v
          CT compilation or lowering
                    |
                    v
       HW simulation, analysis, or execution
                    |
                    v
       Versioned artifacts and provenance
```

SE provides packaging, CI, runtime validation, and reproducibility practices
across the entire workflow. The exact operations must be supported by repository
documentation, tests, or a stable API. The curator will not invent scientific
behavior or imply project endorsement.

One verified slice executes OpenQEvo's pinned `list_methods_detail()` API
through a digest-checked wheel runtime, persists the method-catalog artifact,
and exports complete run provenance. This is a registry operation rather than
a scientific circuit-generation claim.

A second verified slice connects QASMTrans transpilation to STABSim structural
metrics through `qhpc.transpiled-circuit@1`. Both native runtimes reproduce
identical bundle digests across isolated builds. Full STABSim execution is not
claimed because the IBM `SX` basis emitted by QASMTrans is outside the audited
simulator gate set. DS and SE participate through artifact and release policy;
AS integration remains optional until repository evidence supports a useful
versioned recommendation or assistance contract.

QASMTrans currently initializes routing with `std::random_device` and does not
expose a seed. Run provenance captures the exact output checksum, but repeated
transpilation is not guaranteed to be bit-for-bit identical until upstream
adds seed control or adopts deterministic initialization.

Exit criteria:

- The workflow uses released contributions from the Software Thrust projects
  rather than substitute implementations.
- Cross-cutting DS and SE contributions are validated without adding no-op
  executable nodes.
- Each node displays project, repository revision, operation version, runtime
  identity, inputs, outputs, and validation status.
- The workflow can be saved, rerun with new inputs, and exported with complete
  provenance.

### Phase 6 - HPC and DOE Hardening

Status: Local worker boundary implemented; storage and target integration pending

Production containerization occurs here, after integration scope, contracts,
adapters, fixtures, and tests have stabilized. Shared development images remain
development tools and are not promoted directly into production execution.

Deliverables:

- [ ] Provision an approved service host or managed application platform for
      the API and static Workbench behind institutional TLS and identity.
- [ ] Replace local SQLite orchestration state with PostgreSQL, managed schema
      migrations, transactional leases, backup, and tested restore procedures.
- [ ] Integrate an approved artifact metadata and payload store with checksum,
      quota, retention, backup, and recovery policy.
- [ ] Deploy workers separately from the API on approved HPC service or edge
      nodes; the browser and API processes never execute scientific commands.
- [ ] Integrate institutional logs, metrics, traces, audit forwarding, secrets,
      health checks, alerting, and operational ownership.
- [x] Implement Slurm submission, polling, cancellation, accounting fallback,
      and failure-classification primitives.
- [ ] Integrate an asynchronous Slurm runner with worker leases, persisted job
      IDs, heartbeats, cancellation, timeout, and output collection.
- [ ] Define target execution-class policy for local interactive, warm HPC
      pilot, ordinary batch, and target-specific asynchronous backends.
- [ ] Implement site-approved warm Slurm pilot allocations for eligible short
      operations, including capacity accounting, health checks, idle timeout,
      maximum lifetime, cache prewarming, draining, and ordinary-batch fallback.
- [ ] Restrict pilot workers to authorized operations, immutable runtime
      digests, fresh resource-isolated job steps and container processes,
      per-task workspaces, and the same artifact and audit controls as
      independently scheduled jobs.
- [ ] Execute approved workloads with Apptainer on target HPC systems.
- [ ] Build tool-specific immutable Linux operation images; development images,
      Python wheels, and Darwin bundles do not satisfy this requirement.
- [ ] Integrate an approved internal image registry or shared image cache.
- [ ] Define target storage profiles for image staging, read-only inputs,
      node-local scratch, result collection, quotas, retention, and purge.
- [ ] Add controlled bind mappings; workflows cannot provide arbitrary host
      paths.
- [ ] Verify host parallel-filesystem access and required RDMA, MPI, UCX,
      libfabric, GPU, and GPUDirect paths through site-approved libraries and
      devices.
- [ ] Benchmark native and container startup, metadata, throughput, scaling, and
      representative application wall time using shared and node-local image and
      workspace variants.
- [ ] Benchmark cold batch, warm pilot, cached and uncached runtime staging, and
      unavailable-pilot fallback; validate complete stage telemetry and target
      clock synchronization.
- [ ] Integrate institutional identity through the approved authentication
      boundary.
- [x] Implement deployment-neutral role-based authorization rules for
      publishing, composing, executing,
      administering, and viewing controlled resources.
- [x] Implement tamper-evident chained audit records for deployment integration.
- [x] Store secret references rather than credentials in workflows, logs,
      artifacts, or images.
- [ ] Integrate institutional identity and policy enforcement into the deployed
      API boundary.
- [x] Define execution-target allowlists and resource-limit validation
      primitives.
- [ ] Enforce target, storage, image, bind, account, and resource policy in the
      deployed API and worker boundaries.
- [ ] Enforce target network policy.
- [ ] Produce required software inventories, checksums, attestations, or SBOMs.
- [ ] Complete security, operations, backup, recovery, and deployment reviews.

Exit criteria:

- The same workflow contract runs locally and through Slurm without changing
  scientific operation definitions.
- Target evidence demonstrates approved native-versus-container performance and
  preserves the expected parallel-filesystem and RDMA data paths.
- Eligible short operations use approved warm capacity within measured target
  thresholds, fall back predictably, and report each latency stage without
  bypassing scheduler, account, quota, or authorization policy.
- Images and inputs are staged according to target policy, temporary work uses
  approved scratch, and only declared outputs enter artifact storage.
- Authorization and audit tests demonstrate that users cannot publish or run
  capabilities outside their assigned policy.
- Runtime images and artifacts can be traced to approved, immutable sources.

### Phase 7 - Expansion and Operations

Status: Future

- [ ] Onboard additional project components through the contributor contract.
- [ ] Admit an onboarded component to a deployment only through a reviewed
      deployment-profile version change.
- [ ] Add controlled quantum backend adapters.
- [ ] Add reusable workflow publication and review.
- [ ] Add compatibility and deprecation reporting.
- [ ] Add operational dashboards, quotas, retention, and cost/resource
      reporting as required.
- [ ] Add agentic assistance only through the same authorization, registry, and
      workflow APIs used by human users.

## Current Delivery Sequence

Because the project has one primary maintainer, work will follow this sequence
unless an institutional dependency makes the next item temporarily impossible.
The phase sections remain the complete requirements; this sequence identifies
the shortest route from the current local MVP to a credible shared deployment.

| Order | Delivery milestone | Status | Completion gate |
| --- | --- | --- | --- |
| 1 | Close pre-container integration scope | Completed | All ten initial components have closed source, interface, adapter or not-applicable, fixture, and test gates; OpenQSE is pinned and ChatQEC has a provider-neutral service contract |
| 2 | Make execution durable and asynchronous | Pending | Attempts and stage events are append-only; workers have durable identity, heartbeats, target handles, reconciliation, and restart-safe output collection |
| 3 | Prove one cold Slurm execution slice | Pending | One representative operation moves from an API-created task lease through Slurm and Apptainer to verified artifact collection under an approved target and storage profile |
| 4 | Add the low-latency HPC path | Pending | Policy selects eligible warm-pilot execution, enforces isolation and capacity, falls back to batch, and reports complete stage-by-stage latency |
| 5 | Publish initial production runtimes | Pending | Stable executable providers in the initial allowlist have immutable Linux images, required supply-chain evidence, target acceptance, and registry capabilities |
| 6 | Deploy the shared service and complete the Workbench MVP | Pending | PostgreSQL, approved artifact storage, identity and policy, secrets, audit and monitoring integration, recovery procedures, and arbitrary typed visual composition pass acceptance |

Containerization begins only after milestone 1 stabilizes the remaining
interfaces. Milestone 3 deliberately accepts one representative runtime first
so storage, Slurm, security, and performance assumptions are tested before
building every initial component image.

## Verification Strategy

Testing will scale with each layer:

- Contract tests for valid and invalid descriptors, service interfaces,
  workflows, and artifacts.
- Registry tests for determinism, conflicts, ownership, versions, and drift.
- State-machine tests for retries, cancellation, restart, leases, and duplicate
  completion.
- Runner contract tests using controlled fake local and Slurm adapters.
- Dispatch tests for class eligibility, warm capacity, saturation, draining,
  expiry, worker loss, and ordinary-batch fallback.
- Telemetry tests for stage ordering variants, correlation, retries,
  cancellation, failures, missing events, and clock-offset handling.
- Integration tests using small project-owned reference operations.
- API authorization and audit tests.
- Frontend component tests for typed composition and execution states.
- End-to-end tests for discover, compose, run, inspect, rerun, and export.
- Target-system acceptance tests for Apptainer and Slurm that remain separate
  from the local unit suite.
- Native-versus-container tests for startup, metadata operations, sequential and
  representative application I/O, multi-node scaling, and target-required RDMA
  or GPUDirect paths.
- Failure-injection tests for staging, worker restart, Slurm reconciliation,
  output collection, and cleanup.

## Current Readiness Gaps

The following issues are known as of 2026-07-24:

- The initial deployment allowlist is fixed, but five selected components are
  not yet registry-published: TN-Sim, NWQEC, FTPrimitiveBench, LightStim, and
  ChatQEC.
- All ten components have validated integration scaffolds and completed their
  pre-container source, interface, adapter or not-applicable, fixture, and
  integration-test gates. TN-Sim, NWQEC, FTPrimitiveBench, and LightStim still
  require production runtimes and executable registry capabilities.
- TN-Sim's canonical source is the public `tn_sim` branch of `pnnl/NWQ-Sim`
  and does not require a QSC mirror. Its CPU iTensor MPS contract and controlled
  CLI adapter are fixture-tested, but the external binary still needs a
  reproducible build, source-backed correctness execution, immutable runtime,
  and target acceptance. OpenQSE is resolved to a pinned non-executable
  specification resource. ChatQEC's interface and client adapter are complete,
  but its server plus concrete model, embedding, egress, retention, corpus, and
  identity services need implementation and institutional acceptance.
- NWQEC's upstream build metadata uses a deprecated `scikit-build-core` key.
  Reproducible builds currently require the compatible 0.10.x backend or an
  upstream metadata update before production runtime construction.
- CT does not have a dedicated local checkout in this coordination workspace.
- SE, AS, and HW are sparsely populated locally and require canonical project
  content or release locations for capability onboarding.
- HeteQSys does not yet have an authoritative repository URL.
- FTQC has an unresolved canonical-source decision between internal GitLab and
  public GitHub locations.
- OpenQEvo method discovery and the QASMTrans-to-STABSim metrics workflow are
  verified with digest-checked local runtimes. Production container builds and
  target-system signatures remain pending.
- The API and local worker are separate processes, but the worker still uses a
  synchronous local runner protocol and has no persistent worker identity,
  heartbeat, asynchronous target handle, or reconciliation loop.
- No warm worker or pilot allocation manager, execution-class dispatcher, or
  persistent stage-by-stage latency telemetry is implemented yet.
- Task retries update a current task record; append-only attempt history and
  authoritative contract-shaped API records remain pending.
- The Workbench queues templates and one-operation drafts but does not yet
  provide arbitrary visual node-and-edge composition.
- No target storage profile, node-local staging policy, controlled HPC bind map,
  or native-versus-container RDMA/I/O acceptance evidence exists yet.
- The approved identity, deployment, container registry, artifact storage, and
  network boundaries, filesystem topology, RDMA policy, and performance
  thresholds for a DOE-hosted service remain institutional decisions; required
  decisions and acceptance tests are recorded in `docs/deployment-readiness.md`.

These gaps do not block the implemented local registry, engine, workbench, or
OpenQEvo slice. They block claiming a complete five-project scientific workflow
or DOE production readiness.

## Milestone Definitions

### Local Orchestration MVP

Status: Complete

A user can discover attributed capabilities, inspect their contracts, publish
and run a valid workflow through the API or CLI, execute approved local
operations through a separate worker, inspect state and artifacts, retry or
cancel work, and export provenance. OpenQEvo and the
QASMTrans-to-STABSim structural-metrics path provide verified local slices.
This milestone does not claim arbitrary visual composition, production Linux
containers, shared multi-user operation, or HPC target acceptance.

### Workbench Composition MVP

Status: In progress

This milestone is complete when a user can:

1. Discover and inspect attributed operations and examples.
2. Compose and edit an arbitrary typed workflow graph.
3. Save an immutable workflow version and submit it through the same API used
   by the CLI.
4. Observe stage-specific progress, logs, failures, artifacts, and provenance.
5. Rerun or branch from history without bypassing server-side validation.

### Shared HPC MVP

Status: Pending

This milestone requires the same scientific operation contract to execute
locally and through a worker-managed Slurm and Apptainer path. It includes a
target-owned storage profile, immutable runtime verification, asynchronous job
reconciliation, declared-output collection, append-only attempts and stage
events, cancellation and recovery, and measured cold-batch and warm-pilot
latency. It does not imply full DOE production approval.

### DOE Production Readiness

Status: Pending

Production readiness additionally requires institutional identity and
authorization, PostgreSQL and approved artifact storage, secrets and workload
identity, central audit and observability, backup and recovery, signed and
attested runtime releases, network and target policy enforcement, approved
native-versus-container performance evidence, and security, deployment, and
operations review.

## Plan Maintenance

- Update this file when scope, phase status, architecture boundaries, or exit
  criteria change.
- Keep completed implementation details and user instructions in `README.md`.
- Record significant technical decisions as architecture decision records and
  link them from this plan.
- Keep project-specific roadmaps in their owning repositories. This plan tracks
  only integration work and cross-project dependencies.
- Do not mark a project integrated until a pinned upstream revision passes the
  capability contract and participates in a verified workflow.
