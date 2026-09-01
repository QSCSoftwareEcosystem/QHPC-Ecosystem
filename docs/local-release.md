# EQO Local Lifecycle Preview

The `dev-local` branch contains the first executable part of the portable EQO
release: a production-named, single-user lifecycle for the Workbench, API,
local worker, and optional Assistant. It is a development preview and not yet a
signed release artifact.

Install the project and its local Workbench dependency in an isolated Python
environment:

```bash
python -m pip install -e '.[local]'
```

Start EQO Local in the background and inspect it:

```bash
eqo local up
eqo local status
eqo local open
eqo local down
```

By default, EQO binds only to loopback addresses. It refuses non-loopback
hosts, conflicting service ports, duplicate supervisors, invalid state, and
unverified stale process identifiers. `status` reports service health, the
compatible local worker, release version, registry digest, database path,
artifact path, and supervisor log.

## Portable paths

On macOS, EQO uses the appropriate `Library/Application Support`, `Caches`, and
`Logs` locations. On Linux it follows the XDG configuration, data, cache, and
state variables. Set `EQO_HOME` or pass `--home` to keep every local path under
one explicit root:

```bash
eqo local up --home /path/to/eqo-local
eqo local status --home /path/to/eqo-local
eqo local down --home /path/to/eqo-local
```

The versioned configuration and runtime-state documents contain no generated
Assistant identity token. Runtime identity is generated inside the detached
supervisor and scoped only to the API and Assistant processes.

## Backup and restore

Stop EQO Local, then create a portable backup:

```bash
eqo local down
eqo local export
```

The default destination is the EQO Local exports directory reported by
`status`. An explicit destination can be supplied when the bundle needs to be
placed on removable or shared storage:

```bash
eqo local export /path/to/research-state.eqo
```

The `.eqo` archive contains a versioned manifest, logical application records,
and checksum-verified artifact payloads. It preserves workflow drafts,
published workflows, terminal run history, tasks, attempts, events, logs, and
artifact provenance. It does not copy SQLite internals, service credentials,
worker heartbeats, machine-specific paths, caches, or installed scientific
runtimes. Export refuses nonterminal runs; finish or cancel them before
creating a portable snapshot.

Restore into an empty EQO Local home with:

```bash
eqo local import /path/to/research-state.eqo
```

Import validates the manifest, schema versions, declared members, logical
relationships, payload sizes, and SHA-256 checksums before installing any
state. Artifact locations are rewritten for the destination machine and a
fresh current-schema database is constructed through the application model.

If the destination already contains state, import refuses to overwrite it.
Use `--replace` only when replacement is intentional:

```bash
eqo local import /path/to/research-state.eqo --replace
```

Replacement first moves the previous database and artifact tree into the
timestamped backup directory printed by the command. Keep the original `.eqo`
archive until the restored Workbench and artifacts have been verified.

## Database upgrades

EQO checks the database schema and integrity before starting any local service.
When an installed release needs to upgrade an existing schema, it first creates
a consistent SQLite backup under the EQO Local `backups` directory. The backup
includes an `upgrade.json` record with the source and destination schema
versions and checksums.

After migration, EQO verifies the expected schema version and runs SQLite's
integrity check. If either migration or verification fails, the modified
database is retained for diagnosis and the pre-upgrade database is restored
automatically. `eqo local status` reports the active database schema and the
most recent backup created by that startup.

## Building a release candidate

Produce a release candidate from the repository root with:

```bash
python tools/build_local_release.py
```

The release builder performs a clean `npm ci`, TypeScript validation, frontend
unit tests, and a production Workbench build. It refuses to package when that
build differs from the committed frontend assets. It then runs the complete
Python suite, builds the wheel without resolving unreviewed dependencies, and
writes the wheel and `SHA256SUMS` under `dist/`.

## Current boundary

The default Assistant preparation still needs access to the pinned ChatQEC
source on the first run. Use `--no-assistant` when validating the control plane
without it. Bundled offline Assistant data, installers, dependency and license
inventories, and cross-platform release acceptance remain subsequent
`dev-local` milestones.
