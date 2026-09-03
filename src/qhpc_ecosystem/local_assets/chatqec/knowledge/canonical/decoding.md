---
topic_slug: decoding
title: "Decoding (General)"
aliases:
  - "quantum decoder"
  - "syndrome decoding"
see_also:
  - syndrome-extraction
  - mwpm-decoder
  - bp-osd-decoder
  - union-find-decoder
  - threshold-theorem
authority_tier: canonical
last_reviewed: 2026-07-10
maintainers:
  - sharmin
---

# Decoding (General)

Decoding is the classical inference problem at the heart of QEC: given a
syndrome — the pattern of stabilizer violations from [[syndrome-extraction]] —
infer a correction that returns the system to the code space without applying a
logical error. The decoder is what turns raw measurements into a working
logical qubit, and its speed and accuracy set both the [[threshold-theorem|threshold]]
and the real-time latency budget.

## The inference problem

An error $E$ produces syndrome $s = H E$ (over $\mathbb{F}_2$, with $H$ the
parity-check matrix). Many errors share the same syndrome — they differ by a
stabilizer or a logical operator. The decoder must pick a correction $\hat{E}$
with $H\hat{E} = s$ such that $\hat{E}E$ is a **stabilizer** (harmless), not a
**logical** operator (a failure). Two notions of "best":

- **Most likely error (MLE):** return the single most probable $E$ consistent
  with $s$. This is what MWPM and Union-Find approximate.
- **Maximum likelihood (ML) / degenerate decoding:** return the most probable
  *logical class*, summing over all stabilizer-equivalent errors. Optimal but
  generally #P-hard; approximated by tensor-network decoders.

## Accuracy, threshold, and speed

- **Accuracy** determines the [[threshold-theorem|threshold]] $p_{\text{th}}$: a
  better decoder tolerates a higher physical error rate before logical errors
  grow.
- **Speed matters** because syndromes stream out every cycle (~1 µs on
  superconducting hardware). A decoder that cannot keep up causes the
  **backlog problem**, where the reaction time to non-Clifford gates blows up
  exponentially. Real-time decoding is a hard systems constraint, not just an
  accuracy question.

## Decoder families

| Decoder | Best for | Note |
|---------|----------|------|
| [[mwpm-decoder]] | surface code, graphlike checks | fast, near-optimal for matchable codes |
| [[union-find-decoder]] | surface code, real-time | almost-linear time, small accuracy cost |
| [[bp-osd-decoder]] | [[qldpc-codes]] | handles high-weight, non-graphlike checks |
| Tensor-network | small codes, benchmarking | approximates true ML decoding |
| Neural / ML | learned noise, leakage | data-driven, hardware-tailored |

## See also

- [[syndrome-extraction]] — where the syndrome comes from
- [[mwpm-decoder]], [[union-find-decoder]], [[bp-osd-decoder]] — concrete decoders
- [[threshold-theorem]] — decoder accuracy sets the threshold
