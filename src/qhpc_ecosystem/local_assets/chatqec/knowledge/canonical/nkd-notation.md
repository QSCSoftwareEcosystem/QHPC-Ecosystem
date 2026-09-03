---
topic_slug: nkd-notation
title: "[[n,k,d]] Code Parameters"
aliases:
  - "code distance"
  - "n k d notation"
  - "code parameters"
see_also:
  - logical-operators
  - stabilizer-formalism
  - threshold-theorem
authority_tier: canonical
last_reviewed: 2026-07-10
maintainers:
  - sharmin
---

# [[n,k,d]] Code Parameters

The notation $[[n, k, d]]$ compactly describes a quantum error-correcting code:
$n$ physical qubits encode $k$ logical qubits with code distance $d$. The double
brackets distinguish a *quantum* code from a classical $[n, k, d]$ code (single
brackets). These three numbers set the resource cost and the error-suppression
power of any stabilizer code.

## The three parameters

- **$n$ — physical qubits.** The size of the register the code lives on.
- **$k$ — logical qubits.** The dimension of the protected code space is $2^k$.
  For a stabilizer code with $n - k$ independent stabilizer generators,
  $k = n - (n-k)$; each independent generator halves the code space.
- **$d$ — distance.** The minimum weight of any nontrivial logical operator —
  equivalently, the smallest number of single-qubit errors that maps one
  codeword to another *without* being detected (see [[logical-operators]]).

## What distance buys you

A code of distance $d$ can:

- **detect** up to $d - 1$ errors, and
- **correct** up to $t = \lfloor (d-1)/2 \rfloor$ arbitrary single-qubit errors.

Distance $d = 2t + 1$ is the odd-distance sweet spot for correcting $t$ errors.
Codes with even $d$ can correct $t = d/2 - 1$ and detect $d/2$.

## The rate and the trade-off

The **rate** $k/n$ measures encoding efficiency. Good codes push $k$ and $d$ up
while keeping $n$ down, but these compete: for topological codes like the
[[surface-code]], $k = 1$ and $d = L$ on an $n \sim L^2$ lattice, so the rate
vanishes as distance grows. [[qldpc-codes]] break this scaling, keeping a
constant rate as $d$ grows. The distance also determines the sub-threshold
scaling of the logical error rate, $p_L \sim (p/p_{\text{th}})^{d/2}$, which is
the basis of the [[threshold-theorem]].

## Examples

| Code | $[[n,k,d]]$ | Note |
|------|-------------|------|
| Five-qubit | $[[5,1,3]]$ | smallest code correcting any single error |
| Steane | $[[7,1,3]]$ | CSS, transversal Clifford |
| Shor | $[[9,1,3]]$ | first QEC code |
| Surface (distance $L$) | $[[L^2 + (L-1)^2,\,1,\,L]]$ | rotated: $[[d^2,1,d]]$ |

## See also

- [[logical-operators]] — the operators whose minimum weight *is* $d$
- [[stabilizer-formalism]] — where $n - k$ generators come from
- [[threshold-theorem]] — how $d$ controls logical error suppression
