# FTQC OCI Preparation Runtime Smoke Evidence

- Date: 2026-09-10
- Source: `https://github.com/QSCSoftwareEcosystem/FTQC`
- Source revision: `779216de8805ea0c1d473c640eaf17d6cbfa04e8`
- Source archive SHA-256:
  `e1cdcb76528293c1b222bd7eda5ee841818acbb1986041f6052d226138d7319e`
- Platform: `linux/amd64`
- Base builder and runtime: `zhongruoyu/llvm-ports:22-jammy@sha256:eb7caed5cfe7e765bde2c5f8e7654ceb0a0282728ea1db4433fa00c4059dc7a9`
- LLVM/MLIR available in the build image: 22.1.8
- Locally built image: `qhpc/ftqc:779216de-linux-amd64`
- Local OCI image identity:
  `sha256:f46f1c36dc78310453776706316e8cc6baa0bb112ff2dea8512697cd0f005c96`

## Constrained smoke

The `ftqc-prepare-iqm-linux-amd64` runtime was built from its exact archive
with build networking disabled. Its smoke invoked the fixed entrypoint with the
checked-in measured Bell fixture, a read-only root filesystem, no network, a
read-only `/inputs` mount, and a writable `/outputs` mount.

| Declared output | SHA-256 | Size |
| --- | --- | ---: |
| `program.mlir` | `e538c58feaf1f7ea0e8be006000ef6a4be09ab33c16ff2694288022e01579b96` | 1,474 bytes |
| `iqm-circuit.json` | `f799bf4527f84c0e5a7d0c8d52d6947b6806f4fc5917b217bf5aeb2852d810a1` | 1,314 bytes |
| `preparation-report.json` | `cde1c8d13dff22f03e237871fcde9efa078af3a624340f3e5cf2bf98ab0772c8` | 924 bytes |

The report records two device qubits and `not-submitted`; the runtime neither
receives credentials nor has a network path. The worker admits only this
checksum-pinned OCI image for `prepare-iqm`. The former macOS native bundle is
historical evidence and is not an EQO execution target.

This is local OCI smoke evidence. The image is not published, converted to
SIF, or accepted for a deployment target, and this run makes no hardware,
routing, calibration, or scientific-performance claim.
