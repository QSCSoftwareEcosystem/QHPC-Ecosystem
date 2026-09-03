---
topic_slug: css-codes
title: "CSS Codes"
aliases:
  - "Calderbank-Shor-Steane codes"
  - "CSS construction"
see_also:
  - stabilizer-formalism
  - surface-code
authority_tier: canonical
last_reviewed: 2026-05-29
maintainers:
  - sharmin
---

# CSS Codes

CSS codes (Calderbank-Shor-Steane, 1996) are stabilizer codes whose generators
can be split into two sets: one consisting purely of $X$-type operators and
one purely of $Z$-type. They are constructed from a pair of classical linear
codes satisfying a duality condition.

## Construction

Let $C_1, C_2$ be classical binary linear codes with $C_2 \subseteq C_1$. The
parity-check matrices $H_1$ (for $C_1$) and $H_2$ (for $C_2^\perp$) define the
stabilizer generators:

- $X$-stabilizers: one $X$ on each non-zero column of $H_2$ — using rows of $H_2$
- $Z$-stabilizers: one $Z$ on each non-zero column of $H_1$ — using rows of $H_1$

The resulting quantum code has parameters $[[n, k, d]]$ where
$k = \dim(C_1) - \dim(C_2)$.

## Why CSS matters

- Bit-flip and phase-flip errors decode *independently*, simplifying decoder design
- Many practical codes are CSS: [[surface-code]], color code, qLDPC codes
- Transversal CNOT works on any CSS code

## Notable CSS codes

| Code | $[[n,k,d]]$ | Construction |
|---|---|---|
| Steane | $[[7,1,3]]$ | $C_1 = C_2^\perp = [7,4]$ Hamming |
| Surface | $[[L^2, 1, L]]$ | toric / planar topological |
| Bivariate bicycle | various | qLDPC family |

## Limitations

Eastin-Knill rules out a universal transversal gate set for any non-trivial
quantum code — including CSS codes. Hence the need for [[magic-state-distillation]].

## See also

- [[stabilizer-formalism]] — the broader algebraic context
- [[surface-code]] — the practical topological CSS code
