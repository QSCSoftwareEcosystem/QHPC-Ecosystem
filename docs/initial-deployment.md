# Initial Deployment Scope

- Status: Authoritative allowlist
- Last updated: 2026-07-24
- Machine-readable profile: [`deployments/initial.yaml`](../deployments/initial.yaml)

The first QHPC deployment is limited to the ten components below. The broader
`ecosystem.yaml` catalog remains an inventory and onboarding queue; catalog
presence alone does not admit a component to this deployment.

| Component | Deployment role | Source | Integration scaffold | Onboarding status |
| --- | --- | --- | --- | --- |
| STABSim | Operation provider | [Repository](https://github.com/seangarn32/STABSim) | [Published](../integrations/stabsim/integration.yaml) | Registry published |
| TN-Sim | Operation provider | [NWQ-Sim `tn_sim` branch](https://github.com/pnnl/NWQ-Sim/tree/tn_sim) | [Interface tested](../integrations/tn-sim/integration.yaml) | Pre-runtime contract complete |
| NWQEC | Operation provider | [Repository](https://github.com/pnnl/nwqec) | [Interface tested](../integrations/nwqec/integration.yaml) | Pre-runtime integration complete |
| FTPrimitiveBench | Operation provider | [Repository](https://github.com/ShuwenKan/FTPrimitiveBench) | [Interface tested](../integrations/ftprimitivebench/integration.yaml) | Pre-runtime integration complete |
| LightStim | Operation provider | [Repository](https://github.com/QuTone/LightStim) | [Interface tested](../integrations/lightstim/integration.yaml) | Pre-runtime integration complete |
| QASMTrans | Operation provider | [Repository](https://github.com/pnnl/qasmtrans) | [Published](../integrations/qasmtrans/integration.yaml) | Registry published |
| OpenQEvo | Operation provider | [Repository](https://github.com/QSCSoftwareThrust/OpenQEvo) | [Published](../integrations/openqevo/integration.yaml) | Registry published |
| OpenQSE | Integration standard | [GitHub organization](https://github.com/openQSE) | [Scaffolded](../integrations/openqse/integration.yaml) | Onboarding |
| QAppsWiki | Knowledge resource | [Repository](https://github.com/QSCSoftwareThrust/QAppsWiki) | [Published](../integrations/qappswiki/integration.yaml) | Registry published |
| ChatQEC | Assistant service | [GitHub repository](https://github.com/QSCSoftwareThrust/ChatQEC) | [Source and boundary defined](../integrations/chatqec/integration.yaml) | Service contract pending |

`Registry published` means a versioned QHPC descriptor is present in the
current example registry. It does not mean that a production Linux image, DOE
authorization, target acceptance, or production review is complete.

Every component now has an integration scaffold. For the eight repository-based
components represented in the GitLab mirror inventory, the scaffold also records
the expected mirror location and assigned reusable Apptainer developer
environment. TN-Sim instead uses its public upstream branch directly, with its
mirror status marked `not-applicable`. `Inventory-listed` does not claim that a
mirror has been fetched or verified at its target revision.

## Enforcement

`qhpc-ecosystem serve` requires an explicit deployment profile. At startup the
profile is contract-validated, repository references are checked against
`ecosystem.yaml`, and the registry is reduced to the non-blocked repositories
on the allowlist before it reaches the API and workflow resolver. Consequently,
an out-of-scope capability cannot be discovered or used to publish a workflow
through that service. Stored workflows are re-resolved against the active
filtered registry when a run is submitted, preventing an older workflow record
from bypassing a narrowed profile.

The current registry has published records for STABSim, QASMTrans, OpenQEvo,
and QAppsWiki. The remaining selected components appear in the profile but are
not exposed as executable capabilities. TN-Sim, NWQEC, FTPrimitiveBench, and
LightStim have exact-revision source audits, runtime-free operation interfaces,
controlled adapters, fixtures, and integration tests. The shared Stim artifact
boundary was also exercised from FTPrimitiveBench into LightStim. TN-Sim's
adapter fixes the documented CPU iTensor MPS path and parses its count format,
but the external binary has not yet been built or source-executed. These records
do not contain capability invocation or runtime details; component-specific
production containers and target acceptance remain the next executable gate,
followed by capability publication with immutable runtime digests.

## Open Decisions

- Build TN-Sim's pinned CPU iTensor path reproducibly, execute source-backed
  correctness fixtures, and accept its immutable Linux runtime on the target.
- Select the specific OpenQSE contracts or repositories QHPC will consume;
  OpenQSE is an integration initiative, not one executable tool image.
- Implement the accepted ChatQEC boundary in
  [ADR 0008](adr/0008-chatqec-internal-service-boundary.md): select the concrete
  institutionally accepted model, embedding, identity, data-egress, and
  retention services, then define the versioned API contract.
- Update NWQEC's deprecated `scikit-build-core` configuration or pin the
  compatible 0.10.x backend for its reproducible production build.
- Build and accept component-specific Linux runtimes for every executable
  operation on each deployment target.

Profile version `0.2.0` selects the GitHub ChatQEC working source and records
the accepted internal service boundary. Further first-deployment scope or
source changes require another reviewed version change to
`deployments/initial.yaml`; adding a repository to `ecosystem.yaml` is not
sufficient.
