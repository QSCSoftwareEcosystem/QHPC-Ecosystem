---
topic_slug: cat-codes
title: "Cat Codes"
aliases:
  - "cat qubits"
  - "dissipative cat codes"
see_also:
  - gkp-codes
  - biased-noise
authority_tier: canonical
last_reviewed: 2026-07-10
maintainers:
  - sharmin
---

# Cat Codes

Cat codes encode a qubit in superpositions of **coherent states** of a bosonic
mode ("Schrödinger cat" states). Their signature property is an exponentially
**biased** noise channel: bit flips are suppressed exponentially in the cat size,
leaving an almost purely dephasing qubit that a tailored outer code can protect
cheaply.

## Encoding

A two-component cat qubit uses coherent states $|\pm\alpha\rangle$:

$$
|\bar{0}\rangle \propto |\alpha\rangle + |-\alpha\rangle,\qquad
|\bar{1}\rangle \propto |\alpha\rangle - |-\alpha\rangle
$$

(even/odd photon-number cats). The mean photon number $\bar{n} = |\alpha|^2$ sets
the code's protection.

## The noise bias

Cat qubits are **stabilized** — either by engineered two-photon dissipation
(dissipative cats) or a Kerr Hamiltonian (Kerr cats) — which pins the state to the
cat manifold. The result:

- **Bit-flip rate** (leaking between $|\pm\alpha\rangle$) is suppressed
  $\propto e^{-2|\alpha|^2}$ — exponentially small in photon number.
- **Phase-flip rate** grows only linearly in $|\alpha|^2$.

So the qubit has a large, tunable [[biased-noise|noise bias]] $\eta = $ (phase
rate)/(bit rate) reaching $10^3$–$10^5$.

## Why the bias is useful

A strongly biased qubit needs only to be protected against the dominant phase
errors. Concatenating cat qubits with a **repetition code** (against phase flips)
or a bias-tailored surface code (e.g. [[xzzx-surface-code]]) yields fault tolerance
with far fewer qubits than an unbiased architecture — the basis of Amazon and
Alice & Bob cat-qubit roadmaps.

## See also

- [[gkp-codes]] — the displacement-oriented bosonic code
- [[biased-noise]] — the asymmetric noise cat codes exploit
