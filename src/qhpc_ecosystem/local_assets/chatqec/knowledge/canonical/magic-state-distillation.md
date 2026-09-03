---
topic_slug: magic-state-distillation
title: "Magic State Distillation"
aliases:
  - "MSD"
  - "T-state distillation"
  - "state distillation"
see_also:
  - css-codes
  - stabilizer-formalism
authority_tier: canonical
last_reviewed: 2026-05-29
maintainers:
  - sharmin
---

# Magic State Distillation

Magic state distillation (Bravyi & Kitaev 2005) is the standard route to
universal fault-tolerant quantum computation on stabilizer codes. Eastin-Knill
forbids a transversal universal gate set, so non-Clifford operations are
implemented by **injecting** a noisy magic state and **distilling** purified
copies using stabilizer operations only.

## The magic states

The canonical resource state is

$$|T\rangle = \cos(\pi/8)|0\rangle + e^{i\pi/4}\sin(\pi/8)|1\rangle$$

Consuming one ideal $|T\rangle$ enables one $T = \mathrm{diag}(1, e^{i\pi/4})$
gate by gate teleportation. Combined with the Clifford group (achievable
transversally on many stabilizer codes), this gives universality.

## The protocol

1. Prepare $n$ noisy $|T\rangle$ states with error rate $p$.
2. Encode them into the $[[15, 1, 3]]$ Reed-Muller code (or a triorthogonal code).
3. Measure the code's stabilizers; on the trivial syndrome, the output magic
   state has lower error rate $p' \sim O(p^d)$ where $d$ is the code distance.
4. Repeat in cascade until the desired fidelity is reached.

## Cost

Magic state distillation dominates the resource cost of fault-tolerant
algorithms (Gidney-Ekera 2021 RSA estimate). Modern work (Litinski 2019,
Wills-Lin-Yoder 2024) substantially reduces this overhead via
**triorthogonal codes** and improved factory architectures.

## See also

- [[css-codes]] — the codes used in distillation factories
- [[stabilizer-formalism]] — what makes Clifford-only operations "free"
