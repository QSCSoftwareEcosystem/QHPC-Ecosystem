# TN-Sim Source And Interface Audit - 2026-07-24

This record defines the first QHPC integration boundary for TN-Sim before
production containerization. It records source evidence and a controlled
adapter contract. It does not claim project review, a verified source build,
HPC target acceptance, or production runtime readiness.

## Source Identity

- Canonical source: `https://github.com/pnnl/NWQ-Sim`
- Branch: `tn_sim`
- Exact revision: `0f15b60012ccc62e2c9f71ceb2c411ad07d3b13b`
- Remote verification: the public branch head resolved to the exact revision
  above on 2026-07-24.
- Visibility and mirror decision: public upstream; no QSC mirror is required.
- License: MIT.
- Release identity: the repository README labels NWQSim as version 2.0, while
  the branch's top-level CMake project declares 0.0.1. TN-Sim does not publish
  a separate release version, so QHPC pins the exact source revision.

The audit inspected the TN-Sim manual, QASM executable, command-line parser,
backend manager, QASM execution and count formatting paths, CPU iTensor MPS
implementation, TAMM implementation, and CMake configuration at the pinned
revision.

## Selected Initial Operation

The source documents the following CPU tensor-network invocation:

```text
nwq_qasm --qasm_file CIRCUIT.QASM --backend CPU --sim tn
```

The QASM frontend accepts OpenQASM 2.0 files, always performs final shot
sampling, and prints one binary outcome and integer count per line. The
command-line parser exposes `shots`, `max_dim`, `sv_cutoff`, and `random_seed`.
The CPU backend selects `TN_ITENSOR` when iTensor support is built.

The first QHPC operation is therefore `simulate-mps`:

- input: one `qhpc.quantum-circuit@1` OpenQASM 2.0 artifact;
- fixed implementation path: backend `CPU`, simulation method `tn`;
- parameters: shots, maximum bond dimension, singular-value cutoff, and an
  explicit random seed;
- output: one `qhpc.measurement-counts@1` JSON artifact; and
- behavior: seeded rather than deterministic, because the operation samples
  measurement outcomes.

TAMM CPU and GPU backends are outside this initial operation. They require
separate MPI, accelerator, scaling, correctness, storage, and target evidence
and will not be selected indirectly through a user parameter.

## Controlled Adapter Boundary

The ecosystem adapter:

1. accepts only an existing executable and OpenQASM 2.0 file;
2. validates and bounds every published parameter;
3. rejects unknown parameters;
4. constructs an argument vector without a shell;
5. fixes the backend and simulation method to the audited values;
6. requires a successful process exit;
7. parses only the documented measurement-count section;
8. verifies that the reported and summed counts equal the requested shots; and
9. emits data matching `qhpc.measurement-counts@1`.

The Bell-state QASM and representative stdout fixtures under
`integrations/tn-sim/fixtures/` exercise command construction and result
parsing. The stdout fixture follows the pinned `print_counts()` implementation;
it is not represented as output captured from a production TN-Sim binary.

## Build And Runtime Findings

- The CPU MPS path requires C++17, BLAS/LAPACK, and an external iTensor source
  and static library at the location expected by the branch's CMake logic.
- The TN-Sim manual still refers to a differently named development branch in
  parts of its clone instructions, so the exact QHPC source pin must remain
  authoritative.
- The top-level build contains site-specific assumptions, including a
  hard-coded Cray LibSci location, and requires a reproducible overlay or
  upstream corrections before it is a portable production recipe.
- The TAMM path adds MPI, Global Arrays, HDF5, accelerator, and tensor-library
  dependencies and is documented as functionally correct but not performance
  complete.
- The source tree was audited, but the iTensor or TAMM binary was not built or
  executed in this integration workspace.

Before registry publication, QHPC must build the exact revision with pinned
dependencies, execute the fixture and larger representative circuits, verify
seeded repeatability and result equivalence, produce the required supply-chain
evidence, and accept the immutable Linux runtime on the target system.
