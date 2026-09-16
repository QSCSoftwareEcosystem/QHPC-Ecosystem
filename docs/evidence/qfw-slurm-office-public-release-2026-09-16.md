# QFw-SLURM public compatibility-image release — 2026-09-16

## Published package

- Package: <https://github.com/orgs/QSCSoftwareEcosystem/packages/container/package/eqo-qfw-slurm>
- Public immutable index:
  `ghcr.io/qscsoftwareecosystem/eqo-qfw-slurm@sha256:5d6a15ba9338e54c4eda135381cc74d1f65e582da9fc861abfb1c0b1dd359105`
- Published tag: `0.1.0`. Consumers must pull the immutable index above, never
  rely on a mutable tag.
- Linux/AMD64 platform manifest:
  `sha256:0fed63f95914df4927ea26a34296d1862821bc52629bffd5fb7869ecf612de41`.
- Image configuration:
  `sha256:1ee74220fa86caec44abe12993e794e9e911abef7c4ef37fdbc1e3fa6d9cd95b`.

## Remote verification

With no Docker GHCR credentials configured, `docker pull --platform linux/amd64`
successfully pulled the immutable index. `docker buildx imagetools inspect`
resolved the same index and reported the expected Linux/AMD64 platform manifest
and an attached `unknown/unknown` attestation manifest. The package API reports
public visibility. The copied OCI index therefore matches the existing office
admission evidence without rebuilding or changing the Dockerfile labels.

The copied descriptor set retains the SPDX SBOM statement
`sha256:b3fea92dff3b17c56e69ca704a5125774f941d3e1714b266d61e7fd5c79dea95`
and SLSA v1 provenance statement
`sha256:60e410b837edbb82a0c0cda1adfbf790cec1759ffa77118925a0d66821ecece4`.
The original admission statement and detached Ed25519 signature remain
unchanged and verifiable.

## Release boundary

This public package distributes a development-only office simulation fixture.
It is not facility-HPC evidence, a hardware target, or a generally available
EQO workflow, CLI, or Workbench runtime. A separate reviewed QFw operation or
target-adapter contract remains required for workflow use.
