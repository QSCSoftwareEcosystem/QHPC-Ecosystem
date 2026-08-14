# Virtual Slurm Ecosystem Smoke Evidence

- Date: 2026-07-28
- Result: passed
- Scope: supervised development execution
- Target: `development-slurm-docker`

## Coverage

The ecosystem smoke exercised every currently executable OCI-backed operation
through the normal asynchronous worker, real Slurm scheduling, the reviewed
development OCI shim, artifact staging, declared-output collection, and
persisted run provenance:

| Workflow | Operations | Run | Duration |
| --- | --- | --- | ---: |
| `ct-hw-qasm-analysis@0.1.0` | QASMTrans `transpile-qasm`, STABSim `analyze-metrics` | `run-b909ad90b915442088e4b2b37b2c90c5` | 4,945 ms |
| `qec-memory-estimation@0.1.0` | FTPrimitiveBench `build-memory`, LightStim `estimate-logical-error` | `run-bc02feed75324d4baea4ec3df5a6fae9` | 9,489 ms |
| `nwqec-counts@0.1.0` | NWQEC `count-clifford-t` | `run-b88ecc2452034e85ad737740d420b60e` | 1,430 ms |

All three runs reached `succeeded` and persisted their declared artifacts. This
is execution evidence for the five operation images, not only a scheduler-only
smoke.

## Supervision And Readiness

The complete development stack was started with:

```bash
qhpc-ecosystem dev up --port 8094 --no-cluster-start
```

The API reported both required workers as available with current heartbeats:

- `dev-local-worker`: `local-development`, `interactive-local`
- `dev-virtual-slurm-worker`: `development-slurm-docker`, `batch-hpc`

Each worker advertised its accepted immutable runtime digests. The
virtual-Slurm worker process was terminated once after readiness. The
supervisor observed its exit, started a replacement process, and the same
worker identity returned to ready state.

After recovery, `qec-memory-estimation@0.1.0` completed as
`run-baf3357353864145abab823292051b4b` in 8,980 ms. Its scheduler-total stage
durations were 2,181 ms for FTPrimitiveBench and 5,430 ms for LightStim.
The supervised local worker also completed
`openqevo-method-catalog@0.1.0` as
`run-dbfba7c3f0fd445e9e36a8add6c8b827` in 6 ms.

Run admission now checks for a non-stale worker that advertises every required
execution target, execution class, and runtime digest. Interactive API and
Workbench submissions receive an immediate unavailable response when that
condition is not met. Durable offline batch queueing remains an explicit
`queue_if_unavailable: true` choice.

## Regression Verification

The normal local suite passed with 148 tests and one intentional skip. The two
socket-binding API tests also passed when run outside the filesystem sandbox.

## Boundary

This fixture uses real Slurm inside Docker, but development operation jobs use
a constrained shim over the host Docker socket. Possession of that socket is
host-equivalent authority, so the target is restricted to isolated development
data and is not suitable for shared multi-user execution.

This evidence does not validate an accepted Apptainer SIF, a DOE facility Slurm
transport, parallel storage, MPI, RDMA, GPU or GPUDirect behavior, facility
identity, production security controls, representative queue latency, or
representative HPC performance. Those remain separate site-acceptance gates.
