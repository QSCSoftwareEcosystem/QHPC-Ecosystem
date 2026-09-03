---
topic_slug: shor-code
title: "Shor Code"
aliases:
  - "9-qubit code"
  - "Shor 9-qubit code"
  - "[[9,1,3]] code"
see_also:
  - steane-code
  - css-codes
  - concatenated-codes
authority_tier: canonical
last_reviewed: 2026-07-10
maintainers:
  - sharmin
---

# Shor Code

The Shor code is the first quantum error-correcting code (Peter Shor, 1995). A
$[[9,1,3]]$ code, it protects one logical qubit against an **arbitrary**
single-qubit error by combining protection against bit flips and phase flips. It
proved that QEC is possible at all, launching the field.

## Construction: concatenation

The Shor code is a concatenation of two classical-style repetition codes (see
[[concatenated-codes]]):

- **Inner (phase-flip) code:** encode $|0\rangle \to |+{+}{+}\rangle$,
  $|1\rangle \to |-{-}{-}\rangle$ across three blocks.
- **Outer (bit-flip) code:** encode each $|\pm\rangle$ into three qubits via the
  repetition code.

The logical states are

$$
|\bar{0}\rangle = \tfrac{1}{2\sqrt 2}(|000\rangle+|111\rangle)^{\otimes 3},\quad
|\bar{1}\rangle = \tfrac{1}{2\sqrt 2}(|000\rangle-|111\rangle)^{\otimes 3}.
$$

## Stabilizers

Eight generators ($n - k = 9 - 1$):

- Six $Z$-type checks $Z_iZ_{i+1}$ within each block of three, detecting bit flips.
- Two $X$-type checks $X_1\cdots X_6$ and $X_4\cdots X_9$ comparing blocks,
  detecting phase flips.

## Why it corrects any single-qubit error

A general single-qubit error is a linear combination of $I, X, Z, XZ$. The
$Z$-checks catch $X$ (and the $X$ part of $Y$); the $X$-checks catch $Z$ (and the
$Z$ part of $Y$). Because QEC only needs to correct a *basis* of errors (a
consequence of the [[knill-laflamme]] conditions), correcting $X$ and $Z$
separately corrects every single-qubit error — the key insight of the Shor code.

## Significance and degeneracy

The Shor code is **degenerate**: different weight-2 $Z$-errors within a block act
identically on the code space. It is a CSS code (see [[css-codes]]) and the
conceptual ancestor of the [[steane-code]] and modern topological codes.

## See also

- [[steane-code]] — a more efficient $[[7,1,3]]$ CSS code
- [[css-codes]] — the construction the Shor code exemplifies
- [[concatenated-codes]] — the concatenation idea behind it
