# EQO Local

The `dev-local` branch contains the portable, single-user EQO distribution: the
Workbench, control API, local worker, and optional Assistant. The current
artifact is a release candidate; it is not signed or approved for publication.

## Build and install the release candidate

From a reviewed source checkout, build the candidate:

```bash
python tools/build_local_release.py
cd dist
shasum -a 256 -c SHA256SUMS
```

On Linux, `sha256sum -c SHA256SUMS` is an equivalent checksum command. The
release directory contains the wheel, checksum manifest, and
`EQO_LOCAL_SOFTWARE_INVENTORY.json`. The inventory is intentionally marked
`project-review-required` until its dependency and license entries are approved.

Install the wheel into a dedicated Python environment. The final filename is
printed by the build command:

```bash
python -m venv eqo-local
source eqo-local/bin/activate
python -m pip install './qhpc_ecosystem-0.1.0-py3-none-any.whl[local]'
```

On Windows, activate with `eqo-local\Scripts\activate` instead. Native launchers
and installers are deliberately deferred until this shared portable core has
passed its release gates.

For repository development, install the editable project instead:

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
hosts, conflicting service ports, insufficient or unknown storage, duplicate
supervisors, invalid state, and unverified stale process identifiers. Startup
requires at least 512 MiB free on the application-data volume. `status` reports
service health, the compatible local worker, release version, registry digest,
database path, artifact path, and supervisor log.

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

## Optional scientific runtimes

EQO Local starts and supports discovery without scientific runtimes. Install a
reviewed wheel or native ZIP only with its expected immutable reference and
SHA-256 digest:

```bash
eqo local runtime list
eqo local runtime install /path/to/runtime.whl \
  --reference qhpc-runtime://wheels/runtime.whl \
  --digest sha256:EXPECTED_DIGEST
eqo local runtime remove qhpc-runtime://wheels/runtime.whl
```

Installation verifies the digest before atomically placing the artifact in the
local runtime store. Existing content is not replaced unless `--replace` is
explicit. Removing a runtime does not remove workflow records or research
artifacts. The release candidate's included, optional, unavailable, and
license-blocked software is recorded in
[`release/eqo-local-software-inventory.json`](../release/eqo-local-software-inventory.json).

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

## Upgrade

Create a portable snapshot before installing a newer wheel:

```bash
eqo local down
eqo local export /path/to/pre-upgrade.eqo
python -m pip install --upgrade '/path/to/qhpc_ecosystem-VERSION-py3-none-any.whl[local]'
eqo local up
eqo local status
```

Keep the `.eqo` snapshot and any automatic database-upgrade backup until the
Workbench, run history, and artifacts have been checked. EQO refuses a database
schema newer than the installed application.

## Diagnostics and recovery

Print a support report or save it to a private file:

```bash
eqo local diagnose
eqo local diagnose eqo-diagnostic.json
```

The report includes platform and dependency availability, sanitized service
health, database integrity and schema, free storage, bundled Assistant identity,
and installed runtime digests. It does not include configuration values,
absolute local paths, log contents, service credentials, or research data.
Saved reports use owner-only file permissions where the operating system
supports them.

For a port conflict, stop the other listener or choose three distinct loopback
ports with `--port`, `--api-port`, and `--assistant-port`. An unavailable local
worker makes `status` report `unhealthy`. A missing optional runtime fails the
affected operation with its expected runtime reference; it does not prevent the
Workbench from starting. Failed database upgrades automatically restore the
pre-upgrade database and retain recovery evidence under the backup location.

## Building a release candidate

Produce a release candidate from the repository root with:

```bash
python tools/build_local_release.py
```

The release builder performs a clean `npm ci`, TypeScript validation, frontend
unit tests, and a production Workbench build. It refuses to package when that
build differs from the committed frontend assets. It then runs the complete
Python suite, builds the wheel without resolving unreviewed dependencies, and
writes the wheel, software inventory, and `SHA256SUMS` under `dist/`. GitHub
Actions repeats the installed-wheel start, health, stop, and offline restart
lifecycle outside the checkout on supported macOS and Linux runners.

## Uninstall

Stop the application, preserve an export, and uninstall the Python package:

```bash
eqo local down
eqo local export /path/to/final-state.eqo
python -m pip uninstall qhpc-ecosystem
```

Uninstalling the package deliberately retains application data, exports,
backups, logs, and optional runtimes. After verifying the final export, those
locations may be moved to the operating system's Trash using the paths reported
by `eqo local status`. They are never silently deleted by the uninstaller.

## Security and trust boundary

EQO Local is a single-user application, not a multi-user service. Its HTTP
services bind only to the local machine. The Assistant-to-API identity token is
generated for each supervisor process and is never written to configuration or
state. The bundled Assistant corpus is verified against its source revision,
license digest, page count, and content digest before use. Optional runtimes are
accepted only by expected SHA-256 digest, but project review is still required
before trusting or distributing third-party code.

Do not publish the loopback services through a proxy or port-forward them to a
shared network. Local logs and application data may describe research activity;
protect the user account and filesystem accordingly. Shared deployments require
TLS, institutional identity, authorization policy, managed secrets, and an
approved storage and audit design.

## Current boundary

The default Assistant uses the Apache-2.0 ChatQEC canonical corpus bundled in
the installed wheel. EQO verifies its source revision, license checksum, page
count, and corpus digest before starting the loopback service, so first start
and later restarts require no network access or source checkout. Developers may
still pass `--assistant-source-checkout` to test an exact-revision Git checkout.
Use `--no-assistant` when validating only the control plane.

Publication still requires project approval of the software inventory and
successful clean-host CI. Scientific runtimes remain separate, optional
artifacts until their own licensing, reproducibility, and target-acceptance
gates pass. Developer and author evidence for every cataloged tool is maintained
in [the attribution record](tool-attribution.md).
