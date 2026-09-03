---
topic_slug: logical-operators
title: "Logical Operators"
aliases:
  - "logical Pauli operators"
  - "logical X"
  - "logical Z"
  - "encoded operators"
see_also:
  - stabilizer-formalism
  - nkd-notation
  - transversal-gates
authority_tier: canonical
last_reviewed: 2026-07-10
maintainers:
  - sharmin
---

# Logical Operators

Logical operators are the encoded versions of Pauli operators: they act on the
$2^k$-dimensional code space of an $[[n,k,d]]$ code the way $X$ and $Z$ act on a
bare qubit. They are the operators that manipulate protected information, and
their minimum weight *is* the code distance.

## Definition via the stabilizer

Let $\mathcal{S}$ be the stabilizer group and $N(\mathcal{S})$ its normalizer in
the [[pauli-group]] (the Paulis commuting with every stabilizer). Logical
operators are elements of the quotient

$$
\mathcal{L} = N(\mathcal{S}) \,/\, \mathcal{S}.
$$

Concretely, a logical operator:

- **commutes with every stabilizer** (so it preserves the code space and is
  undetected by syndrome measurement), but
- **is not itself in $\mathcal{S}$** (so it acts nontrivially on encoded data).

Multiplying a logical operator by a stabilizer gives an equivalent logical
operator — same action on the code space, possibly different weight and support.

## Logical X and Z

For $k$ logical qubits there are $2k$ generators $\bar{X}_1, \bar{Z}_1, \dots,
\bar{X}_k, \bar{Z}_k$ chosen so that

$$
\bar{X}_i \bar{Z}_j = (-1)^{\delta_{ij}}\, \bar{Z}_j \bar{X}_i,
$$

i.e. each $\bar{X}_i$ anticommutes with its partner $\bar{Z}_i$ and commutes
with all others — exactly the algebra of $k$ independent bare qubits.

## Distance = minimum logical weight

The code distance is

$$
d = \min_{\,\bar{L}\,\in\, N(\mathcal{S})\setminus\mathcal{S}} \operatorname{wt}(\bar{L}),
$$

the smallest weight over all nontrivial logical operators, minimized over each
stabilizer-equivalent class. An undetectable logical error is precisely a
low-weight member of this set (see [[nkd-notation]]). In the [[surface-code]],
logical operators are strings spanning the lattice between boundaries, so their
weight — and thus $d$ — grows with lattice size.

## Why weight matters

Because a weight-$w$ logical operator can be caused by $w$ single-qubit errors,
raising the minimum logical weight is the whole game of code design. It also
governs fault tolerance: a [[transversal-gates|transversal]] logical gate must
implement the logical action while keeping errors from spreading within a code
block.

## See also

- [[stabilizer-formalism]] — the normalizer/stabilizer structure
- [[nkd-notation]] — distance as minimum logical weight
- [[transversal-gates]] — implementing logical gates fault-tolerantly
