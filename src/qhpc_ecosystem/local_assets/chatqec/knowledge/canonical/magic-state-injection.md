---
topic_slug: magic-state-injection
title: "Magic State Injection"
aliases:
  - "state injection"
  - "T-state injection"
see_also:
  - magic-state-distillation
  - lattice-surgery
  - transversal-gates
authority_tier: canonical
last_reviewed: 2026-07-10
maintainers:
  - sharmin
---

# Magic State Injection

Magic state injection is how a non-Clifford gate is applied to encoded data. The
[[transversal-gates|Eastin–Knill]] barrier forbids a transversal universal gate
set, so the $T$ gate is instead **teleported** into the computation by consuming a
prepared **magic state** $|T\rangle = |0\rangle + e^{i\pi/4}|1\rangle$.

## Gate teleportation

To apply $T$ to a logical qubit $|\psi\rangle$:

1. Prepare a logical magic state $|T\rangle_L$ (raw, then refined by
   [[magic-state-distillation]]).
2. Measure the joint $Z_L \otimes Z_L$ parity of the data qubit and the magic
   state — on the surface code this is a [[lattice-surgery]] merge.
3. Conditioned on the outcome, apply a Clifford correction ($S$ or identity).

The result is $T|\psi\rangle$ using only Clifford operations plus the consumed
magic state — all of which are fault-tolerant.

## Raw injection

A *raw* (undistilled) magic state is created by injecting a physical single-qubit
$|T\rangle$ into a small code patch and growing the patch to full distance. This
injected state carries the physical error rate, so it is only useful as the input
to a distillation factory, not directly in the algorithm.

## Why it dominates cost

Every non-Clifford gate in an algorithm consumes one distilled magic state, and
distillation factories are large. As a result, the $T$-count (see
[[t-gate-count]]) of a compiled circuit, times the footprint of the distillation
and injection machinery, sets the overall resource budget of fault-tolerant
computing.

## See also

- [[magic-state-distillation]] — produces the high-fidelity states injected here
- [[lattice-surgery]] — realizes the joint measurement on surface codes
- [[transversal-gates]] — the barrier injection circumvents
