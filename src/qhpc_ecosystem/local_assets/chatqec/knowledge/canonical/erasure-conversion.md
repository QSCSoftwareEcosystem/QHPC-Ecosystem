---
topic_slug: erasure-conversion
title: "Erasure Conversion"
aliases:
  - "erasure qubits"
  - "erasure errors"
  - "erasure-biased noise"
  - "erasure conversion"
see_also:
  - neutral-atom-qec
  - photonic-qec
  - biased-noise
  - threshold-theorem
authority_tier: canonical
last_reviewed: 2026-07-12
maintainers:
  - sharmin
---

# Erasure Conversion

**Erasure conversion** is the design of qubits and gates so that the dominant
physical errors are **erasures** — errors whose *location is known* — rather than
ordinary Pauli errors of unknown position. A located error is far easier to correct:
the decoder is handed "the error is on qubit *j*" instead of having to infer it from
syndromes, which sharply raises the tolerable error rate.

## Why located errors are cheaper

For a distance-$d$ code, unknown (Pauli) errors are corrected up to weight
$\lfloor (d-1)/2 \rfloor$, but **erasures** — errors at known positions — can be
corrected up to weight $d-1$, because half the decoding problem (finding *where*) is
already solved. Concretely, converting errors to erasures roughly **doubles the
correctable weight** and pushes the [[threshold-theorem|threshold]] up substantially:
for the surface code the erasure threshold is $\approx 4.15\%$ versus $\approx 0.94\%$
for depolarizing noise.

## How errors are made detectable

The trick is a physical mechanism that *flags* when an error has occurred:

- **Neutral atoms (metastable qubits).** Encoding in a metastable manifold (e.g. the
  $^3P_0$ level of $^{171}$Yb) lets Rydberg-gate leakage decay to states outside the
  computational space that are read out by a cycling transition — the leakage is
  *heralded* as an erasure. Atom loss is likewise a heralded erasure
  (see [[neutral-atom-qec]]).
- **Dual-rail encodings.** A photon or a pair of superconducting modes encodes one
  qubit across two rails; the dominant loss/amplitude-damping event moves the system
  to a detectable "no-photon" or leakage state rather than flipping the logical bit.

## Relationship to biased noise

Erasure conversion is a form of **noise structuring**, complementary to
[[biased-noise|biased noise]]: instead of skewing errors toward one Pauli type, it
skews them toward a *detectable* type. Decoders exploit the erasure flags much like
they exploit bias — both convert a hard, unstructured decoding problem into an easier
structured one.

## See also

- [[neutral-atom-qec]] — metastable-qubit and atom-loss erasures
- [[photonic-qec]] — dual-rail photon-loss erasures
- [[biased-noise]] — the complementary noise-structuring idea
- [[threshold-theorem]] — why located errors raise the threshold
