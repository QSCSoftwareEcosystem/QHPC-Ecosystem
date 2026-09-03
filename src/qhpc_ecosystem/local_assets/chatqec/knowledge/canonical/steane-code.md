---
topic_slug: steane-code
title: "Steane Code"
aliases:
  - "[[7,1,3]] code"
  - "7-qubit Steane code"
  - "Hamming-based code"
see_also:
  - css-codes
  - shor-code
  - transversal-gates
  - color-code
authority_tier: canonical
last_reviewed: 2026-07-10
maintainers:
  - sharmin
---

# Steane Code

The Steane code is a $[[7,1,3]]$ CSS code built from the classical $[7,4,3]$
Hamming code (Andrew Steane, 1996). More efficient than the Shor code and endowed
with a transversal Clifford group, it is a standard testbed for fault-tolerant
protocols and the smallest 2D [[color-code]].

## CSS construction from the Hamming code

The Steane code is the CSS code $\mathrm{CSS}(H, H)$ where $H$ is the parity-check
matrix of the $[7,4,3]$ Hamming code. Because the Hamming code contains its own
dual, the same $H$ defines both the $X$-type and $Z$-type stabilizers:

$$
H = \begin{pmatrix}0&0&0&1&1&1&1\\0&1&1&0&0&1&1\\1&0&1&0&1&0&1\end{pmatrix}.
$$

There are three $X$-checks and three $Z$-checks ($n-k = 6$), distance $d = 3$.
This self-dual CSS structure is what gives the Steane code its clean gate set.

## Transversal gates

The Steane code has a **transversal full Clifford group**: logical $H$, $S$, and
CNOT are all implemented by applying the corresponding physical gate qubit-by-qubit
(bitwise), so a single fault stays a single fault (see [[transversal-gates]]).
This makes Clifford operations fault-tolerant "for free." As with all 2D codes,
the non-Clifford $T$ gate is *not* transversal and must be supplied by magic
states.

## Relation to other codes

- More qubit-efficient than the $[[9,1,3]]$ [[shor-code]] for the same distance.
- Equivalent to the smallest 2D triangular [[color-code]].
- Its Steane-style error correction (using an encoded ancilla block) is a
  classic fault-tolerant [[syndrome-extraction]] method.

## See also

- [[css-codes]] — the general construction Steane instantiates
- [[shor-code]] — the earlier, larger single-error-correcting code
- [[color-code]] — the topological family whose smallest member is Steane
- [[transversal-gates]] — the Steane code's fault-tolerant Clifford set
