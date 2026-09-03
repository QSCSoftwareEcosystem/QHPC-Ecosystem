---
topic_slug: mwpm-decoder
title: "MWPM Decoder"
aliases:
  - "MWPM"
  - "Edmonds blossom decoder"
  - "PyMatching"
see_also:
  - surface-code
  - decoding
  - union-find-decoder
authority_tier: canonical
last_reviewed: 2026-07-10
maintainers:
  - sharmin
---

# MWPM Decoder

Minimum-weight perfect matching (MWPM) is the workhorse decoder for the
[[surface-code]] and other graphlike codes. It models decoding as a graph problem
and returns the lowest-weight error consistent with the syndrome, achieving
near-optimal accuracy at high speed.

## The matching picture

For codes where every error triggers **at most two** detectors (a "graphlike"
check structure), the syndrome is a set of flipped detectors. Each independent
error corresponds to an edge connecting the two detectors it flips (or a detector
to a boundary). Decoding becomes: pair up the flipped detectors so that the total
weight of the connecting paths is minimized — a **minimum-weight perfect
matching** on the detector graph, solved by Edmonds' blossom algorithm.

Edge weights are set to $-\log p_e$ for each error mechanism's probability $p_e$,
so the minimum-weight matching is the most likely combination of independent
errors (an MLE decoder, see [[decoding]]).

## Space-time decoding

Under [[circuit-level-noise]], detectors live in a $(2{+}1)$-D space-time volume:
horizontal edges are data errors, vertical edges are measurement errors, and
diagonal (hook) edges come from gate faults spreading through the extraction
circuit. MWPM matches over this whole graph, which is why it naturally handles
measurement noise.

## Performance

- **Threshold:** ~1% for the surface code under circuit-level depolarizing noise.
- **Speed:** the sparse blossom variant (PyMatching v2) runs in roughly linear
  time in practice, fast enough for many real-time settings.
- **Tooling:** `PyMatching` is the standard implementation; it pairs directly
  with Stim's detector-error-model output.

## Limitations

MWPM assumes graphlike checks. It is a poor fit for [[qldpc-codes]] and
[[color-code|color codes]], whose stabilizers flip more than two detectors per
error — those need hyperedge decoders like [[bp-osd-decoder]] or specialized
[[color-code-decoders]]. MWPM also ignores error degeneracy, costing a small
amount of accuracy versus true maximum-likelihood decoding.

## See also

- [[surface-code]] — the primary code MWPM decodes
- [[union-find-decoder]] — faster, slightly less accurate alternative
- [[decoding]] — where MWPM sits among decoder families
