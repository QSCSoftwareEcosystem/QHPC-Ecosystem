---
topic_slug: threshold-theorem
title: "Threshold Theorem"
aliases:
  - "fault tolerance threshold"
  - "accuracy threshold theorem"
see_also:
  - surface-code
  - stabilizer-formalism
authority_tier: canonical
last_reviewed: 2026-05-29
maintainers:
  - sharmin
---

# Threshold Theorem

The threshold theorem (Aharonov & Ben-Or 1999; Knill, Laflamme, Zurek 1996;
Kitaev 1997) states that if the physical error rate per gate is below a
code-dependent constant $p_{th}$, then arbitrarily long quantum computations
are possible with polylogarithmic overhead.

## Statement (informal)

For a family of fault-tolerant constructions of code distance $d$, there
exists a threshold $p_{th}$ such that the logical error rate satisfies

$$p_L(d) \lesssim A \left( \frac{p}{p_{th}} \right)^{(d+1)/2}$$

for $p < p_{th}$. Increasing distance exponentially suppresses logical errors
below threshold.

## Surface code threshold

Under circuit-level depolarizing noise with the standard syndrome-extraction
circuit, the surface code threshold is approximately $p_{th} \approx 1\%$.
Under biased noise, tailored variants like [[surface-code]] XZZX achieve
higher thresholds against the dominant error type.

## What "below threshold" means experimentally

A system operates **below threshold** when increasing the code distance
*decreases* the logical error rate. Google's 2024 Willow result (arXiv:2408.13687)
demonstrated this for $d = 3, 5, 7$ on a superconducting surface code.

## Common misconceptions

- The threshold is *not* the physical error rate at which one logical qubit
  beats one physical qubit — that's a separate engineering threshold.
- The threshold depends on the *noise model*, the *code*, the *decoder*, and
  the *syndrome-extraction circuit*. Quoting a threshold without specifying
  these is meaningless.

## See also

- [[surface-code]] — primary code where below-threshold has been demonstrated
- [[stabilizer-formalism]] — algebraic framework used in threshold proofs
