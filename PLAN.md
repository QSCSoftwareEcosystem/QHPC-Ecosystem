# QHPC Ecosystem Plan

- Status: Active
- Last updated: 2026-07-11
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

## System Boundaries

```text
Software Thrust project repositories
  SE | DS | AS | CT | HW | OpenQEvo
                    |
                    | project-owned capability releases
                    v
          QHPC Ecosystem Registry
                    |
          +---------+----------+
          |                    |
          v                    v
   QHPC Workbench       Workflow API and Engine
                               |
                     +---------+----------+
                     |         |          |
                     v         v          v
                   Local   Slurm/HPC   Quantum backend

Supporting layers:
  QAppsWiki       documentation, package context, interfaces, and provenance
  DataSchema      shared artifact and metadata contracts
  QHPC-Ecosystem  repository inventory, integration schemas, CLI, and containers
```

`QHPC-Ecosystem` will remain the integration-contract and packaging project.
The deployable web application and workflow service should be developed as a
separate project, provisionally named `QHPC-Workbench`, which consumes the
QHPC registry instead of becoming authoritative for project software.

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

## Resource Model

The platform will distinguish the following resources:

| Resource | Definition |
| --- | --- |
| Repository | Source location, ownership, visibility, maturity, and project metadata |
| Component | Versioned software release produced by a repository |
| Operation | Executable capability exposed by a component |
| Artifact type | Versioned contract for a workflow input or output |
| Artifact | Immutable or versioned data object with a URI, media type, checksum, and provenance |
| Workflow | User-authored directed acyclic graph of operation references and connections |
| Workflow version | Immutable workflow definition with resolved contract versions |
| Run | Execution of a workflow version with inputs, parameters, identity, and target |
| Task | Execution state and outputs for one workflow node |
| Execution target | Local, CPU, GPU, Slurm partition, simulator, or quantum backend destination |
| Environment | Immutable runtime image and dependency metadata |

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

## Implementation Phases

### Phase 0 - Repository and Container Foundation

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

### Phase 1 - Integration Contracts and Readiness

Status: Completed initial contract and readiness baseline

Deliverables:

- [x] Define the initial `capability-v1` schema.
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

Status: Completed local engine baseline

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

The engine will own orchestration state, not scientific behavior. A task invokes
a validated project operation through its runtime contract.

Exit criteria:

- A workflow can be validated, submitted, canceled, inspected, and rerun
  without a web interface.
- Restarting the engine does not duplicate completed tasks.
- A run can be exported with the information required to understand and repeat
  it.

### Phase 4 - QHPC Workbench MVP

Status: Implemented local workbench baseline

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

Exit criteria:

- A user can discover project-owned operations, compose a valid workflow,
  submit it locally, inspect progress, examine artifacts, and rerun it from
  history.
- Project ownership and resolved component versions remain visible throughout
  discovery, composition, and execution.
- The interface cannot create a workflow that the API contract rejects.

### Phase 5 - Cross-Project Vertical Slice

Status: In progress; CT-HW workflow verified

The first integrated workflow is provisionally:

```text
DS context and artifact schema
        |
        v
AS method recommendation or workflow assistance
        |
        v
OpenQEvo algorithm selection and execution
        |
        v
CT compilation or IR lowering
        |
        v
HW simulation, QEC, or execution operation
        |
        v
Versioned results and provenance bundle
```

SE provides packaging, CI, runtime validation, and reproducibility practices
across the entire workflow. The exact operations must be supported by repository
documentation, tests, or a stable API. The curator will not invent scientific
behavior or imply project endorsement.

The first verified slice executes OpenQEvo's pinned `list_methods_detail()` API
through a digest-checked wheel runtime, persists the method-catalog artifact,
and exports complete run provenance. The full DS-AS-OpenQEvo-CT-HW scientific
slice remains pending because DS and AS do not yet publish executable nodes and
the verified HW operation currently analyzes circuit structure rather than
executing an incompatible gate basis.

A second verified slice connects QASMTrans transpilation to STABSim structural
metrics through `qhpc.transpiled-circuit@1`. Both native runtimes reproduce
identical bundle digests across isolated builds. Full STABSim execution is not
claimed because the IBM `SX` basis emitted by QASMTrans is outside the audited
simulator gate set. DS and AS executable nodes remain pending.

