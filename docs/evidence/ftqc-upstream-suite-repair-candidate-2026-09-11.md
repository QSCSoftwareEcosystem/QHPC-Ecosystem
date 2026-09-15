# FTQC Upstream-Suite Repair Candidate — 2026-09-11

## Scope and Boundary

This is a local, non-admitted source-repair validation. It demonstrates that
the pinned LLVM/MLIR test-enabled OCI builder correctly passes FTQC's complete
applicable upstream suite after narrow test-suite corrections. It is not a
source-release, OCI-release, SIF, HPC, or IQM hardware-acceptance record.

## Reproduced Baseline

The committed FTQC revision
`779216de8805ea0c1d473c640eaf17d6cbfa04e8` was first run in the same
network-disabled Linux/amd64 builder specified by
`containers/operations/ftqc/runtime.yaml`.

| Outcome | Count |
| --- | ---: |
| Passed | 91 |
| Unresolved | 5 |
| Failed | 4 |

The unresolved files were checked-in MLIR input/reference artifacts with no
`RUN:` directive. The failed expectations assumed non-canonical MLIR spelling,
`func.return` instead of the printer's `return`, a non-shorthand `CCZ`
magic-state type, and distinct `x_anc`/`z_anc` roles even though the current
implementation uses three reusable `anc` qubits.

## Local Repair Candidate

The local candidate changes only FTQC test configuration, test expectations,
and the matching source comment:

- exclude the five non-test `.mlir` fixtures from lit discovery;
- test semantic QASM3-import output while allowing MLIR's canonical shorthand;
- test the emitted `CCZ` magic state and `return` spelling;
- assert three reusable `anc` roles, matching `STEANE_ANC = 3` and the
  implementation; and
- describe the actual reusable-ancilla behavior in `ExpandPhysical.cpp`.

The candidate source archive has digest
`sha256:b8f8e2efc48dbb3d694ee5e8e974d77f19d70c109e335892b2aede7cbd12f3ac`.
It is intentionally distinct from the admitted runtime manifest's source
archive: the repair has not yet been reviewed and committed to FTQC.

## Container Validation

| Input | Value |
| --- | --- |
| Builder and runtime base | `zhongruoyu/llvm-ports:22-jammy@sha256:eb7caed5cfe7e765bde2c5f8e7654ceb0a0282728ea1db4433fa00c4059dc7a9` |
| LLVM source | `llvm-project-22.1.8.src.tar.xz` (`sha256:922f1817a0df7b1489272d18134ee0087a8b068828f87ac63b9861b1a9965888`) |
| Test tools | `llvm-lit`, `FileCheck`, `not`, and `count`, built in the test-builder |
| Platform | `linux/amd64` |
| Builder networking | disabled |
| Full-suite command | `cmake --build /build --target check-ftqc --parallel 2` |
| Full-suite result | 95 discovered, 95 passed |
| Candidate local tag | `qhpc/ftqc:779216de-suite-repair-b8f8e2e` |
| Candidate image ID | `sha256:94afc8d04a24183d0db054845fe407c0ca698740b54c50bab32a476d284e6a2f` |

The candidate was then run through the declared no-network, read-only-root OCI
Bell smoke. It produced the required MLIR program, IQM circuit JSON, and
preparation report. Its same constrained execution also prepared both
credential-free Steane fixtures:

| Input | Preparation result | Routing / submission |
| --- | --- | --- |
| `logical0.qasm` | 7 loci, 58 instructions | not performed / not submitted |
| `logical0-H.qasm` | 7 loci, 114 instructions | not performed / not submitted |

The candidate is local-only and does not replace the existing admitted image
or permit publication.

## Required Admission Action

An FTQC maintainer must review and commit the repair, after which EQO must pin
the new immutable revision and its git-archive digest in the runtime manifest.
EQO must then rebuild the test-enabled OCI image from that exact revision and
rerun the full suite and OCI smoke before any image, SIF, provenance, or target
HPC release gate can be considered.
