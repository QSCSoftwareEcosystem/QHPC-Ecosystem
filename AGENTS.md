# EQO agent guide

EQO is the QSC quantum-HPC ecosystem: a contract-first orchestration control
plane and Workbench. It connects **admitted** quantum/HPC operations through
typed artifacts, records provenance, and makes execution readiness explicit.
It does not replace scientific project tools with arbitrary notebook-side or
host-side calls.

## Start with the product and architecture

- Read `PRODUCT.md` before changing user-facing behavior. EQO must not
  overstate simulations, optional runtimes, hardware readiness, or facility
  acceptance.
- Read `docs/architecture.md` and the relevant ADR or contract documentation
  before changing execution boundaries or data flow.
- Main implementation areas:
  - `src/qhpc_ecosystem/`: CLI, registry, contracts, worker/runtime admission,
    local supervisor, and bundled assets.
  - `src/qhpc_workbench/`: Django Workbench and its browser-facing API.
  - `workbench/frontend/`: React/TypeScript Composer source. Its production
    assets are committed under `src/qhpc_workbench/static/qhpc_workbench/`.
  - `tests/`: Python unit and integration coverage.
  - `docs/`: operational and scientific boundary documentation.

Published workflows and runtime contracts are immutable evidence. Preserve
pinned digests, typed handoffs, preflight checks, and explicit `ready`,
`blocked`, `simulated`, or hardware-gated states. Do not bypass an admission
gate merely to make a demonstration succeed.

## Local development

Use Python 3.10+ and an isolated environment:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev,local]'
eqo local up --open
```

EQO Local needs Docker for its complete execution profile. On an HPC system
without a Docker daemon, use `USE_APPTAINER=1` only when the task explicitly
calls for the supported Apptainer path. `eqo local status` is the first check
when a local service or worker looks unavailable.

Optional capabilities are opt-in. ChatQEC can use an explicitly configured
model backend; IQM hardware execution requires an admitted endpoint, device
alias, compatible worker, and a credential. A successful HTTP health endpoint
does not alone prove that an optional model or hardware backend is usable.

## Validation

Run the narrowest relevant tests while iterating, then the appropriate suite
before handing off:

```bash
pytest
```

For Workbench frontend changes, Node.js `>=20.19.0` is required (CI uses Node
22). Rebuild the committed production assets and run the relevant checks:

```bash
npm ci --prefix workbench/frontend
npm run check --prefix workbench/frontend
npm test --prefix workbench/frontend
npm run build --prefix workbench/frontend
```

Run `npm run test:e2e --prefix workbench/frontend` when browser behavior or
workflow composition changed and the required browser dependencies are
available. State clearly which checks ran and any environment limitation.

## Security and shared deployments

- Never print, commit, log, place in command arguments, or put into notebooks
  any API key, IQM token, password, vault key, certificate private key, or
  authentication hash. Use prompt-based options or protected environment/key
  files outside the checkout.
- Do not expose the Workbench, API, Assistant, worker, or database ports
  directly. A shared deployment keeps EQO loopback-bound and exposes only a
  trusted, authenticated TLS proxy.
- Per-user IQM mode uses an operator-owned encryption key and a per-user
  encrypted vault. The browser may submit a new token but must never receive a
  stored token. The worker must derive the credential from the
  proxy-authenticated run owner, never from a workflow or browser-selected
  principal.
- A proxy must overwrite `X-EQO-Pilot-User` using its authenticated identity;
  never accept that header from a browser. With Caddy, preserve handler order
  using `route`, run `basic_auth` first, then use `reverse_proxy` with
  `header_up X-EQO-Pilot-User "{http.auth.user.id}"`.
- Treat internal pilot hosts as shared systems. Do not reboot them, stop
  unrelated services, prune images/volumes, or submit hardware work without
  the user's explicit instruction. Validate configuration changes before a
  restart and verify a spoofed identity header cannot change the effective
  principal afterward.
- Do not commit internal hostnames, IP addresses, account names, deployment
  paths, certificates, or any credentials into this repository. Obtain current
  deployment details from the user or the authorized environment at runtime.

## Git and workspace hygiene

- The active development branch is normally `dev-local`; do not merge into
  `main` or change branches without an explicit request. Confirm the actual
  branch before work.
- Keep changes focused. Preserve existing user edits and untracked files;
  specifically, do not stage ad-hoc notebooks or `.ipynb_checkpoints/` unless
  the user explicitly asks.
- `.development/` is intentionally ignored and is suitable for local plans,
  demos, and working notes. Move durable, shareable documentation into `docs/`
  or the repository root instead.
- When asked to commit, use the user's requested identity. The current project
  convention is `Vicente <vicenley@gmail.com>`; never use an AI-agent identity.
- Do not force-push, reset hard, or discard changes unless the user has clearly
  requested that exact action.