QASMTrans currently initializes routing with `std::random_device` and does not
expose a seed. Run provenance captures the exact output checksum, but repeated
transpilation is not guaranteed to be bit-for-bit identical until upstream
adds seed control or adopts deterministic initialization.

Exit criteria:

- The workflow uses released contributions from the Software Thrust projects
  rather than substitute implementations.
- Each node displays project, repository revision, operation version, runtime
  identity, inputs, outputs, and validation status.
- The workflow can be saved, rerun with new inputs, and exported with complete
  provenance.

### Phase 6 - HPC and DOE Hardening

Status: Local policy and adapter foundation implemented; target acceptance pending

Deliverables:

- [x] Implement a Slurm runner with submission, polling, cancellation, timeout,
      and failure classification.
- [ ] Execute approved workloads with Apptainer on target HPC systems.
- [ ] Integrate an approved internal image registry or shared image cache.
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
- [x] Enforce execution-target allowlists and resource limits in local and
      Slurm contracts.
- [ ] Enforce target network policy.
- [ ] Produce required software inventories, checksums, attestations, or SBOMs.
- [ ] Complete security, operations, backup, recovery, and deployment reviews.

Exit criteria:

- The same workflow contract runs locally and through Slurm without changing
  scientific operation definitions.
- Authorization and audit tests demonstrate that users cannot publish or run
  capabilities outside their assigned policy.
- Runtime images and artifacts can be traced to approved, immutable sources.

### Phase 7 - Expansion and Operations

Status: Future

- [ ] Onboard additional project components through the contributor contract.
- [ ] Add controlled quantum backend adapters.
- [ ] Add reusable workflow publication and review.
- [ ] Add compatibility and deprecation reporting.
- [ ] Add operational dashboards, quotas, retention, and cost/resource
      reporting as required.
- [ ] Add agentic assistance only through the same authorization, registry, and
      workflow APIs used by human users.

## Verification Strategy

Testing will scale with each layer:

- Contract tests for valid and invalid descriptors, workflows, and artifacts.
- Registry tests for determinism, conflicts, ownership, versions, and drift.
- State-machine tests for retries, cancellation, restart, leases, and duplicate
  completion.
- Runner contract tests using controlled fake local and Slurm adapters.
- Integration tests using small project-owned reference operations.
- API authorization and audit tests.
- Frontend component tests for typed composition and execution states.
- End-to-end tests for discover, compose, run, inspect, rerun, and export.
- Target-system acceptance tests for Apptainer and Slurm that remain separate
  from the local unit suite.

## Current Readiness Gaps

The following issues are known as of 2026-07-11:

- CT does not have a dedicated local checkout in this coordination workspace.
- SE, AS, and HW are sparsely populated locally and require canonical project
  content or release locations for capability onboarding.
- HeteQSys does not yet have an authoritative repository URL.
- FTQC has an unresolved canonical-source decision between internal GitLab and
  public GitHub locations.
- OpenQEvo method discovery and the QASMTrans-to-STABSim metrics workflow are
  verified with digest-checked local runtimes. Production container builds and
  target-system signatures remain pending.
- The approved identity, deployment, container registry, artifact storage, and
  network boundaries for a DOE-hosted service remain institutional decisions;
  required decisions and acceptance tests are recorded in
  `docs/deployment-readiness.md`.

These gaps do not block the implemented local registry, engine, workbench, or
OpenQEvo slice. They block claiming a complete five-project scientific workflow
or DOE production readiness.

## MVP Definition

The local platform MVP is implemented for a verified single-operation project
slice. The cross-project scientific MVP remains Phase 5 work.

The ecosystem MVP is complete when a user can:

1. Discover attributed capabilities from Software Thrust repositories.
2. Inspect ownership, versions, inputs, outputs, runtime, documentation, and
   validation status.
3. Compose a typed cross-project workflow visually or through the API.
4. Execute it through the controlled local runner.
5. Observe task state, logs, failures, and produced artifacts.
6. Save and rerun the workflow with different inputs.
7. Export a reproducibility bundle containing the workflow, resolved versions,
   parameters, artifact metadata, checksums, and provenance.

Slurm execution and production DOE controls are required for the subsequent HPC
deployment milestone, but not for the local MVP.

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
