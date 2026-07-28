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
qhpc-ecosystem integration validate deployments/initial.yaml
qhpc-ecosystem integration list deployments/initial.yaml
qhpc-ecosystem integration info deployments/initial.yaml nwqec
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
execution target or activate a DOE profile. The current provider and operating
procedure are documented in [hpc-execution.md](hpc-execution.md).

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
run records.

## Workflows and Runs

Workflows are directed acyclic graphs. They contain pinned capability versions,
typed edges, parameters, and declared external inputs and outputs. A workflow
definition is independent of frontend canvas coordinates and presentation
state.

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
qhpc-ecosystem contract list
qhpc-ecosystem contract schema capability
```

Validate YAML or JSON documents:

```bash
qhpc-ecosystem contract validate capability capability.yaml
qhpc-ecosystem contract validate integration-scaffold integrations/nwqec/integration.yaml
qhpc-ecosystem contract validate operation-interface integrations/nwqec/interface.yaml
qhpc-ecosystem contract validate operation-runtime containers/operations/qasmtrans/runtime.yaml
qhpc-ecosystem contract validate service-interface integrations/chatqec/service.yaml
qhpc-ecosystem contract validate slurm-test-cluster infrastructure/test-clusters/slurm-docker-cluster/cluster.yaml
qhpc-ecosystem contract validate workflow workflow.yaml
```
