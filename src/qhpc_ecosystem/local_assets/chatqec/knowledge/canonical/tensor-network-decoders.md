---
topic_slug: tensor-network-decoders
title: "Tensor Network Decoders"
aliases:
  - "TN decoder"
  - "MPS decoder"
see_also:
  - decoding
  - surface-code
authority_tier: canonical
last_reviewed: 2026-07-10
maintainers:
  - sharmin
---

# Tensor Network Decoders

Tensor-network (TN) decoders approximate the *optimal* maximum-likelihood
decoder by contracting a tensor network that represents the sum over all errors
consistent with a syndrome. They are the accuracy gold standard used to benchmark
faster heuristic decoders like [[mwpm-decoder|MWPM]].

## Maximum-likelihood decoding as a contraction

True ML decoding requires summing the probability of every error in each logical
coset — a #P-hard problem in general (see [[decoding]]). For the
[[surface-code]], Bravyi, Suchara, and Vargo showed this coset sum can be written
as the contraction of a 2D tensor network whose geometry mirrors the code
lattice. Each logical class corresponds to one contraction; the decoder picks the
class with the largest total weight.

## Approximate contraction

Exact 2D contraction is itself intractable, so TN decoders contract
**approximately** using a matrix-product-state (MPS) sweep with a bounded bond
dimension $\chi$. Increasing $\chi$ trades runtime for accuracy and converges to
the true ML decoder — which is why TN decoders are used to establish the
**optimal (code-capacity) threshold** of the toric/surface code: ~10.9% under
independent $X$/$Z$ noise and ~18.9% under depolarizing noise, the ceilings
against which all other decoders are measured.

## Uses and limits

- **Benchmarking:** the reference for how much accuracy a fast decoder gives up.
- **Degenerate codes:** naturally accounts for error degeneracy, unlike MWPM.
- **Limit:** too slow for real-time use at scale, and hardest to apply to
  fully 3D space-time circuit-level decoding; mostly a code-capacity and
  phenomenological-noise tool.

## See also

- [[decoding]] — ML vs MLE decoding and decoder families
- [[surface-code]] — where TN decoders set the optimal threshold
