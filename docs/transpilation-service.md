# EQO Transpilation Service

## Purpose

The EQO Transpilation Service is an artifact-first adapter layer
inspired by XACC's interoperability model. It is not a replacement for XACC's
programming or execution framework. Its job is to carry a circuit from one
declared dialect through a normalized exchange artifact into another declared
dialect, while preserving the evidence needed to assess whether the result is
safe to use.

The service accepts circuit artifacts. It does not execute arbitrary user
Python in order to discover a circuit. A future Qiskit importer must accept a
bounded serialised circuit form or execute in a deliberately isolated
importer.

The initial bounded adapters are implemented in
`qhpc_ecosystem.circuit_exchange`. They convert one Qiskit QPY binary artifact
or OpenQASM 2/3 text artifact to or from `CircuitExchange`; they do not
evaluate a Python program. The implemented subset is `id`, Pauli gates, H/S/T and
inverses, RX/RY/RZ/P, CX/CZ, SWAP, barrier, and measurement. Control flow,
classically conditioned instructions, custom definitions, and provider
metadata fail closed.

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

The service persists the source circuit reference, normalized
`CircuitExchange`, transformed circuit, qubit mapping, and warning/loss report
as checksum-verified immutable EQO artifacts. This keeps a conversion chain
inspectable now; attaching a selected conversion chain to Composer and run
receipt views remains a separate integration step.

## Conversion API

`POST /api/v1/transpilation/convert` accepts only an existing EQO artifact ID,
a declared source format, and a declared target format. It never accepts or
executes Python source. The initial source formats are `openqasm-2`,
`openqasm-3`, `qiskit-qpy`, and `circuit-exchange`; the initial target formats
are `openqasm-2`, `openqasm-3`, and `qiskit-qpy`.

The source must have a declared EQO circuit artifact type. A successful
conversion returns and persists:

- the unchanged source artifact reference;
- a `qhpc.circuit-exchange@1` normalized artifact;
- a `qhpc.transpiled-circuit@1` transformed artifact; and
- a `qhpc.transpilation-report@1` artifact that links the chain and records
  mapping, classification, adapters, target profile, and warnings.

The report has empty swap/decomposition lists only for the admitted exact
subset; it is not target-compilation or hardware-admission evidence.

## Directional adapter registry

Adapters are directional. A reverse arrow is a separate implementation with
its own contract and tests; it is never inferred from a forward converter.

| Direction | Initial gate-model scope | Classification | Status |
| --- | --- | --- | --- |
| OpenQASM 2 ↔ CircuitExchange | named qubits/bits, declared supported gate subset, measurement | exact within the implemented subset | implemented |
| CircuitExchange → Qiskit QPY | same gate subset and symbolic parameters | exact within the implemented subset | implemented |
| Qiskit QPY ↔ CircuitExchange | bounded QPY artifact and declared gate subset | exact within the implemented subset | implemented |
| Qiskit QPY ↔ CircuitExchange ↔ pytket | static `q`/`c` register circuits, identity qubit mapping, static numeric angles | exact within the implemented subset | implemented |
| CircuitExchange → pytket / Quantinuum target | declared native gate subset, explicit routing profile | equivalent after lowering | planned |
| pytket / Quantinuum target → CircuitExchange | bounded circuit artifact with mappings | depends on target metadata | planned |
| OpenQASM 3 ↔ CircuitExchange | static gate-model subset; no timing, pulse, control-flow, or custom-operation semantics | exact within the implemented subset | implemented |
| Qiskit QPY ↔ CircuitExchange ↔ Cirq | static contiguous `LineQubit` circuits; declared gate subset; `c<number>` measurement keys | exact within the implemented subset | implemented |

`exact` means the exchange representation preserves all semantics in scope.
`equivalent-after-lowering` means a declared decomposition or basis rewrite is
used. `lossy` requires a warning artifact describing the dropped semantics.
`unsupported` must fail before an execution artifact is produced.

## Scope controls

The Cirq adapter deliberately accepts only contiguous zero-based `LineQubit`
indices and single-qubit measurements keyed `c0`, `c1`, and so on. It rejects
named/grid qubits, non-static parameter expressions, non-zero global phase,
barriers, and unrepresented gates instead of inferring a mapping or a loss
report.

The OpenQASM 3 adapter uses Qiskit's `qasm3.loads()` importer and `dumps()`
exporter, with the separately declared `qiskit-qasm3-import` dependency for
the importer. Parsing a larger language does not broaden the EQO subset:
dynamic control, timing, pulse semantics, custom operations, and every
unrepresented instruction fail before an exchange artifact is produced.

The static pytket bridge publishes a structured conversion report with the
logical qubit mapping, implicit-swap list, gate-decomposition list, compiler
options, target profile, and warnings. In the admitted initial subset these are
an identity mapping and empty evidence lists; symbolic parameters, barriers,
multi-register layouts, routing, and target compilation fail closed. A real
Quantinuum target compiler remains separate because a target-specific default
compilation pass needs live device information and can introduce routing and
native-gate lowering that must be captured as distinct evidence.

The OpenQASM and Qiskit ↔ Cirq paths require the same declaration discipline
before they are admitted as operations.

Routing, noise models, pulse schedules, calibration data, and provider job
submission are out of scope for an exchange adapter unless a target profile
explicitly declares them. A transpilation result is never evidence that a
hardware target has admitted the circuit; standard EQO execution preflight
continues to own that decision.
