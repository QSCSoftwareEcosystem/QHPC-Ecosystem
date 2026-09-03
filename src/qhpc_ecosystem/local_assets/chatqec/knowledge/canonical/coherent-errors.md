---
topic_slug: coherent-errors
title: "Coherent Errors"
aliases:
  - "unitary errors"
  - "over-rotation errors"
see_also:
  - pauli-channels
  - pauli-frame-tracking
authority_tier: canonical
last_reviewed: 2026-07-10
maintainers:
  - sharmin
---

# Coherent Errors

Coherent errors are **unitary** deviations from the intended operation — a small
systematic over- or under-rotation, e.g. applying $R_z(\theta + \epsilon)$ instead
of $R_z(\theta)$. Unlike stochastic Pauli noise, coherent errors preserve phase
information and can **add up amplitude-wise**, making them subtler and sometimes
more damaging than an incoherent channel of the same average fidelity.

## Why coherence matters

A stochastic $X$ error with probability $p$ contributes error $\sim p$. A coherent
over-rotation by angle $\epsilon$ contributes amplitude $\sim \epsilon$, so its
worst-case (diamond-norm) error scales as $\epsilon \sim \sqrt{p}$ — potentially
much larger than the fidelity would suggest. Coherent errors can also
**constructively interfere** across many gates, so the naive assumption that
errors accumulate linearly can badly underestimate the true logical error.

## Fidelity vs. worst case

This produces a well-known gap: average gate fidelity (what randomized
benchmarking measures) can look excellent while the diamond distance — the
relevant quantity for worst-case algorithm error — is quadratically worse. Two
devices with identical fidelity can behave very differently if one's errors are
coherent.

## Taming coherent errors

- **Twirling.** Randomly conjugating gates by Paulis converts a coherent channel
  into an effective stochastic [[pauli-channels|Pauli channel]], removing the
  dangerous coherence at the cost of turning it into honest (Pauli) noise that
  decoders handle well.
- **Error correction itself** partially decoheres errors: syndrome measurement
  projects the error onto Pauli outcomes, so a QEC cycle tends to "Pauli-ize"
  residual coherent noise — one reason logical noise is often more stochastic than
  physical noise.
- **Randomized compiling** builds twirling into the circuit compilation so the
  effective noise seen by a decoder is stochastic by design.

## See also

- [[pauli-channels]] — what coherent errors become after twirling
- [[pauli-frame-tracking]] — tracks the Pauli corrections twirling introduces
