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
still points to the originating repository and an immutable revision.

Use [the contributor template](../templates/qhpc-capability.yaml) as a starting
point. The examples in `examples/contracts/` validate the contract machinery;
they are not published project capabilities.

## Publication Validation

Registry publication requires all of the following:

- The capability passes the packaged `capability-v1` schema and semantic rules.
- The repository URL matches exactly one entry in `ecosystem.yaml` after
  normalizing a trailing slash or `.git` suffix.
- The catalog repository has a canonical source decision.
- The capability project matches the catalog project. Legacy `data-science` and
  `hardware-tools` catalog labels map explicitly to `data-schema` and
  `hybrid-workflows` contract IDs.
- Integration authority, curator identities, project-review state, validation
  maturity, and supporting evidence are explicit.
- A full commit hash or semantic release tag pins the project revision.
- Runtime references and digests are immutable.
- Internal sources do not publish public capabilities.
- QAppsWiki documentation is linked.

The generated registry embeds each validated descriptor together with its
SHA-256 digest, catalog repository slug, curation metadata, and validation
results. It also records
the source catalog digest. It deliberately contains no generation timestamp or
absolute discovery path, making output deterministic for identical descriptors
and catalog content.

## Commands

Build from one or more release checkouts or explicit descriptors:

```bash
qhpc-ecosystem registry build \
  --source /path/to/project-release \
  --source /path/to/another/qhpc-capability.yaml \
  --output registry.yaml
```

Validate ownership against the current repository catalog:

```bash
qhpc-ecosystem registry validate registry.yaml
```

Inspect generated content without contacting repositories or registries:

```bash
qhpc-ecosystem registry list registry.yaml
qhpc-ecosystem registry info registry.yaml CAPABILITY_ID
qhpc-ecosystem registry info registry.yaml CAPABILITY_ID --version 1.2.0
qhpc-ecosystem registry digest registry.yaml
```

Authenticated GitLab retrieval is intentionally outside the local registry
builder. An approved release checkout or staging service supplies local source
directories; the same deterministic builder then validates and aggregates
them. This keeps credentials and network access outside the registry format.
