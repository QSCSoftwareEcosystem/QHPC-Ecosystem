---
topic_slug: trapped-ion-qec
title: "Trapped Ion QEC"
aliases:
  - "ion trap QEC"
see_also:
  - color-code
  - transversal-gates
authority_tier: canonical
last_reviewed: 2026-07-10
maintainers:
  - sharmin
---

# Trapped Ion QEC

Trapped-ion platforms encode qubits in the internal electronic states of ions
confined in electromagnetic traps, with gates mediated by shared motional modes.
Their hallmark QEC advantages are **very high gate and measurement fidelity** and
**all-to-all connectivity** within an ion crystal, which together make small,
high-quality logical qubits achievable.

## Why the architecture is distinctive

- **All-to-all coupling.** Within a single trap zone, any pair of ions can be
  entangled through the collective motion, so codes are not restricted to
  nearest-neighbor layouts. This suits codes with non-local checks and enables
  clean [[transversal-gates|transversal]] logic between blocks.
- **Highest fidelities.** Ion two-qubit gates and state readout reach the best
  error rates of any platform, so error correction starts well below threshold per
  operation.
- **QCCD architectures.** Quantum charge-coupled devices shuttle ions between
  storage and interaction zones, scaling beyond a single crystal much as
  atom-array shuttling does.

## The color code on ions

The **[[color-code]]** is a natural match for trapped ions: it has a fully
transversal [[clifford-group|Clifford]] group, and the platform's connectivity and
fidelity let those transversal gates be run directly. Landmark ion demonstrations
have realized fault-tolerant logical qubits and fault-tolerant universal gate sets
in the [[7,1,3]] color (Steane) code, including flag-qubit
[[syndrome-extraction|syndrome extraction]] and real-time correction.

## Challenges

- **Speed.** Gates and especially shuttling/recooling are slower than
  superconducting operations, limiting clock rate.
- **Scaling** to very large ion numbers requires networking many traps
  (photonic interconnects) rather than growing one crystal indefinitely.

## See also

- [[color-code]] — the code well-suited to transversal ion logic
- [[transversal-gates]] — enabled by all-to-all ion connectivity
