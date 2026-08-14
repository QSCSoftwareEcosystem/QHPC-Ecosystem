# OpenQSE QFw Slurm Cluster Source Audit

- Audit date: 2026-07-28
- Repository: `https://github.com/openQSE/QFw-SLURM-Cluster.git`
- Default branch: `main`
- Revision: `16bc49691679d99fc4f28a27612425a2a67909c1`
- Repository license: MIT
- QHPC role: planned Tier 1C project-stack development provider
- Activation: blocked

## Scope

The repository is a Docker Compose Slurm development environment rather than a
QHPC workflow engine or an operation runtime. At the audited revision it
contains:

- MariaDB, `slurmdbd`, `slurmctld`, `slurmrestd`, and workers `c1` through `c8`;
- normal and synthetic quantum partitions with example QPU GRES and features;
- Rocky Linux 10, Slurm 25.05, OpenMPI, libfabric, and OSU micro-benchmarks;
- image-contained and host-mounted OpenQSE QFw development paths;
- TNQVM and NWQ-Sim runners;
- QRMI, its Slurm SPANK plugin, and IQM's QDMI implementation; and
- local QFw QRMI/QDMI routing and optional IQM introspection smoke scripts.

QHPC's initial OpenQSE capability remains the separately pinned
`openqse-spec` documentation resource. This audit does not change that
capability or publish a QFw operation.

## Published Image Observation

The repository documents
`ghcr.io/openqse/qfw-slurm-cluster:20260503-v1.0`. Registry manifest inspection
on 2026-07-28 found:

- manifest digest:
  `sha256:fc5c5828a53ff0f6fd3c8db5bf41e446ce1ae95a372639fe3480ccc21896cc29`;
- platform: `linux/amd64`;
- compressed layer bytes: `3835770007` (approximately 3.84 GB); and
- largest compressed layer: approximately 3.12 GB.

The tag-to-source relationship, embedded QFw revision, transitive dependency
set, SBOM, signature, and attestation were not established. The image was not
pulled or executed during this audit.

## Findings

1. The Dockerfile appends `sslverify=false` to the package-manager
   configuration and uses `curl --insecure` while retrieving the `gosu` signing
   key. This is not acceptable for a QHPC compatibility build.
2. The image clones the default QFw branch without an immutable revision and
   performs unpinned Python installations, including `Cython`, `pytest`,
   `scons`, and `iqm-qdmi[qiskit]`.
3. Compose publishes `6820:6820`, which binds `slurmrestd` beyond loopback by
   default, while the entrypoint disables multiple REST daemon security checks.
4. Compose uses a fixed database password, shared root SSH material, fixed
   container names, broad development mounts, and synthetic QPU resources.
5. Slurm declares `TaskPlugin=task/none`; this environment does not establish
   production task isolation or resource enforcement.
6. The `linux/amd64` image and hard-coded amd64 helper are not a native match
   for the current arm64 development host.
7. The repository's MIT license does not by itself resolve the licenses and
   redistribution requirements of QFw, TNQVM, NWQ-Sim, QRMI, QDMI, OpenMPI,
   libfabric, or other embedded dependencies.
8. Optional hardware testing passes an API key into a container environment.
   QHPC must instead use approved secret references and redacted telemetry.

## QHPC Admission

The source is pinned in
`infrastructure/test-clusters/qfw-slurm-cluster/cluster.yaml` with status
`planned`. The QHPC service allowlist excludes `slurmrestd`, and runtime code
blocks start and smoke operations for non-validated providers.

Activation requires:

1. a reviewed compatibility Dockerfile with approved CA handling and no TLS
   bypass;
2. immutable source, base image, package, archive, and helper identities;
3. transitive license review and an SBOM;
4. a signed, attested image digest tied to the audited source;
5. isolated `linux/amd64` host validation with non-sensitive fixtures;
6. recorded Slurm, MPI/libfabric, QFw, QRMI/QDMI, simulator, storage, latency,
   restart, and cleanup evidence; and
7. a separately reviewed QFw operation or target-adapter contract before any
   workflow or deployment-registry admission.
