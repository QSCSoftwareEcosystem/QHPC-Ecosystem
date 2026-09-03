---
topic_slug: biased-noise
title: "Biased Noise"
aliases:
  - "Z-biased noise"
  - "dephasing-dominated noise"
see_also:
  - cat-codes
  - xzzx-surface-code
  - depolarizing-noise
authority_tier: canonical
last_reviewed: 2026-07-10
maintainers:
  - sharmin
---

# Biased Noise

Biased noise is error that is **asymmetric** across Pauli axes — one type
dominates. On most physical qubits, dephasing ($Z$ errors) is far more likely than
bit flips ($X$), often by one to three orders of magnitude. Codes and hardware
that exploit this asymmetry can dramatically outperform their
[[depolarizing-noise|symmetric-noise]] baselines.

## The bias parameter

The bias $\eta$ is the ratio of the dominant error rate to the others, e.g.
$\eta = p_Z / (p_X + p_Y)$. Depolarizing noise is $\eta = 1/2$; realistic
superconducting and cat qubits reach $\eta = 10^2$–$10^4$. As $\eta \to \infty$
the noise becomes pure dephasing, and the correction problem effectively decouples
into an almost-classical one.

## Codes that exploit bias

- **[[xzzx-surface-code]]** — a Clifford-deformed surface code whose threshold
  climbs toward $50\%$ as the bias grows, versus $\sim 1\%$ for the CSS surface
  code under depolarizing noise. Under infinite bias its decoding reduces to
  independent classical repetition codes.
- **[[cat-codes]]** — bosonic qubits *engineered* to have exponentially suppressed
  bit-flips, so the residual noise is almost pure dephasing by construction. They
  are the archetypal biased-noise hardware.

## Why bias helps

If $X$ errors are rare, the code only has to protect strongly against $Z$. Half
the error-correction "budget" can be reallocated, raising thresholds and lowering
overhead. The catch: gates and measurements must be **bias-preserving**, or they
reintroduce the suppressed error type and the advantage collapses. Designing
bias-preserving CNOTs is the central engineering challenge for cat-qubit
architectures.

## See also

- [[cat-codes]] — hardware with built-in bias
- [[xzzx-surface-code]] — code tailored to biased noise
- [[depolarizing-noise]] — the symmetric baseline biased noise beats
