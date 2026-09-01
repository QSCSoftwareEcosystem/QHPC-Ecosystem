# QHPC-Ecosystem

`QHPC-Ecosystem` is the integration layer for QSC quantum-HPC software. It
combines the repository inventory and reusable Apptainer environments with an
attributed capability registry, persistent workflow engine, controlled runners,
versioned API, and browser workbench. Scientific source repositories remain
independent.

Remaining deployment dependencies are tracked in
[docs/deployment-readiness.md](docs/deployment-readiness.md). The target
control, execution, data, container, and storage boundaries are defined in
[docs/architecture.md](docs/architecture.md). Integration contracts,
architecture decisions, curator evidence, and DOE deployment readiness are
maintained under [docs/](docs/).

The first deployment uses the explicit allowlist in
[deployments/initial.yaml](deployments/initial.yaml): STABSim, TN-Sim, NWQEC,
FTPrimitiveBench, LightStim, QASMTrans, FTQC, OpenQEvo, OpenQSE, QAppsWiki,
QSC Materials Repository, ChatQEC, ExaChem QFlow, QIRIS over IRIS/QIR-EE, and
the NWQSim QFlow VQE plugin. See
[docs/initial-deployment.md](docs/initial-deployment.md) for
roles, onboarding state, and production gates. The larger catalog remains
available for future onboarding but is not deployment scope. Each selected
component has a validated record under [integrations/](integrations/), the
pre-container source, contract, adapter, fixture, and integration-test scope is
closed for the twelve published components; the three QFlow/QIRIS records are
explicitly scaffolded, non-executable prototypes. All fifteen components have
registry records admitted by the initial deployment profile, including one
static non-executable data-service schema for QSC materials. STABSim,
QASMTrans, NWQEC, FTPrimitiveBench,
and LightStim now have reproducible, digest-recorded, locally smoke-tested
operation images; see
[docs/operation-runtimes.md](docs/operation-runtimes.md) and the status matrix
in [containers/operations/README.md](containers/operations/README.md).
STABSim image publication remains blocked until its upstream project supplies
explicit license terms.

TN-Sim's pinned public `tn_sim` branch now has a runtime-free CPU MPS operation
contract and fixture-tested controlled CLI adapter. Its iTensor binary has not
yet been built or accepted as a production runtime.

FTQC uses the private `QSCSoftwareThrust/FTQC` working mirror synchronized from
the authoritative internal `qsc-ct/ftqc` GitLab repository. Its pinned QASM
import contract, FTQC MLIR artifact type, controlled adapter, fixtures, and
source smoke evidence are complete. A reproducible LLVM/MLIR 22 runtime,
license clearance, immutable release, and target acceptance remain pending.

OpenQSE is resolved to the pinned `openQSE/openqse-spec` glossary and
architecture repository and is published only as non-executable documentation
resources.

The QFlow/QIRIS incubation admits ExaChem as chemistry-cycle owner, IRIS/QIR-EE
as the proposed QIRIS runtime substrate, and a main-branch NWQSim VQE plugin as
one solver backend. Their task-set, task-set-result, and cycle-checkpoint
contracts and H6 evidence are visible in Tools and Knowledge, but they publish
no Compose or Run operation until the source, live orchestration,
amplitude-update, immutable-runtime, and HPC acceptance gates pass.

ChatQEC uses the accepted internal-service design summarized in
[docs/chatqec-service-boundary.md](docs/chatqec-service-boundary.md), with the
formal decision in
[ADR 0008](docs/adr/0008-chatqec-internal-service-boundary.md). The ecosystem
works from the `QSCSoftwareThrust/ChatQEC` GitHub repository; GitLab copies are
secondary mirrors. A versioned provider-neutral HTTPS JSON/SSE contract,
bounded client adapter, fixtures, and tests are implemented. A supervised
loopback development service now serves cited extractive answers from the
exact-revision ChatQEC canonical corpus through the QHPC API. The model-backed
production runtime and concrete DOE-approved model, identity, egress,
retrieval, and retention services remain deployment work.

The responsibilities are intentionally separate:

- `ProjectManagement/gitlab-mirror` defines where source repositories live.
- `QHPC-Ecosystem` defines how those repositories are built and run.
- `QAppsWiki` describes packages, interfaces, workflows, and provenance.
- `spack-packages` owns package-level HPC integration as components mature.

