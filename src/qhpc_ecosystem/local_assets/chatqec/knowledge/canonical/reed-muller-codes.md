---
topic_slug: reed-muller-codes
title: "Reed-Muller Codes (Quantum)"
aliases:
  - "quantum Reed-Muller"
  - "[[15,1,3]] code"
see_also:
  - transversal-gates
  - magic-state-distillation
  - triorthogonal-codes
authority_tier: canonical
last_reviewed: 2026-07-10
maintainers:
  - sharmin
---

# Reed-Muller Codes (Quantum)

Quantum Reed-Muller codes are CSS codes built from classical Reed-Muller codes.
Their defining feature is a **transversal non-Clifford gate**: the $[[15,1,3]]$
punctured Reed-Muller code supports transversal $T$, which is why it is the
backbone of the standard magic-state distillation routine.

## The [[15,1,3]] code

Constructed from the punctured Reed-Muller codes $\mathrm{RM}(1,4)$ and
$\mathrm{RM}(2,4)$, the $[[15,1,3]]$ code encodes one logical qubit in fifteen
physical qubits with distance 3. Its $X$- and $Z$-stabilizers come from the
nested Reed-Muller structure $\mathrm{RM}(1,4) \subseteq \mathrm{RM}(2,4)$.

## Transversal T and the Eastin-Knill dodge

The [[15,1,3]] code admits **transversal $T$** (up to a Clifford correction):
applying $T^\dagger$ to all fifteen qubits implements logical $T$. This does not
violate the Eastin-Knill theorem — the code still has no transversal *universal*
gate set, and the transversal gate here is the non-Clifford one while the
Clifford gates require other means (see [[transversal-gates]]).

## Role in distillation

The 15-qubit code is the basis of the original **15-to-1 magic-state distillation**
protocol: encode noisy $T$ states, apply the transversal gate, decode, and reject
on nonzero syndrome. This suppresses the input error rate $p \to 35p^3$, the
workhorse of [[magic-state-distillation]]. Its generalization to codes optimized
for distillation gives the [[triorthogonal-codes]].

## See also

- [[transversal-gates]] — why transversal $T$ is special
- [[magic-state-distillation]] — the 15-to-1 protocol
- [[triorthogonal-codes]] — the distillation-optimized generalization
