# Repository Audit Evidence - 2026-07-11

This record supports ecosystem-curated capability descriptors. Revisions are
pinned in each descriptor.

## OpenQEvo

- The package exposes `list_methods`, `get`, and validated context loading.
- Unit tests cover context, Trotter references, and Qiskit/PennyLane adapters.
- The README explicitly labels native Trotter implementations as placeholders.
- Decision: publish library and context resources; do not claim a production
  scientific execution operation.
- A reproducible wheel was built twice from revision
  `250550a3992bd57c032d4066843c2b03055c4b9d` with source timestamp
  `1781106436`; both builds produced digest
  `sha256:78a572973dcb086e5904c54c1f7c6229ffdb33e883b009b8d3936f6814a8acec`.
- The `list_methods_detail()` API is exposed as a local development operation.
  It discovers project methods and does not execute the placeholder scientific
  implementations.

## DataSchema

- The repository contains hardware survey source material and documentation.
- No executable validator or versioned machine-readable cross-project schema is
  present at the audited revision.
- Decision: publish the survey dataset as a discovered resource.

## QSCSpack

- The repository contains a valid Spack repository index and package recipes.
- Decision: publish the package repository as a contract-valid resource.

## QAppsWiki

- The `qappswiki` package exposes validated `validate`, `build`, `report`,
  `query`, `path`, `explain`, and `cite` commands with an automated test suite.
- Decision: publish the tool and corpus resources. Container execution remains
  unverified.

## Quantum SDK Dashboard

- The repository contains a deterministic ranking engine and a Streamlit
  interface. Live collection requires a GitHub token and network access.
- Decision: publish the ranking library as a contract-valid resource. A future
  operation should accept captured metrics rather than require live network
  access.

## QASMTrans

- Revision `1843c98fa4bac9cf6b88412145b69457e9176124` configured and compiled with
  CMake and AppleClang.
- The documented `bv10.qasm` example transpiled successfully for the supplied
  `ibmq_toronto` topology, producing 117 basis gates.
- A seven-qubit topology correctly failed for the eleven-qubit input, although
  the uncaught exception currently aborts the process.
- Decision: mark the component smoke-tested; publish an executable operation
  only after an immutable image and failure wrapper are verified.
- The isolated CMake runtime builder produced identical native bundle digest
  `sha256:16dd5fe10c63bc1a036dc2ba22eb315d9f6bb8afba738ef5b77fed3862b24ad9`
  across two independent builds. The bundle contains the QASMTrans executable
  and pinned IBM Toronto topology, and the controlled adapter restricts mode
  and backend to the audited values.
- QASMTrans seeds its initial mapping with `std::random_device` and exposes no
  seed option at the audited revision. Runtime and input identity are
  reproducible, while mapped output may vary between runs. QHPC records each
  output checksum and does not claim bit-for-bit result determinism.

## STABSim

- Revision `a0d8d2e2a9fdec9785857104220b8e7f0346c761` advertises QASM, Stim, CPU,
  GPU, and MPI execution and contains the `nwq_qasm` source.
- The checkout has `qasm/CMakeLists.txt` but no top-level `CMakeLists.txt`, so
  the advertised executable was not reproducibly built from the audit checkout.
- Decision: retain discovered status until the build entry point is resolved.
- An ecosystem-owned C++17 build adapter compiled `qasm/nwq_qasm.cpp` without
  modifying scientific source. Two isolated builds produced native bundle
  digest `sha256:be15c1898b50095536f39cba25d4725673b496cb0e525c693a4ab59997d1c8c5`.
- STABSim's metrics path successfully parsed QASMTrans output. Full stabilizer
  execution correctly rejected the IBM `SX` basis gate, so the integrated
  operation is limited to structural metrics and does not claim simulation.