The project remains one modular monorepo while it has one primary maintainer.
The target deployment separates the API control plane, task-executing workers,
and browser Workbench. The local API and worker now run as separate processes
over persistent SQLite task leases. Durable worker identities and heartbeats,
append-only attempts and execution events, asynchronous target handles,
restart reconciliation, cancellation, and declared-output collection are
implemented. Workers advertise their execution targets, classes, and runtime
digests; stale heartbeats are treated as unavailable, and interactive API
submission fails before queueing when no compatible worker is healthy. This
verifies the production-shaped lifecycle locally, not the
PostgreSQL, multi-host, or approved DOE deployment.

For short approved operations, a target may maintain workers inside a warm,
site-governed Slurm pilot allocation. Policy selects between local interactive,
warm-pilot, ordinary batch, and backend-specific execution; unavailable warm
capacity falls back to batch when permitted. Each attempt exposes separate
authorization, dispatch, scheduler, image, input, execution, collection, and
finalization latency instead of treating all delay as scientific runtime.
The durable pilot controller and fallback policy are locally tested; launching
and operating a worker inside a real site allocation remains target work.

## Quick start

Install the CLI in editable mode from this directory:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev,workbench]"
```

The primary command is `eqo`. The previous `qhpc-ecosystem` executable remains
available as a compatibility alias for existing scripts.

Catalog inspection works without a container runtime or network access:

```bash
eqo list
eqo info OpenQEvo
eqo validate
eqo sync-manifest --check
eqo updates list
eqo updates check
eqo contract list
eqo contract validate capability examples/contracts/valid/capability.yaml
eqo contract validate operation-interface integrations/nwqec/interface.yaml
eqo contract validate operation-runtime containers/operations/qasmtrans/runtime.yaml
eqo contract validate service-interface integrations/chatqec/service.yaml
eqo integration validate deployments/initial.yaml
eqo integration list deployments/initial.yaml
```

Integration scaffolds and runtime-free operation or service interfaces
deliberately contain no executable command or runtime digest. They are the
pre-runtime onboarding layer. After an executable component's source,
contract, adapter, fixtures, and tests stabilize, its tool-specific production
image is built and accepted. The executable capability is then published with
that immutable runtime digest.

Project release checkouts that contain `qhpc-capability.yaml` can be aggregated
into a deterministic federated registry:

```bash
eqo registry build --source /path/to/project-release --output registry.yaml
eqo registry validate registry.yaml
eqo registry list registry.yaml
```

See [docs/registry.md](docs/registry.md) for publication rules and contributor
workflow.

The Workbench **Tools** catalog shows each capability's purpose directly in the
catalog. Open a Tool Record for recommended use cases, quick-start steps,
example workflows, operation contracts, limitations, and source provenance.
The same guidance is available from
`eqo registry info REGISTRY CAPABILITY`.

Build the verified local OpenQEvo wheel runtime and publish the method catalog
and circuit-synthesis example workflows:

```bash
eqo local-runtime build-wheel ../OpenQEvo \
  --revision 250550a3992bd57c032d4066843c2b03055c4b9d
eqo workflow publish examples/workflows/openqevo-method-catalog.yaml \
  --registry examples/registry.yaml
eqo workflow publish examples/workflows/openqevo-trotter-synthesis.yaml \
  --registry examples/registry.yaml
