# Native Linux/ARM64 operation images — unsigned internal alpha

Date: 2026-09-18

## Scope and release state

This record covers only the three native `linux/arm64` Apptainer-executable
EQO operations built on an Apple Silicon M2 host:

| Candidate OCI name | Operation | Source revision |
| --- | --- | --- |
| `ghcr.io/qscsoftwareecosystem/eqo-stim:0.1.0-linux-arm64` | Stim / ChatQEC bounded simulation tools | `dd19a85b08637a61dc1afc124d2f4b32745b527b` |
| `ghcr.io/qscsoftwareecosystem/eqo-nwqsim:0.1.0-linux-arm64` | NWQ-Sim CPU simulation | `b35763d846e6512ed817d3f88ac8ce79a7e82a7e` |
| `ghcr.io/qscsoftwareecosystem/eqo-ftqc:0.1.0-linux-arm64` | FTQC IQM preparation | `779216de8805ea0c1d473c640eaf17d6cbfa04e8` |

These are **unsigned internal-alpha candidates**. They were not pushed to a
registry, made public, added to the admitted public image manifest, or marked
released. **signature pending approved QSC release identity.** No Cosign key
was generated and no credential was read or exposed.

QFw-SLURM, virtual Slurm, and every other Docker fixture are outside this
ARM64 candidate scope.

## Reproducible native build inputs

Docker reported a native `linux/arm64` server. Each build used Docker Buildx
with `--platform linux/arm64 --network none --pull=false` after prefetching
the exact pinned ARM64 base manifest. No x86 emulation was used.

| Runtime | Pinned ARM64 base manifest(s) |
| --- | --- |
| Stim | `python:3.11.13-slim-bookworm@sha256:18ce9b03d18802119f4f9270d10a1ceb45d0acb768c305b7fbbd7c6b5b5a020b` |
| NWQ-Sim | `gcc:13.4.0-bookworm@sha256:802aeefa60cee3ceaef2ef4f0e143776e26a4811a08c27ca844e8761eede505f`; `debian:bookworm-slim@sha256:6bd27d44e6c32a66bbd72d7cb2b76a8ae3497ec2e5274a81abd1b37f6013fa1f` |
| FTQC | `zhongruoyu/llvm-ports:22-jammy@sha256:920afd24025997909f8887055e1363c11147a425f593a206ad7e4e9d895ef5a7` |

The Stim contract pins ARM64-compatible hashes for every wheel. Upstream does
not distribute Linux/ARM64 wheels for pinned `stim==1.15.0` or
`PyMatching==2.4.0`; both were built natively from their pinned source
archives in an ARM64 container with `--network none`. Their resulting wheel
hashes are respectively
`sha256:62354c0dfd130025194de446fd01a48ec13239eb8b200d2aebf85e14e16022a3`
and
`sha256:b843c8845ad11d01a30a5cb60769b6a44bd384d19fd97d8cf4bf650e45d453c7`.
The contract verifies them before the OCI build begins.

## OCI archives and attestations

The archives are local-only, attested OCI layout tarballs under
`.development/arm64-internal-alpha/archives/`. The listed subject manifest is
the future immutable registry identity if the exact candidate is published;
it is **not** a GHCR digest yet.

