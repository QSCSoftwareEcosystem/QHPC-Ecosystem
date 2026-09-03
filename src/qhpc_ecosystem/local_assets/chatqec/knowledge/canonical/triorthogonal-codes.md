---
topic_slug: triorthogonal-codes
title: "Triorthogonal Codes"
aliases:
  - "Bravyi-Haah codes"
see_also:
  - magic-state-distillation
  - reed-muller-codes
authority_tier: canonical
last_reviewed: 2026-07-10
maintainers:
  - sharmin
---

# Triorthogonal Codes

Triorthogonal codes (Bravyi and Haah, 2012) are a family of CSS codes engineered
for one job: **efficient magic-state distillation**. They generalize the
$[[15,1,3]]$ [[reed-muller-codes|Reed-Muller code]] and give a tunable trade-off
between distillation yield and overhead.

## The triorthogonality condition

A binary matrix $G$ (whose rows generate the relevant CSS subcode) is
**triorthogonal** if every pair and every triple of rows overlaps evenly:

$$
\sum_i G_{a,i}G_{b,i} \equiv 0 \pmod 2,\qquad
\sum_i G_{a,i}G_{b,i}G_{c,i} \equiv 0 \pmod 2
$$

for distinct rows $a,b,c$ (with a controlled exception for the logical rows). This
algebraic condition is exactly what guarantees that applying transversal $T$
implements logical $T$ (up to Clifford correction) on the encoded qubits — the
property needed for distillation (see [[transversal-gates]]).

## Why they matter for distillation

Given transversal $T$, a triorthogonal $[[n,k,d]]$ code implements an
**$n \to k$** magic-state distillation routine that suppresses the input error
rate $p \to O(p^{d})$ (or $O(p^{2})$ for $d=2$ constructions optimized for yield).
By choosing the code, one tunes:

- **yield** ($k/n$, output states per input),
- **error suppression** (set by distance $d$),
- **overhead** (total qubits and $T$-gates).

Bravyi–Haah's original family already improved on the 15-to-1 protocol, and
triorthogonal constructions underpin most modern low-overhead distillation
factories (see [[magic-state-distillation]]).

## See also

- [[magic-state-distillation]] — what triorthogonal codes are built for
- [[reed-muller-codes]] — the $[[15,1,3]]$ special case
