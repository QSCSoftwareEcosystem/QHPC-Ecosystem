---
topic_slug: circuit-level-noise
title: "Circuit-Level Noise Models"
aliases:
  - "SD6"
  - "SI1000"
see_also:
  - depolarizing-noise
  - measurement-errors
  - surface-code
authority_tier: canonical
last_reviewed: 2026-07-10
maintainers:
  - sharmin
---

# Circuit-Level Noise Models

A circuit-level noise model attaches an error to **every operation** in the
syndrome-extraction circuit — each gate, idle step, reset, and measurement — rather
than depositing errors only on the data qubits between rounds. It is the realistic
noise setting for QEC, and thresholds quoted "under circuit-level noise" are far
more meaningful than code-capacity or phenomenological numbers.

## The three noise levels

- **Code capacity:** errors only on data qubits, perfect syndrome extraction. A
  toy model useful for code-distance intuition.
- **Phenomenological:** data errors *plus* [[measurement-errors]], but gates are
  still ideal. Adds the time dimension to decoding.
- **Circuit-level:** every gate, reset, idle, and measurement can fail. This
  captures **hook errors** — a single two-qubit gate fault spreading to two data
  qubits through the ancilla — which can reduce the effective code distance if the
  extraction circuit is ordered badly.

## Standard parameterizations

- **SD6** — a "standard depolarizing" model with six error locations, applying
  single- and two-qubit [[depolarizing-noise|depolarizing]] channels of strength
  $p$ after each operation, plus measurement/reset flips at rate $p$.
- **SI1000** — a "superconducting-inspired" model calibrated to a $1000\,$ns cycle,
  with idle errors, weaker single-qubit gate error, and stronger measurement/reset
  error, reflecting real transmon device characteristics.

These are the models implemented in **Stim** and used for most modern
[[surface-code]] threshold estimates.

## Why gate ordering matters

Because a CNOT can propagate an ancilla error onto a data qubit, the *order* in
which stabilizer CNOTs are scheduled determines whether hook errors align with or
across the code's logical direction. A good schedule keeps hook errors from
shortening the distance — a purely circuit-level concern invisible to simpler
models.

## See also

- [[depolarizing-noise]] — the per-operation channel used inside these models
- [[measurement-errors]] — the readout component of circuit-level noise
- [[surface-code]] — the code these models are usually applied to
