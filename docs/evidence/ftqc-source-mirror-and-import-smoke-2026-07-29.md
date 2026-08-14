# FTQC Source, Mirror, and Import Smoke Evidence

- Date: 2026-07-29
- Internal upstream: `https://code.ornl.gov/qsc-ct/ftqc`
- QHPC working mirror: `https://github.com/QSCSoftwareThrust/FTQC`
- Admitted revision: `947fd0a067f15a9f9d6e7418742080cf34cfb51a`
- Source tree: `822214a378d199fb102e01055843baf011f705ef`

## Mirror verification

The internal GitLab repository and private GitHub mirror expose the same seven
branches at identical commit IDs:

| Branch | Revision |
| --- | --- |
| `main` | `947fd0a067f15a9f9d6e7418742080cf34cfb51a` |
| `iqm` | `74510158980077c6e5b08ec6d075954b964a4add` |
| `lightstim` | `04674f08bb2cf490092e41dd9e1b0aeeae89e821` |
| `lightstim.atomic` | `8604e080e2d9ad994217b60b55a34b3cd8b54720` |
| `qsim` | `16f14cce3c2333992c5b4efea1f1f51f9cfa7163` |
| `qsim.qir` | `0221453a9addc8c156b5f0db6d1419e477eaad17` |
| `ulrik/qldpc` | `fba38f15befed8cda32ddd42c8df95fc078bfa19` |

Neither repository exposes tags. The synchronization copied branches and tags
only; no GitLab-specific refs were published.

## Source audit

FTQC is a C++17 LLVM/MLIR 22 compiler project. The pinned source provides the
`ftqc-opt` driver, a standalone dependency-light `qasm3-import` frontend,
fault-tolerant dialect operations and passes, resource estimation, and QASM 3,
STIM, QIR, and IQM JSON lowerings. The repository contains 94 MLIR fixtures and
five QASM fixtures.

No license, copying, or notice file is present at the admitted revision. No
container recipe or portable LLVM/MLIR dependency lock is present. Scripts that
use IQM credentials read them from environment variables; the audited main tree
does not hard-code an API token.

## Source-backed import smoke

The standalone importer was compiled directly from the admitted source:

```text
Compiler: Apple clang 21.0.0, arm64-apple-darwin
Command: clang++ -std=c++17 -O2 src/qasm3-import.cpp
Binary SHA-256: 9484444ef342317d678dad52784c54cb6595a3c61b5539bb03261a1b37a58622
Fixture: test/Integration/bell.qasm
Arguments: --ecc=steane --distance=3 --func-name=bell
Output SHA-256: ecbd136d17bb29efa6415751171ae491ff2b52aad0826c99fc419833f5196e1d
```

The output contains the expected FTQC MLIR initialization, logical Hadamard,
logical CNOT, measurements, and return operation. The ecosystem fixture records
that exact text.

## Activation boundary

This evidence admits the source, interface, and adapter but not an executable
Workbench operation. Full activation requires an exact-revision LLVM/MLIR 22
Linux build, upstream lit execution, explicit distribution terms, immutable
OCI and SIF publication, supply-chain evidence, and target acceptance.

The same admitted revision also contains a real-IQM development path and
one-logical-qubit fixtures. The separate
[IQM hardware demonstration candidate](ftqc-iqm-logical-qubit-candidate-2026-07-29.md)
records what the source proves, what the developers reported, and why a
hardware job receipt and measurement artifacts are still required before that
run can be labeled verified evidence.
