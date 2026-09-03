---
topic_slug: solovay-kitaev
title: "Solovay-Kitaev Theorem"
aliases:
  - "SK theorem"
  - "gate synthesis"
see_also:
  - clifford-group
  - t-gate-count
authority_tier: canonical
last_reviewed: 2026-07-10
maintainers:
  - sharmin
---

# Solovay-Kitaev Theorem

The Solovay–Kitaev (SK) theorem guarantees that any single-qubit unitary can be
approximated to arbitrary precision using a **finite, discrete** gate set,
efficiently. It is the theoretical foundation of gate synthesis: it explains why a
fault-tolerant machine, which can only run a discrete set like
$\{\text{Clifford}, T\}$, can still implement arbitrary continuous rotations.

## Statement

If a gate set is universal and closed under inverses, then any target unitary $U$
can be approximated to error $\epsilon$ by a sequence of

$$O\!\left(\log^c (1/\epsilon)\right)$$

gates, with $c \approx 3.97$ for the original algorithm. The key point is
**polylogarithmic** scaling: halving the error costs only a constant factor more
gates, so high-precision synthesis is cheap.

## Why it matters for FTQC

A fault-tolerant computer's native operations are the [[clifford-group|Clifford]]
gates (available transversally) plus one non-Clifford gate, usually $T$. Arbitrary
$R_z(\theta)$ rotations from an algorithm must be *compiled* into this discrete
alphabet. SK guarantees this is possible efficiently, and modern
number-theoretic synthesis algorithms (e.g. Ross–Selinger) do far better than the
generic SK bound, achieving near-optimal

$$\sim 3\log_2(1/\epsilon)$$

$T$ gates per rotation.

## Connection to resource counting

Because each synthesized rotation costs a number of $T$ gates growing with
precision, gate synthesis is a primary driver of the [[t-gate-count]] — and hence
the magic-state budget — of a compiled quantum algorithm. Reducing the required
precision, or using catalysis, directly shrinks the resource estimate.

## See also

- [[clifford-group]] — the "free" part of the fault-tolerant gate set
- [[t-gate-count]] — synthesis is a main source of $T$-count
