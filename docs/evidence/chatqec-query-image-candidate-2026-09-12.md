# ChatQEC Query Image Candidate — 2026-09-12

## Scope

This records a local, Linux/amd64 **candidate** image for the containerized,
read-only ChatQEC query adapter. It is not a published or approved release.
No model-provider, IQM, registry, corpus, or user credential was used.

## Immutable inputs

| Input | Value |
| --- | --- |
| Upstream source revision | `a1ddc2e4916b1f4152fba4c94c9c7512eea0d977` |
| Git archive checksum | `sha256:1af97636073b031a2e859bd56e544ea2064c3b7af1ebf6af827202177a472718` |
| Upstream `uv.lock` checksum | `sha256:214fff8b9ffc463ecea2667a15436b6beb8cb8a20173667941003b891508a511` |
| Runtime base | `python:3.11.13-slim-bookworm@sha256:cec9aa7aa96eea4fa036e9b82be1e6b325f2e3707f462d885868df51ec0a4b47` |
| Wheelhouse builder | `ghcr.io/astral-sh/uv@sha256:aaeebd3aab31e193633f104cbec66d24777538fee7a8e819217066046e1deb40` |
| Wheel count | 248 Linux/amd64 wheels |
| Wheel manifest checksum | `sha256:97dc61160818d614a8071094c6deff38a4db1026c10a7b53f263fa6238098a94` |
| Wheel payload size | 3,272,769,655 bytes |

The wheelhouse was collected in the pinned Linux/amd64 builder from the
admitted upstream lock. Three source distributions (`antlr4-python3-runtime`,
`langdetect`, and `sgmllib3k`) were converted to wheels inside that builder.

## Offline build result

The final build used the generated context and `docker build --platform=linux/amd64
--network=none`. It installed every recorded wheel without a network path and
verified imports of the archived `chatqec` and `chatqec_app` source.

| Field | Value |
| --- | --- |
| Local tag | `qhpc/chatqec-query:a1ddc2e-linux-amd64` |
| Local immutable image digest | `sha256:bb59cd1be5919f8f63afada4f9f15abec8912aaf0cc1627e9460e475bb13a3dc` |
| Image size | 6,576,651,415 bytes |
| Build-network policy | disabled (`--network=none`) |

The image imports the verified source archive through `PYTHONPATH` rather than
building the upstream Python distribution. This is intentional: upstream
declares `hatchling` as a non-versioned PEP 517 build requirement and it is
not part of its admitted `uv.lock`; EQO does not resolve that implicit
dependency during the release build.

After this candidate was built, the source-controlled recipe's OCI source label
was aligned from the historical `QSCSoftwareThrust` namespace to the current
`QSCSoftwareEcosystem/QHPC-Ecosystem` remote. Because this image is local-only
and unpromoted, rebuild it from that updated recipe before any admission or
publication step; do not relabel this candidate as release evidence.

## No-credential runtime check

With `--network=none` and a disposable local workload-identity token, the
container served `GET /v1/health` and returned:

- `status: degraded`;
- source revision `a1ddc2e4916b1f4152fba4c94c9c7512eea0d977`;
- `model: not-configured`, `qdrant: not-provisioned`, and `corpus:
  not-provisioned`;
- `tool_execution: false`.

This proves only the container admission and explicit degraded boundary. It
does **not** prove model-backed answers, Qdrant retrieval, corpus provenance,
or streaming against a provider.

## Remaining release gates

1. Approve the dependency/license/vulnerability review and promote the
   wheelhouse from candidate to admitted input.
2. Select one approved model provider and secret-provider route.
3. Admit an immutable reviewed corpus/Qdrant snapshot and run a controlled
   query/stream smoke against it.
4. Produce SBOM, signature, and provenance attestation; publish only to an
   approved immutable registry.
