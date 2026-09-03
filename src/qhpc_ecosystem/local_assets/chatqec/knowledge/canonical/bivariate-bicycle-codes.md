---
topic_slug: bivariate-bicycle-codes
title: "Bivariate Bicycle Codes"
aliases:
  - "BB codes"
  - "IBM bicycle codes"
  - "gross code"
see_also:
  - qldpc-codes
  - bp-osd-decoder
authority_tier: canonical
last_reviewed: 2026-07-10
maintainers:
  - sharmin
---

# Bivariate Bicycle Codes

Bivariate bicycle (BB) codes are a family of [[qldpc-codes|quantum LDPC codes]]
that IBM highlighted (Bravyi et al., *Nature* 2024) as a near-term, low-overhead
alternative to the surface code. The flagship $[[144,12,12]]$ "**gross code**"
stores 12 logical qubits in 144 data qubits — roughly an order of magnitude better
qubit efficiency than surface-code memory of comparable distance.

## Construction

BB codes are CSS codes built from two polynomials over a cyclic group
$\mathbb{Z}_\ell \times \mathbb{Z}_m$. Let $x$ and $y$ be shift matrices; choose

$$
A = A_1 + A_2 + A_3,\qquad B = B_1 + B_2 + B_3,
$$

each term a monomial $x^i y^j$. The check matrices are $H_X = [A \mid B]$ and
$H_Z = [B^\top \mid A^\top]$. Every qubit is in exactly **six** checks (weight-6
stabilizers) — sparse and uniform.

## Why they are hardware-friendly

- **Constant, useful rate:** the gross code's 12 logical qubits vs the surface
  code's 1 per patch.
- **Low, uniform degree:** weight-6 checks and a qubit degree of 6, laid out on a
  bilayer with mostly short-range plus a few longer "bicycle" connections — a
  connectivity IBM argues is feasible on superconducting hardware.
- **Good distance:** $[[144,12,12]]$ and larger members maintain distance
  competitive with surface-code patches at far lower overhead.

## Decoding

Like other qLDPC codes, BB codes are decoded with [[bp-osd-decoder|BP+OSD]]; the
IBM demonstrations report pseudo-thresholds around $\sim 0.7\%$ under circuit-level
noise, in the surface-code ballpark but with an order-of-magnitude overhead
saving.

## See also

- [[qldpc-codes]] — the broader family BB codes belong to
- [[bp-osd-decoder]] — the decoder used in the demonstrations