```

In the Workbench, select **Compose**, choose guided scientific showcase **01 —
Evolution to hardware readiness**, load or upload a Pauli-Hamiltonian JSON
file, and run the path to produce an OpenQASM 2.0 circuit plus a structured
synthesis report, a hardware-mapped circuit, structural metrics, and Clifford/T
counts. See [docs/showcases.md](docs/showcases.md) for the complete suite and
[docs/openqevo-integration.md](docs/openqevo-integration.md) for the supported
OpenQEvo contract and current development boundary.

With the five development OCI images and OpenQEvo wheel prepared, start the
complete local stack in one foreground supervisor:

```bash
eqo dev up
```

This prepares or starts the pinned virtual Slurm cluster, starts the API,
publishes the five initial workflow templates, starts the separately deployed
Django Workbench, prepares and supervises the pinned local ChatQEC canonical
service, starts separate local and virtual-Slurm worker processes, waits for
their health, and restarts a failed child process. The public Workbench uses a
fixed-origin proxy to the internal control API. The generated ChatQEC workload
token is supplied only to ChatQEC and the API child processes. The command
prints the Workbench URL and stops its child processes cleanly on `Ctrl-C`.
The cluster remains available by default so a subsequent start does not rebuild
it.

To back the Workbench **Data** panel's materials-db view with live object
storage instead of only the static capability record, point `dev up` at a
prepared [`databucket`](https://github.com/naughtont3/databucket) checkout
(a sibling repo in this demo, at
`../databucket-ecosystemdemo/databucket`):

```bash
eqo dev up --databucket-checkout /path/to/databucket
```

The databucket checkout must already have a generated `.env` (run
`./scripts/setup.sh` once inside it — `dev up` does not do this for you) and
its own Garage containers are otherwise managed automatically: started if not
already running, a `materials-db` project (bucket + scoped key) provisioned
idempotently, and the local `qsc-materials-db` schema/provenance files
published into it. Pass `--no-databucket` to skip this entirely, or
`--no-databucket-start` to require Garage to already be running. See
[docs/databucket-integration.md](docs/databucket-integration.md) for the full
flag reference, the API surface this adds, and how to test just the Data
panel directly (`eqo serve` + `qhpc-workbench`) without the rest of `dev up`.

Open the printed URL and select **Assistant** to use ChatQEC. Questions travel
through the Workbench's CSRF-protected fixed-origin proxy and the QHPC API;
browser code receives no ChatQEC workload credential and cannot choose its
subject, policy, model, provider, or corpus. Answers are rendered as untrusted
text with an exact-revision source ledger. The local service is a deterministic
canonical-corpus implementation, not the pending production model service.

Select **Updates** to check the upstream refs admitted by the active deployment
profile, prepare an exact detached candidate, or release that selection. The
same lifecycle is available with
`eqo updates list|check|stage|discard`. Prepared sources remain
outside the active registry and runtime cache until their component-specific
rebuild, tests, evidence, and promotion are complete. See
[docs/repository-updates.md](docs/repository-updates.md).

Open the printed URL and select **Compose**. The default **Guided** mode
presents six runnable scientific showcases and one evidence-backed H6
incubation blueprint. The two runnable cross-tool studies take a
Hamiltonian through evolution synthesis, mapping, structural analysis, and
fault-tolerant resource counting, or compare two surface-code memory distances.
Four focused examples teach each boundary independently. The H6 blueprint shows
the proposed ExaChem → QIRIS → NWQSim chemistry cycle and an optional future
FTQC circuit-lowering branch without publishing a false Run action. Circuit
paths accept pasted OpenQASM 2 text, a local `.qasm` file, or the included
fixtures and submit the immutable published workflow directly. Generated
circuits, estimates, metrics, counts, and provenance are available through
**Runs** and **Artifacts**.

Select **Open in Advanced** on a path, or switch to **Advanced**, to edit its
connected operation graph. The graph composer supports typed ports, workflow
input and output boundaries, operation parameters, template forking,
revisioned draft autosave, server validation, immutable publication, and run
submission. Canvas coordinates and zoom are stored with the draft but do not
participate in the published workflow digest.

The frontend production build is committed for normal Python installation.
When changing the TypeScript source, rebuild and verify it with:

```bash
npm ci --prefix workbench/frontend
npm run check --prefix workbench/frontend
npm test --prefix workbench/frontend
npm run build --prefix workbench/frontend
```

With `eqo dev up` running and Google Chrome installed, exercise the
browser workflow at desktop and mobile dimensions with:

```bash
npm run test:e2e --prefix workbench/frontend
```

For process-level debugging, the services can still be run in separate
terminals:

```bash
eqo serve --registry examples/registry.yaml \
  --deployment-profile deployments/initial.yaml

eqo worker --registry examples/registry.yaml \
  --deployment-profile deployments/initial.yaml \
  --runtime-root .qhpc/runtimes

eqo target-worker --registry examples/registry.yaml \
  --deployment-profile deployments/initial.yaml \
  --slurm-test-cluster \
    infrastructure/test-clusters/slurm-docker-cluster/cluster.yaml
