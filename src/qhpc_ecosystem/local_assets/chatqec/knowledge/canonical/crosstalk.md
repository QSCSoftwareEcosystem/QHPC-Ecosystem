---
topic_slug: crosstalk
title: "Crosstalk"
aliases:
  - "ZZ crosstalk"
  - "spectator errors"
see_also:
  - leakage
  - circuit-level-noise
authority_tier: canonical
last_reviewed: 2026-07-10
maintainers:
  - sharmin
---

# Crosstalk

Crosstalk is unwanted interaction between qubits or operations that should be
independent: driving one qubit disturbs its neighbours, or a gate on one pair
affects a spectator qubit nearby. It breaks the standard QEC assumption that errors
are **independent and local**, producing correlated errors that decoders modeled on
independent noise handle poorly.

## Common forms

- **Always-on $ZZ$ coupling.** Residual static coupling between fixed-frequency
  transmons applies a slow, correlated phase between neighbours even when idle —
  the dominant crosstalk term in many superconducting devices.
- **Spectator errors.** A two-qubit gate on qubits $(a,b)$ imparts an unintended
  rotation or error on a nearby spectator $c$.
- **Drive/microwave crosstalk.** A pulse meant for one qubit partially drives
  another at a similar frequency, and simultaneous operations interfere.

## Why it hurts QEC

Correlated, non-local errors can flip **multiple stabilizers** in patterns the
decoder's error model does not include, effectively lowering the threshold and, in
the worst case, creating error mechanisms shorter than the code distance. Crosstalk
is also closely tied to [[leakage]]: interactions with higher levels both leak
population and mediate crosstalk.

## Mitigation

- **Frequency allocation** and tunable couplers to null residual $ZZ$.
- **Dynamical decoupling** and echo sequences on idling qubits.
- **Scheduling** so that simultaneously executed gates are spatially separated.
- **Crosstalk-aware noise models** feeding correlated edges into the decoder rather
  than assuming independence.

Because crosstalk violates the independence assumption baked into simple
[[circuit-level-noise]] models, characterizing and suppressing it is essential
before measured thresholds match theory.

## See also

- [[leakage]] — a tightly coupled correlated-error mechanism
- [[circuit-level-noise]] — the independent-noise baseline crosstalk violates
