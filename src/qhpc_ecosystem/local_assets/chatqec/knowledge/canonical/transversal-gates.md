---
topic_slug: transversal-gates
title: "Transversal Gates"
aliases:
  - "transversal logic"
  - "Eastin-Knill"
see_also:
  - clifford-group
  - steane-code
  - reed-muller-codes
  - magic-state-distillation
authority_tier: canonical
last_reviewed: 2026-07-10
maintainers:
  - sharmin
---

# Transversal Gates

A transversal gate applies physical gates **qubit-wise** across code blocks: the
$i$-th physical qubit of one block interacts only with the $i$-th physical qubit
of another (or with nothing else). This structure is the gold standard for
[[fault-tolerance]], because a fault in any single physical gate can produce at
most one error per block and therefore cannot spread into a logical error.

## Why transversality is fault-tolerant

Because there is no coupling *within* a block, an error on one physical qubit
stays on that qubit. A weight-1 physical fault maps to a weight-1 data error, well
below the distance-$d$ correction limit. This is exactly the "one fault → one
error per block" condition of [[fault-tolerance]].

## Examples

- The **[[steane-code]]** ([[7,1,3]]) implements the full logical
  [[clifford-group|Clifford]] group transversally: bit-wise $H$, $S$, and CNOT.
- **CSS codes** built from a self-dual classical code always have transversal
  CNOT; the [[15,1,3]] Reed–Muller code (see [[reed-muller-codes]]) has a
  transversal $T$ gate.
- Any [[css-codes|CSS code]] has transversal CNOT between two blocks.

## The Eastin-Knill barrier

**No** quantum code with a nontrivial distance can implement a **universal** gate
set transversally (Eastin–Knill theorem, 2009). The transversal gates of any code
form a discrete group — you can get the Clifford group but never a continuous or
universal set for free.

This is the fundamental reason FTQC needs an extra ingredient: the non-Clifford
gate must be supplied some other way, most commonly via
[[magic-state-distillation]] and gate teleportation, or by
[[code-deformation|code switching]] between codes with complementary transversal
gates.

## See also

- [[clifford-group]] — the group typically available transversally
- [[steane-code]] — transversal Clifford exemplar
- [[reed-muller-codes]] — transversal $T$, complementary to Steane
- [[magic-state-distillation]] — the standard workaround for Eastin–Knill
