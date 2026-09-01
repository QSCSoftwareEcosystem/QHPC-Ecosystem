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

## Current boundary

The default Assistant preparation still needs access to the pinned ChatQEC
source on the first run. Use `--no-assistant` when validating the control plane
without it. Bundled offline Assistant data, schema-managed export/import,
compiled release assets, installers, checksums, dependency inventories, and
cross-platform release acceptance remain subsequent `dev-local` milestones.
