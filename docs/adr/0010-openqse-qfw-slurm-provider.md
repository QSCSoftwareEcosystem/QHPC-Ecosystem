# ADR 0010: OpenQSE QFw Slurm Development Provider

- Status: Accepted
- Date: 2026-07-28

## Context

The lightweight Slurm Docker provider in ADR 0009 validates real scheduler
submission, polling, accounting, cancellation, shared-path mapping, and restart
continuity. It intentionally contains no project scientific stack and therefore
cannot validate OpenQSE QFw, MPI, libfabric, QRMI/QDMI, simulator runners, or
QPU-oriented Slurm resource descriptions.

OpenQSE publishes
[`QFw-SLURM-Cluster`](https://github.com/openQSE/QFw-SLURM-Cluster) as a Docker
Compose development environment containing those components. Revision
`16bc49691679d99fc4f28a27612425a2a67909c1` also defines eight compute nodes,
normal and synthetic quantum partitions, an optional mounted QFw development
tree, and a QFw shim smoke test.

The source is useful but cannot be activated unchanged. Its Dockerfile disables
TLS verification, retrieves a signing key with an insecure request, clones QFw
without an immutable revision, and installs mutable dependencies. Its Compose
configuration uses development credentials, shared root SSH, and a host-exposed
`slurmrestd` whose development security checks are reduced. The published image
is a large, single-platform development artifact without QHPC-reviewed supply
chain evidence.

## Decision

QHPC onboards the repository as a second, separately governed, planned
development provider:

1. The exact repository commit is recorded in a `SlurmTestCluster` manifest.
2. The provider is Tier 1C project-stack infrastructure and does not replace the
   Tier 1 scheduler-conformance provider.
3. QHPC prepares the pinned source under ignored `.qhpc/` state but refuses to
   start or smoke-test any provider whose manifest is not `validated`.
4. `slurmrestd` is excluded from the QHPC service allowlist. A future REST
   transport requires a separate authenticated, TLS-protected decision.
5. A reviewed compatibility image must restore TLS verification, pin QFw and
   all material build inputs, and record image digest, SBOM, signature,
   attestation, licenses, platform, and source-to-image provenance.
6. A QFw-specific operation or target-adapter contract is required before a
   QHPC workflow can invoke the project stack.
7. Hardware credentials must enter through approved secret references and must
   never be placed in command history, Compose files, images, logs, or committed
   environment files.

## Consequences

- QHPC gains a concrete path for project-owned quantum-HPC integration tests
  without turning a project development image into the ecosystem runtime.
- Source preparation and review can proceed before the expensive image is built
  or pulled.
- The large image must remain cached on an isolated development host; it must
  not be staged per task.
- Docker-host MPI, libfabric, QPU GRES, and software-overhead results are useful
  development evidence but are not facility network or performance evidence.
- The provider cannot satisfy Apptainer, SIF, storage, identity, RDMA, GPU,
  security, warm-pilot, or DOE target acceptance.
