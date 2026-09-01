# QHPC Integration Contract Rules

- Status: Initial v1 rules
- Contract API version: `qhpc/v1`

This document defines the governance rules applied by the packaged JSON Schemas
and semantic validators. The schemas are distributed with the
`qhpc_ecosystem` Python package under `qhpc_ecosystem/contracts/`.

## Identifiers

Contract identifiers use lowercase ASCII letters, digits, dots, underscores,
and hyphens. They begin with a letter and are stable after publication.

Identifiers are scoped by resource type. Capability IDs must be unique in the
aggregated registry. Operation IDs must be unique within a capability. Workflow
node IDs must be unique within a workflow version.

Artifact type references include the major contract version:

```text
qhpc.quantum-circuit@1
qhpc.compilation-report@1
```

## Workflow Drafts

A `WorkflowDraft` is mutable control-plane state for interactive composition.
It stores a candidate `Workflow` object and canvas layout under a server-owned
draft identity, owner, revision, and timestamps. The candidate workflow may be
incomplete or invalid while it is being edited.

Canvas nodes record only presentation kind and position. Viewport state,
position, zoom, and future selection state do not participate in the canonical
workflow or its digest. Duplicate canvas node IDs are invalid.

Draft updates require the last observed revision. A stale revision is rejected
instead of silently overwriting newer state. Validation resolves the candidate
workflow against the active deployment-filtered registry without publishing
it. Publication succeeds only after authoritative workflow validation and uses
the existing immutable `(workflow ID, semantic version)` registration rule.

## Portable State Bundles

A `PortableStateBundle` manifest describes an EQO Local `.eqo` archive. It
pins the bundle and database schema versions, source release, registry and
deployment-profile digests, logical record counts, state-document checksum,
and every included artifact payload by identity, provenance, path, size, and
SHA-256 checksum.

The archive is an application-level interchange format, not a database backup
format. SQLite files, worker heartbeats, service credentials, caches, absolute
host paths, and installed scientific runtimes are excluded. Import validates
the manifest and all declared payloads, reconstructs a current-schema database,
and rewrites artifact URIs beneath the destination EQO Local data root. See
[the EQO Local lifecycle guide](local-release.md) for operating procedures.

## Deployment Profiles

A deployment profile is a versioned, deny-by-default component allowlist. It
records each selected component's source, ecosystem role, catalog mapping when
applicable, and onboarding state. Component IDs and catalog repository
references must be unique.

An unresolved source must be blocked and carry an explicit blocker. A catalog
mapping is validated against both the repository slug and canonical source URL.
Before a service starts, its registry is filtered through the profile; catalog
presence without profile admission cannot make a capability discoverable or
usable by workflow validation.

## Canonical And Release Repositories

Capability `metadata.repository.url` identifies the exact source repository for
that published release and revision. Optional `canonical_url` identifies the
current project repository when ownership has moved or a working mirror has
diverged from the admitted release history. Registry ownership is resolved
through `canonical_url` when present, while the release URL must still be the
catalog's canonical source or an explicitly admitted alternate.

The Workbench presents the canonical repository and labels a differing release
source separately. This permits a project to move under QSC ownership without
rewriting the provenance of an already-built runtime.

## Capability Guidance

A capability descriptor separates the upstream project identity from the
specific integration EQO publishes. `spec.component.name` and
`spec.component.description` identify and explain the upstream project or
tool. `metadata.name` names the narrower EQO capability, while operations,
guidance, limitations, and runtime evidence state exactly which part of that
project is currently integrated. Consumers fall back to `metadata.name` for
older descriptors that do not yet provide `spec.component.name`.

A capability may publish a structured `spec.guidance` block so the registry,
Workbench, and CLI explain the tool from the same source of truth. Curated
guidance contains:

- `use_when`: concrete situations in which a researcher should choose the tool;
- `quick_start`: ordered steps that lead to a supported operation or resource;
- `example_workflows`: published workflow identifiers that demonstrate the
  capability;
- `limitations`: current scientific, runtime, or integration boundaries.

`use_when` and `quick_start` are required whenever `guidance` is present.
Guidance is optional so older project-authored descriptors remain compatible.
Consumers fall back to the component description and executable-operation
status when a descriptor has not yet published guidance. Operation-specific
descriptions, artifact ports, parameters, runtimes, and execution targets
remain authoritative and are rendered alongside the capability-level guide.

## Repository Update State

Repository update operations are mutable control-plane state, not integration
contracts. Targets are derived from a validated deployment profile and
registry. The API accepts no client-supplied repository URL, ref, credential,
checkout path, or Git option. Candidate staging verifies the configured remote
ref again and records a full immutable commit without modifying the active
capability, operation runtime, or registry contracts. See
[Repository Updates](repository-updates.md).

## Integration Scaffolds

