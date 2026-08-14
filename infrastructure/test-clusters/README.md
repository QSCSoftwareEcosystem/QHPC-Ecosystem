# Development Slurm Fixture

QHPC keeps local Slurm virtualization separate from DOE target acceptance.

`slurm-docker-cluster` is the only admitted fixture. It is revision-pinned and
validated for lightweight scheduler conformance through the QHPC CLI. It uses
non-sensitive test data and produces no DOE production evidence.

The source is cloned on demand under ignored `.qhpc/test-clusters/` state. Its
manifest pins an exact source commit, uses the tracked QHPC compatibility
build, assigns QHPC-scoped image and container names, and excludes
`slurmrestd` from the started service list.

This fixture does not contain Apptainer. Initial-package HPC acceptance must run
accepted SIFs through the normal worker on an Apptainer-capable Slurm target.
