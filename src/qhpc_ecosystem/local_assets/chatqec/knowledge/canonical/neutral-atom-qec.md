---
topic_slug: neutral-atom-qec
title: "Neutral Atom QEC"
aliases:
  - "Rydberg atom QEC"
see_also:
  - qldpc-codes
  - transversal-gates
authority_tier: canonical
last_reviewed: 2026-07-10
maintainers:
  - sharmin
---

# Neutral Atom QEC

Neutral-atom platforms encode qubits in individual atoms (e.g. rubidium or cesium)
held in optical-tweezer arrays, with entangling gates mediated by **Rydberg**
interactions. Their defining QEC advantage is **movable qubits and reconfigurable
connectivity**, which relaxes the locality constraints that dominate solid-state
architectures.

## Why the architecture is distinctive

- **Atom shuttling.** Tweezers physically transport atoms during a computation, so
  any pair of qubits can be brought together to interact. This gives *effectively
  long-range, all-to-all* connectivity — a natural fit for
  [[qldpc-codes|qLDPC codes]], whose non-local checks are prohibitive on a fixed 2D
  grid.
- **Parallel global gates.** A single laser pulse can drive many atoms at once,
  enabling highly parallel — and naturally **transversal** — logical operations
  across code blocks (see [[transversal-gates]]).
- **Large arrays.** Hundreds to thousands of atoms are trapped in one system, with a
  reservoir for replacing lost atoms.

## Demonstrated capabilities

Neutral-atom experiments have realized transversal logical gates across many code
blocks, logical circuits on dozens of logical qubits, and mid-circuit measurement
with atom reloading. The combination of transversal gates and qLDPC-friendly
connectivity makes them a leading route to **low-overhead** fault tolerance.

## Challenges

- **Atom loss** — atoms escape traps and must be detected and reloaded; loss is a
  heralded erasure the architecture must manage.
- **Rydberg gate errors** and finite coherence during shuttling.
- **Measurement** is comparatively slow (fluorescence imaging), complicating fast
  feedback.

## See also

- [[qldpc-codes]] — codes enabled by reconfigurable connectivity
- [[transversal-gates]] — naturally parallel on atom arrays
