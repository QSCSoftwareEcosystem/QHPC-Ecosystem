# Operation Runtime Containers

QHPC uses two separate container models:

- shared Apptainer developer environments provide reusable interactive
  toolchains; and
- tool-specific operation images provide narrow, immutable workflow execution.

A developer environment is never promoted directly into production. An
operation image begins from an exact source revision and a validated
`OperationRuntime` contract under `containers/operations/`.

## Runtime States

| State | Meaning |
| --- | --- |
| `build-ready` | Source, recipe, context files, base images, mounts, and smoke fixture are pinned and locally verifiable |
| `oci-smoke-tested` | The constrained operation passed its declared local OCI smoke test; no target acceptance is implied |
| `target-accepted` | A published immutable release, SIF, supply-chain evidence, storage profile, and target tests have passed |

The release remains `unpublished` until an approved registry supplies an
immutable OCI digest. `target-accepted` additionally requires an immutable
Apptainer reference and digest, SBOM, signature, and attestation references.

## Initial Runtime Set

Five operation images have local `oci-smoke-tested` evidence:

| Component | Operation | Local evidence |
| --- | --- | --- |
| QASMTrans | `transpile` | [Build and smoke](evidence/qasmtrans-oci-smoke-2026-07-27.md) |
| STABSim | `analyze-metrics` | [Build and smoke](evidence/stabsim-oci-smoke-2026-07-27.md) |
| NWQEC | `count-clifford-t` | [Build and smoke](evidence/nwqec-oci-smoke-2026-07-27.md) |
| FTPrimitiveBench | `build-memory` | [Build and smoke](evidence/ftprimitivebench-oci-smoke-2026-07-27.md) |
| LightStim | `estimate-logical-error` | [QSC-source rebuild and smoke](evidence/lightstim-oci-update-2026-09-03.md) |

Local build evidence does not grant redistribution rights. STABSim's audited
revision contains no license file, so its image cannot be published until the
project supplies explicit terms. OpenQEvo is not in the table because its
source declares the license as `TBD` and no image was built.

The complete component matrix, including non-executable resources and explicit
containerization blockers, is in
[`containers/operations/README.md`](../containers/operations/README.md).

## Build Flow

QASMTrans is the smallest reference operation runtime:

```bash
eqo operation-runtime verify \
  containers/operations/qasmtrans/runtime.yaml

eqo operation-runtime prepare \
  containers/operations/qasmtrans/runtime.yaml \
  /path/to/qasmtrans \
  --output .qhpc/build/qasmtrans

eqo operation-runtime build-oci \
  containers/operations/qasmtrans/runtime.yaml \
  /path/to/qasmtrans \
  --context .qhpc/build/qasmtrans-build \
  --tag qhpc/qasmtrans:1843c98-linux-amd64

eqo operation-runtime smoke-oci \
  containers/operations/qasmtrans/runtime.yaml \
  --image qhpc/qasmtrans:1843c98-linux-amd64
```

Use `prepare` alone to inspect a context without building. `build-oci` performs
the same preparation itself, so its `--context` path must be new. Preparation
exports the exact Git revision rather than copying a mutable working tree,
verifies the declared source-archive and workspace-file digests, applies the
source commit timestamp, and writes build metadata. `build-oci` pins
`linux/amd64`, disables build-step networking, and suppresses BuildKit's
implicit non-deterministic provenance envelope. Formal release provenance is
produced and signed by the approved supply-chain process.

Python runtimes declare every external wheel as a dependency archive with its
source URL and SHA-256 digest. The acquisition step populates a controlled
cache, and context preparation copies only matching files:

```bash
eqo operation-runtime build-oci \
  containers/operations/ftprimitivebench/runtime.yaml \
  /path/to/FTPrimitiveBench \
  --dependency-cache /approved/wheel-cache \
  --context .qhpc/build/ftprimitivebench \
  --tag qhpc/ftprimitivebench:ba15eba-linux-amd64
```

No package download occurs inside an operation-image build. C++ runtimes use
source contained in the pinned repository archive. NWQEC builds its vendored
GMP and MPFR sources with generic x86-64 code and assembly disabled.

## Apptainer Transition

After the OCI image is published, render the target build command from an
immutable registry reference:

```bash
eqo operation-runtime apptainer-command \
  containers/operations/qasmtrans/runtime.yaml \
  --oci-reference docker://registry.example/qhpc/qasmtrans@sha256:... \
  --output /approved/image-cache/qasmtrans.sif
```

The command is rendered for an approved Linux/Apptainer build host; it is not
executed by a Slurm job. The resulting SIF does not become executable through
the registry until its checksum, signature, supply-chain evidence, storage
profile, native comparison, and target smoke tests are accepted.

## Execution Boundary

Operation images run with:

- a read-only root filesystem and disabled network unless target policy
  explicitly approves otherwise;
- declared read-only input, writable output, and optional scratch mounts;
- no caller-controlled host paths;
- a fixed entrypoint and validated parameters rather than shell text; and
- output collection limited to declared paths.

Input mounts and smoke fixtures are required only for operations with input
ports. Generator operations such as FTPrimitiveBench declare no input bind and
still receive only their writable output boundary.

Site-owned storage profiles map those logical mounts to parallel storage,
node-local scratch, and the artifact store. MPI, RDMA, GPU, and host-library
binds are target-specific policy and cannot be inferred from a local OCI test.
The asynchronous target-worker and activation gates are documented in
[hpc-execution.md](hpc-execution.md).
