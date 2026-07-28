# QHPC-Ecosystem

`QHPC-Ecosystem` is the integration layer for QSC quantum-HPC software. It
combines the repository inventory and reusable Apptainer environments with an
attributed capability registry, persistent workflow engine, controlled runners,
versioned API, and browser workbench. Scientific source repositories remain
independent.

The roadmap and remaining deployment dependencies are tracked in
[PLAN.md](PLAN.md). The target control, execution, data, container, and storage
boundaries are defined in [docs/architecture.md](docs/architecture.md).
Integration contracts, architecture decisions, curator evidence, and DOE
deployment readiness are maintained under [docs/](docs/).

The first deployment uses the explicit allowlist in
[deployments/initial.yaml](deployments/initial.yaml): STABSim, TN-Sim, NWQEC,
FTPrimitiveBench, LightStim, QASMTrans, OpenQEvo, OpenQSE, QAppsWiki, and
ChatQEC. See [docs/initial-deployment.md](docs/initial-deployment.md) for roles,
onboarding state, and production gates. The larger catalog remains available
for future onboarding but is not deployment scope. Each selected component has
a validated record under [integrations/](integrations/), and the initial
pre-container source, contract, adapter, fixture, and integration-test scope is
closed. STABSim, QASMTrans, NWQEC, FTPrimitiveBench, and LightStim now have
reproducible, digest-recorded, locally smoke-tested operation images; see
[docs/operation-runtimes.md](docs/operation-runtimes.md) and the status matrix
in [containers/operations/README.md](containers/operations/README.md).
STABSim image publication remains blocked until its upstream project supplies
explicit license terms.

TN-Sim's pinned public `tn_sim` branch now has a runtime-free CPU MPS operation
contract and fixture-tested controlled CLI adapter. Its iTensor binary has not
yet been built or accepted as a production runtime.

OpenQSE is resolved to the pinned `openQSE/openqse-spec` glossary and
architecture repository and is published only as non-executable documentation
resources.

ChatQEC uses the accepted internal-service design summarized in
[docs/chatqec-service-boundary.md](docs/chatqec-service-boundary.md), with the
formal decision in
[ADR 0008](docs/adr/0008-chatqec-internal-service-boundary.md). The ecosystem
works from the `QSCSoftwareThrust/ChatQEC` GitHub repository; GitLab copies are
secondary mirrors. A versioned provider-neutral HTTPS JSON/SSE contract,
bounded client adapter, fixtures, and tests are implemented. The ChatQEC server
runtime and concrete DOE-approved model, identity, egress, and retention
services remain deployment work.

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
implemented. This verifies the production-shaped lifecycle locally, not the
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
python -m pip install -e ".[dev]"
```

Catalog inspection works without a container runtime or network access:

```bash
qhpc-ecosystem list
qhpc-ecosystem info OpenQEvo
qhpc-ecosystem validate
qhpc-ecosystem sync-manifest --check
qhpc-ecosystem contract list
qhpc-ecosystem contract validate capability examples/contracts/valid/capability.yaml
qhpc-ecosystem contract validate operation-interface integrations/nwqec/interface.yaml
qhpc-ecosystem contract validate operation-runtime containers/operations/qasmtrans/runtime.yaml
qhpc-ecosystem contract validate service-interface integrations/chatqec/service.yaml
qhpc-ecosystem integration validate deployments/initial.yaml
qhpc-ecosystem integration list deployments/initial.yaml
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
qhpc-ecosystem registry build --source /path/to/project-release --output registry.yaml
qhpc-ecosystem registry validate registry.yaml
qhpc-ecosystem registry list registry.yaml
```

See [docs/registry.md](docs/registry.md) for publication rules and contributor
workflow.

Build the verified local OpenQEvo wheel runtime and publish the example
workflow:

```bash
qhpc-ecosystem local-runtime build-wheel ../OpenQEvo \
  --revision 250550a3992bd57c032d4066843c2b03055c4b9d
qhpc-ecosystem workflow publish examples/workflows/openqevo-method-catalog.yaml \
  --registry examples/registry.yaml
