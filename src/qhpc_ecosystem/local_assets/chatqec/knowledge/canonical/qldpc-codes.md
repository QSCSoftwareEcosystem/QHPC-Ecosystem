---
topic_slug: qldpc-codes
title: "Quantum LDPC Codes"
aliases:
  - "qLDPC"
see_also:
  - bivariate-bicycle-codes
  - bp-osd-decoder
  - css-codes
authority_tier: canonical
last_reviewed: 2026-07-10
maintainers:
  - sharmin
---

# Quantum LDPC Codes

Quantum low-density parity-check (qLDPC) codes are stabilizer codes whose checks
are **sparse** — each stabilizer touches $O(1)$ qubits and each qubit is in
$O(1)$ checks — but which, unlike the surface code, can encode many logical
qubits at a **constant rate** with growing distance. They are the leading route
to low-overhead fault tolerance.

## Beyond the topological scaling

The [[surface-code]] is a qLDPC code, but a poor one for overhead: it has $k = 1$
and $d \sim \sqrt{n}$, so protecting many logical qubits costs a factor of
$\sim 10^3$ physical qubits each. General qLDPC codes break this: they keep
checks sparse (hence hardware-friendly extraction) while achieving

$$
k = \Theta(n), \qquad d = \Theta(n),
$$

the "**good**" regime. Constructions of asymptotically good qLDPC codes
(Panteleev–Kalachev and others, 2021–2022) resolved a long-standing open problem,
showing constant rate *and* linear distance are simultaneously achievable.

## The cost: connectivity

Sparse does not mean local. Good qLDPC codes require checks between qubits that
are **not** geometrically nearest-neighbour, so they demand long-range
connectivity — natural for neutral-atom and trapped-ion hardware, harder for
fixed 2D superconducting grids. Balancing rate, distance, and connectivity is the
central engineering trade-off.

## Decoding

qLDPC checks are high-weight and non-graphlike, so matching does not apply;
the standard decoder is [[bp-osd-decoder|BP+OSD]]. All are CSS codes
(see [[css-codes]]) with $X$- and $Z$-type sparse parity checks.

## See also

- [[bivariate-bicycle-codes]] — a hardware-oriented qLDPC family
- [[bp-osd-decoder]] — the standard qLDPC decoder
- [[css-codes]] — the CSS structure qLDPC codes use
