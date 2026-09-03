---
topic_slug: bp-osd-decoder
title: "BP+OSD Decoder"
aliases:
  - "belief propagation OSD"
  - "ordered statistics decoding"
see_also:
  - qldpc-codes
  - bivariate-bicycle-codes
authority_tier: canonical
last_reviewed: 2026-07-10
maintainers:
  - sharmin
---

# BP+OSD Decoder

Belief propagation with ordered-statistics decoding (BP+OSD) is the standard
decoder for [[qldpc-codes]] and other codes whose checks are **not** graphlike.
Where MWPM needs each error to flip at most two detectors, BP+OSD handles the
high-weight, overlapping stabilizers of general quantum LDPC codes.

## Belief propagation

BP is the classical message-passing decoder for sparse parity-check codes. It
runs on the Tanner graph (qubits ↔ checks), iteratively passing probability
estimates until it converges on a per-qubit error likelihood. It is fast and
near-optimal for classical LDPC codes.

## Why BP alone fails on quantum codes

Quantum LDPC codes are highly **degenerate**: many distinct errors have the same
syndrome and the same effect. This creates symmetric configurations where BP
oscillates and fails to converge — the "split-belief" / trapping-set problem
unique to the quantum setting.

## The OSD post-processor

When BP does not converge, **ordered-statistics decoding** cleans up: it uses
BP's soft output to rank qubits by reliability, then solves the syndrome equation
exactly on the most-reliable subset of columns (a small Gaussian elimination),
optionally searching low-weight combinations of the remaining columns (OSD-$w$).
This guarantees a valid correction and sharply improves the logical error rate.

## Where it is used

- General [[qldpc-codes]] with high-weight stabilizers.
- [[bivariate-bicycle-codes]] (IBM's "gross code"), where BP+OSD is the reference
  decoder in the demonstrations.
- Any code lacking a matchable structure.

The cost is speed: OSD's linear algebra makes BP+OSD slower and harder to
real-time than [[union-find-decoder|Union-Find]] or MWPM, and reducing its
latency is an active research area.

## See also

- [[qldpc-codes]] — the code family BP+OSD targets
- [[bivariate-bicycle-codes]] — a leading qLDPC family decoded with BP+OSD
