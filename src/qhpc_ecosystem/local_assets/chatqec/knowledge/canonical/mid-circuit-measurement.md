---
topic_slug: mid-circuit-measurement
title: "Mid-Circuit Measurement"
aliases:
  - "mid-circuit readout"
  - "MCM"
  - "in-circuit measurement"
see_also:
  - syndrome-extraction
  - measurement-errors
  - pauli-frame-tracking
authority_tier: canonical
last_reviewed: 2026-07-12
maintainers:
  - sharmin
---

# Mid-Circuit Measurement

**Mid-circuit measurement (MCM)** is measuring a *subset* of qubits partway through a
circuit while the rest continue to hold coherent quantum information. It is a
prerequisite for error correction: every round of
[[syndrome-extraction|syndrome extraction]] measures the ancilla qubits mid-circuit
and *must not* collapse the data qubits.

## Why it is essential

- **Syndrome extraction.** Ancillas are repeatedly measured and reset each QEC cycle;
  the data qubits must survive untouched.
- **Feedforward / adaptive circuits.** The measured outcome conditions later gates —
  needed for T-gate teleportation, [[magic-state-injection|magic-state injection]],
  and repeat-until-success primitives. This ties MCM to real-time decoding: the result
  must arrive in time to steer the next operation.
- **Classical bookkeeping.** Outcomes are tracked in software (see
  [[pauli-frame-tracking]]) so many corrections are applied by relabeling frames rather
  than by physical gates.

## What makes it hard

- **Measurement crosstalk / back-action.** The readout of one qubit can dephase or
  excite its neighbors — a leading error source that MCM-heavy QEC must suppress.
- **Duration.** Measurement is often the *slowest* operation (µs-scale fluorescence
  imaging on atoms/ions, resonator readout on superconductors), so idle data qubits
  accumulate error while ancillas are read.
- **Reset and reuse.** Ancillas must be reset (or fresh qubits supplied) for the next
  round without disturbing the logical state.

## Platform approaches

Trapped ions and neutral atoms often *physically move* the qubits being measured to a
separate readout zone so imaging light does not scatter onto data qubits; neutral-atom
arrays additionally reload lost atoms mid-circuit (see [[neutral-atom-qec]]).
Superconducting devices use dedicated readout resonators with careful frequency
allocation to limit [[measurement-errors|measurement error]] and crosstalk.

## See also

- [[syndrome-extraction]] — the canonical use of mid-circuit measurement
- [[measurement-errors]] — the error channel MCM introduces
- [[pauli-frame-tracking]] — how outcomes are applied in software
