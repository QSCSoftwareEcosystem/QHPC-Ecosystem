# Software Thrust Integration Readiness

- Status: Curator audit queue
- Last updated: 2026-07-29

This matrix tracks the evidence required before a repository capability enters
the QHPC registry. Project review is recorded when available, but an
evidence-backed ecosystem curator may perform local integration independently.

| Project | Source position | Initial contribution | Curator action | Readiness |
| --- | --- | --- | --- | --- |
| SE | `spack-packages/` is available; `SoftEng/` is sparse | Packaging and release resources | Audit package definitions and stage a resource descriptor | Source available |
| DS | `DataSchema/` is available | Artifact types and metadata validators | Publish versioned schema resources | Source available |
| AS | Supporting repositories are cataloged; `AgenticSoftware/` is sparse | Recommendation or workflow assistance | Select an operation with tests and a stable entry point | Audit required |
| CT | Compiler repositories are cataloged | QASMTrans transpilation and FTQC QASM import | QASMTrans OCI verified; FTQC source, contract, adapter, fixtures, and source smoke verified; package and accept the FTQC runtime | Mixed: QASMTrans OCI smoke-tested; FTQC pre-runtime integration complete |
| HW | Simulator and QEC repositories are cataloged | STABSim structural metrics | Native workflow and reproducible OCI runtime verified; obtain explicit license terms before image publication | OCI smoke-tested; publication license-blocked |
| OpenQEvo | `OpenQEvo/` is available | Method discovery and time-evolution operation | Resolve upstream licensing before redistributable container packaging | Registry published; OCI license-blocked |

Within the initial deployment, TN-Sim, NWQEC, FTPrimitiveBench, LightStim, and
FTQC
have passed the pre-runtime contract portion of this ladder at exact source
revisions: runtime-free contracts, controlled adapters, fixtures, and
integration tests. NWQEC, FTPrimitiveBench, and LightStim were also exercised
against their pinned source dependencies and now have reproducible locally
smoke-tested OCI operation images. TN-Sim's controlled CLI adapter is
fixture-tested against the audited output format, but its external iTensor
binary still requires a corrected reproducible build and source-backed
execution. FTQC's standalone QASM importer was source-smoke-tested, but its full
LLVM/MLIR 22 compiler runtime and license terms remain open. None is
production-approved, and those without an existing
capability remain non-executable in the registry until immutable releases pass
target acceptance.

OpenQSE and QAppsWiki complete the non-executable resource path: their pinned
capabilities contain documentation or dataset/library resources and no
operation runtime. ChatQEC completes the pre-runtime service path with a pinned
source, accepted boundary, machine-valid HTTPS JSON/SSE contract, controlled
client adapter, fixtures, and integration tests. Its cited canonical-corpus
development server is functional through the QHPC API; the model-backed server
and institutional deployment dependencies remain production gates.

## Validation Ladder

1. `discovered`: repository and candidate behavior identified.
2. `contract-valid`: descriptor and immutable provenance pass QHPC validation.
3. `smoke-tested`: pinned source completes a controlled representative command.
4. `integration-tested`: operation succeeds through a QHPC workflow boundary.
5. `production-approved`: applicable DOE release and deployment controls pass.

## Cross-Cutting Source Decisions

- `HeteQSys` still lacks an authoritative repository URL.
- FTQC's private QSC working mirror is synchronized from its authoritative
  internal GitLab upstream; recurring synchronization requires approved
  GitLab and GitHub service identities.
- Internal automated retrieval requires an approved service identity.
- A catalog entry alone does not establish a supported operation.

## Curator Onboarding Checklist

- [ ] Create or update the component's validated integration scaffold.
- [ ] Record the originating project and attribution identifiers.
- [ ] Match a cataloged repository and pin a commit or semantic release.
- [ ] Select behavior supported by documentation, tests, or a stable API.
- [ ] Define operation inputs, outputs, parameters, and artifact types.
- [ ] Implement the controlled adapter without embedding scientific behavior.
- [ ] Link upstream tests or add an ecosystem-owned smoke fixture.
- [ ] Pass local integration tests through the adapter boundary.
- [ ] Link QAppsWiki documentation and provenance.
- [ ] Record authority, curators, project review state, and evidence.
- [ ] Pass capability and registry validation.
- [ ] Participate in a cross-project workflow when executable.
- [ ] Confirm local and HPC resource requirements.
- [ ] Build, verify, and accept the immutable production runtime image.

QHPC must not imply project endorsement when `project_reviewed` is false.
Integration status follows evidence rather than repository presence or an
inferred owner nomination.
