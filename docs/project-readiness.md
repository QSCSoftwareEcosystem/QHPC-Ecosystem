# Software Thrust Integration Readiness

- Status: Curator audit queue
- Last updated: 2026-07-11

This matrix tracks the evidence required before a repository capability enters
the QHPC registry. Project review is recorded when available, but an
evidence-backed ecosystem curator may perform local integration independently.

| Project | Source position | Initial contribution | Curator action | Readiness |
| --- | --- | --- | --- | --- |
| SE | `spack-packages/` is available; `SoftEng/` is sparse | Packaging and release resources | Audit package definitions and stage a resource descriptor | Source available |
| DS | `DataSchema/` is available | Artifact types and metadata validators | Publish versioned schema resources | Source available |
| AS | Supporting repositories are cataloged; `AgenticSoftware/` is sparse | Recommendation or workflow assistance | Select an operation with tests and a stable entry point | Audit required |
| CT | Compiler repositories are cataloged | QASMTrans transpilation | Native runtime and workflow verified; resolve FTQC independently | Integration-tested locally |
| HW | Simulator and QEC repositories are cataloged | STABSim structural metrics | Native metrics runtime verified; simulation compatibility remains separate | Integration-tested locally |
| OpenQEvo | `OpenQEvo/` is available | Method discovery and time-evolution operation | Build the first curated executable descriptor | First candidate |

## Validation Ladder

1. `discovered`: repository and candidate behavior identified.
2. `contract-valid`: descriptor and immutable provenance pass QHPC validation.
3. `smoke-tested`: pinned source completes a controlled representative command.
4. `integration-tested`: operation succeeds through a QHPC workflow boundary.
5. `production-approved`: applicable DOE release and deployment controls pass.

## Cross-Cutting Source Decisions

- `HeteQSys` still lacks an authoritative repository URL.
- FTQC has competing internal GitLab and public GitHub source references.
- Internal automated retrieval requires an approved service identity.
- A catalog entry alone does not establish a supported operation.

## Curator Onboarding Checklist

- [ ] Record the originating project and attribution identifiers.
- [ ] Match a cataloged repository and pin a commit or semantic release.
- [ ] Select behavior supported by documentation, tests, or a stable API.
- [ ] Define operation inputs, outputs, parameters, and artifact types.
- [ ] Identify or build an immutable runtime image.
- [ ] Confirm local and HPC resource requirements.
- [ ] Link upstream tests or add an ecosystem-owned smoke fixture.
- [ ] Link QAppsWiki documentation and provenance.
- [ ] Record authority, curators, project review state, and evidence.
- [ ] Pass capability and registry validation.
- [ ] Participate in a cross-project workflow when executable.

QHPC must not imply project endorsement when `project_reviewed` is false.
Integration status follows evidence rather than repository presence or an
inferred owner nomination.
