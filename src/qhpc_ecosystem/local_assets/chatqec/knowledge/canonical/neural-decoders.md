---
topic_slug: neural-decoders
title: "Neural and ML Decoders"
aliases:
  - "ML decoder"
  - "transformer decoder"
see_also:
  - decoding
  - mwpm-decoder
authority_tier: canonical
last_reviewed: 2026-07-10
maintainers:
  - sharmin
---

# Neural and ML Decoders

Neural decoders learn the syndrome-to-correction map from data instead of
assuming an explicit noise model. Their promise is to capture correlated,
hard-to-model noise — leakage, crosstalk, drift — that degrades analytic
decoders like [[mwpm-decoder|MWPM]], and to run fast at inference time.

## Why learn a decoder

Analytic decoders assume a known, often factorized noise model (independent
Pauli errors with fixed weights). Real hardware has correlated and non-Pauli
noise that is hard to write down. A neural network trained on real or simulated
syndrome data can, in principle, learn the true error statistics and decode
closer to the maximum-likelihood limit (see [[decoding]]) for that specific
device.

## Architectures

- **Feed-forward / CNN:** early decoders treat the syndrome as an image;
  effective for small codes but scale poorly with distance.
- **Recurrent / graph networks:** handle multiple rounds of
  [[syndrome-extraction]] and the code's graph structure.
- **Transformers:** Google DeepMind's **AlphaQubit** (2024) used a transformer to
  decode real Sycamore surface-code data, outperforming MWPM and tensor-network
  decoders on that hardware by learning device-specific correlated noise.

## Trade-offs

- **Accuracy:** can exceed analytic decoders when noise is correlated or
  poorly modeled.
- **Cost:** training data and compute are expensive; a network trained at one
  distance/device may not transfer.
- **Real-time:** inference latency and the cost of scaling to large distances
  remain the central obstacles to deployment as a live decoder.

## See also

- [[decoding]] — the inference problem neural decoders learn
- [[mwpm-decoder]] — the analytic baseline they aim to beat
