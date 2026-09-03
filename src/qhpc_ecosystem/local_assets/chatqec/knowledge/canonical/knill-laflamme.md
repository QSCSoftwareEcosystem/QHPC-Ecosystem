---
topic_slug: knill-laflamme
title: "Knill-Laflamme Conditions"
aliases:
  - "KL conditions"
  - "QEC conditions"
see_also:
  - stabilizer-formalism
  - nkd-notation
  - syndrome-extraction
authority_tier: canonical
last_reviewed: 2026-07-10
maintainers:
  - sharmin
---

# Knill-Laflamme Conditions

The Knill-Laflamme (KL) conditions are the exact, necessary-and-sufficient
criterion for a quantum code to correct a given set of errors. They are the
theoretical foundation of QEC: any code, stabilizer or not, works if and only if
it satisfies them.

## Statement

Let $\{|\psi_i\rangle\}$ be an orthonormal basis for the code space, with
projector $P$ onto that space, and let $\{E_a\}$ be a set of error operators
(a basis for the correctable errors). The code corrects $\{E_a\}$ if and only if

$$
P\, E_a^{\dagger} E_b\, P = C_{ab}\, P
$$

for some Hermitian matrix $C_{ab}$ that is independent of the code state. In
index form,

$$
\langle \psi_i |\, E_a^{\dagger} E_b\, | \psi_j \rangle = C_{ab}\, \delta_{ij}.
$$

## What the two parts mean

- **$\delta_{ij}$ (no distortion within the code space).** Different codewords
  stay distinguishable and are not mixed by the errors — the recovery must not
  depend on *which* logical state was encoded, or it would disturb superpositions.
- **$C_{ab}$ independent of $i,j$.** The environment learns nothing about the
  encoded data: the overlap depends only on which errors occurred, not on the
  logical state. This is the "no information leakage" half.

## Degenerate vs non-degenerate codes

- If $C_{ab}$ is **full rank**, distinct errors take the code space to
  orthogonal subspaces — a **non-degenerate** code, and each error has a distinct
  syndrome.
- If $C_{ab}$ is **rank-deficient**, some distinct errors act identically on the
  code space — a **degenerate** code (e.g. the [[surface-code]]). Degeneracy can
  let a code correct more errors than a naive counting bound suggests.

## Connection to distance and stabilizers

For a stabilizer code, the KL conditions reduce to a statement about the
[[pauli-group]]: a set of Pauli errors is correctable iff for every pair
$E_a^{\dagger} E_b$ either lies in the stabilizer (degenerate case) or
anticommutes with some stabilizer generator (distinct syndromes). A code of
distance $d$ corrects all errors of weight $\le \lfloor (d-1)/2 \rfloor$ because
any product of two such errors has weight $< d$ and therefore cannot be an
undetected logical operator (see [[nkd-notation]]). Syndrome measurement
(see [[syndrome-extraction]]) is the physical realization of distinguishing the
errors the KL conditions guarantee are distinguishable.

## See also

- [[stabilizer-formalism]] — the KL conditions specialized to Pauli errors
- [[nkd-notation]] — why distance $d$ corrects $\lfloor (d-1)/2 \rfloor$ errors
- [[syndrome-extraction]] — measuring which correctable error occurred
