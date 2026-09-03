---
topic_slug: depolarizing-noise
title: "Depolarizing Noise"
aliases:
  - "depolarizing channel"
  - "symmetric Pauli noise"
see_also:
  - pauli-channels
  - circuit-level-noise
  - biased-noise
authority_tier: canonical
last_reviewed: 2026-07-10
maintainers:
  - sharmin
---

# Depolarizing Noise

Depolarizing noise is the standard **symmetric** error model for QEC benchmarking:
each qubit suffers an $X$, $Y$, or $Z$ error with equal probability. It is the
default noise assumption behind most quoted code thresholds because it is
worst-case symmetric and analytically clean.

## Single-qubit channel

With total error probability $p$, the single-qubit depolarizing channel is

$$\mathcal{E}(\rho) = (1-p)\,\rho + \frac{p}{3}\left(X\rho X + Y\rho Y + Z\rho Z\right),$$

i.e. each of the three non-identity Paulis occurs with probability $p/3$. As $p
\to 3/4$ the state is fully mixed. It is the maximally symmetric [[pauli-channels|Pauli
channel]].

## Two-qubit version

For entangling gates the two-qubit depolarizing channel applies one of the 15
non-identity two-qubit Paulis each with probability $p/15$. This is the error
attached to CNOT/CZ gates in a simple [[circuit-level-noise]] model.

## Why it is the default

- **Symmetry.** $X$, $Y$, $Z$ are treated identically, so it makes no assumption
  about the hardware's dominant error axis — a conservative choice.
- **Twirling.** Any noise channel can be converted into an effective Pauli (often
  depolarizing) channel by [[pauli-channels|Pauli twirling]], so depolarizing
  results are a meaningful proxy for real devices after twirling.
- **Comparability.** Because everyone reports thresholds under depolarizing noise,
  it is the common yardstick — e.g. the surface code's $\sim 1\%$ circuit-level
  threshold.

## Contrast with biased noise

Real qubits are rarely symmetric; dephasing ($Z$) usually dominates. Codes tuned
to that asymmetry (see [[biased-noise]], [[xzzx-surface-code]], [[cat-codes]])
beat their depolarizing-noise thresholds substantially, which is why the symmetric
model is a pessimistic baseline for biased hardware.

## See also

- [[pauli-channels]] — the general family depolarizing noise sits in
- [[circuit-level-noise]] — how depolarizing errors attach to gates
- [[biased-noise]] — the asymmetric alternative
