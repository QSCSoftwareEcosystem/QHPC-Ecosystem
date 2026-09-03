---
topic_slug: real-time-decoding
title: "Real-Time Decoding"
aliases:
  - "online decoding"
  - "decoder latency"
  - "decoding backlog problem"
  - "real-time quantum error correction"
see_also:
  - decoding
  - mwpm-decoder
  - union-find-decoder
  - syndrome-extraction
authority_tier: canonical
last_reviewed: 2026-07-12
maintainers:
  - sharmin
---

# Real-Time Decoding

**Real-time decoding** is the systems requirement that a decoder consume syndrome
data *as fast as the quantum hardware produces it*, with low enough latency to close
the feedback loop before the computation stalls. It is a distinct concern from the
decoding **algorithm** ([[mwpm-decoder|MWPM]], [[union-find-decoder|Union-Find]],
BP-OSD): those decide *how accurately* errors are inferred; real-time decoding is
about *how fast*, and it is often the harder engineering problem.

## The backlog problem

A fault-tolerant computer emits a fresh round of [[syndrome-extraction|syndromes]]
every QEC cycle — on the order of **~1 µs** for superconducting qubits. If the decoder
takes longer than one cycle *on average* to process a round, unprocessed rounds pile
up: the backlog grows without bound and, because logical operations must sometimes
wait on a decoding result, the effective clock rate collapses **exponentially**. The
decoder's throughput must therefore *match or exceed* the syndrome generation rate —
not merely be "fast enough" on a single round.

## Why it is hard

- **Latency vs. accuracy.** The most accurate decoders are often too slow; practical
  systems trade a little accuracy for bounded latency.
- **Feedforward.** Some operations (e.g. non-Clifford gates, T-gate teleportation)
  need a decoding result *before* the next gate, so latency directly gates the logic.
- **Scale.** Latency and bandwidth must hold as the code distance and qubit count
  grow.

## Techniques

- **Windowed / streaming decoding** — decode overlapping time windows so results
  stream out continuously instead of waiting for the whole circuit.
- **Two-stage decoding** — a fast lightweight first pass handles the common case and
  only escalates hard cases to a slower decoder, cutting average latency and bandwidth.
- **Hardware decoders** — FPGA/ASIC implementations (and co-located control systems)
  achieve sub-microsecond rounds, and have been integrated with real hardware to
  demonstrate real-time, repeated error correction.

## See also

- [[decoding]] — the general decoding problem this constrains
- [[mwpm-decoder]], [[union-find-decoder]] — algorithms that must run in budget
- [[syndrome-extraction]] — the source of the data stream being decoded
