# Repository Updates

- Status: Implemented for controlled discovery, staging, and opt-in candidate build evidence
- Last updated: 2026-10-30
- Decision: [ADR 0011](adr/0011-controlled-repository-updates.md)

The update controller tracks both components admitted by the selected
deployment profile and registry, and explicitly locally admitted component
revisions produced by repository onboarding. Those remain separate activation
domains. The controller never pulls code into a running container or changes
an active runtime digest.

## CLI

The initial deployment and registry are the defaults:

```bash
eqo updates list
eqo updates check
eqo updates check stabsim chatqec
eqo updates stage stabsim
eqo updates build qasmtrans
eqo updates discard stabsim
```

Locally admitted onboarding components use a namespaced ID so they cannot be
confused with deployment components:

```bash
eqo updates list
eqo updates check onboarding:my-component
eqo updates stage onboarding:my-component
eqo updates discard onboarding:my-component
```

The locally admitted component state root defaults to
`.qhpc/component-onboarding`; override it with
`--component-onboarding-state-root` when the onboarding service uses a
different state directory.

Use `--json` on any command for automation. `stage --revision <full-commit>`
adds an optimistic check: staging fails if that commit is no longer the
configured remote ref. Git authentication must already be available through a
credential helper or SSH configuration; commands disable terminal prompts.

`eqo updates build COMPONENT` only works after **stage**, and only when the
component's reviewed operation-runtime contract explicitly declares a
`candidate_rebuild` policy. EQO writes a separate build-ready candidate
contract from the staged commit, builds with `--network none`, and smoke-tests
the resulting local image with no network, read-only root filesystem, dropped
capabilities, and no-new-privileges. It records only bounded digest and output
evidence. It never replaces the active contract, registry entry, image digest,
or worker runtime.

## Workbench

The **Updates** view calls the same controller through:

```text
GET  /api/v1/repository-updates
POST /api/v1/repository-updates/check
POST /api/v1/repository-updates/stage
POST /api/v1/repository-updates/build
POST /api/v1/repository-updates/discard
```

The Django fixed-origin proxy supplies the Workbench CSRF boundary. Check
requests accept only an optional component-ID list. Stage requests accept only
`component_id` and `candidate_revision`; build and discard accept only
`component_id`.
Repository locations and tracked refs come from server-side admitted records.
When a capability release predates a repository move, the response reports the
canonical update repository separately from `current_repository_url`, which
preserves the source of the active release.

Each listed component also reports the immutable runtime identities used by its
published operations. Once a candidate is prepared, EQO reads its commit date
and subject from the verified detached checkout and records bounded lifecycle
evidence (`checked`, `prepared`, `build-succeeded`, `build-failed`, and
`discarded`). A successful deployment candidate build records the isolated
local image ID, candidate-contract digest, source-archive digest, smoke-test
duration, and checksums of declared smoke outputs. This makes source revision,
active runtime digest, and the preparation decision visible together without
claiming that a source commit has been activated.

For an onboarding component, **prepare** means that an immutable successor
source draft has been retained for review, not that a detached deployment
checkout was created. Its next action is an isolated build and smoke test in
the Components view, followed by a separate explicit local admission. Discard
never modifies the currently active local image; it preserves the candidate's
audit evidence and allows a later explicit re-prepare.

Standalone `serve` processes expose these operations only with
`--enable-repository-updates`. `eqo dev up` enables them using
`.qhpc/live/updates` unless `--no-repository-updates` is supplied.

## Opt-In Upstream Detection

An operator can request periodic discovery checks without granting any update
or deployment action:

```bash
eqo serve \
  --registry examples/registry.yaml \
  --deployment-profile deployments/initial.yaml \
  --enable-repository-updates \
  --repository-update-poll-seconds 3600
```

The interval must be at least 30 seconds. A check updates the candidate
listing only; it cannot prepare a checkout, rebuild an image, activate a
component, or alter a running worker.

For event-driven discovery, enable a provider separately and keep its secret
in a local file rather than a command line or environment variable:

```bash
eqo serve \
  --registry examples/registry.yaml \
  --deployment-profile deployments/initial.yaml \
  --enable-repository-updates \
  --github-webhook-secret-file /secure/path/github-webhook-secret \
  --gitlab-webhook-signing-token-file /secure/path/gitlab-webhook-token
```

The optional endpoints are `POST /api/v1/repository-updates/webhooks/github`
and `POST /api/v1/repository-updates/webhooks/gitlab`. GitHub requests must
use a valid `X-Hub-Signature-256` HMAC-SHA256 signature over the exact raw
request body. GitLab requests use its Standard Webhooks signature headers and
a `whsec_` signing token; stale signatures are rejected. Only push events
trigger a coalesced discovery check. Other correctly signed events receive a
202 response marked `ignored`; unsigned, invalid, stale, and disabled
endpoints fail closed. EQO does not expose these routes outside the serving
host: TLS termination, an authenticated reverse proxy, and provider delivery
configuration remain the operator's responsibility.

## State And Checkouts

The controller stores:

```text
.qhpc/updates/
  state.json
  checkouts/<component>/<full-commit>/
  runtime-contracts/<component>/<full-commit>/runtime.json
```

State writes are process-locked and atomic. A prepared checkout must have the
expected origin, exact detached `HEAD`, and no tracked or untracked changes.
Existing mismatched or dirty candidate directories fail closed.

Lifecycle evidence is intentionally bounded to the 50 most recent events per
component and contains no credentials, build logs, or provider tokens. A
candidate runtime contract is a local, build-ready artifact: it contains the
staged source archive digest and timestamp while preserving the reviewed
recipe, fixture, static context, and base-image pins. Older state files are
migrated in place when the controller next writes them.

The TN-Sim deployment source explicitly tracks `refs/heads/tn_sim`; ordinary
repository URLs track the remote `HEAD`. A remote branch move between check and
fetch is detected and staging must be repeated.

STABSim tracks `QSCSoftwareThrust/STABSim` at the same commit as its admitted
release. LightStim also tracks its QSC repository; revision
`23924ee997a27af7a0aa17623357bf8bc7170625` was rebuilt and locally requalified
on 2026-09-03. Future LightStim candidates still require rebuild and
requalification rather than a metadata-only source substitution.

## Activation Boundary

Preparing an update answers: "Which exact source revision should we evaluate?"
It does not answer: "Which runtime may execute production workflows?"

For an operation provider with an explicit candidate-rebuild policy, the
controlled local build covers steps 1–3 only for its declared OCI smoke check.
Activation still requires:

1. review the candidate OCI build and its bounded smoke evidence;
2. run any adapter, integration, and virtual-Slurm checks not represented by
   the runtime's smoke fixture;
3. produce required license and supply-chain evidence;
4. publish and repin the capability, runtime manifest, and registry together;
   and
5. restart or roll workers only after the new digest is admitted.

Service and knowledge-resource candidates require their corresponding review,
registry republication, and controlled restart. The active deployment remains
on the previous known revision until those gates finish.
