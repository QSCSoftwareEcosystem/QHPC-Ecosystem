# OpenQEvo integration

OpenQEvo supplies quantum time-evolution methods and adapter metadata. EQO-QSC
keeps that scientific concern behind a capability contract, then handles the
artifacts, workflow definition, execution record, and user interface around it.
The integration therefore does not copy OpenQEvo's algorithms into the
orchestrator.

## Available development operations

The pinned `openqevo-library@0.1.0` capability exposes four local-development
operations:

| Operation | Purpose | Output |
| --- | --- | --- |
| `list-methods` | Discover registered OpenQEvo methods | `qhpc.method-catalog@1` |
| `describe-method` | Inspect attributed applicability, limitations, complexity, and references | `qhpc.evolution-method-context@1` |
| `evaluate-dense-reference` | Evaluate a bounded exact, Trotter, qDRIFT, Krylov, interaction-picture, or annealing numerical reference | `qhpc.evolution-result@1` and `qhpc.dense-unitary@1` |
| `synthesize-evolution` | Convert a real-weighted Pauli Hamiltonian to an OpenQASM 2.0 Trotter circuit | `qhpc.quantum-circuit@1` and `qhpc.evolution-synthesis-report@1` |

The synthesis operation accepts `qhpc.pauli-hamiltonian@1` JSON:

```json
{
  "qubits": 2,
  "terms": [
    {"pauli": "ZI", "coefficient": 1.0},
    {"pauli": "IZ", "coefficient": 0.5},
    {"pauli": "XX", "coefficient": 0.25}
  ]
}
```

Each Pauli string must have the declared qubit count. Coefficients are real.
The local adapter accepts 1–32 qubits, 1–256 terms, 1–256 Trotter steps, and
Suzuki order 1, 2, or 4. The product of term count and step count may not exceed
4096.

`evaluate-dense-reference` accepts the same input shape, but is intentionally
limited to eight qubits. It is for numerical comparison and method evaluation:
it returns a structured result plus a NumPy `.npy` unitary. It neither creates
a circuit nor submits quantum hardware work. The source revision is retained
in the result parameters so the reference can be reproduced.

## Use from the Workbench

Start the development stack with:

```bash
eqo dev up
```

Open **Compose** and choose **04 — Hamiltonian to evolution circuit**. Load the
built-in two-qubit example or upload a `.json` Hamiltonian, review the
published evolution time, step count, and Suzuki order, then select **Run
scientific path**. A successful run publishes:

- `circuit`: OpenQASM 2.0 in the `u1`, `u2`, `u3`, and `cx` basis
- `report`: method parameters, source revision, circuit depth, and gate counts

The equivalent workflow is
[`examples/workflows/openqevo-trotter-synthesis.yaml`](../examples/workflows/openqevo-trotter-synthesis.yaml),
with example input in
[`examples/inputs/openqevo-two-qubit-hamiltonian.json`](../examples/inputs/openqevo-two-qubit-hamiltonian.json).

### Compare dense evolution methods

For the newly integrated numerical methods, open **Compose** and choose
**07 — Compare dense evolution methods**. Load the same two-qubit example and
run it to evaluate the default Krylov reference. The run produces an
inspectable evolution-result record and the `.npy` dense unitary.

To compare **exact**, **first- or second-order Trotter**, **qDRIFT**,
**interaction-picture**, or **annealing**, choose
**Open in Advanced**, select the OpenQEvo operation, and change **Dense
reference method**. Method steps apply to Trotter, qDRIFT,
interaction-picture, and annealing; the qDRIFT random seed makes its sampled
trajectory reproducible; Krylov dimension and tolerance apply only to Krylov.
The method is deliberately bounded to eight qubits, so it is suitable for
validation and comparison—not a scalable circuit or hardware execution path.

## Scientific and production boundary

This is deliberately a development integration:

- OpenQEvo remains the named scientific method provider; EQO-QSC owns
  orchestration, validation, provenance, and artifacts.
- The pinned wheel does not package OpenQEvo's `context/` directory, so EQO-QSC
  carries an attributed snapshot from the exact pinned source revision.
- OpenQEvo's current public evolution API returns dense matrices. To produce a
  scalable circuit artifact, the development adapter uses Qiskit's
  `PauliEvolutionGate` and product-formula synthesis while recording OpenQEvo
  and Qiskit provenance in the report.
- Execution is admitted only on `local-development`. This is not an accepted
  HPC runtime or a performance claim.

Production promotion requires a project-reviewed OpenQEvo circuit-returning
API, packaged method context, an immutable adapter dependency set, scientific
acceptance evidence, and explicit source-distribution rights for an OCI image.
