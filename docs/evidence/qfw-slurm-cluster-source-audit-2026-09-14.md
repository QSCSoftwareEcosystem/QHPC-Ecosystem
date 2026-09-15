# OpenQSE QFw–SLURM Cluster Source Intake

- Intake date: 2026-09-14
- Repository: `https://github.com/openQSE/QFw-SLURM-Cluster.git`
- Branch observed: `main`
- Pinned revision: `eeb42e601383f3d33020f823d4a387ef30b9dd7d`
- Repository license: MIT
- EQO status: cataloged development-cluster reference; not executable

## What was ingested

This intake records the current public source as a distinct OpenQSE QFw
development and integration-test environment. It is not a duplicate of EQO's
lightweight scheduler-conformance cluster, an EQO tool, an EQO service, or an
admitted execution target.

At the pinned revision, the repository describes a Docker Compose Slurm test
environment with MariaDB, `slurmdbd`, `slurmctld`, `slurmrestd`, and eight
compute services (`c1`–`c8`). Its documented normal and synthetic quantum
partitions support QFw development, integration testing, and profiling. The
image includes QFw/DEFw, OpenMPI/PRRTE, libfabric, QRMI plus its Slurm SPANK
plugin, QDMI support, and the TNQVM and NWQ-Sim circuit runners. It also
contains an optional dashboard and QFw-specific test and operational-recipe
documentation.

The repository's own documentation says that the environment is not intended
to model production HPC performance. EQO therefore presents it as a source and
documentation reference only. The Workbench offers no start, build, shell,
credential, dashboard, or hardware controls for it.

## Source and image observations

The current Dockerfile uses `rockylinux/rockylinux:10.1.20251123`, disables
package-manager TLS verification, and retrieves the `gosu` signing key with
`curl --insecure`. These settings are not acceptable in an EQO compatibility
image.

The source's `do_build.sh` resolves selected QFw and `qfw-slurm` refs to commits
at build time and passes those commits into the Docker build. That is an
improvement over an unverified in-image default-branch clone, but the resolved
identities are still determined at build time and are not an EQO-reviewed
source lock, SBOM, signed image, or provenance attestation. The Dockerfile also
uses mutable package and Python dependency inputs.

The previously documented image
`ghcr.io/openqse/qfw-slurm-cluster:20260503-v1.0` was not pulled or executed
for this intake. Its approximately 3.84 GB `linux/amd64` manifest observation
from 2026-07-28 remains historical evidence only; its relationship to this
newer source revision has not been established.

## EQO boundary and admission gates

The pinned source is represented by
`infrastructure/test-clusters/qfw-slurm-cluster/cluster.yaml` with status
`planned`. EQO can prepare the source into ignored, revision-addressed local
state for inspection, but its normal test-cluster controls refuse to start or
smoke-test a provider until it is `validated`. `slurmrestd` is excluded from
the EQO service allowlist.

The controlled intake command completed on 2026-09-14. It cloned the pinned
commit into `.qhpc/test-clusters/openqse-qfw-slurm-eeb42e601383`, verified the
origin, clean revision, license, upstream Compose file, and EQO compatibility
overlay, then stopped. No image was built, pulled, or started.

Before any execution admission, the project needs all of the following:

1. a compatibility build that restores TLS verification and pins every
   material source, base image, package, archive, and helper input;
2. a reviewed license inventory, SBOM, signed immutable image digest, and
   source-to-image provenance;
3. isolated non-secret validation on the intended platform, including cleanup
   and shared-storage behavior; and
4. a QFw-specific operation or target-adapter contract, plus approved secret
   references for any hardware access.

Those gates preserve the useful OpenQSE source relationship without treating a
development Compose environment as the common EQO runtime.
