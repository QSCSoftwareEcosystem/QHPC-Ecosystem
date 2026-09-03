---
topic_slug: pauli-frame-tracking
title: "Pauli Frame Tracking"
aliases:
  - "Pauli frame"
  - "frame tracking"
see_also:
  - clifford-group
  - syndrome-extraction
authority_tier: canonical
last_reviewed: 2026-07-10
maintainers:
  - sharmin
---

# Pauli Frame Tracking

Pauli frame tracking is the technique of **not physically applying** Pauli
corrections, but instead recording them in classical software and updating the
interpretation of future measurements accordingly. It removes a huge number of
real gates from a fault-tolerant computation, at essentially no cost.

## The idea

When a [[decoding|decoder]] concludes that a logical qubit has picked up, say, an
$X$ error, one option is to physically apply $X$ to fix it. But applying a gate is
itself noisy. Since $X$ is a Pauli, it can instead be *tracked*: remember "there is
a pending $X$ on this qubit" in a classical **Pauli frame** and leave the hardware
untouched. The true logical state is the physical state conjugated by the recorded
frame.

## Why it works: Cliffords commute Paulis

A [[clifford-group|Clifford]] gate $C$ maps a Pauli $P$ to another Pauli $CPC^\dagger$.
So a pending Pauli correction can be *pushed through* any subsequent Clifford gate
by simply rewriting the frame — no physical operation needed. The frame is only
"cashed in" at:

- **Measurements**, where the recorded Pauli tells you whether to classically flip
  the measured bit, and
- **Non-Clifford gates**, where a pending Pauli does not commute trivially and a
  real correction (or an adjusted magic-state protocol) is required.

## Benefits

- Eliminates almost all real correction gates, since Clifford-dominated circuits
  can defer every Pauli to the end.
- Makes [[syndrome-extraction]] and decoding an offline bookkeeping problem — the
  decoder output modifies a frame, not the quantum hardware, relaxing real-time
  latency requirements between rounds.

Pauli frame tracking is standard in every practical FTQC control stack.

## See also

- [[clifford-group]] — why Paulis can be commuted through the circuit
- [[syndrome-extraction]] — produces the corrections that get tracked