Every component selected by the initial deployment profile links to a validated
`IntegrationScaffold`. The scaffold is a pre-runtime onboarding record: it
tracks canonical source and GitLab mirror information, the reusable developer
environment, intended interfaces, scope, source audit, interface contract,
adapter, fixtures, integration tests, registry publication, and blockers.

A scaffold is not an executable capability and contains no invocation command,
runtime reference, or digest. This allows integration work to proceed without
inventing a placeholder container or implying that a tool is runnable. The
delivery order is source audit, interface contract, adapter, fixtures,
integration tests, production runtime build and target acceptance, and then
executable capability publication. Resource-only integrations may declare the
production runtime not applicable.

The deployment profile and all linked scaffolds can be checked together:

```bash
eqo integration validate deployments/initial.yaml
eqo integration list deployments/initial.yaml
eqo integration info deployments/initial.yaml nwqec
```

## Operation Interfaces

An `OperationInterface` is the runtime-free contract between a source audit and
an executable capability. It pins one exact source revision and defines each
operation's deterministic, seeded, or stochastic behavior; typed artifact
ports; and validated parameters. It contains no entrypoint, command, runtime
reference, image digest, or execution-target claim.

`contract-valid` interfaces must link evidence and may be exercised by
controlled adapters before production container work starts. They are not
discoverable executable registry entries. After the adapter stabilizes, the
runtime is built and accepted, and the interface is translated into a
`Capability` that records immutable invocation and runtime identity. Project
review is represented separately by the `project-reviewed` status.

## Operation Runtimes

An `OperationRuntime` pins the build and execution boundary for one operation
on one Linux architecture. It records the exact project revision and Git
archive digest, recipe and context-file digests, digest-pinned builder and
runtime bases, exact offline dependency archives, logical mounts, fixed
entrypoint, network and root-filesystem policy, and release state. An input
fixture is required for operations with an input port and omitted for
controlled no-input generators. Every runtime still requires at least one
declared output mount and a smoke assertion for its declared output.

Runtime states distinguish `build-ready`, local `oci-smoke-tested`, and
`target-accepted` evidence. A local image ID cannot populate the release
record. Published releases require an immutable OCI registry reference and
digest; target acceptance additionally requires an immutable Apptainer
reference and digest plus SBOM, signature, and attestation references. See
[operation-runtimes.md](operation-runtimes.md) for the build and acceptance
flow.

## Execution, Storage, And Pilot Profiles

An `ExecutionTarget` is an administrator-owned target policy. It identifies
the runner, accepted runtime formats, execution classes, scheduler policy,
resource ceilings, network mode, and associated storage profile. A workflow
selects a logical target and execution class; it cannot supply an account,
partition, executable, host path, or container command.

A `StorageProfile` owns image-cache and task-staging roots, logical container
mounts, optional node-local staging, checksum enforcement, input-byte limits,
and cleanup policy. Logical input, output, and scratch mounts are translated
only through this profile. Arbitrary user host binds are invalid.

A `PilotProfile` constrains a warm Slurm allocation by target, scheduler
accounting, capacity, lifetime, idle and health timeouts, operation allowlist,
runtime digest allowlist, resource eligibility, cache policy, and batch
fallback. A profile describes policy and does not itself prove that an
allocation exists or is site-approved. Planned profiles cannot be activated
while they contain placeholder paths, scheduler values, digests, or missing
evidence. See [hpc-execution.md](hpc-execution.md) for the implemented lifecycle
and site activation boundary.

A `SlurmTestCluster` pins an external Docker Compose source revision and defines
the controller, worker, shared-path, service, and readiness boundary used for
development scheduler testing. Its schema fixes the scope to
`development-only` and `production_evidence: false`; it cannot be used as an
execution target or activate a DOE profile. The current fixture and operating
procedure are documented in [hpc-execution.md](hpc-execution.md).

An `HpcAcceptanceProfile` maps every component in one deployment profile to
exactly one acceptance classification. Batch operations require an
`OperationRuntime`; services, integration standards, and knowledge or library
resources are recorded as explicitly outside the Slurm batch gate. The profile
also references the scheduler fixture and the planned site target and storage
contracts. Cross-file inspection rejects deployment membership, role,
integration, runtime, or component drift.

## Service Interfaces

A `ServiceInterface` is the runtime-free contract for a separately deployed
internal service. It pins the audited source, requires encrypted transport and
workload identity, records the QHPC authorization action and policy invariants,
and defines versioned request, response, and stream-event JSON Schemas.

Each endpoint references a schema declared in the same contract. Semantic
validation rejects invalid nested JSON Schemas, duplicate endpoint identities,
duplicate method/path pairs, and unknown schema references. A service
interface contains no provider credential, workload-identity secret, runtime
image, or deployment endpoint. Those values remain target-owned deployment
configuration.