```

The API prints the local Workbench URL. The Workbench queues runs and polls
persistent state while workers execute admitted tasks. Before submission, the
Workbench verifies that a healthy worker advertises the required target,
execution class, and immutable runtime digest. API clients may set
`queue_if_unavailable: true` only when deliberate offline batch queueing is
required. The local OpenQEvo operation calls the project's real method
registry; it does not execute the
placeholder Trotter implementations. See [docs/worker.md](docs/worker.md) for
the process and admission boundaries.

The verified CT-HW example uses a reproducible native QASMTrans bundle followed
by STABSim's structural-metrics path:

```bash
eqo local-runtime build-native /path/to/qasmtrans \
  --revision 1843c98fa4bac9cf6b88412145b69457e9176124 \
  --name qasmtrans --target QASMTrans --executable QASMTrans \
  --asset data/devices/ibmq_toronto.json
eqo local-runtime build-cpp /path/to/STABSim \
  --revision a0d8d2e2a9fdec9785857104220b8e7f0346c761 \
  --name stabsim --executable nwq_qasm \
  --source-file qasm/nwq_qasm.cpp \
  --include-directory include --include-directory qasm
eqo workflow publish examples/workflows/ct-hw-qasm-analysis.yaml \
  --registry examples/registry.yaml
```

Input files can be registered with
`eqo artifact register FILE --type qhpc.quantum-circuit@1` or pasted
into the Workbench workflow inspector. The slice performs real transpilation
and circuit analysis. It does not claim STABSim execution of QASMTrans's IBM
`SX` basis, which the audited simulator correctly rejects.

Completed run outputs and indexed artifacts expose controlled preview and
download actions. The content endpoint serves only local artifacts contained
under the configured artifact root and verifies the stored size and SHA-256
checksum before returning bytes.

Workflow and run state can also be managed without the browser:

```bash
eqo workflow validate workflow.yaml --registry registry.yaml
eqo workflow list
eqo run-record submit WORKFLOW_ID VERSION
eqo run-record list
eqo run-record info RUN_ID
eqo run-record cancel RUN_ID
eqo run-record retry RUN_ID NODE_ID
eqo run-record export RUN_ID --output run-bundle.json
```

On a system with Apptainer, build and enter the environment associated with a
repository:

```bash
eqo build OpenQEvo
eqo shell OpenQEvo
eqo run OpenQEvo -- python3 -m pytest
```

Images are shared by environment class and stored under
`~/.cache/qhpc-ecosystem/images` by default. For example, OpenQEvo and
FTCircuitBench both use `python-lib.sif`; this avoids maintaining one large image
per repository. `--image-dir` changes that location. A cataloged local checkout
is bound at `/workspace`; use `--workspace PATH` to override it.

The shared images above are developer environments. Tool-specific operation
containers use the separate `operation-runtime` commands:

```bash
eqo operation-runtime verify \
  containers/operations/qasmtrans/runtime.yaml
eqo operation-runtime build-oci \
  containers/operations/qasmtrans/runtime.yaml /path/to/qasmtrans \
  --context .qhpc/build/qasmtrans --tag qhpc/qasmtrans:1843c98-linux-amd64
eqo operation-runtime smoke-oci \
  containers/operations/qasmtrans/runtime.yaml \
  --image qhpc/qasmtrans:1843c98-linux-amd64
```

This local OCI result is not an accepted HPC runtime. Publication by immutable
registry digest, SIF conversion, supply-chain evidence, target storage policy,
and Slurm/Apptainer acceptance remain separate gates.

The production-shaped HPC path is documented in
[docs/hpc-execution.md](docs/hpc-execution.md). It includes the versioned
execution-target and storage-profile contracts, asynchronous Slurm runner,
persisted scheduler handles, controlled input and output staging, restart
reconciliation, and pilot state controller. The included target, storage, and
pilot YAML files are planned configurations and cannot be activated until an
administrator supplies and approves site-specific paths and scheduler policy.

For scheduler development, the repository includes a contract and CLI harness
for Thomas Naughton's revision-pinned Slurm Docker cluster. It exercises real
Slurm submission, polling, accounting, and cancellation while remaining
explicitly separate from Apptainer, storage-performance, and DOE acceptance:

```bash
eqo slurm-test-cluster prepare \
  infrastructure/test-clusters/slurm-docker-cluster/cluster.yaml \
  --build-ca /approved/path/development-build-ca.pem
