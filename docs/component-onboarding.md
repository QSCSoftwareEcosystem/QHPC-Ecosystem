# Component Onboarding

EQO can inspect an admitted public GitHub or GitLab repository and create a
reviewable integration draft. This is a source-discovery step, not a build or
deployment mechanism.

## Safety boundary

The onboarding controller accepts only HTTPS repository URLs from its public
host allowlist. It rejects credentials, query strings, fragments, non-default
ports, local paths, and arbitrary Git arguments. It resolves a branch, tag, or
advertised commit to an exact commit before producing a draft.

Inspection uses Git remote metadata and tracked file names. It does **not**:

- run repository code, hooks, installers, tests, or build recipes;
- accept, persist, or expose host credentials;
- create a runnable capability, OCI image, worker registration, or active
  runtime; or
- change the deployment profile, capability registry, or any existing
  revision.

The draft records the selected source URL, requested ref, resolved commit,
optional monorepo subdirectory, recognized project files, selected template,
and a proposed capability/runtime contract. Drafts are stored under the
configured component-onboarding state root.

## Workbench and server enablement

`eqo local up` enables the public-source inspection view and stores its state
under the EQO Local state directory. A standalone server must opt in:

```bash
eqo serve \
  --registry examples/registry.yaml \
  --deployment-profile deployments/initial.yaml \
  --enable-component-onboarding
```

The Workbench calls:

```text
GET  /api/v1/component-onboarding
POST /api/v1/component-onboarding/inspect
```

The inspect request is limited to `repository_url`, `ref`, `subdirectory`, and
`template`. Credentials, build commands, paths outside the selected
repository, runtime flags, and activation choices are not accepted.

## Admission remains separate

A draft remains `inspected` and its build state is `not-run`. Before a source
can become an EQO component, a future reviewed pipeline must build it in an
isolated environment without host credentials, run a relevant smoke test,
record an immutable image digest, publish a versioned capability contract, and
admit the resulting runtime. Repository updates then use the separate
controlled revision lifecycle documented in
[Repository Updates](repository-updates.md).
