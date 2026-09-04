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

## FTQC–IQM flagship showcase

Select **Showcases** in the Workbench to follow one specimen from authored
OpenQASM through the explicit IQM hardware boundary. The page makes the
scientific result, software handoffs, runtime state, and claim boundary visible
before asking a visitor to operate the workflow composer.

Two preparation workflows are runnable when the optional local FTQC runtime
and compatible worker are available:

1. **Prepare one Steane logical qubit for IQM** lowers either the tracked
   `logical0.qasm` or `logical0-H.qasm` input through the pinned FTQC C API,
   expands one logical qubit to seven Steane data-qubit loci, and emits typed
   FTQC MLIR, IQM JSON, and a preparation report.
2. **Prepare a two-device-qubit Bell circuit for IQM** lowers the measured Bell
   fixture directly to two IQM loci. It deliberately makes no Steane-expansion
   claim.

The accepted local smoke produced 58 IQM instructions for `logical0`, 114 for
the four-H logical variant, and 9 for the Bell circuit. Every run preserves the
input and output digests, exact FTQC source revision, preparation mode, circuit
width, instruction count, gate counts, and an explicit record that routing and
submission were not performed. See the
[local preparation evidence](evidence/ftqc-local-iqm-preparation-smoke-2026-09-03.md).

Calibration-aware topology routing and hardware submission remain a separate
credentialed stage. Its `quantum-backend` contract and mock adapter now preserve
the selected device/calibration identity, routed layout, job receipt, raw
counts, and Steane Z-basis logical result while keeping the token inside the
worker. This is interface evidence, not a hardware run; see the
[mock backend acceptance record](evidence/ftqc-iqm-mock-backend-2026-09-04.md).

Promotion of that stage still requires a real qiskit-iqm client, confirmed
site policy, developer-approved hardware packet, and an approved comparison
rule. The earlier
[hardware candidate record](evidence/ftqc-iqm-logical-qubit-candidate-2026-07-29.md)
documents those gaps. Until that packet exists, the showcase does not claim
verified hardware execution, error suppression, or fault-tolerant advantage.

## Beyond executable workflows

Not every ecosystem capability should be represented as an executable workflow
node. QAppsWiki's knowledge graph and ChatQEC support evidence-led exploration
in Knowledge and Assistant. ExaChem, QIRIS, and NWQSim QFlow are visible in the
H6 Compose blueprint while remaining explicitly non-executable until their
runtime and HPC acceptance gates pass. FTQC is executable for credential-free
local IQM preparation; only its routing and hardware stage remains gated.

These are development showcases. Their admitted local and virtual-Slurm
targets demonstrate orchestration and artifact interoperability; they do not
claim production readiness or scientific validation beyond each capability's
published limitations.

The checked-in
[development smoke evidence](evidence/scientific-showcases-smoke-2026-07-29.md)
records one successful end-to-end run of each cross-tool study.
