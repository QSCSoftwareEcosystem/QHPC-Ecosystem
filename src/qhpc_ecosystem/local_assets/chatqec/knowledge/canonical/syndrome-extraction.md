---
topic_slug: syndrome-extraction
title: "Syndrome Extraction"
aliases:
  - "stabilizer measurement"
  - "syndrome measurement"
  - "parity checks"
see_also:
  - stabilizer-formalism
  - decoding
  - fault-tolerance
  - measurement-errors
  - circuit-level-noise
authority_tier: canonical
last_reviewed: 2026-07-10
maintainers:
  - sharmin
---

# Syndrome Extraction

Syndrome extraction is the act of measuring the stabilizer generators of a code
to learn *which* error occurred without learning the encoded data. It is the
repeated, error-corrected heartbeat of any QEC memory: every round produces a
syndrome that a decoder turns into a correction.

## What is measured

For a stabilizer code with generators $\{g_1, \dots, g_{n-k}\}$, syndrome
extraction measures the eigenvalue $\pm 1$ of each $g_i$. Because the code state
is a $+1$ eigenstate of every stabilizer, an outcome of $-1$ flags that an error
anticommuting with $g_i$ has occurred. The bit string of outcomes is the
**syndrome**. Crucially, since stabilizers commute with all logical operators,
the measurement collapses errors without disturbing the encoded qubit.

## The extraction circuit

Each stabilizer is measured with an **ancilla** qubit and a sequence of
controlled-Pauli gates, followed by measuring the ancilla:

- For a $Z$-type check $g = Z_{a}Z_{b}\cdots$: prepare ancilla in $|0\rangle$,
  apply CNOTs from each data qubit to the ancilla, measure in the $Z$ basis.
- For an $X$-type check: prepare ancilla in $|+\rangle$, apply CNOTs from ancilla
  to data qubits, measure in the $X$ basis.

The ancilla's measurement outcome is the parity of the involved data qubits —
hence "parity checks."

## Why one round is not enough

The extraction circuit is itself noisy: gates fail, and the ancilla measurement
can misreport (see [[measurement-errors]]). A single faulty measurement is
indistinguishable from a data error in one round. The standard fix is to
**repeat** syndrome extraction over many rounds and decode in the resulting
$(2{+}1)$-D space-time graph, so measurement errors appear as *vertical* edges
and data errors as *horizontal* ones. This space-time picture, under a realistic
[[circuit-level-noise]] model, is what decoders like MWPM actually run on.

## Fault-tolerant extraction

A naive shared ancilla can spread a single fault into a high-weight data error,
destroying the code's protection. **Fault-tolerant** syndrome extraction
prevents this using Shor-style (cat state), Steane, or Knill (teleportation)
ancilla constructions, or — in the surface code — a carefully ordered CNOT
schedule with one ancilla per check so no single fault produces a logical error
(see [[fault-tolerance]]). The decoder then consumes these syndromes
(see [[decoding]]).

## See also

- [[stabilizer-formalism]] — the generators being measured
- [[decoding]] — turning syndromes into corrections
- [[measurement-errors]] — why repeated rounds are needed
- [[fault-tolerance]] — extraction that doesn't spread errors
