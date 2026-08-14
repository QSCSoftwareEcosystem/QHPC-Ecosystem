# Workbench Typed Composer Smoke Evidence

- Date: 2026-07-28
- Scope: local development only
- Workbench: Django 5.2.16 with fixed-origin QHPC API proxy
- Composer: React 19 and React Flow 12
- Execution fixture: supervised local and virtual-Slurm workers

## Behavior Verified

The browser loaded the approved QSC Workbench shell and mounted the typed
composer only in the Compose view. At both 1440 by 1000 and 390 by 844 browser
dimensions it:

1. Loaded deployment-admitted operations, published templates, and owned
   drafts from the control API.
2. Presented three complete scientific paths in Guided mode by default.
3. Loaded an OpenQASM 2 circuit from a local `.qasm` file and issued the
   expected typed-artifact and `ct-hw-qasm-analysis@0.1.0` submission payloads
   with the `development-slurm-docker` target. The browser test intercepts
   those two mutating responses; API integration is covered by the Python
   suite.
4. Displayed each path's connected operations, immutable workflow identity,
   published parameters, and produced artifact contracts.
5. Opened the QASMTrans plus STABSim path in Advanced mode as two connected
   operation nodes with one input and two output boundaries.
6. Added an OpenQEvo operation to the Advanced canvas.
7. Exposed its declared `qhpc.method-catalog@1` output as a workflow boundary.
8. Saved the editing resource as a revisioned `WorkflowDraft`.
9. Validated the canonical workflow through the server and confirmed the draft
   through the proxied API.

The operation library closes after a selection at narrow widths so the canvas
becomes the primary surface. Desktop and mobile screenshots were inspected for
blank rendering, clipping, and incoherent overlap.

## Contract And Security Checks

- Four representative workflow examples round-trip through canvas conversion
  without changing the canonical workflow document.
- Client validation rejects cycles, artifact-type mismatches, duplicate input
  connections, required disconnected inputs, and orphaned workflow boundaries.
- Draft create, read, revisioned update, delete, validate, and publish routes
  pass engine and API tests.
- Django enforces CSRF on mutating proxied requests and has no engine or SQLite
  import.
- Artifact content is limited to resolved files under the configured artifact
  root and is rechecked against stored size and SHA-256 before preview or
  download.

## Commands And Results

```text
.venv/bin/python -m pytest -q
154 passed, 1 skipped in 20.40s

.venv/bin/python -m pytest -q tests/test_api.py
2 passed in 0.80s

npm run check --prefix workbench/frontend
passed

npm test --prefix workbench/frontend
7 passed

npm run test:e2e --prefix workbench/frontend
6 passed

npm run build --prefix workbench/frontend
passed

npm audit --prefix workbench/frontend
0 vulnerabilities
```

The one default-suite skip is the managed sandbox restriction on binding a
localhost test socket. The same API test passed with localhost binding enabled.
This evidence does not represent DOE identity, shared persistence, production
artifact storage, target Apptainer acceptance, accessibility certification, or
security authorization.
