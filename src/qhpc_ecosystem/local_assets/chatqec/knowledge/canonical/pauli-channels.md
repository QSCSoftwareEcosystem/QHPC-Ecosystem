---
topic_slug: pauli-channels
title: "Pauli Channels and Twirling"
aliases:
  - "Pauli twirling"
see_also:
  - depolarizing-noise
  - coherent-errors
authority_tier: canonical
last_reviewed: 2026-07-10
maintainers:
  - sharmin
---

# Pauli Channels and Twirling

A Pauli channel applies a random Pauli operator drawn from a probability
distribution over the [[pauli-group]]. It is the noise model at the heart of
stabilizer QEC: because Pauli errors either commute or anticommute with each
stabilizer, they produce discrete syndromes, and correcting them reduces to a
classical inference problem.

## Definition

For a single qubit,

$$\mathcal{E}(\rho) = p_I\,\rho + p_X\,X\rho X + p_Y\,Y\rho Y + p_Z\,Z\rho Z,$$

with $p_I + p_X + p_Y + p_Z = 1$. Special cases include
[[depolarizing-noise|depolarizing]] noise ($p_X = p_Y = p_Z$) and pure dephasing
($p_Z$ only). General $n$-qubit Pauli channels assign a probability to each of the
$4^n$ Pauli strings.

## Why QEC loves Pauli channels

- **Discretization of errors.** Correcting the Pauli basis is enough — any error
  is a linear combination of Paulis, and syndrome measurement collapses it onto
  one of them.
- **Efficient simulation.** Pauli noise on Clifford circuits is classically
  simulable (Gottesman–Knill / Stim), enabling million-shot threshold estimates.
- **Tractable decoding.** Edge weights $-\log p_e$ come directly from the channel
  probabilities.

## Twirling

**Pauli twirling** converts an *arbitrary* noise channel into a Pauli channel by
averaging (twirling) it over random Pauli conjugations:

$$\tilde{\mathcal{E}} = \frac{1}{4^n}\sum_{P} P^\dagger\, \mathcal{E}(P \cdot P^\dagger)\, P.$$

The off-diagonal (coherent) parts of the channel average to zero, leaving only the
diagonal Pauli-error probabilities. This tames [[coherent-errors]] — turning a
dangerous unitary over-rotation into honest stochastic noise a decoder can handle —
and underlies **randomized compiling**, which builds the twirl into circuit
execution so the effective noise is Pauli by construction.

## See also

- [[depolarizing-noise]] — the maximally symmetric Pauli channel
- [[coherent-errors]] — what twirling converts into Pauli noise
