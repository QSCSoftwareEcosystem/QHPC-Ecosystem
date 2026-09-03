---
topic_slug: fault-tolerance
title: "Fault Tolerance"
aliases:
  - "fault-tolerant quantum computation"
  - "FTQC"
see_also:
  - threshold-theorem
  - transversal-gates
  - syndrome-extraction
  - magic-state-distillation
authority_tier: canonical
last_reviewed: 2026-07-10
maintainers:
  - sharmin
---

# Fault Tolerance

Fault-tolerant quantum computation (FTQC) is the design discipline that lets a
noisy device run an arbitrarily long computation with bounded logical error. The
core problem is that error correction is itself built from noisy gates and
measurements — a naive circuit can *spread* one physical fault into many, defeating
the code. Fault tolerance is the set of rules that keeps faults contained.

## The central rule

A protocol is fault-tolerant if a single faulty component causes **at most one
error per code block** (more precisely, no error whose weight exceeds the number
of faults). This prevents a lone gate failure from producing a logical error in a
distance-$d$ code until at least $\lceil d/2 \rceil$ independent faults occur.

Concretely this forbids naive constructions where one bad qubit talks to many
data qubits. It motivates:

- **Transversal gates** (see [[transversal-gates]]), where the $i$-th qubit of one
  block only ever couples to the $i$-th qubit of another, so errors cannot cascade
  within a block.
- **Fault-tolerant [[syndrome-extraction]]**, using cat/flag ancillas or repeated
  measurement so that a single ancilla or measurement fault does not inject a
  high-weight data error or a mis-corrected syndrome.

## Threshold and overhead

The payoff is the **[[threshold-theorem]]**: below a physical error rate
$p_{\text{th}}$, increasing the code distance drives logical error down
exponentially. Above threshold, more qubits make things worse. Realistic surface-code
thresholds sit near $\sim 1\%$ under [[circuit-level-noise]].

The price is overhead — many physical qubits per logical qubit, plus repeated
syndrome rounds in time. Reducing this overhead (better codes like
[[qldpc-codes]], cheaper magic states) is the central engineering thrust of FTQC.

## Universality

A fault-tolerant [[clifford-group|Clifford]] set is not universal. The missing
non-Clifford resource (usually the $T$ gate) is supplied by
[[magic-state-distillation]] and injected into the computation, which typically
dominates the resource budget of a large algorithm.

## See also

- [[threshold-theorem]] — why fault tolerance scales
- [[transversal-gates]] — the cleanest fault-tolerant gate construction
- [[syndrome-extraction]] — must itself be made fault-tolerant
- [[magic-state-distillation]] — supplies fault-tolerant non-Clifford gates
