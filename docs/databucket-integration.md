# databucket/Garage Integration

- Status: Working, not yet formally reviewed (no ADR backs this integration)
- databucket source: [naughtont3/databucket](https://github.com/naughtont3/databucket)
- Garage lifecycle wrapper: [`databucket_stack.py`](../src/qhpc_ecosystem/databucket_stack.py)
- S3 client: [`s3_client.py`](../src/qhpc_ecosystem/s3_client.py)
- Materials-db ingestion: [`materials_db_ingest.py`](../src/qhpc_ecosystem/materials_db_ingest.py)
- Control API routes: [`api.py`](../src/qhpc_ecosystem/api.py) (`/api/v1/data/objects`, `/api/v1/data/objects/content`)
- Data panel: [`workbench/app.js`](../src/qhpc_ecosystem/workbench/app.js) (`renderData`/`dataDetail`)
- Materials-db admission record (unaffected by this integration): [`qhpc-capability.yaml`](../capabilities/qsc-materials-db/schema/qhpc-capability.yaml)

## What this is

The `qsc-materials-db` capability was, until this integration, a purely
static admission record — the Data panel could show its declared
schema/provenance resources, but made no live storage calls (see the
capability record's own `guidance.limitations`). This integration gives the
Data panel a real, live backing store by wiring `eqo dev up` to
[databucket](https://github.com/naughtont3/databucket), a separate
docker-compose Garage/S3 service, without blending the two projects
together:

- **databucket/Garage** stays a generic S3 store — it has no knowledge of
  QHPC or materials-db. Nothing in this integration modifies databucket.
- **`databucket_stack.py`/`s3_client.py`** are QHPC-side, materials-db-agnostic:
  a Docker Compose lifecycle wrapper (mirrors
  [`slurm_test_cluster.py`](../src/qhpc_ecosystem/slurm_test_cluster.py)'s
  pattern) and a minimal hand-rolled SigV4 S3 client (no `boto3` dependency,
  matching the project's existing stdlib-only external-client convention —
  see [`assistant.py`](../src/qhpc_ecosystem/assistant.py)).
- **`materials_db_ingest.py`** is the only materials-db-aware piece: it
  uploads the two local static resources
  (`data-services/qsc-materials-db/materials-schema-v0.1.yaml` and
  `provenance-v0.1.yaml`) into the provisioned bucket. It does not fetch the
  external ORNL-hosted KCuF3 dataset payloads the capability record also
  references — that would be live-SDL integration, which stays explicitly
  out of scope.

## Prerequisite: databucket's `.env`

`dev up` does **not** run databucket's setup for you. Before using
`--databucket-checkout`, the checkout needs a generated `.env` (Garage's
admin token, webui auth, etc.) at its root, alongside its
`docker-compose.yml`:

```bash
cd /path/to/databucket
./scripts/setup.sh
./scripts/set-webui-user.sh <username>   # if not done already
```

`GarageStack.prepare()` checks for `<checkout>/.env` and raises a clear error
naming this script if it's missing. Everything after that — starting the
Garage containers, assigning the cluster layout, provisioning the
`materials-db` project (bucket + scoped key), and publishing the schema
files — happens automatically inside `dev up`.

## Using it with `eqo dev up`

```bash
eqo dev up --databucket-checkout /Users/3t4/projects/quantum/qscv2/repos/databucket-ecosystemdemo/databucket
```

Relevant flags (all on `eqo dev up`):

| Flag | Default | Effect |
|---|---|---|
| `--databucket-checkout PATH` | none | Path to a prepared databucket checkout. Required unless `--no-databucket`. |
| `--databucket-project NAME` | `materials-db` | Project name to provision; bucket is `proj-<name>`. |
| `--no-databucket` | off | Skip databucket entirely — Data panel's live section reports unavailable. |
| `--no-databucket-start` | off | Require Garage to already be running instead of auto-starting it. |
| `--stop-databucket-on-exit` | off | Run `docker compose down` on the databucket checkout when `dev up` exits. |

Credentials are generated/retrieved fresh on each `dev up` and passed to the
control API subprocess only via environment variables
(`QHPC_DATABUCKET_S3_ENDPOINT`, `_BUCKET`, `_ACCESS_KEY_ID`,
`_SECRET_ACCESS_KEY`) — the same injection pattern used for the ChatQEC
workload identity token. Nothing is written to disk.

## Testing just the Data panel, without `dev up`

`dev up` also starts the virtual Slurm test cluster and ChatQEC
unconditionally, which can require unrelated local setup (a trusted CA for
intercepted build traffic, pre-built `linux-amd64` operation-runtime images).
To exercise only the databucket-backed Data panel, run the control API and
Django Workbench directly instead, pointed at each other:

```bash
# terminal 1 — control API
cd /path/to/QHPC-Ecosystem
QHPC_DATABUCKET_S3_ENDPOINT="http://127.0.0.1:3900" \
QHPC_DATABUCKET_BUCKET="proj-materials-db" \
QHPC_DATABUCKET_ACCESS_KEY_ID="<key-id>" \
QHPC_DATABUCKET_SECRET_ACCESS_KEY="<secret-key>" \
./venv/bin/python -m qhpc_ecosystem.cli serve \
  --registry examples/registry.yaml \
  --deployment-profile deployments/initial.yaml \
  --host 127.0.0.1 --port 8081

# terminal 2 — Django workbench
cd /path/to/QHPC-Ecosystem
./venv/bin/python -m qhpc_workbench --host 127.0.0.1 --port 8080 --api-base http://127.0.0.1:8081
```

`proj-materials-db` and its key need to exist first — either from a prior
`eqo dev up --databucket-checkout ...` run, or by running
`./scripts/provision-project.sh materials-db` directly in the databucket
checkout. Either way, get `<key-id>`/`<secret-key>` from inside that checkout:

```bash
cd /path/to/databucket
docker compose exec garage /garage key info proj-materials-db-key --show-secret
```

Then open `http://127.0.0.1:8080/?view=data`, select the materials-db
capability, and check the "Live Object Storage (databucket)" section and the
"Live · N objects" badge on its card.

## API surface added

- `GET /api/v1/data/objects?prefix=<prefix>` — lists objects in the
  configured bucket. Returns `{"available": false, "reason": "..."}` (200)
  when databucket isn't configured, matching the existing
  `/api/v1/knowledge` convention.
- `GET /api/v1/data/objects/content?key=<key>` — downloads one object's
  bytes (`?download=1` forces an attachment `Content-Disposition`, mirroring
  `/api/v1/artifacts/<id>/content`). Returns 503 when databucket isn't
  configured. **The key must travel as a query parameter, not a path
  segment** — Django's `path("api/v1/<path:api_path>", ...)` proxy route
  decodes `%2F` back into a literal `/` before re-forwarding, so a
  slash-bearing key packed into a path segment breaks once it goes through
  the real proxy even though it works against the control API directly. Only
  the query string survives that round-trip unmodified.

## Known gaps

- No `boto3` dependency was added; the hand-rolled SigV4 client only
  implements `PUT`/`GET`/`ListObjectsV2` — enough for this integration, not a
  general-purpose S3 SDK.
- `eqo dev up` builds the virtual Slurm test cluster and verifies pinned
  `linux-amd64` operation-runtime images unconditionally, regardless of
  `--databucket-*` flags — on Apple Silicon this requires either pre-built
  amd64 images or `--no-target-worker`-style scoping that doesn't exist yet.
  This is a pre-existing gap in `dev up`, unrelated to databucket.
