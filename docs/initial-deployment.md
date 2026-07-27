# Initial Deployment Scope

- Status: Authoritative allowlist
- Last updated: 2026-07-27
- Machine-readable profile: [`deployments/initial.yaml`](../deployments/initial.yaml)

The first QHPC deployment is limited to the ten components below. The broader
`ecosystem.yaml` catalog remains an inventory and onboarding queue; catalog
presence alone does not admit a component to this deployment.

| Component | Deployment role | Source | Integration scaffold | Onboarding status |
| --- | --- | --- | --- | --- |
| STABSim | Operation provider | [Repository](https://github.com/seangarn32/STABSim) | [Published](../integrations/stabsim/integration.yaml) | Registry published; OCI smoke tested; image publication license-blocked |
| TN-Sim | Operation provider | [NWQ-Sim `tn_sim` branch](https://github.com/pnnl/NWQ-Sim/tree/tn_sim) | [Interface tested](../integrations/tn-sim/integration.yaml) | Pre-runtime contract complete |
| NWQEC | Operation provider | [Repository](https://github.com/pnnl/nwqec) | [Interface tested](../integrations/nwqec/integration.yaml) | OCI smoke tested; registry pending |
| FTPrimitiveBench | Operation provider | [Repository](https://github.com/ShuwenKan/FTPrimitiveBench) | [Interface tested](../integrations/ftprimitivebench/integration.yaml) | OCI smoke tested; registry pending |
| LightStim | Operation provider | [Repository](https://github.com/QuTone/LightStim) | [Interface tested](../integrations/lightstim/integration.yaml) | OCI smoke tested; registry pending |
| QASMTrans | Operation provider | [Repository](https://github.com/pnnl/qasmtrans) | [Published](../integrations/qasmtrans/integration.yaml) | Registry published; OCI smoke tested |
| OpenQEvo | Operation provider | [Repository](https://github.com/QSCSoftwareThrust/OpenQEvo) | [Published](../integrations/openqevo/integration.yaml) | Registry published; OCI blocked on license |
| OpenQSE | Integration standard | [Specification repository](https://github.com/openQSE/openqse-spec) | [Published](../integrations/openqse/integration.yaml) | Registry published |
| QAppsWiki | Knowledge resource | [Repository](https://github.com/QSCSoftwareThrust/QAppsWiki) | [Published](../integrations/qappswiki/integration.yaml) | Registry published |
| ChatQEC | Assistant service | [GitHub repository](https://github.com/QSCSoftwareThrust/ChatQEC) | [Contract tested](../integrations/chatqec/integration.yaml) | Pre-runtime service integration complete |

`Registry published` means a versioned QHPC descriptor is present in the
current example registry. It does not mean that a production Linux image, DOE
authorization, target acceptance, or production review is complete.

STABSim, QASMTrans, NWQEC, FTPrimitiveBench, and LightStim have digest-pinned
`linux/amd64` operation recipes and runtime contracts that pass
deterministic-context checks, constrained local OCI smoke tests, and repeat
no-cache image builds. Existing registry capabilities still use their admitted
runtime records; no capability will be changed to a container until an
immutable registry release and target-accepted SIF exist.

Every component now has an integration scaffold. For the eight repository-based
components represented in the GitLab mirror inventory, the scaffold also records
the expected mirror location and assigned reusable Apptainer developer
environment. TN-Sim instead uses its public upstream branch directly, with its
mirror status marked `not-applicable`; the selected public OpenQSE
specification also requires no QSC mirror. `Inventory-listed` does not claim
that a mirror has been fetched or verified at its target revision.

## Enforcement

`qhpc-ecosystem serve` requires an explicit deployment profile. At startup the
profile is contract-validated, repository references are checked against
`ecosystem.yaml`, and the registry is reduced to the non-blocked repositories
on the allowlist before it reaches the API and workflow resolver. Consequently,
an out-of-scope capability cannot be discovered or used to publish a workflow
through that service. Stored workflows are re-resolved against the active
filtered registry when a run is submitted, preventing an older workflow record
from bypassing a narrowed profile.

The current deployment registry has published records for STABSim, QASMTrans,
OpenQEvo, OpenQSE, and QAppsWiki. OpenQSE and QAppsWiki expose resources only,
with no operations or runtime. TN-Sim, NWQEC, FTPrimitiveBench, and LightStim
have exact-revision source audits, runtime-free operation interfaces,
controlled adapters, fixtures, and integration tests. The shared Stim artifact
boundary was also exercised from FTPrimitiveBench into LightStim. NWQEC,
FTPrimitiveBench, and LightStim now additionally have local OCI build and smoke
evidence. TN-Sim's adapter fixes the documented CPU iTensor MPS path and parses
its count format, but the external binary has not yet been reproducibly built
or source-executed.

ChatQEC has a pinned source, accepted service boundary, versioned HTTPS
JSON/SSE interface, bounded transport-injected client adapter, and contract
fixtures. It is not registry-published or deployable until a conforming server
runtime and institutionally approved service dependencies are available. The
initial pre-container integration scope is therefore closed; production
container, target, and service acceptance remain the next gates.

## Open Decisions

- Build TN-Sim's pinned CPU iTensor path reproducibly, execute source-backed
  correctness fixtures, and accept its immutable Linux runtime on the target.
- Obtain explicit distributable license terms for STABSim before publishing
  its locally verified operation image; the audited revision contains no
  license file.
- Obtain an explicit distributable license for OpenQEvo before constructing or
  publishing a Linux operation image; the audited repository currently
  declares its license as `TBD` and contains no license file.
- Implement a ChatQEC server conforming to
  [ADR 0008](adr/0008-chatqec-internal-service-boundary.md) and the versioned
  service contract, then select and approve the concrete model, embedding,
  workload identity, data-egress, retention, and corpus services.
- Publish the five verified OCI images to the approved registry, convert and
  verify immutable SIFs, produce required supply-chain evidence, and accept
  each executable runtime on its deployment targets.

Profile version `0.3.0` resolves OpenQSE to the pinned `openqse-spec` resource
and records the completed provider-neutral ChatQEC service contract. Further
first-deployment scope or source changes require another reviewed version to
`deployments/initial.yaml`; adding a repository to `ecosystem.yaml` is not
sufficient.
