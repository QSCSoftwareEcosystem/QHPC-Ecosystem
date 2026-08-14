# QFlow/QIRIS Incubation Architecture

Status: resource-only incubation  
Registry maturity: prototype  
Executable EQO-QSC operations: none

## Ownership Boundary

```text
EQO-QSC
  admits the workflow, runtime policy, target, provenance, and artifact contracts
        |
        v
ExaChem / QFlow
  owns chemistry state, cycle formation, amplitude snapshots, convergence,
  result acceptance, amplitude updates, and restart checkpoints
        |
        | qflow-taskset@1 (one complete cycle)
        v
QIRIS boundary over IRIS / QIR-EE
  owns task admission, heterogeneous scheduling, backend selection, retries,
  identity preservation, and complete-cycle aggregation
        |
        | one formed-Hamiltonian task
        v
NWQSim QFlow VQE plugin
  owns the selected task solve and returns energy, convergence, parameters or
  amplitudes, ordering, and backend provenance
        |
        | qflow-taskset-result@1 (complete aggregate)
        v
QFlow accepts or rejects the result, applies amplitudes, writes
qflow-cycle-checkpoint@1, and only then forms the next cycle
```

The hard synchronization rule is a cycle barrier. Every task in a task set must
reference the same amplitude snapshot. QIRIS may run those tasks concurrently,
but it must not create the next QFlow cycle and QFlow must not apply a partial
amplitude update.

## Admitted Sources

| Layer | Public base source | Audited revision | Incubation qualification |
| --- | --- | --- | --- |
| ExaChem/QFlow | `https://github.com/ExaChem/exachem` | `0991cb52ce687ccf35ba29f3746a6fb13a13c464` | Task-set export hook is a local, uncommitted qiris-qflow patch |
| IRIS/QIR-EE | `https://github.com/ORNL/iris` | `ff57e620a92fcf62eff3568d9c6eeaaf078f0340` | Runtime substrate is public; the high-level QIRIS task-set service is not claimed as implemented |
| NWQSim | `https://github.com/pnnl/nwq-sim` | `b35763d846e6512ed817d3f88ac8ce79a7e82a7e` | QFlow VQE plugin and adapter are local, uncommitted qiris-qflow patches |

The NWQSim record here uses the main repository and is distinct from EQO-QSC's
existing `NWQ-Sim` record for the `tn_sim` branch.

## Artifact Boundary

- `qhpc.qflow-taskset@1` carries all active-space tasks formed for one cycle.
- `qhpc.qflow-taskset-result@1` carries one terminal result per submitted task
  and the complete-cycle aggregation decision.
- `qhpc.qflow-cycle-checkpoint@1` is the proposed QFlow-owned restart record
  around task-set acceptance and amplitude application.

These contracts are draft ecosystem contracts. The upstream qiris-qflow
schemas remain named `qflow.qiris.*.v1`; the QHPC artifact records wrap those
schemas without changing their ownership semantics.

When a selected backend exposes an OpenQASM quantum kernel, a separate,
optional compilation branch may pass `qhpc.quantum-circuit@1` to FTQC's
contract-valid `import-qasm` interface and produce `qhpc.ftqc-mlir@1`. That
branch is not part of the current H6 evidence because the application-level
NWQSim VQE replay does not emit a circuit artifact and FTQC has no admitted
executable runtime.

## Promotion Gates

The records may appear in Tools and Knowledge, but Compose and Run remain
disabled until all of the following are true:

1. ExaChem export and NWQSim plugin changes have stable, reviewable revisions.
2. The QIRIS adapter performs live submit, wait, backend dispatch, and
   complete-cycle result aggregation over IRIS/QIR-EE.
3. QIR generation and expectation-result conversion are defined and tested.
4. Returned amplitudes are compared with native QFlow update inputs and applied
   to a live ExaChem cycle with restart equivalence.
5. Immutable runtimes pass EQO-QSC local and HPC target acceptance.

See [H6 validation workflow](h6-validation-workflow.md) and the
[incubation evidence](../../docs/evidence/qiris-qflow-incubation-2026-07-29.md).