The initial ChatQEC contract terminates user authorization at QHPC, forbids
forwarded browser credentials and direct tool execution, and exposes fixed
JSON and SSE answer paths. Its transport-injected client adapter validates
bounded conversation context, response correlation, corpus provenance, token
accounting, citations, and stage latency without selecting an institutional
identity mechanism.

## Versions

Components, capabilities, operations, and workflows use semantic versions.
Artifact types use an integer compatibility version because a change either
preserves the representation contract or requires a new major artifact type.

A published capability version is immutable. Any change to operation behavior,
parameters, ports, runtime, or packaged resources requires a new capability
version. The central registry records the resolved source commit even when a
project descriptor names a release tag.

## Attribution and Integration Authority

Every capability and artifact type declares an originating Software Thrust
project and stable attribution identifiers. Capability metadata separately
records whether integration authority is `project` or `ecosystem`, the active
curators, project-review state, runtime status, validation maturity, and linked
evidence.

Originating projects remain authoritative for scientific behavior. An
ecosystem curator may publish an evidence-backed overlay from a pinned revision
without implying project endorsement. `project_reviewed: false` remains visible
in the registry and workbench.

## Deprecation

Published resources are not deleted from reproducibility records. A deprecated
capability sets `metadata.deprecated: true` and declares `metadata.replaced_by`.
Existing workflow versions continue to reference the deprecated version, while
new workflow composition surfaces the replacement.

Artifact types use `metadata.status: deprecated` and publish a successor as a
new type version. Compatibility declarations state which prior versions a
consumer accepts.

## Runtime Identity

Every executable operation declares a runtime type, reference, and SHA-256
digest. Mutable `latest` references are forbidden.

- OCI references end in the declared `@sha256:...` digest.
- Apptainer references use an absolute path, `file://` URI, or `oras://` URI and
  carry a separately validated SHA-256 digest.
- Reproducible local Python wheels use `qhpc-runtime://wheels/...`; the
  controlled adapter verifies the file digest before import. This development
  runtime does not satisfy production container policy.
- An execution target may impose stricter registry, path, signature, or
  attestation policy.

The five shared images in `containers/` are developer environments. A
production operation must use a component-specific immutable image or an
approved immutable mapping maintained by SE.

## Invocation

An operation declares an entrypoint vector and argument vector. The runner
executes the vector directly and does not pass it through a shell. Template
substitution is limited to validated inputs, outputs, and parameters defined by
the operation contract.

Arbitrary shell snippets, command substitution, host paths, environment
mutation, and undeclared output locations are outside the v1 contract.

## Ports and Artifacts

Operation inputs and outputs reference versioned artifact types. Workflow edges
carry the artifact type on both endpoints, and those types must match exactly in
v1. Registry-aware validation confirms that edge endpoints match referenced
operation ports, required inputs are connected, parameters satisfy their
declared types and bounds, and execution targets are supported.

Artifacts record a storage URI, type, SHA-256 checksum, size, creator, and
optional producing run/task. Artifact payloads are not embedded in workflow or
run records. Local preview and download resolve only `file:` artifacts below
the configured artifact root and recheck the recorded checksum and size before
returning content.

## Workflows and Runs

Workflows are directed acyclic graphs. They contain pinned capability versions,
typed edges, parameters, and declared external inputs and outputs. A workflow
definition is independent of frontend canvas coordinates and presentation
state.

A `WorkflowDraft` is a mutable, revision-checked wrapper around a possibly
incomplete workflow and separate canvas layout. Its layout records node
positions and viewport only. Draft saves do not publish a workflow, and stale
updates or deletes fail on revision mismatch. Draft validation resolves the
embedded workflow against the active registry without creating an immutable
version; publication repeats that validation and then uses the normal workflow
publication path.

A run resolves the workflow digest, execution target, operation versions,
runtime digests, task attempts, states, and output artifact IDs. Run records are
append-oriented provenance records; task retries create new attempts rather
than rewriting prior execution facts.

## Extension Policy

The `qhpc/v1` schemas reject unknown fields. Proposed extensions must be added
through a reviewed schema revision so that project descriptors do not acquire
incompatible project-specific behavior. Experimental data can be published as
an artifact with an owned artifact type instead of adding ungoverned fields to
core contracts.

## CLI

List and inspect packaged schemas:

```bash
eqo contract list
eqo contract schema capability
```

Validate YAML or JSON documents:

```bash
eqo contract validate capability capability.yaml
eqo contract validate hpc-acceptance infrastructure/hpc-acceptance/initial.yaml
eqo contract validate integration-scaffold integrations/nwqec/integration.yaml
eqo contract validate operation-interface integrations/nwqec/interface.yaml
eqo contract validate operation-runtime containers/operations/qasmtrans/runtime.yaml
eqo contract validate service-interface integrations/chatqec/service.yaml
eqo contract validate slurm-test-cluster infrastructure/test-clusters/slurm-docker-cluster/cluster.yaml
eqo contract validate workflow workflow.yaml
```
