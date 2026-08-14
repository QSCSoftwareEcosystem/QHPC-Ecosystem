# OpenQEvo synthesis smoke evidence — 2026-07-29

## Scope

This record covers the local-development OpenQEvo method-context and
Pauli-Hamiltonian circuit-synthesis integration at repository revision
`250550a3992bd57c032d4066843c2b03055c4b9d`. It does not constitute HPC runtime
acceptance, a scalability result, or a production scientific validation.

## Contract and automated checks

- The capability contract admits `list-methods`, `describe-method`, and
  `synthesize-evolution`.
- Full backend test suite: `172 passed`.
- Full Python lint across `src` and `tests`: passed.
- Frontend TypeScript validation: passed.
- Frontend unit tests: `8 passed`.
- Full desktop and mobile Playwright suite: `18 passed`, including the guided
  OpenQEvo Composer path in both projects.

## Real local adapter smoke

The pinned OpenQEvo wheel and the development worker's Qiskit 2.3.0 dependency
processed
`examples/inputs/openqevo-two-qubit-hamiltonian.json`. The adapter produced
OpenQASM 2.0 and reported:

- qubits: 2
- Pauli terms: 3
- circuit depth: 28
- gate counts: `cx=8`, `u2=16`, `u3=20`
- bridge classification: `development`

## Live workflow smoke

The local control API admitted
`openqevo-trotter-synthesis@0.1.0`. Run
`run-45cc857c741f4c71b31dec2116977a40` completed successfully on
`dev-local-worker` and published the `circuit` and `report` outputs.

The Django Workbench exposed the guided path on desktop and mobile with:

- JSON Hamiltonian example loading and upload
- visible OpenQEvo/Qiskit toolchain attribution
- published method, evolution time, Trotter steps, and Suzuki order
- typed circuit and synthesis-report outputs
- an enabled run action once the input was present

## Remaining production gates

- Add a project-reviewed circuit-returning OpenQEvo API.
- Include method context in the distributable OpenQEvo package.
- Pin the full adapter dependency set in an immutable runtime.
- Complete scientific and QHPC acceptance testing.
- Resolve the upstream `TBD` license before OCI redistribution.
