---
topic_slug: bacon-shor-code
title: "Bacon-Shor Code"
aliases:
  - "Bacon-Shor subsystem code"
  - "compass code family"
see_also:
  - subsystem-codes
  - shor-code
  - css-codes
authority_tier: canonical
last_reviewed: 2026-07-10
maintainers:
  - sharmin
---

# Bacon-Shor Code

The Bacon-Shor code (Dave Bacon, 2006) is the subsystem-code version of the
[[shor-code]]. By promoting some stabilizers to **gauge** operators, it reduces
syndrome extraction to simple weight-2 measurements, at the cost of a lower
threshold. It is the prototypical [[subsystem-codes|subsystem code]].

## Layout

Qubits sit on an $m \times m$ square lattice. The code is defined by **gauge
operators**:

- $X$-type gauge operators on horizontally adjacent pairs, $X_{i,j}X_{i,j+1}$.
- $Z$-type gauge operators on vertically adjacent pairs, $Z_{i,j}Z_{i+1,j}$.

The **stabilizers** are products of gauge operators over full rows/columns
(weight-$2m$ operators), and there is one logical qubit. Because the gauge group
is non-abelian, some degrees of freedom (the gauge qubits) carry no information
and need not be protected.

## Why the gauge structure helps

The key practical win: stabilizer values are reconstructed by measuring only
**weight-2 gauge operators** and taking products, instead of measuring
high-weight stabilizers directly. Low-weight, geometrically local measurements
are far easier on hardware and improve fault tolerance of the extraction circuit
(see [[syndrome-extraction]]). The trade-off is a lower threshold than the
surface code and no asymptotic error threshold for the fixed-shape family.

## Compass codes

Interpolating between the Bacon-Shor code and the [[surface-code]] by choosing
which gauge operators to fix gives the **compass code** family, letting one tune
between easy measurement (Bacon-Shor) and high threshold (surface), and to tailor
the code to biased noise.

## See also

- [[subsystem-codes]] — the general gauge-qubit framework
- [[shor-code]] — the stabilizer code Bacon-Shor "gauges"
- [[css-codes]] — the CSS structure underneath
