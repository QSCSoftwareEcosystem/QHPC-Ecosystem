---
topic_slug: code-deformation
title: "Code Deformation and Code Switching"
aliases:
  - "gauge fixing"
see_also:
  - lattice-surgery
  - color-code
  - surface-code
authority_tier: canonical
last_reviewed: 2026-07-10
maintainers:
  - sharmin
---

# Code Deformation and Code Switching

Code deformation changes a code *during* a computation by altering which
stabilizers are measured, moving from one code (or one code geometry) to another
without ever leaving fault-tolerant protection. It is the umbrella technique behind
[[lattice-surgery]], boundary movement, and switching between codes with
complementary transversal gates.

## Deforming a code

Because the encoded information lives in the joint $+1$ eigenspace of the
stabilizers, one can slowly *reshape* that space by turning checks on and off. If
each intermediate code still has distance $\ge d$, the logical information is
protected throughout. Growing, shrinking, or moving a [[surface-code]] patch — and
merging/splitting patches in [[lattice-surgery]] — are all code deformations.

## Gauge fixing

In a subsystem code the gauge operators can be *fixed* to definite values,
promoting them to stabilizers. Choosing which gauge operators to fix selects a
particular stabilizer code inside the subsystem code. Gauge fixing is thus a
controlled deformation: it converts one code into another with the same qubits.

## Code switching for universality

The [[transversal-gates|Eastin–Knill]] barrier means no single code has a
transversal universal gate set. **Code switching** sidesteps this by moving between
two codes with *complementary* transversal gates. The canonical example:

- The 2D [[color-code]] has transversal Clifford gates.
- The 3D color code has a transversal $T$ gate but not a transversal Hadamard.

Switching (via gauge fixing) between the 2D and 3D color codes gives access to a
universal set fault-tolerantly, an alternative to
[[magic-state-distillation|magic-state]] injection.

## See also

- [[lattice-surgery]] — the most-used code deformation on surface codes
- [[color-code]] — code switching's flagship example
- [[surface-code]] — patches grown and moved by deformation