```

Start the control plane and worker in separate terminals:

```bash
# Terminal 1
qhpc-ecosystem serve --registry examples/registry.yaml \
  --deployment-profile deployments/initial.yaml

# Terminal 2
qhpc-ecosystem worker --registry examples/registry.yaml \
  --deployment-profile deployments/initial.yaml \
  --runtime-root .qhpc/runtimes
```

The API prints the local Workbench URL. The Workbench queues runs and polls
persistent state while the worker executes admitted tasks. Its current verified
operation calls OpenQEvo's real method registry; it does not execute the
placeholder Trotter implementations. See [docs/worker.md](docs/worker.md) for
the process and admission boundaries.

The verified CT-HW example uses a reproducible native QASMTrans bundle followed
by STABSim's structural-metrics path:

```bash
qhpc-ecosystem local-runtime build-native /path/to/qasmtrans \
  --revision 1843c98fa4bac9cf6b88412145b69457e9176124 \
  --name qasmtrans --target QASMTrans --executable QASMTrans \
  --asset data/devices/ibmq_toronto.json
qhpc-ecosystem local-runtime build-cpp /path/to/STABSim \
  --revision a0d8d2e2a9fdec9785857104220b8e7f0346c761 \
  --name stabsim --executable nwq_qasm \
  --source-file qasm/nwq_qasm.cpp \
  --include-directory include --include-directory qasm
qhpc-ecosystem workflow publish examples/workflows/ct-hw-qasm-analysis.yaml \
  --registry examples/registry.yaml
```

Input files can be registered with
`qhpc-ecosystem artifact register FILE --type qhpc.quantum-circuit@1` or pasted
into the Workbench workflow inspector. The slice performs real transpilation
and circuit analysis. It does not claim STABSim execution of QASMTrans's IBM
`SX` basis, which the audited simulator correctly rejects.

Workflow and run state can also be managed without the browser:

```bash
qhpc-ecosystem workflow validate workflow.yaml --registry registry.yaml
qhpc-ecosystem workflow list
qhpc-ecosystem run-record submit WORKFLOW_ID VERSION
qhpc-ecosystem run-record list
qhpc-ecosystem run-record info RUN_ID
qhpc-ecosystem run-record cancel RUN_ID
qhpc-ecosystem run-record retry RUN_ID NODE_ID
qhpc-ecosystem run-record export RUN_ID --output run-bundle.json
```

On a system with Apptainer, build and enter the environment associated with a
repository:

```bash
qhpc-ecosystem build OpenQEvo
qhpc-ecosystem shell OpenQEvo
qhpc-ecosystem run OpenQEvo -- python3 -m pytest
```

Images are shared by environment class and stored under
`~/.cache/qhpc-ecosystem/images` by default. For example, OpenQEvo and
FTCircuitBench both use `python-lib.sif`; this avoids maintaining one large image
per repository. `--image-dir` changes that location. A cataloged local checkout
is bound at `/workspace`; use `--workspace PATH` to override it.

The shared images above are developer environments. Tool-specific operation
containers use the separate `operation-runtime` commands:

```bash
qhpc-ecosystem operation-runtime verify \
  containers/operations/qasmtrans/runtime.yaml
qhpc-ecosystem operation-runtime build-oci \
  containers/operations/qasmtrans/runtime.yaml /path/to/qasmtrans \
  --context .qhpc/build/qasmtrans --tag qhpc/qasmtrans:1843c98-linux-amd64
qhpc-ecosystem operation-runtime smoke-oci \
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
qhpc-ecosystem slurm-test-cluster prepare \
  infrastructure/test-clusters/slurm-docker-cluster/cluster.yaml \
  --build-ca /approved/path/development-build-ca.pem
qhpc-ecosystem slurm-test-cluster start \
  infrastructure/test-clusters/slurm-docker-cluster/cluster.yaml
qhpc-ecosystem slurm-test-cluster smoke \
  infrastructure/test-clusters/slurm-docker-cluster/cluster.yaml
```

Omit `--build-ca` on development networks that do not intercept TLS.

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

`HeteQSys` is currently blocked because its authoritative source URL is unknown.
The FTQC compiler remains visible with `canonical_status: ambiguous` until the
internal GitLab and public GitHub source decision is resolved.

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
