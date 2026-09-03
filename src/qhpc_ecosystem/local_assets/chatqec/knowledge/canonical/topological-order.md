---
topic_slug: topological-order
title: "Topological Order"
aliases:
  - "topological phase"
  - "topological quantum memory"
see_also:
  - anyons
  - surface-code
  - floquet-codes
authority_tier: canonical
last_reviewed: 2026-07-10
maintainers:
  - sharmin
---

# Topological Order

Topological order is a phase of matter characterized by long-range entanglement,
ground-state degeneracy that depends on the **topology** of the underlying surface,
and [[anyons|anyonic]] excitations — not by any local order parameter. It is the
physics underlying topological QEC codes: a topologically ordered ground space *is*
a quantum code, and its robustness is the physical origin of error correction.

## Degeneracy as code space

On a surface of genus $g$, a topologically ordered system has a ground-state
degeneracy that grows with $g$ (e.g. $4^g$ for the toric-code phase). This
degenerate space is locally indistinguishable — **no local measurement can tell the
ground states apart** — which is exactly what a good quantum code needs: logical
information hidden from local noise. The [[surface-code]] is precisely this phase
realized on a lattice, with logical qubits stored in the topological degeneracy.

## Why it protects information

Because the ground states differ only by global (topologically nontrivial)
operators, any *local* perturbation cannot cause a logical error at low order. A
logical operation requires an [[anyons|anyon]] to traverse a non-contractible loop —
a macroscopic process — which is why the code distance scales with the linear size
of the system. This is the physical restatement of the code's distance.

## Beyond static order

- **Topological entanglement entropy** is the order parameter that detects the
  phase, revealing the constant $-\gamma$ correction to area-law entanglement.
- **[[floquet-codes|Floquet codes]]** generate topologically ordered logical
  information *dynamically*, through a schedule of low-weight measurements, showing
  that topological protection need not come from a static Hamiltonian ground state.

## See also

- [[anyons]] — the excitations of a topologically ordered phase
- [[surface-code]] — topological order realized as a code
- [[floquet-codes]] — dynamically generated topological order
