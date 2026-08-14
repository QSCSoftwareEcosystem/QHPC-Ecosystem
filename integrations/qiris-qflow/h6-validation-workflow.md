# H6 Cycle-1 Validation Workflow

Status: non-executable evidence workflow  
Workbench Compose: visible as an incubation blueprint  
Workbench Run action: intentionally disabled

This procedure imports the existing qiris-qflow H6 evidence into EQO-QSC as a
reviewable validation workflow. It is not a QHPC `Workflow` contract because
the three incubation capabilities do not yet publish immutable executable
operations.

## Validation Flow

```text
H6/STO-3G input
  -> native ExaChem QFlow cycle 1 in observe/export mode
  -> validate qflow.qiris.taskset.v1 and shared amplitude snapshot
  -> materialize three formed-Hamiltonian tasks
  -> scheduler-neutral QIRIS contract replay
  -> invoke the native NWQSim plugin once per task
  -> aggregate qflow.qiris.taskset_result.v1 by task identity
  -> compare native/plugin energies and validate complete-cycle acceptance
  -> STOP before live QFlow amplitude application
```

## Fixed Fixture

- Molecule: linear H6, coordinates `0, 2, 4, 6, 8, 10` bohr
- Basis: STO-3G
- QFlow cycles: 1
- Active-space dimensions: `nactive_oa=2`, `nactive_ob=2`,
  `nactive_va=3`, `nactive_vb=3`
- DUCC level: 2
- Task count: 3
- Per-task system: 4 particles on 10 qubits
- Formed-Hamiltonian term counts: 1,695; 3,375; 3,415
- Shared snapshot:
  `h6_qflow_cycle1.sto-3g:cycle-1:dt1dt2-before-cycle`

## Current Results

| Task | Native observe energy | NWQSim plugin energy | Absolute difference |
| --- | ---: | ---: | ---: |
| 1 | -3.173416876000 | -3.173416876226 | 2.262e-10 |
| 2 | -3.200023047000 | -3.200023046772 | 2.282e-10 |
| 3 | -3.217620883000 | -3.217620882509 | 4.911e-10 |

All three comparisons pass the `1e-8` hartree tolerance. Each plugin result
reports convergence and 30 parameters plus 30 excitation-mapped amplitudes.
The aggregate passes the saved QFlow complete-cycle acceptance harness.

## Gate Accounting

Passed:

- real ExaChem H6 cycle-1 observe/export evidence;
- task-set identity and shared-snapshot validation;
- deterministic scheduling and failure-contract tests;
- native NWQSim plugin execution for all three tasks;
- energy, convergence, ordering, and explicit amplitude mapping;
- aggregate complete-cycle acceptance in the file-backed harness.

Not passed:

- live QIRIS service submission over IRIS/QIR-EE;
- QIR generation and expectation-result conversion;
- scheduler admission on an EQO-QSC HPC target;
- comparison against a separately captured native amplitude-update artifact;
- application of the accepted aggregate to live ExaChem QFlow state;
- restart equivalence using `qflow-cycle-checkpoint@1`.

Consequently, this workflow remains evidence only and cannot be submitted from
Compose or Runs. Compose exposes the complete path and its evidence so users
can understand the integration without mistaking it for a published runtime.

## Optional FTQC Circuit-Lowering Branch

FTQC is a useful future branch, but it is not part of the validated H6 cycle
above. The current H6 contract delegates application-level formed-Hamiltonian
VQE tasks and does not publish an OpenQASM circuit artifact.

The branch becomes valid when QIRIS or its selected backend exposes a circuit
kernel:

```text
QIRIS-selected quantum kernel
  -> qhpc.quantum-circuit@1 (OpenQASM 2 or 3)
  -> FTQC import-qasm
  -> qhpc.ftqc-mlir@1
  -> future fault-tolerant lowering and target execution
```

EQO-QSC therefore presents FTQC as optional and pending. It does not claim
that the saved NWQSim VQE evidence emitted circuits, nor that FTQC has an
accepted executable LLVM/MLIR runtime.
