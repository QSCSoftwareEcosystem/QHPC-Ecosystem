---
topic_slug: leakage
title: "Leakage Errors"
aliases:
  - "leakage reduction"
see_also:
  - crosstalk
  - circuit-level-noise
authority_tier: canonical
last_reviewed: 2026-07-10
maintainers:
  - sharmin
---

# Leakage Errors

Leakage is population escaping the computational $\{|0\rangle, |1\rangle\}$
subspace into higher levels — $|2\rangle$ on a transmon, or other non-qubit states
on ions and atoms. It is especially damaging because most physical qubits are
really multi-level systems, and the standard Pauli/QEC framework assumes a strict
two-level qubit. A leaked qubit violates that assumption entirely.

## Why leakage is worse than a Pauli error

- **It is not a Pauli error.** A leaked qubit is outside the code space, so
  stabilizer measurements return garbage and the [[decoding|decoder]]'s error model
  no longer applies.
- **It persists.** A leaked qubit stays leaked across many rounds, corrupting every
  syndrome it participates in — a long correlated error rather than a one-shot flip.
- **It spreads.** Two-qubit gates involving a leaked qubit can transport the leakage
  or inject correlated errors onto neighbours, closely related to [[crosstalk]].

## Leakage reduction

Because correction assumes qubits stay in the code space, hardware must actively
return leaked population:

- **Leakage-reduction units (LRUs)** — circuits, often using an auxiliary reset or a
  swap to a freshly reset ancilla, that convert leakage back into a
  correctable computational-space error each cycle.
- **Reset of ancillas** every round naturally limits ancilla leakage buildup.
- **Leakage-aware decoding** — flagging suspected leaked qubits (e.g. from anomalous
  syndrome patterns) and soft-informing the decoder.

Without such measures, leakage produces error floors that cap the achievable
logical fidelity even far below threshold, so LRUs are now standard in
[[superconducting-qec]] surface-code experiments and enter realistic
[[circuit-level-noise]] budgets.

## See also

- [[crosstalk]] — a related mechanism that spreads correlated errors
- [[circuit-level-noise]] — where leakage enters the noise budget
