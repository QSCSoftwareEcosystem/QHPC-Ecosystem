# Scientific Showcases

The EQO-QSC showcase suite demonstrates why the ecosystem is useful: it joins
independently developed quantum software through typed artifacts, preserves
provenance at every handoff, and dispatches each operation to its admitted
local or QHPC development target.

## Evolution circuit readiness

**Question:** What does a Hamiltonian-derived evolution circuit look like after
hardware mapping, and what are its structural and fault-tolerant resource
characteristics?

The `showcase-evolution-readiness` workflow starts from a real-weighted Pauli
Hamiltonian and runs:

1. **OpenQEvo** synthesizes a Suzuki-Trotter OpenQASM circuit and records the
   method parameters.
2. The source circuit fans out to two analyses.
3. **QASMTrans** maps one branch to the audited IBM Toronto topology.
4. **STABSim** measures the mapped circuit's structural metrics.
5. **NWQEC** counts Clifford and T resources in the source evolution circuit.

One run produces the source circuit, synthesis report, transpiled circuit,
circuit metrics, and Clifford/T counts. Open Compose, choose **Evolution to
hardware readiness**, load the included two-qubit Hamiltonian, and select
**Run workflow**.

Sources:

- Workflow: [`examples/workflows/showcase-evolution-readiness.yaml`](../examples/workflows/showcase-evolution-readiness.yaml)
- Input: [`examples/inputs/openqevo-two-qubit-hamiltonian.json`](../examples/inputs/openqevo-two-qubit-hamiltonian.json)

## QEC distance study

**Question:** With the same physical error model, how do distance-three and
distance-five surface-code memory experiments compare?

The `showcase-qec-distance-study` workflow creates two independent experiment
branches. **FTPrimitiveBench** constructs each detector-annotated memory circuit
and **LightStim** samples and decodes it. One run preserves both Stim circuits
and both logical-error estimates so the researcher can compare them from the
same provenance record.

Open Compose, choose **Compare QEC memory protection**, review the two branches,
and select **Run workflow**. The checked-in sampling limits are intentionally
small enough for a development demonstration; they are not a scientific
convergence claim.

Source:

- Workflow: [`examples/workflows/showcase-qec-distance-study.yaml`](../examples/workflows/showcase-qec-distance-study.yaml)

## Focused examples

The guided composer also keeps smaller examples for learning one boundary at a
time:

| Example | Tools | Result |
| --- | --- | --- |
| Circuit transformation and metrics | QASMTrans + STABSim | Mapped OpenQASM and circuit metrics |
| Fault-tolerant memory estimate | FTPrimitiveBench + LightStim | Stim circuit and logical-error estimate |
| Clifford and T resource count | NWQEC | Exact gate-count report |
| Hamiltonian to evolution circuit | OpenQEvo | OpenQASM circuit and synthesis report |

## H6 QFlow chemistry-cycle blueprint

Compose also exposes **H6 QFlow chemistry cycle** as a non-executable
incubation blueprint. It makes the most complete heterogeneous story visible:

1. ExaChem/QFlow exports three formed-Hamiltonian tasks from one H6/STO-3G
   amplitude snapshot.
2. The QIRIS boundary over IRIS/QIR-EE preserves identity and schedules the
   task set.
3. The NWQSim VQE plugin solves all three tasks and returns energies,
   convergence, ordering, parameters, and amplitude mappings.
4. QFlow validates the complete aggregate before any amplitude update.
5. An optional future FTQC branch can import OpenQASM and emit FTQC MLIR after
   a selected backend exposes a circuit kernel.

The blueprint shows the saved three-task energy comparison and the remaining
runtime gates. It deliberately has no Run action: live QIRIS submission,
circuit emission, QFlow amplitude application, restart equivalence, and the
FTQC LLVM/MLIR runtime are not yet accepted.

## FTQC logical-qubit IQM blueprint

Compose exposes **One logical qubit on IQM** as a dedicated non-executable
hardware-evidence blueprint. It makes the reported FTQC path inspectable
without presenting the result as verified:

1. Load the tracked one-logical-qubit OpenQASM 3 fixtures.
2. Lower the circuit to logical FTQC MLIR.
3. Expand the logical qubit with the Steane `[[7,1,3]]` code.
4. Lower to IQM-native JSON and route against the tracked topology.
5. Submit 512 shots to the ORNL IQM backend.
6. Recover raw and syndrome-corrected logical outcomes.

The first four stages are source-backed. Hardware submission is
developer-reported, and the result stage remains pending because no job
receipt, confirmed device identity, routed layout, raw counts, or corrected
logical histogram is preserved in the repository.

The blueprint therefore keeps **Run unavailable** and shows the exact evidence
packet required for promotion. It also states that running an encoded circuit
does not by itself demonstrate error suppression or fault-tolerant
performance. The supporting record is
[`docs/evidence/ftqc-iqm-logical-qubit-candidate-2026-07-29.md`](evidence/ftqc-iqm-logical-qubit-candidate-2026-07-29.md).

## Beyond executable workflows

Not every ecosystem capability should be represented as an executable workflow
node. QAppsWiki's knowledge graph and ChatQEC support evidence-led exploration
in Knowledge and Assistant. ExaChem, QIRIS, NWQSim QFlow, and FTQC are visible
in the H6 Compose blueprint while remaining explicitly non-executable until
their runtime and HPC acceptance gates pass.

These are development showcases. Their admitted local and virtual-Slurm
targets demonstrate orchestration and artifact interoperability; they do not
claim production readiness or scientific validation beyond each capability's
published limitations.

The checked-in
[development smoke evidence](evidence/scientific-showcases-smoke-2026-07-29.md)
records one successful end-to-end run of each cross-tool study.
