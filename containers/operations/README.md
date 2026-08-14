# Operation Containers

These directories define narrow, component-specific workflow runtimes. They are
separate from the shared developer environments under `containers/`.

## Initial Scope

| Component | Operation image state | Boundary or blocker |
| --- | --- | --- |
| QASMTrans | `oci-smoke-tested` | Transpile QASM for the fixed IBM Toronto target |
| STABSim | `oci-smoke-tested` | Report structural QASM metrics; publication is blocked until the upstream license is explicit |
| NWQEC | `oci-smoke-tested` | Count Clifford and T gates through the portable C++ CLI |
| FTPrimitiveBench | `oci-smoke-tested` | Generate one detector-annotated memory circuit |
| LightStim | `oci-smoke-tested` | Estimate logical error with the CPU PyMatching pipeline |
| TN-Sim | Not build-ready | Pinned iTensor, BLAS/LAPACK, build correction, and source-backed correctness evidence remain required |
| OpenQEvo | Not build-ready | The repository license is `TBD`; redistribution in an OCI image is blocked until licensing is explicit |
| ChatQEC | Not build-ready | A conforming server and institutional identity, model, egress, corpus, and retention services are not selected |
| OpenQSE | Runtime not applicable | Versioned specification and documentation resource |
| QAppsWiki | Runtime not applicable | Versioned knowledge resource |

`oci-smoke-tested` is local evidence only. None of these images is published,
signed, converted to an accepted SIF, or approved for a DOE execution target.

## Offline Build Inputs

Every runtime manifest pins:

- the Git revision, archive digest, and source commit timestamp;
- the recipe, wrapper, fixture, and base-image digests;
- the fixed entrypoint, typed parameters, mounts, and output paths; and
- any external dependency archive by filename, source URL, and SHA-256 digest.

Python dependency wheels are acquired into a controlled cache before the image
build. They are not stored in this repository. Context preparation verifies the
cache against the manifest, and Docker build steps run with networking
disabled:

```bash
eqo operation-runtime build-oci \
  containers/operations/ftprimitivebench/runtime.yaml \
  /path/to/FTPrimitiveBench \
  --dependency-cache /approved/wheel-cache \
  --context .qhpc/build/ftprimitivebench \
  --tag qhpc/ftprimitivebench:ba15eba-linux-amd64
```

The release pipeline must download only the manifest-declared archives, retain
the acquisition record, and fail closed on any checksum mismatch.

## Acceptance Sequence

1. Verify and build the exact context.
2. Run the constrained local OCI smoke test.
3. Rebuild without cache and compare the platform manifest and config digests.
4. Publish to an approved registry by immutable digest.
5. Generate the required SBOM, scan, signature, and attestation.
6. Convert the immutable OCI release to SIF on an approved host.
7. Activate a site-owned storage and execution-target profile.
8. Run correctness, security, storage, latency, and performance acceptance on
   the target.

The evidence under `docs/evidence/` stops after step 3.
