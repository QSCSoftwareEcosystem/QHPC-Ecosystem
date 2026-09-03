---
topic_slug: photonic-qec
title: "Photonic QEC"
aliases:
  - "fusion-based quantum computing"
see_also:
  - gkp-codes
  - continuous-variable-qec
authority_tier: canonical
last_reviewed: 2026-07-10
maintainers:
  - sharmin
---

# Photonic QEC

Photonic QEC builds fault-tolerant computation from single photons (or bosonic
optical modes). Photons barely interact with their environment — long coherence,
room-temperature operation, and natural networkability — but they also barely
interact with **each other**, so deterministic two-qubit gates are hard. Photonic
architectures are designed around this constraint.

## The measurement-based / fusion approach

Because deterministic entangling gates are unavailable, photonic proposals are
**measurement-based**: prepare small entangled resource states and stitch them
together with probabilistic **fusion** measurements (two-photon Bell measurements).

**Fusion-based quantum computing (FBQC)** is the leading model: many identical few-photon
resource states are generated and fused according to a schedule that directly builds
a fault-tolerant [[surface-code|surface-code]]-like structure in space-time. Fusion
failures and photon loss are treated as located ("heralded") erasures, which codes
tolerate at much higher rates than general errors.

## Loss is the dominant error

The defining challenge is **photon loss**. Every optical component has some loss
probability, and a lost photon is an erasure. Photonic fault tolerance therefore
lives or dies by the loss threshold, driving two responses:

- **Erasure-tolerant codes** — heralded loss is far cheaper to correct than a Pauli
  error, so architectures maximize the fraction of errors that are detected
  erasures.
- **Bosonic encodings** — [[gkp-codes|GKP]] and other
  [[continuous-variable-qec|CV codes]] give each optical mode internal protection
  against loss before the outer code even acts.

## Advantages

Photonic systems offer intrinsic connectivity (photons fly through fiber),
room-temperature qubits, and a manufacturing path via integrated photonics — making
them a strong candidate for **networked** and modular fault-tolerant machines.

## See also

- [[gkp-codes]] — bosonic encoding well-matched to optical loss
- [[continuous-variable-qec]] — the bosonic framework photonics often uses
