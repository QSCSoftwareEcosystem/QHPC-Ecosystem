---
topic_slug: concatenated-codes
title: "Concatenated Codes"
aliases:
  - "code concatenation"
see_also:
  - shor-code
  - threshold-theorem
  - steane-code
authority_tier: canonical
last_reviewed: 2026-07-10
maintainers:
  - sharmin
---

# Concatenated Codes

Concatenation encodes each physical qubit of a code inside another code,
recursively. It was the route to the **original proof of the
[[threshold-theorem|threshold theorem]]**, because stacking levels suppresses the
logical error rate doubly-exponentially once the physical error rate is below
threshold.

## The construction

Take a base code that encodes $k$ logical qubits in $n$ physical qubits. At level
2, replace each of those $n$ qubits with an $n$-qubit encoded block of the same
code, giving an $[[n^2, k, \ge d^2]]$ code. Repeating to level $\ell$ yields
$n^\ell$ physical qubits. The [[shor-code]] is itself a concatenation of two
repetition codes.

## Doubly-exponential error suppression

If one level of encoding maps physical error rate $p$ to logical rate
$p_1 \approx (p/p_{\text{th}})\,p_{\text{th}}$, then $\ell$ levels give

$$
p_\ell \le p_{\text{th}}\left(\frac{p}{p_{\text{th}}}\right)^{2^{\ell}},
$$

so below threshold ($p < p_{\text{th}}$) the logical error rate falls **doubly
exponentially** in the number of levels, while the qubit overhead grows only
exponentially. This gap is exactly what makes arbitrarily reliable computation
possible with polylogarithmic overhead (see [[threshold-theorem]]).

## Concatenated vs topological codes

- **Concatenated codes** (e.g. concatenated [[steane-code]]) give clean
  threshold proofs and modular fault-tolerant gadgets, but historically have
  lower thresholds and non-local connectivity between levels.
- **Topological codes** like the [[surface-code]] achieve higher thresholds with
  strictly local checks, which is why they dominate near-term hardware — though
  recent concatenated and qLDPC constructions are competitive on overhead.

## See also

- [[shor-code]] — a concatenation of two repetition codes
- [[threshold-theorem]] — the result concatenation originally proved
- [[steane-code]] — a common base code for concatenation
