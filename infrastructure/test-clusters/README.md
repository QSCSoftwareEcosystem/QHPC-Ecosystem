# Development Slurm Fixture

QHPC keeps local Slurm virtualization separate from DOE target acceptance.

Two fixtures are admitted for isolated, non-sensitive office development:

- `slurm-docker-cluster` is revision-pinned and validated for lightweight
  scheduler conformance through the QHPC CLI.
- `qfw-slurm-cluster` is a separately pinned OpenQSE QFw compatibility image
  with an SBOM, provenance, signature, license inventory, and validation
  record. It models a QFw/Slurm development stack only; it is not a facility
  HPC provider or an EQO workflow target.

The source is cloned on demand under ignored `.qhpc/test-clusters/` state. Its
manifest pins an exact source commit, uses the tracked QHPC compatibility
build, assigns QHPC-scoped image and container names, and excludes
`slurmrestd` from the started service list.

Neither fixture provides Apptainer acceptance or facility identity, storage,
network, accelerator, or performance evidence. Initial-package HPC acceptance
must run accepted SIFs through the normal worker on an Apptainer-capable Slurm
target. The QFw fixture has no host-published ports or `slurmrestd`; its
credentials are Docker file secrets created only in ignored local state.
