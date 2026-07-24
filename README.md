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
onboarding state, and unresolved source or service decisions. The larger
catalog remains available for future onboarding but is not deployment scope.
Each selected component has a validated record under [integrations/](integrations/)
so source review, interface contracts, adapters, fixtures, and integration tests
can proceed before production container work begins.

TN-Sim's pinned public `tn_sim` branch now has a runtime-free CPU MPS operation
contract and fixture-tested controlled CLI adapter. Its iTensor binary has not
yet been built or accepted as a production runtime.

ChatQEC uses the accepted internal-service design summarized in
[docs/chatqec-service-boundary.md](docs/chatqec-service-boundary.md), with the
formal decision in
[ADR 0008](docs/adr/0008-chatqec-internal-service-boundary.md). The ecosystem
works from the `QSCSoftwareThrust/ChatQEC` GitHub repository; GitLab copies are
secondary mirrors.

The responsibilities are intentionally separate:

- `ProjectManagement/gitlab-mirror` defines where source repositories live.
- `QHPC-Ecosystem` defines how those repositories are built and run.
- `QAppsWiki` describes packages, interfaces, workflows, and provenance.
- `spack-packages` owns package-level HPC integration as components mature.

The project remains one modular monorepo while it has one primary maintainer.
The target deployment separates the API control plane, task-executing workers,
and browser Workbench. The local API and worker now run as separate processes
over persistent SQLite task leases. This verifies the process boundary, not the
production PostgreSQL, multi-host worker, or asynchronous target architecture.

For short approved operations, a target may maintain workers inside a warm,
site-governed Slurm pilot allocation. Policy selects between local interactive,
warm-pilot, ordinary batch, and backend-specific execution; unavailable warm
capacity falls back to batch when permitted. Each attempt will expose separate
authorization, dispatch, scheduler, image, input, execution, collection, and
finalization latency instead of treating all delay as scientific runtime.

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
qhpc-ecosystem integration validate deployments/initial.yaml
qhpc-ecosystem integration list deployments/initial.yaml
```

Integration scaffolds and operation interfaces deliberately contain no
executable command or runtime digest. They are the pre-runtime onboarding
layer. After a component's source, contract, adapter, fixtures, and tests
stabilize, its tool-specific production image is built and accepted. The
executable capability is then published with that immutable runtime digest.

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

The current OpenQEvo wheel and QASMTrans/STABSim Darwin native bundles are local
runtime evidence, not production containers. Production images must be built,
verified, and accepted on the target system after integration contracts and
adapters stabilize.

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

The local suite does not claim target-system acceptance. Tool-specific
Apptainer builds, asynchronous Slurm execution, institutional identity,
registry policy, storage and RDMA performance, and security reviews require the
target DOE environment. See
[docs/deployment-readiness.md](docs/deployment-readiness.md).
