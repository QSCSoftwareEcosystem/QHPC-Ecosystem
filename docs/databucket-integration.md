# Optional databucket/Garage mirror

- Status: Optional development integration
- Canonical data source: [DataSchema `tag-20260924`](https://github.com/QSCSoftwareEcosystem/DataSchema/tree/tag-20260924)
- databucket source: [QSCSoftwareEcosystem/databucket](https://github.com/QSCSoftwareEcosystem/databucket)
- Garage lifecycle wrapper: [`databucket_stack.py`](../src/qhpc_ecosystem/databucket_stack.py)
- DataSchema mirror publisher: [`dataschema_mirror.py`](../src/qhpc_ecosystem/dataschema_mirror.py)
- Data capability: [`qhpc-capability.yaml`](../capabilities/qsc-materials-db/schema/qhpc-capability.yaml)

## Storage model

The tagged public DataSchema release is the default and authoritative source.
Without databucket, Garage, or another local data checkout, the Workbench Data
panel opens each declared resource on its canonical GitHub page. Download
actions appear only for resources present in the configured object-storage
mirror.

databucket/Garage is an optional S3 transport for the same immutable resources.
Each resource declares one `source_path`, one `storage_key`, and one SHA-256
digest. When a matching object is present in the configured bucket, Workbench
uses it for Download; Open continues to show the canonical tagged GitHub page.
The optional mirror does not introduce a second catalog or data model.

## Enable and seed the mirror

Clone both repositories once, then prepare the databucket checkout using its
setup script:

```bash
cd /path/to/repos
git clone git@github.com:QSCSoftwareEcosystem/databucket.git
git clone git@github.com:QSCSoftwareEcosystem/DataSchema.git

cd databucket
./scripts/setup.sh
```

Start the development stack with both checkouts explicitly supplied:

```bash
eqo dev up \
  --stop-cluster-on-exit \
  --stop-databucket-on-exit \
  --databucket /path/to/repos/databucket \
  --databucket-seed-source /path/to/repos/DataSchema
```

With both stop flags, pressing Ctrl-C (or a failed startup) also stops the
development cluster and databucket Compose services. Their named volumes are
preserved.

`--databucket` opts into Garage using the supplied checkout. The older
`--databucket-checkout` spelling remains an alias. `--databucket-seed-source` is
optional and publishes the declared resources from a local DataSchema checkout
after verifying every digest. A checkout at tag `tag-20260924` (commit
`808e79f313376528aa40bf8f19279d0021360d0d`) satisfies the current contract.
No DataSchema files are cached in this repository.

Relevant `eqo dev up` flags:

| Flag | Default | Effect |
|---|---|---|
| `--databucket PATH` | none | Enable Garage using a prepared databucket checkout. |
| `--databucket-seed-source PATH` | none | Verify and upload the declared DataSchema resources from this checkout. |
| `--databucket-project NAME` | `materials-db` | Provision bucket `proj-<name>`. |
| `--no-databucket-start` | off | Require the opted-in Garage stack to already be running. |
| `--stop-cluster-on-exit` | off | Stop the development cluster when the supervisor exits. |
| `--stop-databucket-on-exit` | off | Stop the opted-in Garage stack when the supervisor exits. |

Without `--databucket`, no Garage process is started, no credentials
are required, and the Data panel does not display an unavailable-storage
placeholder.

Credentials are passed only to the control API subprocess through
`QHPC_DATABUCKET_*` environment variables. They are not written to this
repository.

## API surface

- `GET /api/v1/data/objects?prefix=<prefix>` lists objects in the optional
  configured bucket.
- `GET /api/v1/data/objects/content?key=<key>` retrieves one object;
  `?download=1` forces an attachment response.

Object keys stay in query parameters because slash-bearing keys cannot safely
round-trip through the Django catch-all proxy as encoded path segments.

The S3 client intentionally implements only the operations needed here:
`PUT`, `GET`, and `ListObjectsV2`. It is not a general-purpose S3 SDK.
