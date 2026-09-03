---
topic_slug: xzzx-surface-code
title: "XZZX Surface Code"
aliases:
  - "tailored surface code"
see_also:
  - surface-code
  - biased-noise
authority_tier: canonical
last_reviewed: 2026-07-10
maintainers:
  - sharmin
---

# XZZX Surface Code

The XZZX surface code is a **Clifford-deformed** variant of the
[[surface-code]] whose stabilizers are tailored to **biased noise**. Under
strongly dephasing noise it reaches thresholds far above the standard surface
code — approaching ~50% in the infinite-bias limit — making it a natural partner
for biased qubits like [[cat-codes|cat qubits]].

## The deformation

The standard surface code has separate $X$-type (star) and $Z$-type (plaquette)
stabilizers. The XZZX code applies a Hadamard on a sublattice so that **every**
stabilizer becomes the same mixed type,

$$
S = X \otimes Z \otimes Z \otimes X
$$

on the four qubits around each face (hence "XZZX"). This single uniform check type
is what re-tunes the code's response to asymmetric noise.

## Why it helps under biased noise

When one Pauli error dominates (say $Z$, pure dephasing), the XZZX structure makes
the dominant errors align into **effectively one-dimensional** decoding chains,
which the decoder handles almost perfectly. Consequences (Ataides et al., 2021):

- **Threshold rises with bias**, approaching the hashing bound and reaching
  ~50% in the infinite-bias limit, versus ~1% for the unbiased surface code.
- Works with standard [[mwpm-decoder|matching]] decoders after the deformation.

## Where it fits

The XZZX code is the outer code of choice for hardware with a strong, structured
[[biased-noise|noise bias]] — cat qubits, fluxonium, or dephasing-dominated
platforms — combining a biased inner qubit with a bias-tailored topological code.

## See also

- [[surface-code]] — the unbiased code it deforms
- [[biased-noise]] — the asymmetric noise it exploits
