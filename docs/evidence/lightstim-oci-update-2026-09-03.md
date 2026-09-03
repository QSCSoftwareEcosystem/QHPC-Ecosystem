# LightStim QSC-source OCI update — 2026-09-03

## Scope

This evidence records the controlled update of the existing EQO LightStim
`estimate-logical-error` operation image. It replaces the prior QuTone source
pin with the current canonical QSC repository revision without widening the
published operation or decoder boundary.

## Pinned inputs

- Source: `https://github.com/QSCSoftwareThrust/LightStim`
- Revision: `23924ee997a27af7a0aa17623357bf8bc7170625`
- Source commit timestamp: `1788403837` (`2026-09-03 02:50:37 UTC`)
- Git archive SHA-256:
  `042ba4c8bc4b189967eb1e2bc4ff286b716d0275ebefa2dabb1eab21ecfb2b4d`
- Containerfile SHA-256:
  `9fbd503aea49873f7d8d0db9bb623bf1028ad154ab62511df95ba1e822b04d19`
- Entrypoint SHA-256:
  `5d84810862d17782f464ee99c38d102b83ee39737d3ca85aa82b6935e2c94a24`
- Fixture SHA-256:
  `d7807f0925b26f5fd845b7dd71ce922ed5b97ed001650d52624260b77bd2f824`
- Dependency cache: all 19 Linux wheels declared by the runtime manifest were
  acquired and checksum-verified before the network-disabled image build.

The source exposes the `SimulationPipeline` and `DecoderConfig` API used by the
EQO adapter. The integrated operation remains CPU-only and continues to admit
only the `pymatching` decoder.

## Build and reproducibility

The image was built for `linux/amd64` with build networking disabled and
BuildKit's implicit provenance envelope disabled:

```text
qhpc/lightstim:23924ee-linux-amd64
```

- Local OCI manifest/image digest:
  `sha256:7731c5d9188a4eb5ad8f9448323b60e6ab722786d8f00f9b691d082edf6ec074`
- OCI config digest:
  `sha256:dda92c8c12c1a5271dfa72dd7a4c8b284911000c2b157a6666ffd4094de4dcc2`

A second build used `--no-cache` and produced the same manifest/image and
config digests.

## Contracted smoke result

The runtime ran with a read-only root filesystem, disabled networking, the
declared read-only Stim input, and the declared writable output mount.

- Result: passed
- Elapsed time: `4661 ms`
- Output: `/outputs/estimate.json` (`175` bytes)
- Output SHA-256:
  `9a6c45ab20d032d90de85d9ac046e3f03ad29c6948971afe937a52a5d9abbe5f`

This is local OCI evidence only. It does not establish registry publication,
signature, attestation, SIF conversion, target-system acceptance, or DOE
production approval.

## Virtual Slurm integration

The updated digest was then admitted through the development registry and run
through the ordinary API engine, asynchronous worker, Slurm scheduler, and
container runner. All three ecosystem smoke workflows passed:

| Workflow | Result | Duration | Artifacts |
| --- | --- | ---: | ---: |
| `ct-hw-qasm-analysis` | passed | 4025 ms | 2 |
| `qec-memory-estimation` | passed | 9391 ms | 2 |
| `nwqec-counts` | passed | 3513 ms | 1 |

The QEC workflow exercised the updated LightStim image after FTPrimitiveBench
generated its detector-annotated circuit. LightStim's recorded application
stage completed in `3839 ms`; the complete scheduled workflow completed in
`9391 ms`.

## Ecosystem regression

- Python: `212 passed, 4 skipped`
- Workbench unit tests: `10 passed`
- TypeScript: `tsc --noEmit` passed
- Registry validation: `17` capabilities passed
- Updated workflow validation: `qec-memory-estimation@0.1.1` and
  `showcase-qec-distance-study@0.1.1` passed
