# Initial Deployment Scope

- Status: Authoritative allowlist
- Last updated: 2026-08-28
- Machine-readable profile: [`deployments/initial.yaml`](../deployments/initial.yaml)

The first QHPC deployment is limited to the fifteen components below. The broader
`ecosystem.yaml` catalog remains an inventory and onboarding queue; catalog
presence alone does not admit a component to this deployment.

| Component | Deployment role | Source | Integration scaffold | Onboarding status |
| --- | --- | --- | --- | --- |
| STABSim | Operation provider | [QSC repository](https://github.com/QSCSoftwareThrust/STABSim) | [Published](../integrations/stabsim/integration.yaml) | Registry published; mirror verified at admitted revision; OCI smoke tested; image publication license-blocked |
| TN-Sim | Operation provider | [NWQ-Sim `tn_sim` branch](https://github.com/pnnl/NWQ-Sim/tree/tn_sim) | [Interface tested](../integrations/tn-sim/integration.yaml) | Pre-runtime contract complete |
| NWQEC | Operation provider | [Repository](https://github.com/pnnl/nwqec) | [Interface tested](../integrations/nwqec/integration.yaml) | OCI smoke tested; registry pending |
| FTPrimitiveBench | Operation provider | [Repository](https://github.com/QSCSoftwareThrust/FTPrimitiveBench) | [Interface tested](../integrations/ftprimitivebench/integration.yaml) | OCI smoke tested; registry published |
| LightStim | Operation provider | [QSC repository](https://github.com/QSCSoftwareThrust/LightStim) | [Interface tested](../integrations/lightstim/integration.yaml) | Registry published; current OCI release retains [QuTone source provenance](https://github.com/QuTone/LightStim); QSC revision rebuild pending |
| QASMTrans | Operation provider | [Repository](https://github.com/pnnl/qasmtrans) | [Published](../integrations/qasmtrans/integration.yaml) | Registry published; OCI smoke tested |
| FTQC | Operation provider | [Private QSC working mirror](https://github.com/QSCSoftwareThrust/FTQC) | [Interface tested](../integrations/ftqc/integration.yaml) | Registry published; GitLab source synchronized; QASM import adapter tested; production LLVM/MLIR runtime and license pending |
| OpenQEvo | Operation provider | [Repository](https://github.com/QSCSoftwareThrust/OpenQEvo) | [Published](../integrations/openqevo/integration.yaml) | Registry published; OCI blocked on license |
| OpenQSE | Integration standard | [Specification repository](https://github.com/openQSE/openqse-spec) | [Published](../integrations/openqse/integration.yaml) | Registry published |
| QAppsWiki | Knowledge resource | [Repository](https://github.com/QSCSoftwareThrust/QAppsWiki) | [Published](../integrations/qappswiki/integration.yaml) | Registry published |
| QSC Materials Repository | Data service | [SDL deployments repository](https://code.ornl.gov/intersect/data/deployments) | [Published](../integrations/qsc-materials-db/integration.yaml) | Static `materials-db` schema and provenance record published; live SDL service deferred |
| ChatQEC | Assistant service | [GitHub repository](https://github.com/QSCSoftwareThrust/ChatQEC) | [Contract tested](../integrations/chatqec/integration.yaml) | Local cited canonical service functional; production service deferred |
| ExaChem QFlow | Operation provider | [ExaChem](https://github.com/ExaChem/exachem) | [Scaffolded](../integrations/exachem-qflow/integration.yaml) | Resource-only prototype; local export hook is uncommitted; no Run action |
| QIRIS Runtime (IRIS/QIR-EE) | Operation provider | [IRIS](https://github.com/ORNL/iris) | [Scaffolded](../integrations/iris-qiris/integration.yaml) | Resource-only prototype; high-level QFlow task-set adapter and live orchestration pending |
| NWQSim QFlow VQE Plugin | Operation provider | [NWQSim main branch](https://github.com/pnnl/nwq-sim) | [Scaffolded](../integrations/nwqsim-qflow/integration.yaml) | Resource-only prototype; local plugin is uncommitted; saved H6 evidence imported |

`Registry published` means a versioned QHPC descriptor is present in the
current example registry. It does not mean that a production Linux image, DOE
authorization, target acceptance, or production review is complete.

STABSim, QASMTrans, NWQEC, FTPrimitiveBench, and LightStim have digest-pinned
`linux/amd64` operation recipes and runtime contracts that pass
deterministic-context checks, constrained local OCI smoke tests, and repeat
no-cache image builds. Existing registry capabilities still use their admitted
runtime records; no capability will be changed to a container until an
immutable registry release and target-accepted SIF exist.

STABSim's QSC mirror exposes the exact admitted commit, so its canonical and
release repository now coincide. LightStim's QSC mirror does not contain the
admitted runtime commit. Its capability therefore presents QSC as the canonical
repository while retaining QuTone as the explicit source of the existing
release until a QSC commit passes rebuild and acceptance.

Every component now has an integration scaffold. For the nine repository-based
components represented in the GitLab mirror inventory, the scaffold also records
the expected mirror location and assigned reusable Apptainer developer
environment. TN-Sim instead uses its public upstream branch directly, with its
mirror status marked `not-applicable`; the selected public OpenQSE
specification also requires no QSC mirror. `Inventory-listed` does not claim
that a mirror has been fetched or verified at its target revision.

## Enforcement

`eqo serve` requires an explicit deployment profile. At startup the
profile is contract-validated, repository references are checked against
`ecosystem.yaml`, and the registry is reduced to the non-blocked repositories
on the allowlist before it reaches the API and workflow resolver. Consequently,
an out-of-scope capability cannot be discovered or used to publish a workflow
through that service. Stored workflows are re-resolved against the active
filtered registry when a run is submitted, preventing an older workflow record
from bypassing a narrowed profile.

The current deployment registry exposes records for all fifteen components.
Twelve have published integration scaffolds; the ExaChem/QFlow, QIRIS, and
NWQSim QFlow records are explicitly scaffolded prototypes with resources,
quick-start guidance, and evidence but no executable operations.
OpenQSE, QAppsWiki, and the QSC materials data-service schema expose resources
only, with no operations or runtime.
TN-Sim, NWQEC, FTPrimitiveBench, LightStim, and FTQC have exact-revision source
audits, controlled adapters, fixtures, and integration tests. The shared Stim
artifact boundary was also exercised from FTPrimitiveBench into LightStim.
NWQEC, FTPrimitiveBench, and LightStim now additionally have local OCI build
and smoke evidence. TN-Sim's adapter fixes the documented CPU iTensor MPS path
and parses its count format, but the external binary has not yet been
reproducibly built or source-executed.

FTQC's seven GitLab branches are synchronized to its private QSC working
mirror. The standalone QASM importer was compiled and smoke-tested from the
admitted source, and the Workbench publishes its QASM-to-FTQC-MLIR contract as
a resource-only capability. The full LLVM/MLIR 22 compiler runtime has not yet
been packaged reproducibly or accepted for execution.

ChatQEC has a pinned source, accepted service boundary, versioned HTTPS
JSON/SSE interface, bounded transport-injected client adapter, and contract
fixtures. Its loopback development server is registry-published and functional
through the QHPC API using all 60 pinned canonical pages. It is not a production
model-backed deployment: institutionally approved model, retrieval, identity,
egress, retention, secrets, telemetry, and service-runtime controls remain
required. The initial pre-container integration scope is therefore closed;
production container, target, and service acceptance remain the next gates.

## Open Decisions

- Build TN-Sim's pinned CPU iTensor path reproducibly, execute source-backed
  correctness fixtures, and accept its immutable Linux runtime on the target.
- Establish FTQC license terms, build its pinned LLVM/MLIR 22 dependency stack
  reproducibly, package the full compiler, and accept its immutable runtime on
  the target.
- Obtain explicit distributable license terms for STABSim before publishing
  its locally verified operation image; the audited revision contains no
  license file.
- Obtain an explicit distributable license for OpenQEvo before constructing or
  publishing a Linux operation image; the audited repository currently
  declares its license as `TBD` and contains no license file.
- Build and accept the production model-backed ChatQEC server conforming to
  [ADR 0008](adr/0008-chatqec-internal-service-boundary.md), then select and
  approve the concrete model, embedding, workload identity, data-egress,
  retention, and corpus services.
- Review and pin the ExaChem task-set export hook and NWQSim QFlow plugin,
  implement live QIRIS orchestration over IRIS/QIR-EE, prove QFlow amplitude
  update and restart equivalence, and accept immutable HPC runtimes before
  publishing any QFlow/QIRIS operation.
- Publish the five verified OCI images to the approved registry, convert and
  verify immutable SIFs, produce required supply-chain evidence, and accept
  each executable runtime on its deployment targets.

Profile version `0.7.0` adds the three non-executable QFlow/QIRIS incubation
records while retaining the QSCSoftwareThrust STABSim, LightStim, and FTQC
source decisions. Further first-deployment scope or source changes require
another reviewed version to `deployments/initial.yaml`; adding a repository to
`ecosystem.yaml` is not sufficient.
