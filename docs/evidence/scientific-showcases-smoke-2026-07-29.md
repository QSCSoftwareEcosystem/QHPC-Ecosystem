# Scientific showcases smoke evidence — 2026-07-29

## Scope

This record covers the two guided EQO-QSC scientific showcases against the
development control plane and pinned Docker Slurm fixture. It demonstrates
typed orchestration and artifact interoperability; it is not production or
scientific acceptance evidence.

## Evolution circuit readiness

Workflow `showcase-evolution-readiness@0.1.0` completed as
`run-34291124cfcd4d4eb3b23e8fd050652a`.

- OpenQEvo synthesized the two-qubit, three-term Hamiltonian locally.
- QASMTrans, STABSim, and NWQEC ran through the
  `development-slurm-docker` worker.
- Every task completed on its first attempt.
- The run published all five declared outputs: source circuit, synthesis
  report, transpiled circuit, circuit metrics, and Clifford/T counts.

The development result reported a source-circuit depth of 28 with 8 `cx`, 16
`u2`, and 20 `u3` gates. The mapped-circuit analysis reported depth 108, 180
one-qubit gates, and 8 two-qubit gates. NWQEC reported a total T count of 664
under the workflow's checked-in `epsilon=0.01` policy.

## QEC distance study

Workflow `showcase-qec-distance-study@0.1.0` completed as
`run-b6212a1187c94b3bafd0e4076a877d87`.

- Both FTPrimitiveBench circuit branches completed through virtual Slurm.
- Both LightStim estimates completed through virtual Slurm.
- Every task completed on its first attempt.
- The run published both Stim circuits and both logical-error estimates.

With the deliberately bounded 500-shot development configuration, the
distance-three branch observed 2 logical errors and the distance-five branch
observed 0. These values verify data flow and comparison ergonomics only; the
sample size is not a convergence or code-performance claim.

## Browser verification

The Playwright Composer suite passed 12 desktop and mobile checks. It verifies
that Compose shows six runnable examples, presents the four-tool workflow as
mixed-target, exposes the included Hamiltonian, lists all produced artifact
types, enables the run control only after required input is present, and
preserves the focused examples and Advanced composer handoff.
