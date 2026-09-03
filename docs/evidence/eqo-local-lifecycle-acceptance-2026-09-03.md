# EQO Local lifecycle acceptance — 2026-09-03

## Scope

This local acceptance exercised the portable release lifecycle on macOS with
an Apple Silicon host. It used an isolated temporary `EQO_HOME` and distinct
loopback ports rather than developer state.

## Result

- `eqo local up` reached `ready` with the Workbench, API, Assistant, and
  `eqo-local-worker` healthy.
- The bundled Assistant reported the pinned ChatQEC revision
  `a1ddc2e4916b1f4152fba4c94c9c7512eea0d977`, 60 canonical pages, and corpus
  digest `sha256:95e43b52660f4789457ef54b0b5c3ffc557b0610e24fc4780ed709c800928330`.
- The Assistant created no Git checkout and required no source preparation.
- `eqo local diagnose` completed without including service credentials or local
  absolute paths.
- `eqo local down` stopped the supervisor and child services.
- A second `eqo local up` against the same application home returned to
  `ready`; the second `down` completed normally.

## Boundary

This is local evidence, not DOE target-system acceptance. Clean-host macOS and
Linux installed-wheel coverage is defined in `.github/workflows/eqo-local.yml`
and must pass after the branch is pushed. Windows launcher work remains a later
milestone.
