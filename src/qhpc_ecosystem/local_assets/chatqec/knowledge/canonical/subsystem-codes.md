---
topic_slug: subsystem-codes
title: "Subsystem Codes"
aliases:
  - "gauge codes"
  - "OQEC"
see_also:
  - bacon-shor-code
  - floquet-codes
  - stabilizer-formalism
authority_tier: canonical
last_reviewed: 2026-07-10
maintainers:
  - sharmin
---

# Subsystem Codes

Subsystem codes (operator quantum error correction, OQEC) generalize stabilizer
codes by declaring some encoded degrees of freedom **irrelevant**. The Hilbert
space of the code factorizes into a logical subsystem and a "gauge" subsystem;
errors on the gauge part are simply ignored, which buys simpler, lower-weight
syndrome extraction.

## The gauge group

A subsystem code is defined by a (generally **non-abelian**) **gauge group**
$\mathcal{G} \subseteq \mathcal{P}_n$. From it:

- The **stabilizer group** is the center $\mathcal{S} = Z(\mathcal{G})$ (the
  elements commuting with all of $\mathcal{G}$).
- The remaining gauge generators pair into **gauge qubits** that carry no
  protected information.
- **Logical operators** commute with $\mathcal{G}$ but are not in it.

The code space thus splits as
$\mathcal{H} = (\mathcal{H}_L \otimes \mathcal{H}_{\text{gauge}}) \oplus \cdots$,
with information stored only in $\mathcal{H}_L$ (see [[stabilizer-formalism]]).

## Why give up qubits?

Ignoring the gauge qubits lets high-weight stabilizers be measured **indirectly**
as products of low-weight gauge operators. The [[bacon-shor-code]] is the classic
example: weight-2 gauge measurements reconstruct weight-$2m$ stabilizers. Benefits:

- lower-weight, more local measurements → simpler, more fault-tolerant extraction;
- freedom to **gauge-fix** (choose which gauge operators to fix) to switch codes
  or tailor to noise (see [[code-deformation]]).

The trade-off is usually a reduced distance or threshold relative to a stabilizer
code on the same qubits.

## Examples

- [[bacon-shor-code]] / compass codes — the canonical subsystem codes.
- [[floquet-codes]] — dynamical codes best understood through a gauge picture.
- Subsystem surface and color codes with reduced-weight checks.

## See also

- [[bacon-shor-code]] — the prototypical subsystem code
- [[floquet-codes]] — dynamical gauge fixing in action
- [[stabilizer-formalism]] — the abelian special case
