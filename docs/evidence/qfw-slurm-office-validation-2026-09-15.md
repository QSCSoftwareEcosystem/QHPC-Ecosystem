# QFw-SLURM office validation — 2026-09-15

## Scope

This is Linux/AMD64 office-host evidence for the QHPC compatibility image. It
demonstrates isolated development behavior only; it is not a facility-HPC
performance, storage, RDMA, GPU, identity, or device-credential validation.

Image admitted: `qhpc/openqse-qfw-slurm:0.1.0-office`

- OCI platform manifest:
  `sha256:0fed63f95914df4927ea26a34296d1862821bc52629bffd5fb7869ecf612de41`
- Public OCI index (published 2026-09-16):
  `ghcr.io/qscsoftwareecosystem/eqo-qfw-slurm@sha256:5d6a15ba9338e54c4eda135381cc74d1f65e582da9fc861abfb1c0b1dd359105`
- Local configuration digest:
  `sha256:1ee74220fa86caec44abe12993e794e9e911abef7c4ef37fdbc1e3fa6d9cd95b`
- Source checkout: `eeb42e601383f3d33020f823d4a387ef30b9dd7d`
- Runtime: Docker Compose internal network; no host-published service ports.

## Results

| Check | Result | Evidence |
| --- | --- | --- |
| Build, pinned source, TLS, exact Python locks, and RPM lock | Pass | The final build completed and its generated 588-package RPM inventory matched `rpm.qhpc.lock` exactly. |
| Supply chain | Pass | SPDX SBOM, SLSA v1 provenance, immutable OCI manifest, source-to-image admission statement, and a verified Ed25519 detached signature are recorded alongside this report. |
| Isolated scheduler startup | Pass | Slurm controller reported `UP`; `c[1-8]` reached `idle`. |
| Submit, poll, cancellation, and cleanup | Pass | Standard smoke completed job 1 and canceled job 2; after controller restart, completed job 7 and canceled job 8. |
| Controller restart | Pass | `slurmctld` restart returned to `UP`, all eight nodes returned to `idle`, and the follow-up scheduler smoke passed. |
| Shared-path mapping | Pass | A Slurm task wrote `/mnt/qhpc-shared-path-test.txt`; the host shared directory read `qhpc-shared-path-ok`. |
| QFw shim | Pass | Credential-free QDMI/QRMI bifurcation and qhw normalization completed with `SHIM BIFURCATION + INTROSPECTION SMOKE: PASS`. |
| NWQSim path | Pass | A two-qubit OpenQASM Bell circuit ran through `circuit_runner.nwqsim` with backend `MPI` and produced only `00`/`11` outcomes. |
| TNQVM path | Pass | An XASM Bell circuit ran through `circuit_runner.tnqvm`, reporting normalized state and `00`/`11` outcomes. |
| libfabric and local Open MPI | Pass | `fi_info` reported the TCP provider; `mpirun -np 2 hostname` completed inside an isolated worker container. |
| Cross-node scheduler launch | Pass | `srun -N2 -n2 hostname` placed tasks on `c1` and `c2`. |
| Cross-node Open MPI/OSU latency under Slurm | Limited | This image exposes Slurm `none`, `cray_shasta`, and `pmi2` MPI plugins, not `pmix`. Open MPI 5 detected PMI2 but started two singletons, so the two-process OSU latency program correctly refused to run. This is recorded as a development limitation, not a facility-network result. |
| Secret and endpoint exposure | Pass | Compose uses Docker file secrets, an internal network, and no `slurmrestd`, SSH daemon, or host-published endpoint. Controller environment inspection found no token, secret, password, or API-key variables. |

The local artifacts `shim-smoke.out`, `simulator-smoke.out`, `mpi-simulator-help.out`,
`slurm-mpi.out`, and `compose-ps.json` are retained under the ignored office
admission workspace for reviewer reproduction. They contain no device or
hardware credentials.

## Acceptance boundary

The fixture is validated as a development simulation. The unimplemented
Slurm-PMIx integration and the absence of facility interconnect hardware mean
that cross-node MPI performance and PMIx launch behavior remain outside this
activation. EQO workflow, CLI, and Workbench use remains gated on a separately
reviewed QFw operation/target-adapter contract with explicit inputs, outputs,
runtime identity, and secret handling.
