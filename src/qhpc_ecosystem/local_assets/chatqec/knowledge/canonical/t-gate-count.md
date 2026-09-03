---
topic_slug: t-gate-count
title: "T-Gate Count and Non-Clifford Resources"
aliases:
  - "T-count"
  - "magic budget"
see_also:
  - magic-state-distillation
  - solovay-kitaev
authority_tier: canonical
last_reviewed: 2026-07-10
maintainers:
  - sharmin
---

# T-Gate Count and Non-Clifford Resources

The $T$-count of a circuit is the number of non-Clifford ($T$) gates it contains.
It is the single most important cost metric in fault-tolerant quantum computing,
because [[clifford-group|Clifford]] gates are cheap (often transversal and
software-tracked, see [[pauli-frame-tracking]]) while each $T$ gate must be fed a
distilled **magic state**.

## Why Clifford gates are (almost) free

By the Gottesman–Knill theorem, a Clifford-only circuit is classically simulable,
so Cliffords carry no quantum computational "hardness". Fault-tolerantly they are
implemented by transversal gates, [[lattice-surgery]], or frame updates — none of
which need a magic state. The quantum power, and the cost, lives entirely in the
non-Clifford gates.

## Where T-count comes from

- **Direct $T$ gates** in the algorithm.
- **Rotation synthesis.** Arbitrary $R_z(\theta)$ rotations are compiled into
  $\{\text{Clifford}, T\}$; by [[solovay-kitaev|Solovay–Kitaev]] and better
  number-theoretic synthesis, each needs $\sim 3\log_2(1/\epsilon)$ $T$ gates.
- **Toffoli / multi-controlled gates**, each of which decomposes into a handful of
  $T$ gates (a Toffoli costs 7, or 4 with measurement-assisted tricks).

## Why it dominates cost

Each $T$ gate consumes one distilled magic state via [[magic-state-injection]], and
[[magic-state-distillation]] factories are large and slow. Consequently the
$T$-count times the per-state distillation cost typically determines the qubit-count
and runtime of a fault-tolerant algorithm — often more than the logical qubit count
itself.

## Reducing T-count

This makes **$T$-count optimization** a major compilation objective: circuit
rewriting (e.g. via the ZX-calculus), $T$-count-aware synthesis, catalysis, and
choosing $T$-sparse algorithm variants all directly reduce the magic-state budget.

## See also

- [[magic-state-distillation]] — what each $T$ gate consumes
- [[solovay-kitaev]] — synthesis, a primary source of $T$-count
