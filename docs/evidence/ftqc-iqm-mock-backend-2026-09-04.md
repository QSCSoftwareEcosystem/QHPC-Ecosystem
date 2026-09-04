# FTQC–IQM mock backend acceptance — 2026-09-04

## Scope

This record validates the EQO credential and provenance boundary for the future
FTQC–IQM hardware stage. It is not evidence of an IQM hardware execution.

The tested boundary accepts paired `qhpc.iqm-circuit@1` and
`qhpc.ftqc-iqm-preparation-report@1` artifacts, derives the readout mode from
the FTQC report, resolves an IQM token only inside a `quantum-backend` worker,
and exercises route, submit, poll, collect, timeout, and cancellation behavior
through an injected mock provider client.

## Preserved outputs

- `qhpc.iqm-routed-layout@1`: source circuit digest, exact device and
  calibration identity, routed circuit, initial/final layout, and routing
  metrics.
- `qhpc.iqm-job-receipt@1`: job ID, shots, timestamps, terminal state, and the
  routed-layout digest.
- `qhpc.iqm-raw-counts@1`: raw counts and explicit Qiskit bit ordering.
- `qhpc.ftqc-logical-result@1`: Steane Z-basis raw parity and classical
  single-X-error syndrome correction, with an explicit scientific claim
  boundary.

## Security and recovery checks

- Workflow parameters accept only a `secret://PROVIDER/IDENTIFIER` reference;
  a plaintext token and a caller-supplied `token` field are rejected.
- The resolved token is absent from target metadata, task logs, errors,
  receipts, and all output artifacts.
- A second runner instance adopts the preserved job handle without submitting
  a duplicate job.
- The adapter bounds shots to 4096, wait time to 30–7200 seconds, input to
  1 MB, provider responses to 2 MB, bitstring width to 64, and count outcomes
  to 4096.
- Exceeding the configured wait limit requests remote cancellation before the
  task fails.

## Command

```bash
.venv/bin/python -m pytest -q tests/test_iqm_runner.py
```

Result: `6 passed` (and `238 passed` for the complete Python suite).

## Remaining acceptance gate

A real qiskit-iqm client, site-approved endpoint and credential policy, and a
developer-approved hardware packet are still required. That packet must
preserve the exact device/calibration identity, job ID, timestamps, routed
layout, raw counts, corrected logical result, and an approved comparison rule.
