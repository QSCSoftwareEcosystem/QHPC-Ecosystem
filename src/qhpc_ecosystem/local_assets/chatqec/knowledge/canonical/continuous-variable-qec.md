---
topic_slug: continuous-variable-qec
title: "Continuous-Variable QEC"
aliases:
  - "CV QEC"
  - "bosonic QEC"
see_also:
  - gkp-codes
  - cat-codes
  - photonic-qec
authority_tier: canonical
last_reviewed: 2026-07-10
maintainers:
  - sharmin
---

# Continuous-Variable QEC

Continuous-variable (CV), or **bosonic**, QEC encodes a logical qubit into the
infinite-dimensional Hilbert space of one or a few harmonic oscillator modes,
rather than into many two-level qubits. A single mode already offers unlimited room
to hide information, so bosonic codes can achieve hardware-efficient protection with
very few physical elements.

## Why use an oscillator

A microwave cavity or optical mode has excellent coherence and a large state space.
The idea is to spread one logical qubit across many photon-number states of a
single mode so that the **dominant** hardware error — photon loss — becomes a
detectable, correctable syndrome. This trades many-qubit overhead for the challenge
of controlling a single complex mode.

## The main code families

- **[[gkp-codes|GKP codes]]** — encode a qubit in a grid of position/momentum
  displacements; small displacement errors are corrected by measuring the state
  modulo the lattice. Excellent against random displacement noise and the leading
  candidate for concatenation with qubit codes.
- **[[cat-codes|Cat codes]]** — encode in superpositions of coherent states; photon
  loss maps between well-separated code words, and the code is naturally
  **[[biased-noise|bias-preserving]]** (exponentially suppressed bit-flips).
- **Binomial and other number-basis codes** — engineered photon-number
  superpositions with exact correctability against a fixed number of loss/gain
  events.

## Concatenation and hardware

Bosonic codes are typically the *inner* code: a GKP or cat qubit provides a
first layer of protection, and many such qubits are then assembled into an outer
[[surface-code]] or [[qldpc-codes|qLDPC]] code. This concatenated approach reaches
fault tolerance with far fewer modes than an all-qubit design. CV encodings are
central to microwave-cavity ([[superconducting-qec]]) and [[photonic-qec|photonic]]
platforms.

## See also

- [[gkp-codes]] — grid-state bosonic encoding
- [[cat-codes]] — coherent-state bosonic encoding
- [[photonic-qec]] — an architecture built on CV/bosonic ideas
