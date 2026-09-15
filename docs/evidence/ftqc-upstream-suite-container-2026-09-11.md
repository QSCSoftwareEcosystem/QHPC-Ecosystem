# FTQC Upstream-Suite Container Gate — 2026-09-11

## Scope

This record exercises the upstream FTQC test target before a new FTQC OCI
operation runtime can be assembled. It is not a release, hardware, or target
acceptance record.

## Immutable Inputs

| Input | Value |
| --- | --- |
| FTQC revision | `779216de8805ea0c1d473c640eaf17d6cbfa04e8` |
| LLVM/MLIR base | `zhongruoyu/llvm-ports:22-jammy@sha256:eb7caed5cfe7e765bde2c5f8e7654ceb0a0282728ea1db4433fa00c4059dc7a9` |
| LLVM source archive | `llvm-project-22.1.8.src.tar.xz` |
| LLVM source SHA-256 | `922f1817a0df7b1489272d18134ee0087a8b068828f87ac63b9861b1a9965888` |
| LLVM source origin | `https://github.com/llvm/llvm-project/releases/download/llvmorg-22.1.8/llvm-project-22.1.8.src.tar.xz` |
| Container networking | disabled |

The `test-builder` stage extracts only LLVM's `lit` Python package and the
sources for `FileCheck`, `not`, and `count`. It builds those tools against the
installed, digest-pinned LLVM 22.1.8 headers and libraries, then runs
`cmake --build /build --target check-ftqc --parallel 2`. The operation runtime
layer is copied only after that command succeeds.

## Result

The command discovered and ran 100 FTQC tests in the constrained Linux/amd64
container. Tool bootstrap succeeded (`lit 22.1.8dev` and LLVM/FileCheck
22.1.8). The FTQC target did not pass:

| Outcome | Count |
| --- | ---: |
| Passed | 91 |
| Unresolved | 5 |
| Failed | 4 |

The unresolved files are integration artifacts without a `RUN:` directive.
The failed checks include three QASM3-import expectations whose expected type
spelling differs from the emitted FTQC IR, and the physical-expansion test's
expected X/Z ancilla roles. These are upstream FTQC source/test-suite issues,
not missing LLVM test tools.

No replacement OCI image was produced or admitted. The existing locally
smoke-tested runtime remains unpublished. A corrected, checksum-pinned FTQC
revision must make `check-ftqc` pass before this gate permits image assembly
and any later publication process.
