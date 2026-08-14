# Federated Capability Registry

The QHPC registry is a deterministic aggregation of validated, attributed
capability descriptors. Descriptors may be project-authored or maintained as
ecosystem overlays. It is generated output, not an alternative source of truth
for scientific software.

## Descriptor Locations

Repository and release directory discovery recognizes:

```text
qhpc-capability.yaml
qhpc-capability.yml
.qhpc/capability.yaml
.qhpc/capability.yml
```

An explicit descriptor file can also be passed as a source. Discovery ignores
version-control, virtual-environment, cache, build, distribution, and
`node_modules` directories.

Curated overlays use
`capabilities/<repository>/<capability>/qhpc-capability.yaml`. The descriptor
still points to the source of that release and an immutable revision. When the
project has moved, optional `metadata.repository.canonical_url` identifies the
current project repository without rewriting historical release provenance.
The descriptor's `spec.component.name` and description identify the upstream
project; `metadata.name` identifies the narrower capability EQO publishes.
This prevents one admitted operation from being presented as the purpose of an
entire project.

Use [the contributor template](../templates/qhpc-capability.yaml) as a starting
point. The examples in `examples/contracts/` validate the contract machinery;
they are not published project capabilities.

Initial-deployment components begin with a non-executable
[`IntegrationScaffold`](contracts.md#integration-scaffolds). The scaffold is
used while source, interfaces, adapters, fixtures, and tests are still being
resolved. It is not discovered by the registry builder and cannot make a
component executable.

## Publication Validation

Registry publication requires all of the following:

- The capability passes the packaged `capability-v1` schema and semantic rules.
- The canonical repository URL matches exactly one entry in `ecosystem.yaml`
  after normalizing a trailing slash or `.git` suffix.
- A differing release-source URL is explicitly admitted through the catalog's
  `alternate_sources`.
- The catalog repository has a canonical source decision.
- The capability project matches the catalog project. Legacy `data-science` and
  `hardware-tools` catalog labels map explicitly to `data-schema` and
  `hybrid-workflows` contract IDs.
- Integration authority, curator identities, project-review state, validation
  maturity, and supporting evidence are explicit.
- A full commit hash or semantic release tag pins the project revision.
- Runtime references and digests for executable operations are immutable.
- Internal sources do not publish public capabilities.
- QAppsWiki documentation is linked.

Production container construction is intentionally after contract, adapter,
fixture, and integration-test stabilization. Resource-only capabilities can be
published with `runtime_status: not-applicable`; executable operations cannot
be published with a placeholder runtime.

The generated registry embeds each validated descriptor together with its
SHA-256 digest, catalog repository slug, curation metadata, and validation
results. It also records
the source catalog digest. It deliberately contains no generation timestamp or
absolute discovery path, making output deterministic for identical descriptors
and catalog content.

## Commands

Build from one or more release checkouts or explicit descriptors:

```bash
eqo registry build \
  --source /path/to/project-release \
  --source /path/to/another/qhpc-capability.yaml \
  --output registry.yaml
```

Validate ownership against the current repository catalog:

```bash
eqo registry validate registry.yaml
```

Inspect generated content without contacting repositories or registries:

```bash
eqo registry list registry.yaml
eqo registry info registry.yaml CAPABILITY_ID
eqo registry info registry.yaml CAPABILITY_ID --version 1.2.0
eqo registry info registry.yaml CAPABILITY_ID \
  --operation OPERATION_ID
eqo registry info registry.yaml CAPABILITY_ID --json
eqo registry digest registry.yaml
```

`registry info` prints the component purpose, recommended use cases,
quick-start steps, example workflows, limitations, and available operation
descriptions. Selecting an operation adds its typed inputs, outputs,
parameters, runtime, and execution targets. `--json` exposes the same
contract-backed record for automation.

Authenticated GitLab retrieval is intentionally outside the local registry
builder. An approved release checkout or staging service supplies local source
directories; the same deterministic builder then validates and aggregates
them. This keeps credentials and network access outside the registry format.
