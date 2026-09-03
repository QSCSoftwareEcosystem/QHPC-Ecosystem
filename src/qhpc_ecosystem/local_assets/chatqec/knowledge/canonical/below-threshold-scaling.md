---
topic_slug: below-threshold-scaling
title: "Below-Threshold Scaling"
aliases:
  - "exponential error suppression"
  - "Lambda factor"
  - "below threshold"
  - "error suppression factor"
see_also:
  - threshold-theorem
  - surface-code
  - superconducting-qec
authority_tier: canonical
last_reviewed: 2026-07-12
maintainers:
  - sharmin
---

# Below-Threshold Scaling

**Below-threshold scaling** is the empirical hallmark of a working error-correcting
code: once the physical error rate is *below* the code's
[[threshold-theorem|threshold]], the **logical** error rate falls **exponentially** as
the code distance grows. Reaching this regime — adding qubits *reduces* logical error
instead of increasing it — is the experimental proof that error correction is helping
rather than hurting.

## The Lambda ($\Lambda$) factor

For a distance-$d$ [[surface-code|surface code]] the logical error per cycle scales as

$$\varepsilon_L \;\propto\; \Lambda^{-(d+1)/2},$$

where $\Lambda$ is the **error-suppression factor**: the multiplicative reduction in
logical error each time the distance increases by 2 (one more "ring" of qubits). $\Lambda$
is the single most-cited figure of merit for a QEC demonstration:

- $\Lambda > 1$ means the device is genuinely below threshold — bigger codes are better.
- $\Lambda \le 1$ means it is *above* threshold — adding qubits makes things worse, and
  no amount of scaling helps.

## Why it matters

The exponential form is what makes fault tolerance *affordable*: to reach a target
logical error rate you need only a code distance that grows **logarithmically** in the
inverse target error, provided $\Lambda$ is comfortably above 1. A larger $\Lambda$
means fewer physical qubits per logical qubit for the same protection, so pushing
$\Lambda$ up (by lowering physical error rates and improving decoders) is the central
hardware goal.

## Demonstrations

Superconducting surface-code experiments have shown $\Lambda$ crossing above 1 and
logical error dropping with each distance increase (e.g. $d=3 \to 5 \to 7$), the first
clear "below threshold" results (see [[superconducting-qec]]). The same $\Lambda$
framing is used to compare platforms and track progress toward
practical [[fault-tolerance|fault tolerance]].

## See also

- [[threshold-theorem]] — the crossover point this regime sits below
- [[surface-code]] — the code whose distance is being scaled
- [[superconducting-qec]] — where below-threshold scaling was first shown
