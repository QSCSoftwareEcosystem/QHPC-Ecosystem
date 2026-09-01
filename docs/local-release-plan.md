# EQO Local Release Plan

- Status: Implementation in progress; release-mode lifecycle implemented
- Branch: `dev-local`
- Initial release target: portable local EQO
- Future deployment target: shared server or cloud profile

## Purpose

The first EQO release will be a portable local distribution that a researcher
can install and operate on a laptop or workstation without deploying a shared
institutional service. The local release must preserve the same API, contracts,
workflow records, runtime identities, and provenance model intended for the
future server deployment.

The local release is a production-quality single-user research distribution.
It is not a claim of multi-user DOE service readiness or HPC target acceptance.

## Branch And Release Model

The repository uses these long-lived branches:

| Branch | Responsibility |
| --- | --- |
| `main` | Stable, released EQO code only |
| `dev-local` | Portable local release development and stabilization |
| `dev` | Future shared server and cloud deployment development |

The first release follows this promotion path:

```text
main
  ├── dev-local ── portable implementation ── pull request ──> main
  │                                                        tag local release
  └── dev ──────── shared-service development <──────────── back-merge main
```

Portable improvements to shared contracts, the Workbench, API, CLI, data
migrations, and provenance must be forwarded from `dev-local` into `dev`.
Cloud-specific work may remain on `dev`, but it must not create a second EQO
product or an incompatible API.

## Product Shape

EQO Local is a small local appliance rather than a static webpage. The browser
interface remains a client of the same versioned API used by the CLI.

```text
Workbench / installable browser interface
                  |
             Versioned API
                  |
    +-------------+--------------+
    |             |              |
 local worker  local storage  local ChatQEC
                  |
        optional operation runtimes
```

The initial local profile contains:

- compiled EQO Workbench assets;
- the EQO control API and CLI;
- a separately supervised local worker;
- the pinned canonical-corpus ChatQEC development service;
- SQLite orchestration state;
- filesystem artifact storage;
- a versioned local deployment profile and admitted registry snapshot; and
- optional, separately distributed scientific operation runtimes.

## User Experience

The release should expose production-named commands rather than requiring the
development supervisor interface:

```text
eqo local up
eqo local status
eqo local open
eqo local export
eqo local import
eqo local down
```

`eqo local up` should initialize the data directory, apply migrations, start
and health-check the Workbench, API, worker, and Assistant, and open or print
the local URL. Users should not need to understand individual service
processes or development ports.

`eqo local status` should report service health, compatible worker readiness,
registry identity, database schema version, artifact location, Assistant
corpus revision, and installed operation runtimes.

## Packaging Strategy

The recommended first distribution is:

1. a versioned Python wheel containing the CLI, API, migrations, contracts,
   local profiles, and compiled Workbench assets;
2. a Docker Compose and Podman Compose compatible service bundle where
   containerized service operation is available;
3. checksums, dependency and license inventories, and release notes; and
4. optional operation-runtime packages distributed only when their source and
   redistribution terms permit publication.

An Electron or other large desktop wrapper is not required for the first
release. A small launcher plus an installable browser experience keeps the
local product close to the future server architecture and reduces the number
of platform-specific release artifacts.

## Portability Requirements

The first supported hosts should be current macOS and Linux systems. Windows
support may follow after the service and filesystem assumptions are validated.

The local control plane must:

- avoid hard-coded repository checkouts and absolute developer paths;
- use an operating-system-appropriate persistent application-data directory;
- make the API origin and browser URL configurable;
- detect port conflicts and support an explicit port override;
- run without network access after required packages and runtimes are present;
- preserve state across service restarts and software upgrades;
- provide schema-managed database migrations;
- provide a complete export/import format independent of SQLite internals;
- distinguish application data, cache, logs, temporary work, and user exports;
- report actionable failures when a required runtime or compatible worker is
  absent; and
- never expose credentials or unrestricted host paths through workflows.

## Portable State Bundle

`eqo local export` should create a versioned portable bundle containing:

- workflow drafts and immutable published workflow versions;
- resolved registry and deployment-profile identities;
- runs, tasks, attempts, events, logs, and provenance;
- artifact metadata, payload checksums, and selected payloads;
- configuration that is safe to transfer; and
- a manifest describing the EQO release and schema versions required to import
  the bundle.

Secrets, local credentials, machine-specific paths, mutable caches, and
unapproved operation images must not be included. Import must validate the
manifest and migrate supported older schema versions rather than copying a
database file blindly.

## Scientific Runtime Boundary

Portability of the Workbench and control plane does not imply portability of
every scientific operation runtime.

- Current operation images are Linux runtimes and may require `linux/amd64`.
- Apple Silicon hosts may require a compatible image or an explicitly supported
  emulation path.
