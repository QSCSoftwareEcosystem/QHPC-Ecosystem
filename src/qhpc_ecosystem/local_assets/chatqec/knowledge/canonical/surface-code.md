---
topic_slug: surface-code
title: "Surface Code"
aliases:
  - "toric code"
  - "planar surface code"
  - "Kitaev surface code"
  - "rotated surface code"
see_also:
  - css-codes
  - threshold-theorem
  - stabilizer-formalism
authority_tier: canonical
last_reviewed: 2026-05-29
maintainers:
  - sharmin
---

# Surface Code

The surface code is a topological CSS quantum error-correcting code defined on a
2D square lattice of qubits. It is the leading near-term candidate for
fault-tolerant quantum computation because of its high threshold (~1% under
circuit-level depolarizing noise), its requirement of only nearest-neighbour
2-qubit gates, and its compatibility with planar superconducting and
neutral-atom architectures.

## Construction

Place a data qubit on every edge of an $L \times L$ square lattice. Associate
two types of stabilizers with the lattice:

- **Plaquette (face) stabilizers** $B_p = \prod_{e \in \partial p} Z_e$
- **Vertex (star) stabilizers** $A_v = \prod_{e \ni v} X_e$

All stabilizers commute by construction (each pair shares an even number of
qubits). For a planar code with rough/smooth boundaries, the code encodes
$k = 1$ logical qubit with distance $d = L$.

## Logical operators

A logical $\bar{X}$ is a string of $X$ operators connecting two rough
boundaries; logical $\bar{Z}$ is a string of $Z$ operators connecting two
smooth boundaries. Both have weight $L$.

## Decoding

Bit-flip errors leave $Z$-syndrome on adjacent plaquettes; phase-flip errors
leave $X$-syndrome on adjacent stars. Decoding is the problem of inferring the
most likely error from the syndrome — typically by **minimum-weight perfect
matching** on the syndrome graph (see [[mwpm-decoder]]).

## Why it dominates near-term QEC

- High threshold under realistic noise (~1% for SD6, SI1000)
- Local 2-qubit gates only
- Well-developed lattice-surgery primitives for logical operations
- Mature simulator + decoder ecosystem (Stim, PyMatching)

## See also

- [[css-codes]] — the CSS construction the surface code instantiates
- [[threshold-theorem]] — what "below threshold" actually means
- [[stabilizer-formalism]] — the abstract framework underneath
