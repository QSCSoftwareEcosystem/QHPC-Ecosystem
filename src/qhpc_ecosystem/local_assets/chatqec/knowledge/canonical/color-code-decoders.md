---
topic_slug: color-code-decoders
title: "Color Code Decoders"
aliases:
  - "restriction decoder"
  - "projection decoder"
see_also:
  - color-code
  - mwpm-decoder
authority_tier: canonical
last_reviewed: 2026-07-10
maintainers:
  - sharmin
---

# Color Code Decoders

Decoding the [[color-code]] is harder than decoding the surface code because its
syndromes are not graphlike: a single error flips **three** stabilizers (one per
color around a vertex), so plain [[mwpm-decoder|matching]] does not directly
apply. A family of specialized decoders works around this.

## Why the color code resists matching

In the surface code, each error anticommutes with at most two detectors, giving
a clean matching graph. In the color code, the three-colorable lattice means a
point-like error creates a **hyperedge** touching three same-type stabilizers.
Matching needs edges, not hyperedges, so the syndrome must first be reshaped.

## Decoder strategies

- **Restriction decoder** (Chamberland et al.): restrict the syndrome to pairs of
  colors, run matching on each restricted graph, then lift the partial matchings
  back to a color-code correction. Near-optimal and relatively simple.
- **Projection decoder** (Delfosse): project the color code onto surface codes,
  decode each with MWPM, and recombine.
- **Union-Find / concatenated variants:** adapt cluster growth to the
  three-color structure for faster, real-time decoding.
- **BP+OSD:** treat the color code as a general [[qldpc-codes|LDPC code]] and use
  [[bp-osd-decoder]] directly — flexible but slower.

## Status

Color-code decoders now reach thresholds within striking distance of the surface
code (~0.2–0.5% circuit-level, decoder-dependent), which — combined with the
color code's [[transversal-gates|transversal Clifford gates]] — keeps it a
competitive alternative despite the harder decoding.

## See also

- [[color-code]] — the code these decoders target
- [[mwpm-decoder]] — the matching primitive several of them reduce to
