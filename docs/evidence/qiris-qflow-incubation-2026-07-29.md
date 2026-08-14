# QFlow/QIRIS Incubation Evidence — 2026-07-29

## Decision

EQO-QSC admits three resource-only prototype records:

- ExaChem/QFlow as chemistry-cycle and amplitude-state owner;
- QIRIS over the public IRIS/QIR-EE runtime as the proposed orchestration layer;
- the main-branch NWQSim QFlow VQE plugin as one proposed execution backend.

No executable capability operation or QHPC workflow is published by this
incubation change.

## Read-Only Source Audit

The sibling `qiris-qflow` workspace was inspected without modification.

| Source | Public base revision | Local state relevant to admission |
| --- | --- | --- |
| ExaChem | `0991cb52ce687ccf35ba29f3746a6fb13a13c464` | QFlow task-set export hook is an uncommitted local patch |
| IRIS/QIR-EE | `ff57e620a92fcf62eff3568d9c6eeaaf078f0340` | Clean public v3.0.1 source; no claim of a completed high-level QIRIS VQE service |
| NWQSim | `b35763d846e6512ed817d3f88ac8ce79a7e82a7e` | QFlow plugin and adapter are uncommitted local patches |

Licenses observed in the source trees are Apache-2.0 for ExaChem, BSD-3-Clause
for IRIS, and MIT for NWQSim. ExaChem also records notices for derived files;
runtime redistribution still requires the normal package review.

## Contract Regression

The QHPC Python environment ran the focused qiris-qflow contract and CLI suites:

```text
../QHPC-Ecosystem/.venv/bin/python -m pytest -q \
  tests/test_qflow_qiris_contract.py tests/test_qiris_qflow_cli.py
```

Result: 24 tests passed.

The suites cover task-set identity, shared amplitude snapshots, plugin request
materialization, result aggregation, QFlow acceptance, and rejection of
missing, duplicate, unknown, failed, stale-snapshot, identity-mismatched, and
malformed successful results.

## Imported H6 Evidence

The saved `qiris-qflow/validation/h6-cycle1` evidence reports:

- one real ExaChem H6 DUCC/QFlow cycle with three active-space tasks;
- 1,695, 3,375, and 3,415 formed-Hamiltonian terms;
- four particles on ten qubits for each task;
- one shared cycle-start amplitude snapshot;
- converged NWQSim plugin results with 30 parameters and 30 mapped amplitudes
  per task;
- native/plugin absolute energy differences of `2.262e-10`, `2.282e-10`, and
  `4.911e-10` hartree.

Evidence identities from the inspected sibling workspace:

| Artifact | SHA-256 |
| --- | --- |
| H6 input | `e6322433946c191f4cc52a4ffb1cea29e422a0362c73825b31e957c1b1a8c126` |
| QFlow task-set manifest | `9127b9521bba529d4badda73684a75014bd35e110732bb08790bbd53c191b4c9` |
| NWQSim task-set result | `e365153db6541be16d6dc4678a1d789c21939e4a99eef157c508d8b9a2804a6c` |
| H6 validation report | `f805a9eb0785bb6ba42ee2b12d75b568c2ff7603b6711cc12e66d88dc44b0a4d` |

The full payloads remain in the qiris-qflow validation workspace; EQO-QSC
imports their digest-qualified result summary rather than duplicating
megabyte-scale formed-Hamiltonian fixtures.

## Current Runtime State and Remaining Gates

The current qiris-qflow doctor check finds compilers and MPI, but the prior
temporary TAMM, ExaChem, and NWQSim plugin binaries are no longer present.
Therefore this admission relies on the saved, digest-qualified H6 evidence and
fresh contract tests; it is not a fresh native rebuild.

The evidence does not establish live QIRIS submission, QIR generation,
expectation-result conversion, native amplitude-update equivalence, application
to live ExaChem state, restart equivalence, or immutable QHPC runtime
acceptance. These remain explicit blockers in the three integration scaffolds.
