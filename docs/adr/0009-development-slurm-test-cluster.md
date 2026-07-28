# ADR 0009: Development Slurm Test Cluster

- Status: Accepted
- Date: 2026-07-27

## Context

QHPC's asynchronous Slurm runner is covered by deterministic fake transports,
but those tests cannot detect incompatibilities in the real `sbatch`, `squeue`,
`sacct`, and `scancel` command lifecycle. Thomas Naughton, the Data Schema
project leader, contributed the
[`naughtont3/slurm-docker-cluster`](https://github.com/naughtont3/slurm-docker-cluster)
repository as a local Slurm virtualization option.

The fork's `tjn-main` branch adds Slurm 25.05 configuration, accounting, two
compute nodes, Slurm REST work, a shared `/mnt` submission directory, and QPU
GRES experiments. It is a development environment with fixed credentials and
does not model a DOE facility's storage, network, identity, or hardware.

## Decision

QHPC uses the fork only as an optional development scheduler test provider. The
provider manifest pins `tjn-main` revision
`8c8065cbebb475a512a66cabff9aceda5f2c57b0`; the repository is cloned on demand
under ignored `.qhpc/` state and is not vendored or made part of the QHPC
runtime supply chain.

The QHPC test harness:

1. verifies the exact source URL and revision before use;
2. starts only MariaDB, `slurmdbd`, `slurmctld`, and workers `c1` and `c2`;
3. does not start the externally exposed `slurmrestd` service;
4. submits scripts through the existing `SlurmClient` using the shared `/mnt`
   path;
5. verifies completion, accounting, and cancellation through real Slurm CLI
   commands;
6. persists controller state in a dedicated named volume so scheduler handles
   survive Compose replacement; and
7. records this result as scheduler-integration evidence only.

The selected source Dockerfile has an amd64-only `gosu` binary, an obsolete
unpinned Python package installation, and a global TLS-verification bypass.
QHPC therefore does not build it directly. A tracked compatibility Dockerfile
is copied into the ignored source checkout, makes the helper
architecture-aware, removes the unused Python install and TLS bypass, and
accepts an explicit local public build CA when an intercepted development
network requires one. The external source remains pinned and unmodified.

## Consequences

- QHPC can test real Slurm command behavior and shared-path mapping without
  waiting for a DOE allocation.
- Failures in scheduler submission, polling, accounting, cancellation, and
  restart recovery can be reproduced locally.
- The first local build compiles Slurm from source and is intentionally not part
  of the ordinary unit suite.
- The cluster does not validate Apptainer, SIF distribution, warm pilots,
  parallel filesystems, MPI, RDMA, GPU, GPUDirect, institutional identity,
  security controls, queue behavior, or performance.
- A successful local smoke test cannot activate the planned DOE execution,
  storage, or pilot profiles and cannot satisfy target acceptance.
