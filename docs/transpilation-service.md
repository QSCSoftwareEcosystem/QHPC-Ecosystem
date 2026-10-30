# EQO Transpilation Service

## Purpose

The planned EQO Transpilation Service is an artifact-first adapter layer
inspired by XACC's interoperability model. It is not a replacement for XACC's
programming or execution framework. Its job is to carry a circuit from one
declared dialect through a normalized exchange artifact into another declared
dialect, while preserving the evidence needed to assess whether the result is
safe to use.

The service accepts circuit artifacts. It does not execute arbitrary user
Python in order to discover a circuit. A future Qiskit importer must accept a
bounded serialised circuit form or execute in a deliberately isolated
importer.

## Circuit exchange contract

`CircuitExchange` is a versioned EQO contract, validated as
`qhpc/v1`. Its initial schema and valid example are located at:

- `src/qhpc_ecosystem/contracts/circuit-exchange-v1.schema.json`
- `examples/contracts/valid/circuit-exchange.yaml`

The artifact records:

- source dialect and version;
- ordered logical qubits and classical bits;
- symbolic parameters and global phase when represented by the source;
- ordered operations, measurements, and classical targets;
- the adapter name, target dialect/version, and semantic classification; and
- explicit semantic limitations.

An EQO run must retain the source circuit, normalized `CircuitExchange`,
transformed circuit, qubit mapping, and any warning/loss report as immutable
artifacts. This keeps a circuit's transformation chain inspectable in both the
Composer and run receipt.

## Directional adapter registry

Adapters are directional. A reverse arrow is a separate implementation with
its own contract and tests; it is never inferred from a forward converter.

| Direction | Initial gate-model scope | Classification | Status |
| --- | --- | --- | --- |
| OpenQASM 2 → CircuitExchange | named qubits/bits, H/X/Y/Z/S/T, RX/RY/RZ, CX/CZ, measurement | exact for represented statements | contract defined |
| CircuitExchange → Qiskit | same gate subset and symbolic parameters | equivalent after lowering | planned |
| Qiskit serialised circuit → CircuitExchange | bounded, serialised circuit artifact only | depends on gate coverage | planned |
| CircuitExchange → pytket / Quantinuum target | declared native gate subset, explicit routing profile | equivalent after lowering | planned |
| pytket / Quantinuum target → CircuitExchange | bounded circuit artifact with mappings | depends on target metadata | planned |
| OpenQASM 3 → CircuitExchange | static gate-model subset; no timing or pulse semantics | lossy unless limitations are empty | planned |
| CircuitExchange → Cirq | documented gate-model subset | equivalent after lowering | planned |

`exact` means the exchange representation preserves all semantics in scope.
`equivalent-after-lowering` means a declared decomposition or basis rewrite is
used. `lossy` requires a warning artifact describing the dropped semantics.
`unsupported` must fail before an execution artifact is produced.

## Scope controls

The first Qiskit ↔ pytket / Quantinuum connection must record qubit mapping,
implicit swaps, gate decompositions, compiler options, target profile, and
equivalence-test evidence. The OpenQASM 2/3 and Qiskit ↔ Cirq paths require
the same declaration discipline before they are admitted as operations.

Routing, noise models, pulse schedules, calibration data, and provider job
submission are out of scope for an exchange adapter unless a target profile
explicitly declares them. A transpilation result is never evidence that a
hardware target has admitted the circuit; standard EQO execution preflight
continues to own that decision.
