# Component Onboarding

EQO can inspect an admitted public GitHub or GitLab repository, create a
reviewable integration draft, and explicitly build that already-pinned draft
for evidence. Neither action deploys or activates a component.

## Safety boundary

The onboarding controller accepts only HTTPS repository URLs from its public
host allowlist. It rejects credentials, query strings, fragments, non-default
ports, local paths, and arbitrary Git arguments. It resolves a branch, tag, or
advertised commit to an exact commit before producing a draft.

Inspection uses Git remote metadata and tracked file names. It does **not**:

- run repository code, hooks, installers, tests, or build recipes;
- accept, persist, or expose host credentials;
- create a runnable capability, worker registration, or active runtime; or
- change the deployment profile, capability registry, or any existing
  revision.

The draft records the selected source URL, requested ref, resolved commit,
optional monorepo subdirectory, recognized project files, likely entrypoint
file names, selected template, and a proposed capability/runtime contract.
Drafts are stored under the configured component-onboarding state root.

## Explicit isolated build

For a draft whose selected context contains `Dockerfile` or `Containerfile`,
the **Build in isolation** action creates a temporary detached worktree at the
resolved commit and invokes Docker with an empty client configuration. The
build has no network, does not receive credentials or an SSH agent, and does
not receive a host bind mount beyond the temporary build context. EQO retains
only bounded build output, detected entrypoint file names, the local immutable
image identity, produced-image reference, and constrained smoke-test result.

The smoke test runs the built image with no network, read-only root filesystem,
all Linux capabilities dropped, no-new-privileges, a non-root user, and bounded
CPU, memory, process count, and wall time. A failed build or smoke test remains
blocked and never changes an active runtime. The image is deliberately not
published, added to the registry, or assigned to any worker by this action.

Because a Docker daemon is part of the local trusted computing base, this is a
developer-local admission gate rather than a substitute for a separately
hardened remote build service. Builds require already available base images:
the network-disabled build does not fetch them.

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
POST /api/v1/component-onboarding/drafts/{id}/build
```

The inspect request is limited to `repository_url`, `ref`, `subdirectory`, and
`template`. The build request accepts no user fields. Credentials, build
commands, paths outside the selected repository, runtime flags, and activation
choices are not accepted.

## Admission remains separate

A draft moves to `built` only after its isolated build and constrained smoke
test pass. It is then **ready for admission**, not active. Before a source can
become an EQO component, a reviewer must still publish a versioned capability
contract, repin the deployment and registry to the resulting immutable image,
and admit the runtime through the worker lifecycle. Repository updates then use
the separate controlled revision lifecycle documented in
[Repository Updates](repository-updates.md).