eqo slurm-test-cluster start \
  infrastructure/test-clusters/slurm-docker-cluster/cluster.yaml
eqo slurm-test-cluster smoke \
  infrastructure/test-clusters/slurm-docker-cluster/cluster.yaml
```

Omit `--build-ca` on development networks that do not intercept TLS.

Inspect the acceptance boundary for all fifteen initial components:

```bash
eqo hpc-acceptance status \
  infrastructure/hpc-acceptance/initial.yaml
```

The corresponding `gate` command remains nonzero until all required package
runtimes have accepted SIF releases and the site target and storage profiles
are active. The Docker Slurm fixture validates scheduler behavior only.

## Environment classes

| Class | Intended use |
| --- | --- |
| `python-lib` | Python libraries, frameworks, decoders, and lightweight benchmarks |
| `hpc-build` | C/C++, Fortran, CMake, MPI, compilers, and native simulators |
| `schema-docs` | Schemas, catalogs, documentation, and knowledge graphs |
| `agentic` | RAG, agents, SDK dashboards, and Python/Node.js tools |
| `packaging` | Spack repository development and HPC package maintenance |

The recipes provide toolchains rather than embedding source code. This keeps
builds reusable and lets the same image operate on a local checkout, a GitLab
worktree, or a batch-job staging directory.

### Container roles

QHPC intentionally distinguishes two container models:

- **Developer environments** provide Distrobox-like `shell` and `run` access,
  share toolchains by environment class, and bind source at `/workspace`.
- **Operation runtimes** are tool-specific immutable Linux images used by
  workers for reproducible local or HPC workflow execution.

The current OpenQEvo wheel and QASMTrans/STABSim Darwin native bundles remain
local runtime evidence. The five locally verified OCI operation images are
production-shaped build artifacts, but they are not production releases until
they are published by immutable registry digest, converted and verified as
SIFs, supplied with required release evidence, and accepted on the target.

Warm pilots reuse verified immutable runtime caches for eligible short
operations but remain normal Slurm allocations with approved accounts, quotas,
resource limits, lifetime, idle timeout, and draining policy. They do not offer
an unrestricted shell or bypass scheduler and authorization controls.

HPC execution also requires an administrator-owned storage profile. The worker
must stage or verify the image, expose only controlled input and result paths,
use approved node-local scratch, and preserve the host parallel-filesystem and
RDMA path. Rebuilding an image alone does not correct storage placement or bind
policy. See [docs/deployment-readiness.md](docs/deployment-readiness.md).

## Catalog governance

`ecosystem.yaml` contains one entry for every row in
`ProjectManagement/gitlab-mirror/repositories.tsv`, plus blocked entries that
still need a source decision. `sync-manifest` updates only the source-owned
fields (`display_name`, `source_url`, and `notes`) and preserves curated runtime
metadata.

Deployment admission is separate from catalog inventory. `serve` requires a
versioned deployment profile and exposes only registry records whose catalog
repositories are on that profile's non-blocked allowlist.

The catalog reuses QAppsWiki vocabulary for package roles, hardware targets,
and interfaces. New repositories synchronized from the mirror manifest start
as `planned` with conservative `unknown` metadata and must be curated before
being treated as a supported environment.

Repository source updates are separate from mirror-manifest synchronization.
The update controller resolves configured refs, persists checks, and creates
clean revision-addressed candidate checkouts. It does not run `git pull` inside
images or mutate active capability and runtime pins. The decision and
activation gates are recorded in
[ADR 0011](docs/adr/0011-controlled-repository-updates.md).

`HeteQSys` is currently blocked because its authoritative source URL is unknown.
The FTQC compiler uses `QSCSoftwareThrust/FTQC` as its private QHPC working
mirror while `code.ornl.gov/qsc-ct/ftqc` remains its authoritative internal
upstream.

## Development

Run the contract, registry, engine, API, runtime, Slurm, security, and catalog
checks with:

```bash
pytest
```

The local suite does not claim target-system acceptance. Accepted Apptainer
SIFs, live Slurm and pilot execution, institutional identity, registry policy,
storage and RDMA performance, and security reviews require the target DOE
environment. See
[docs/deployment-readiness.md](docs/deployment-readiness.md).
