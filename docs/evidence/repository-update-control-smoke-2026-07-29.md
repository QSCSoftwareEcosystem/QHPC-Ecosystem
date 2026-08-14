# Repository Update Control Smoke Evidence

- Date: 2026-07-29
- Scope: local control-plane behavior only
- Components represented: 10

## Verified behavior

- The CLI and HTTP API derive the same update targets from
  `deployments/initial.yaml` and `examples/registry.yaml`.
- A real read-only upstream check resolved the configured NWQEC `HEAD` and
  reported the pinned revision as up to date.
- The QSCSoftwareThrust STABSim mirror resolves to the exact admitted revision,
  so its canonical, update, and current release repository are the QSC mirror.
- The QSCSoftwareThrust LightStim mirror is the canonical update repository,
  while the current qualified release continues to identify its QuTone source
  revision. The newer QSC revision is reported as an update candidate and is
  not activated without rebuild and validation.
- Candidate preparation accepts only a full commit hash returned for the
  admitted repository and tracked ref.
- Prepared source uses a clean detached checkout addressed by the exact commit.
- Discard clears the selected candidate without activating source or deleting
  the immutable checkout cache.
- Browser requests can select only component IDs and returned commit hashes;
  repository URLs, refs, paths, credentials, and Git arguments are rejected.
- The live Workbench Updates view rendered all ten components at desktop and
  mobile dimensions without horizontal overflow.

## Verification results

```text
Python suite:                  165 passed
Frontend unit tests:            7 passed
TypeScript check:               passed
Repository-update Playwright:   4 passed
Broader Workbench Playwright:  11 passed, 1 existing animation check failed
```

The Python result combines 161 non-Django tests in the hydrated system
environment and 4 Django Workbench tests in the project virtual environment.
This split avoids a OneDrive placeholder delay in the virtual environment's
`pip wheel` subprocess without excluding any test.

## Activation boundary

This smoke test does not activate a candidate. Operation-provider updates still
require runtime rebuild, scientific validation, digest publication, evidence,
and explicit promotion. Service and resource updates still require their
documented review and republishing or restart gates.
