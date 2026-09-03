---
topic_slug: union-find-decoder
title: "Union-Find Decoder"
aliases:
  - "UF decoder"
  - "Delfosse-Nickerson decoder"
see_also:
  - mwpm-decoder
  - surface-code
authority_tier: canonical
last_reviewed: 2026-07-10
maintainers:
  - sharmin
---

# Union-Find Decoder

The Union-Find (UF) decoder, introduced by Delfosse and Nickerson, is an
almost-linear-time decoder for the [[surface-code]]. It trades a small amount of
accuracy for dramatic speed, making it a leading candidate for real-time
decoding on hardware.

## How it works

UF decodes by **growing clusters** of the syndrome graph:

1. Start a cluster around each flipped detector.
2. Grow all odd-parity clusters outward by half-edges until clusters merge.
3. When a cluster becomes even-parity (or touches a boundary), it is
   "**syndrome-valid**" — an error internal to it explains its detectors.
4. **Peel** a spanning forest of each valid cluster to read off a concrete
   correction.

The cluster bookkeeping uses the **union-find** (disjoint-set) data structure,
giving almost-linear $O(n\,\alpha(n))$ runtime, where $\alpha$ is the
inverse-Ackermann function (effectively constant).

## Speed vs accuracy

- **Speed:** the fastest general surface-code decoder in its class; well suited to
  FPGA/ASIC real-time implementation, addressing the decoding-backlog problem.
- **Accuracy:** threshold slightly below [[mwpm-decoder|MWPM]] (~0.5–0.9% vs ~1%
  circuit-level, depending on noise model and weighting). Weighted UF variants
  close much of this gap.

## Relationship to MWPM

UF can be seen as a fast approximation to matching: instead of computing the
globally minimum-weight matching, it greedily grows equal-radius clusters, which
usually — but not always — recovers the same pairing. This is why it is a little
less accurate but far more scalable.

## See also

- [[mwpm-decoder]] — the more accurate, slower matching decoder
- [[surface-code]] — the code UF primarily targets
