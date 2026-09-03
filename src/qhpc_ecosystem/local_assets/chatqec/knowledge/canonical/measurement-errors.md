---
topic_slug: measurement-errors
title: "Measurement Errors"
aliases:
  - "readout errors"
  - "syndrome measurement noise"
see_also:
  - syndrome-extraction
  - circuit-level-noise
  - mwpm-decoder
authority_tier: canonical
last_reviewed: 2026-07-10
maintainers:
  - sharmin
---

# Measurement Errors

A measurement error is a faulty *classical outcome* of a stabilizer or readout
measurement — the qubit is fine, but the reported bit is flipped. Because
[[syndrome-extraction]] relies entirely on measuring ancillas, unreliable
measurement is one of the most damaging error sources in QEC: a wrong syndrome
bit can trigger a mis-correction that *creates* a logical error.

## Why one round is not enough

If a syndrome is measured once and a detector fires, the decoder cannot tell
whether a real data error occurred or the measurement simply lied. A naive
correction based on a lied syndrome injects an error. The standard fix is to
**repeat** syndrome extraction over many rounds.

## Space-time decoding

Repeating measurement turns decoding into a $(d{+}1)$-dimensional problem: $d$
rounds of a $d$-distance code build a space-time detector graph. **Detectors** are
defined as the parity of a stabilizer between consecutive rounds, so a measurement
error flips exactly two temporally adjacent detectors — a *vertical* edge in the
matching graph. Data errors are horizontal edges. Decoders like the
[[mwpm-decoder]] then handle data and measurement faults on the same footing.

This is why a distance-$d$ surface code memory experiment runs $\sim d$ rounds of
stabilizer measurement: it provides enough temporal redundancy to protect the
syndrome record itself against measurement error.

## In circuit-level noise

Under a full [[circuit-level-noise]] model, measurement error is one of several
parameters (often a single flip probability $p$ on each ancilla readout,
independently of the gate error rate). Readout is frequently the *noisiest*
operation on real hardware, so measurement-error probability often dominates a
device's effective logical error rate.

## See also

- [[syndrome-extraction]] — the process measurement errors corrupt
- [[circuit-level-noise]] — where readout error enters the noise model
- [[mwpm-decoder]] — decodes data and measurement faults jointly
