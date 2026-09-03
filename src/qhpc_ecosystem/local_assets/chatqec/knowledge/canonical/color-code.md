---
topic_slug: color-code
title: "Color Code"
aliases:
  - "2D color code"
  - "triangular color code"
  - "Bombin color code"
see_also:
  - surface-code
  - css-codes
  - transversal-gates
authority_tier: canonical
last_reviewed: 2026-07-10
maintainers:
  - sharmin
---

# Color Code

The color code (Bombín and Martín-Delgado, 2006) is a topological CSS code that
trades a slightly harder decoding problem for a richer transversal gate set. In
2D it has a transversal full Clifford group — something the surface code lacks —
making it attractive for fault-tolerant logic.

## Construction

Qubits sit on the vertices of a trivalent, **3-colorable** lattice (e.g. the
hexagonal lattice); the faces are colored red, green, blue so that adjacent faces
differ. On *every* face there are **two** stabilizers — one $X$-type and one
$Z$-type — supported on the qubits around that face:

$$
B_f^X = \prod_{v \in f} X_v,\qquad B_f^Z = \prod_{v \in f} Z_v.
$$

Placing both check types on the same faces (unlike the surface code's separated
star/plaquette checks) is what enables the transversal gates. The smallest
triangular color code is the $[[7,1,3]]$ [[steane-code]].

## Transversal gates

The 2D color code admits a **transversal full Clifford group** ($H$, $S$, CNOT
all bitwise), and 3D color codes push further to a transversal non-Clifford gate,
enabling code-switching schemes (see [[transversal-gates]] and
[[code-deformation]]). This gate richness is the color code's main advantage over
the [[surface-code]].

## Cost: decoding and overhead

The price is that a single error flips **three** stabilizers, so the syndrome is
not graphlike and plain matching does not apply — decoding needs specialized
[[color-code-decoders]]. Reported thresholds are somewhat below the surface code,
though the gap has narrowed. Connectivity requirements (weight-6 checks on the
hexagonal lattice) are also higher.

## See also

- [[surface-code]] — the topological cousin with easier decoding, weaker gates
- [[css-codes]] — the CSS structure both codes share
- [[transversal-gates]] — the color code's key selling point
