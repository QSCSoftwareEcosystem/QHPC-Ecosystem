---
topic_slug: anyons
title: "Anyons"
aliases:
  - "anyonic excitations"
  - "non-abelian anyons"
see_also:
  - topological-order
  - surface-code
authority_tier: canonical
last_reviewed: 2026-07-10
maintainers:
  - sharmin
---

# Anyons

Anyons are quasiparticle excitations in two-dimensional systems whose exchange
statistics are neither bosonic nor fermionic. They are the physical language of
[[topological-order]] and topological QEC: in a [[surface-code|surface/toric
code]], syndrome defects behave exactly like abelian anyons, and this picture
explains both how logical information is stored and how it is corrupted.

## Abelian anyons in the toric code

The toric code hosts two types of point excitation:

- **$e$ (electric) charges** — violated $X$-type ("star") stabilizers.
- **$m$ (magnetic) fluxes** — violated $Z$-type ("plaquette") stabilizers.

Braiding an $e$ around an $m$ multiplies the state by $-1$ — nontrivial *mutual
statistics* — while $e$ and $m$ are each bosonic among themselves. A **logical
error** is exactly the process of creating an anyon pair and dragging one member
all the way around a non-contractible loop of the torus before annihilating it.
Decoding is the task of pairing up (annihilating) the observed anyons without
enacting such a loop.

## Non-abelian anyons and topological computation

**Non-abelian** anyons (e.g. Ising anyons, Fibonacci anyons) have a degenerate
fusion space, and *braiding* them applies a unitary that depends only on the
topology of the braid — not on its details. This makes braids intrinsically
fault-tolerant gates, the basis of **topological quantum computation**. Fibonacci
anyons are braiding-universal; Ising anyons (relevant to Majorana platforms) give
only Clifford gates and still need a magic-state supplement.

## Connection to codes

The stabilizer codes with anyonic excitations are the topological codes — surface,
[[color-code|color]], and related models. Their code distance is the length of the
shortest anyon worldline that implements a logical operator, tying the abstract
anyon picture directly to [[nkd-notation|code parameters]].

## See also

- [[topological-order]] — the phase of matter anyons live in
- [[surface-code]] — the code whose syndromes are abelian anyons
