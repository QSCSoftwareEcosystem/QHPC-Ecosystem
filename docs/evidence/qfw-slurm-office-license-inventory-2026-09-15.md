# QFw-SLURM office compatibility image license inventory

This inventory accompanies the Linux/AMD64 QFw-SLURM compatibility image
admitted on 2026-09-15. It is an engineering inventory for development use,
not legal advice or an approval of downstream redistribution.

## Evidence inputs

- Immutable platform manifest:
  `sha256:0fed63f95914df4927ea26a34296d1862821bc52629bffd5fb7869ecf612de41`.
- Image configuration:
  `sha256:1ee74220fa86caec44abe12993e794e9e911abef7c4ef37fdbc1e3fa6d9cd95b`.
- SPDX in-toto statement:
  `qfw-slurm-office-sbom-2026-09-15.spdx.json`
  (`sha256:b3fea92dff3b17c56e69ca704a5125774f941d3e1714b266d61e7fd5c79dea95`).
- Exact installed RPM inventory, including package-declared license expressions:
  `infrastructure/test-clusters/qfw-slurm-cluster/rpm.qhpc.lock`
  (`sha256:1f1671e859e7ee60451c486261f22b4b4231885bf025b361917be23f0b6855d3`).
- Pinned source, archive, Python, and helper inputs:
  `infrastructure/test-clusters/qfw-slurm-cluster/source-lock.json`.

## Findings

The generated SPDX document contains 800 package records. Its package-level
license conclusion fields report 795 `NOASSERTION`, 3 `MIT`, 1 `BSD-3-Clause`,
and 1 combined Apache/BSD expression. `NOASSERTION` means the scanner did not
derive a conclusive license; it must not be treated as a license grant. The
RPM lock is therefore retained as the authoritative package-manager inventory
for the Rocky Linux packages and their declared license expressions.

The directly reviewed OpenQSE source inputs are QFw, DEFw, qhw-admission,
qhw-data, qhw-datastructures, qhw-iqm, qhw-scheduler, and qfw-slurm, all
BSD-3-Clause at the pinned commits recorded in the source lock. The upstream
QFw-SLURM-Cluster checkout is MIT. Other transitive source and archive inputs
remain pinned and are represented in the SBOM and source lock; their license
texts and obligations require normal downstream legal review before any
distribution or production use.

## Review boundary

This evidence supports an isolated office development simulation only. It
does not approve facility deployment, device credentials, a production image
registry, or an EQO QFw workflow/target adapter.