| Candidate | Subject manifest | OCI index | Archive SHA-256 | SPDX SBOM | SLSA provenance |
| --- | --- | --- | --- | --- | --- |
| Stim | `sha256:7d1e0d2396a73438e5198fe929f29cf1df5462889e38af83499450c941db7d18` | `sha256:f0efb9d55beebb4a691553eceab064846159ee4056552f138ce1582a564daa75` | `sha256:90be4ef312b27834724ae88cd75b8888fd29a7de45670f9c621c0cae005d6476` | `sha256:49dc356375df7ee64f8811ce4fe08074c48d3ea6c5578134e3b214add640c79d` | `sha256:3319ea597b283631b51555c008ca69d352d2e3cd2ff3d1621f53410f6d705118` |
| NWQ-Sim | `sha256:a15b4fc512d50ac9c96b7a9179252bc71b85bf6acd9e1730cb1ef2083ba68989` | `sha256:1afbab53b85670d02053366fb3fd1c0e796d35f9353cc0a2b53da33d274cb8dd` | `sha256:2ac1877ad6b4539ff5d0dc57bc29fa3474e9ec203b82a99b8b044d3765e97b52` | `sha256:3b673a7c7558997df647e1fbe50b1dc13fe0a2d7d8f4975b39f2dbaf2685927d` | `sha256:ccd667355736715fbc36cf970264e4e75490a73320efc8c35e3130dd11118146` |
| FTQC | `sha256:a5043a8c3563d9f4ccce53927590b9fe97ef8ab838ac8f27e5b96164f2a0a577` | `sha256:a97fb05603b1b8ee370ad04096798c1cbaa397135877b0bdf8428a7d08a70f37` | `sha256:b345ca5657da9b5dc8d278083588da33325a78dee3b3fb221d79798db6151a1f` | `sha256:48f320b9e3d6dd14e83e9bce74222dd9f9e2025e21c7bbbb3f2d4b2c516460ee` | `sha256:855059f3bcb60a57b214dd1dd09edc6c1be7e059a69d84c0f5bd7f8f8e65b728` |

Each archive was inspected locally. Its attestation manifest contains an
in-toto statement with `https://spdx.dev/Document` and one with
`https://slsa.dev/provenance/v1`; both statements name the corresponding
ARM64 subject manifest above. SBOM generation used the pinned, locally cached
ARM64 scanner
`docker.io/docker/buildkit-syft-scanner@sha256:d802508fd7d9841805c8e616c9965c5dbca0c6c415093ed506309d1c58bdd6c8`.

## Runtime verification

Each local OCI candidate passed its contracted Docker smoke test under
`--network none`, `--read-only`, `--cap-drop ALL`, `no-new-privileges`, and a
noexec `/tmp`.

Apptainer 1.5.3 was built natively in an M2 Lima `aarch64` guest from the
official `apptainer-1.5.3.tar.gz`
(`sha256:5a3bf360a5240086324aa7f7005ab7eeee91095e2091078b3f9783eaf6e7288a`)
with the verified Go 1.25.7 ARM64 archive
(`sha256:ba611a53534135a81067240eff9508cd7e256c560edd5d8c2fef54f083c07129`).
Each local OCI archive was converted to a SIF, then executed as the ordinary
guest user with `--containall --net --network none` and read-only input plus
writable output bind mounts.

| Candidate | SIF SHA-256 | Verified result |
| --- | --- | --- |
| Stim | `sha256:8a7acba393eac0edc5f2cba058805f1d8448254e2a67602c51d53bf69064361c` | 4-shot schema and shot count |
| NWQ-Sim | `sha256:f911ab735baacc20cd7087d42783d59d4a1a8166c3164f18488ef396a1ae5543` | CPU, 2-qubit, state-vector result |
| FTQC | `sha256:7c595660edb7027843a6e95210c10d164f374aab5d07d4e23eac45e476b4a321` | IQM artifacts and `not-submitted` report |

There was no host-network fallback.

## FTQC upstream-suite limitation

The ARM64 FTQC builder compiles and executes the complete `check-ftqc` suite
with pinned LLVM 22.1.8 `llvm-lit`, `FileCheck`, `not`, and `count` present.
The exact pinned FTQC revision exits 2: 91 of 100 tests pass, 4 fail
(`qasm3-import-{adder,bell,qft3}` and `expand-physical`), and 5 are unresolved
because their files have no `RUN:` line. The failures compare current compiler
output to stale expected text; they are not an ARM64 execution fault. The
bounded FTQC IQM preparation smoke test passed in both OCI and SIF forms, but
this non-clean full upstream-suite result remains a release limitation.

Promotion requires an approved QSC Cosign identity (managed key or approved
keyless GitHub OIDC workflow), signature creation and verification, review of
the FTQC suite finding, immutable GHCR publication, anonymous digest-pull
verification, and only then an admitted platform-specific installer entry.
