# Repository Updates

- Status: Implemented for controlled discovery and source staging
- Last updated: 2026-07-29
- Decision: [ADR 0011](adr/0011-controlled-repository-updates.md)

The update controller tracks only components admitted by the selected
deployment profile and registry. It never pulls code into a running container
or changes an active runtime digest.

## CLI

The initial deployment and registry are the defaults:

```bash
eqo updates list
eqo updates check
eqo updates check stabsim chatqec
eqo updates stage stabsim
eqo updates discard stabsim
```

Use `--json` on any command for automation. `stage --revision <full-commit>`
adds an optimistic check: staging fails if that commit is no longer the
configured remote ref. Git authentication must already be available through a
credential helper or SSH configuration; commands disable terminal prompts.

## Workbench

The **Updates** view calls the same controller through:

```text
GET  /api/v1/repository-updates
POST /api/v1/repository-updates/check
POST /api/v1/repository-updates/stage
POST /api/v1/repository-updates/discard
```

The Django fixed-origin proxy supplies the Workbench CSRF boundary. Check
requests accept only an optional component-ID list. Stage requests accept only
`component_id` and `candidate_revision`; discard accepts only `component_id`.
Repository locations and tracked refs come from server-side admitted records.
When a capability release predates a repository move, the response reports the
canonical update repository separately from `current_repository_url`, which
preserves the source of the active release.

Standalone `serve` processes expose these operations only with
`--enable-repository-updates`. `eqo dev up` enables them using
`.qhpc/live/updates` unless `--no-repository-updates` is supplied.

## State And Checkouts

The controller stores:

```text
.qhpc/updates/
  state.json
  checkouts/<component>/<full-commit>/
```

State writes are process-locked and atomic. A prepared checkout must have the
expected origin, exact detached `HEAD`, and no tracked or untracked changes.
Existing mismatched or dirty candidate directories fail closed.

The TN-Sim deployment source explicitly tracks `refs/heads/tn_sim`; ordinary
repository URLs track the remote `HEAD`. A remote branch move between check and
fetch is detected and staging must be repeated.

STABSim tracks `QSCSoftwareThrust/STABSim` at the same commit as its admitted
release. LightStim tracks `QSCSoftwareThrust/LightStim`, but its active release
retains QuTone revision `b08d4c2f9cd69531a51b658e6f88089be69f16c0`.
Consequently, a LightStim QSC candidate is an update requiring rebuild and
requalification, not a metadata-only source substitution.

## Activation Boundary

Preparing an update answers: "Which exact source revision should we evaluate?"
It does not answer: "Which runtime may execute production workflows?"

For an operation provider, activation still requires:

1. build a deterministic source archive from the prepared commit;
2. rebuild the component OCI image and record its immutable digest;
3. run adapter, fixture, local-container, and virtual-Slurm checks;
4. produce required license and supply-chain evidence;
5. repin the capability, runtime manifest, and registry together; and
6. restart or roll workers only after the new digest is admitted.

Service and knowledge-resource candidates require their corresponding review,
registry republication, and controlled restart. The active deployment remains
on the previous known revision until those gates finish.
