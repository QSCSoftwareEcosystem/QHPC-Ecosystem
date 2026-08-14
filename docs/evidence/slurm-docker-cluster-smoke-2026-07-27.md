# Slurm Docker Cluster Scheduler Smoke Evidence

- Date: 2026-07-27
- Result: passed
- Scope: development scheduler lifecycle only
- Provider: `thomas-slurm-docker`

## Inputs

- Source: `https://github.com/naughtont3/slurm-docker-cluster.git`
- Branch: `tjn-main`
- Revision: `8c8065cbebb475a512a66cabff9aceda5f2c57b0`
- Source license: MIT
- Provider manifest SHA-256:
  `49b0c8f07ce8c83747188c2f6d0d0548ee8122deed9a3c1fdb36881639a5ac02`
- QHPC compatibility Dockerfile SHA-256:
  `7d9dab3fd0af85b66692051a5e77aebe4dd4da58eb252ad2a9f0b67dfe882ce8`
- QHPC Compose override SHA-256:
  `694dbb7870ae19f1b2643e9658376371dac38deb9c28080e1795d3b68b2cf1a2`

The external source checkout was clean at the pinned revision. QHPC copied its
tracked compatibility Dockerfile into ignored test state. The compatibility
build removed the source Dockerfile's obsolete unpinned Python package
installation and global TLS-verification bypass and made the `gosu` download
architecture-aware.

The ORNL-managed public build CA was supplied locally and was not committed.
Its SHA-256 certificate fingerprint was
`55:33:55:59:11:54:5D:6C:02:2F:DE:A0:D2:97:15:65:33:09:A3:96:4C:FC:EE:1B:BE:54:18:37:83:DB:47:F6`.
No private key was accepted or used.

## Environment

- Docker client and server: `29.6.2`
- Docker engine: Linux `arm64`
- Local image:
  `slurm-docker-cluster@sha256:399378aa580454cb85a9c0df9f0edbd6418d7d948c2ee73c6542f44129b03afb`
- Image platform: `linux/arm64`
- Started services: MariaDB, `slurmdbd`, `slurmctld`, `c1`, and `c2`
- Excluded service: `slurmrestd`
- Slurm partition: `normal`
- Ready nodes: `c[1-2]|idle|0/16/0/16`
- Controller state: dedicated named volume mounted at `/var/lib/slurmd`

The local image digest identifies this development build only. It is not a
published or signed QHPC runtime release.

## Verification

The QHPC CLI prepared the pinned source, started the cluster, registered Slurm
accounting, waited for worker readiness, and submitted two jobs through the
shared `/mnt` path:

```text
job 1  qhpc-smoke-14d7cdbf537f   COMPLETED       exit 0:0  node c1
job 2  qhpc-cancel-14d7cdbf537f  CANCELLED by 0  exit 0:0  no node assigned
```

Job 1 produced:

```text
QHPC_SLURM_SMOKE_OK:14d7cdbf537f
c1
```

Job 2 was observed as active, canceled with `scancel`, and reconciled through
`sacct`. The two-job smoke command completed in 3105 ms. The local Python suite
also passed with 132 tests and one intentional skip.

The final Compose override was then tested across a complete `down` and `up`.
The first persistent-state smoke used job IDs `1` and `2`; after restart, the
next completion and cancellation smoke used IDs `3` and `4`. Both runs passed,
in 2906 ms and 3208 ms respectively. This verifies that controller job state is
preserved across local cluster replacement.

## Isolation Regression

On 2026-07-28, an unrelated active `qiris-slurm` Compose project exposed the
source stack's global container-name and image-tag collision. The QHPC override
was updated to use `qhpc-slurm-test-*` container names and
`qhpc/slurm-docker-cluster:25.05.0-qhpc`, while retaining the source service
hostnames required by Slurm.

The merged Compose configuration was inspected before activation. The isolated
QHPC fixture then started alongside the existing stack with ready nodes
`c[1-2]|idle|0/16/0/16`. The compatibility image was:

```text
sha256:7053a82f2d3fa1c6813317d972452a4269e55ff9087eb24a928861e424577dc9
linux/arm64
464774986 bytes
```

Completion job `5` reached `succeeded`; cancellation job `6` reached
`canceled`; the smoke completed in 3075 ms. QHPC then stopped its own Compose
project and left no QHPC containers running. The pre-existing `qiris-slurm`
controller, database, REST service, and two workers remained healthy.

## Boundary

This evidence validates the real Slurm CLI path for submission, queue polling,
accounting fallback, worker execution, shared script-path mapping, completion,
and cancellation. It does not validate QHPC's Apptainer runner, operation SIFs,
warm-pilot allocation, facility identity, parallel storage, MPI, RDMA, GPU,
GPUDirect, security controls, representative queue latency, or representative
HPC performance. It cannot activate the planned DOE execution target, storage
profile, or pilot profile.
