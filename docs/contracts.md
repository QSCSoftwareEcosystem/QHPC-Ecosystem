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
qhpc-ecosystem contract validate workflow workflow.yaml
```
