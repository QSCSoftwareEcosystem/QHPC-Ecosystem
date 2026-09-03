---
topic_slug: floquet-codes
title: "Floquet Codes"
aliases:
  - "honeycomb code"
  - "Hastings-Haah code"
  - "dynamical codes"
see_also:
  - surface-code
  - subsystem-codes
authority_tier: canonical
last_reviewed: 2026-07-10
maintainers:
  - sharmin
---

# Floquet Codes

Floquet codes (Hastings and Haah, 2021) are **dynamical** codes whose protection
comes from a periodic *schedule of low-weight measurements* rather than a fixed
stabilizer group. The original honeycomb code corrects errors using only weight-2
measurements, a striking advantage for hardware with native two-qubit parity
measurements.

## Measurement-defined logical qubits

In a stabilizer code the logical information lives in a static code space. In a
Floquet code, one measures a rotating sequence of **two-body check operators**
(e.g. $XX$, $YY$, $ZZ$ on the three edge types of a honeycomb lattice) round by
round. The **instantaneous stabilizer group** changes every round, but the
sequence is engineered so that a protected logical qubit persists and its errors
are detectable across rounds. The code is "born" and maintained dynamically.

## Relation to subsystem codes

Floquet codes are closely tied to [[subsystem-codes]]: the honeycomb code can be
viewed as a subsystem code whose gauge checks are measured in a schedule that
keeps promoting different gauge operators to stabilizers. This dynamical gauge
fixing is what lets weight-2 measurements alone protect a logical qubit that no
single round's stabilizers would.

## Why they matter

- **Weight-2 measurements only:** matches native operations on some
  superconducting and Majorana architectures, easing [[syndrome-extraction]].
- **Competitive thresholds:** honeycomb-code thresholds are comparable to the
  [[surface-code]] under circuit-level noise.
- Spawned a wave of "dynamical" and measurement-based code designs (CSS Floquet
  codes, Floquet color codes).

## See also

- [[surface-code]] — the static topological code for comparison
- [[subsystem-codes]] — the gauge framework Floquet codes generalize
