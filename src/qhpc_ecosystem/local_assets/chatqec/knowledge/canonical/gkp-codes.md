---
topic_slug: gkp-codes
title: "GKP Codes"
aliases:
  - "Gottesman-Kitaev-Preskill code"
  - "grid states"
see_also:
  - cat-codes
  - continuous-variable-qec
authority_tier: canonical
last_reviewed: 2026-07-10
maintainers:
  - sharmin
---

# GKP Codes

Gottesman–Kitaev–Preskill (GKP) codes encode a qubit in the infinite-dimensional
Hilbert space of a single **bosonic mode** (a harmonic oscillator), protecting
against small shifts in position and momentum. They are a leading **bosonic** code
for hardware where the dominant noise is small continuous displacements.

## Encoding in phase space

The ideal GKP codewords are superpositions of position eigenstates spaced by
$2\sqrt{\pi}$ — a "grid" or "comb" in phase space:

$$
|\bar{0}\rangle \propto \sum_{n\in\mathbb{Z}} |q = 2n\sqrt{\pi}\rangle,\quad
|\bar{1}\rangle \propto \sum_{n\in\mathbb{Z}} |q = (2n{+}1)\sqrt{\pi}\rangle.
$$

The stabilizers are the commuting displacement operators
$\hat{S}_q = e^{i 2\sqrt{\pi}\,\hat{p}}$ and $\hat{S}_p = e^{-i 2\sqrt{\pi}\,\hat{q}}$.
Measuring them reads out the position and momentum **modulo** $\sqrt{\pi}$, so any
small shift is detected and corrected back to the nearest grid point.

## Strengths and challenges

- **Corrects small displacements:** the generic error in a bosonic mode, giving
  a natural fit for oscillator noise.
- **Composes well:** a GKP qubit's built-in analog syndrome can be fed into an
  outer qubit code (e.g. GKP-surface code), boosting its threshold.
- **Hard to prepare:** ideal grid states are unphysical (infinite energy); real
  GKP states are finitely squeezed, and preparing high-quality states is the main
  experimental hurdle (demonstrated in trapped-ion and superconducting cavities).

## Relation to other bosonic codes

GKP codes protect against displacements; [[cat-codes]] instead target loss with a
strong noise bias. Both are [[continuous-variable-qec|continuous-variable]] codes
and can serve as the inner layer of a concatenated scheme.

## See also

- [[cat-codes]] — the loss-oriented, biased-noise bosonic alternative
- [[continuous-variable-qec]] — the broader bosonic-code setting
