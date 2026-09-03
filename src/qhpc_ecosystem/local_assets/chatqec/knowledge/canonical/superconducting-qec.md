---
topic_slug: superconducting-qec
title: "Superconducting QEC"
aliases:
  - "transmon QEC"
see_also:
  - surface-code
  - leakage
authority_tier: canonical
last_reviewed: 2026-07-10
maintainers:
  - sharmin
---

# Superconducting QEC

Superconducting-qubit platforms (transmons and related designs) are the most
mature solid-state route to QEC. Qubits are fabricated as lithographic circuits on
a chip with fast microwave gates and fast readout, but with fixed
**nearest-neighbor** connectivity on a 2D grid — a layout that pairs naturally with
the [[surface-code]].

## Why the surface code fits

The surface code needs only local, degree-4, nearest-neighbor stabilizer
measurements on a planar lattice — exactly what a fixed 2D chip of transmons and
couplers provides. This match is why superconducting devices were the first to
demonstrate:

- **Below-threshold** surface-code memory, where increasing the code distance
  *reduces* the logical error rate (Google's $d=3 \to 5 \to 7$ experiments).
- Real-time decoding and repeated stabilizer rounds via
  [[lattice-surgery]]-style planar operations.

Two-qubit logical operations use lattice surgery rather than transversal gates,
because the fixed connectivity forbids the qubit rearrangement that
[[neutral-atom-qec|atom arrays]] enjoy.

## Dominant error sources

- **[[leakage]]** — transmons are weakly anharmonic multi-level systems, so
  population escapes to $|2\rangle$; leakage-reduction units are now standard.
- **Readout error** — measurement is comparatively noisy and is a large term in
  [[circuit-level-noise]] models such as **SI1000**, which is calibrated to
  superconducting timescales.
- **$ZZ$ [[crosstalk]]** between fixed-frequency neighbors, and $T_1/T_2$
  decoherence during idling.

## Overhead outlook

Because the surface code protects only one logical qubit per large patch, the
qubit overhead is high (thousands of physical per logical at useful error rates).
Reducing this — through better gate fidelity, faster cycles, and eventually
[[qldpc-codes|qLDPC codes]] with long-range couplers — is the central scaling
question for the platform.

## See also

- [[surface-code]] — the code matched to 2D transmon connectivity
- [[leakage]] — a defining transmon error mechanism