- License-blocked runtimes must not be bundled with the EQO release.
- Operation runtimes retain their immutable identities, fixed entrypoints,
  declared mounts, and controlled output boundaries.
- The local release must run successfully without optional scientific images
  and clearly identify which workflows require them.

## Implementation Work Packages

### 1. Release-mode lifecycle

- [x] Add the `eqo local` command group.
- [x] Define stable startup, health, shutdown, and failure behavior for
  `up`, `status`, `open`, and `down`.
- [x] Separate the local API, Workbench, Assistant, and local worker from the
  developer-only virtual Slurm fixture and repository-update controller.
- [x] Prevent duplicate supervisors and refuse ambiguous stale process IDs.
- [ ] Add `export` and `import` after the portable state schema is implemented.

### 2. Configuration and paths

- [x] Introduce a versioned local configuration profile and runtime-state
  document without persisted service credentials.
- [x] Make loopback service ports and the optional Assistant source checkout
  configurable while retaining loopback-only local security.
- [x] Define stable macOS and XDG configuration, application-data, cache,
  artifact, runtime, export, state, and log paths.
- [x] Support and document `EQO_HOME` and `--home` as explicit portable-root
  overrides.

### 3. Built Workbench distribution

- [x] Package the compiled Workbench together with a versioned catalog,
  registry, deployment profile, workflows, and Assistant interface.
- [x] Serve the packaged Workbench through the local application boundary.
- [x] Support a configurable API endpoint without embedding credentials.
- [x] Validate an installed wheel from outside the source checkout without
  requiring Node.js on the user's machine.
- [ ] Automate a clean frontend rebuild before producing release artifacts.

### 4. Persistence and migration

- Package and apply schema migrations automatically.
- Add migration rollback or backup behavior for failed upgrades.
- Implement portable export and import.
- Verify restart, upgrade, backup, corruption-detection, and restore paths.

### 5. Service and runtime packaging

- Produce signed or checksummed release artifacts.
- Provide Docker and Podman compatible definitions where practical.
- Define optional runtime installation and removal.
- Generate dependency, license, and software-inventory evidence.

### 6. Cross-platform acceptance

- Test a clean installation on supported macOS and Linux hosts.
- Test Apple Silicon and `linux/amd64` runtime behavior explicitly.
- Verify offline restart after installation.
- Verify port-conflict, missing-runtime, missing-worker, and insufficient-storage
  error states.
- Verify export on one supported host and import on another.

### 7. Documentation and support

- Publish installation, upgrade, backup, restore, and uninstall instructions.
- Document the local security and trust boundary.
- State which runtimes are included, optional, unavailable, or license-blocked.
- Provide a diagnostic report suitable for support without exposing secrets.

## Local Release Gates

The first local release is ready to merge into `main` when:

- installation succeeds on every supported clean host;
- `eqo local up`, `status`, `open`, `export`, `import`, and `down` pass their
  acceptance tests;
- the Workbench, CLI, and API operate from the same contracts and registry;
- the release contains no developer checkout assumptions or tracked private
  planning content;
- state survives restart and a tested release upgrade;
- export/import preserves workflows, run history, provenance, and checksums;
- optional or unavailable runtimes fail clearly without breaking discovery;
- all automated unit, contract, frontend, and local end-to-end suites pass;
- release artifacts include checksums and approved dependency/license
  inventories; and
- documentation clearly separates local evidence from DOE target acceptance.

## Future Server Migration

The later shared deployment should use the same Workbench build, CLI semantics,
API contracts, workflow definitions, runtime identities, and export format.
Deployment adapters change as follows:

| Local release | Future shared deployment |
| --- | --- |
| Local API origin | TLS service endpoint |
| SQLite | PostgreSQL |
| Filesystem artifact store | Approved shared or object storage |
| Single-user local trust | Institutional identity and workspace policy |
| Local worker | Separately deployed service and HPC workers |
| Local secret references | Approved workload identity and secrets provider |
| Local canonical ChatQEC | Production model-backed ChatQEC service |
| Local logs | Central logs, metrics, traces, and audit retention |

The cloud implementation must consume portable local exports through supported
application-level import and migration. It must not depend on copying local
SQLite files or machine-specific artifact paths.

## Non-Goals For The First Release

The local release does not require:

- institutional multi-user identity or workspace administration;
- PostgreSQL or a shared artifact service;
- a DOE-hosted Slurm/Apptainer target;
- target-accepted scientific SIFs;
- a production generative ChatQEC model service;
- warm-pilot allocation on a facility system;
- collaborative real-time workflow editing; or
- production security and operations authorization.

Those remain requirements for `dev` and the future shared-service release, not
blockers for a safe and useful portable local release.
