# OpenQSE Initial Resource Audit

- Audit date: 2026-07-24
- Organization: [openQSE](https://github.com/openQSE)
- Selected repository:
  [openQSE/openqse-spec](https://github.com/openQSE/openqse-spec)
- Selected revision: `c172c716e6566bd0a7502b34896dce7467f5a474`
- Default branch at audit: `main`
- License: Creative Commons Attribution 4.0 International
- QHPC role: non-executable integration-standard resource

## Selection

The OpenQSE organization is an initiative containing multiple independent
repositories; it is not a source repository or one executable tool. Its public
GitHub inventory contained 16 repositories at audit time:

`DEFw`, `Workshops`, `qScheduler`, `openqse-spec`, `openqse.github.io`,
`openqse-admin`, `QFw`, `.github`, `QFw-SLURM-Cluster`,
`qhw-characterization`, `qhw-data`, `qhw-iqm`, `qhw-scheduler`,
`qhw-admission`, `qhw-datastructures`, and `electroboy`.

The initial integration selects `openqse-spec` because that repository is the
organization's concrete shared terminology and architecture source. The
selection does not imply admission of the organization's schedulers,
frameworks, device adapters, workshop material, or experimental projects.
Those repositories require separate source audits and operation contracts if
they enter a later deployment profile.

## Revision Evidence

The selected commit was the `main` branch head inspected on 2026-07-24:

```text
c172c716e6566bd0a7502b34896dce7467f5a474
2026-06-25
arch: Add Requirements, HLD and definitions (#30)
```

The revision contains:

- `specification/term/`, a Markdown glossary of quantum/classical integration
  terms;
- `architecture/openqse-req.md`, architecture requirements;
- `architecture/openqse-hld.md`, the high-level design;
- `architecture/openqse-definitions.md`, timing, locality, and interconnect
  definitions; and
- `specification/sequence_diagrams/`, workflow, reservation, and quantum
  resource sequences.

The repository declares CC BY 4.0 in `LICENSE`. It does not publish a
machine-readable operation interface, runtime image, or executable release
that QHPC can safely infer from the specification.

## QHPC Contract

QHPC publishes the pinned glossary and architecture trees as documentation
resources through
`capabilities/openqse-spec/specification/qhpc-capability.yaml`. The capability
has no operations, invocation, runtime, or execution target. Runtime
containerization and an adapter are therefore not applicable.

The ecosystem integration test validates the descriptor, verifies both
resource URIs contain the selected revision, and confirms that the deployment
registry exposes no OpenQSE operation. Changes to the selected repository or
revision require a new capability and deployment-profile version.
