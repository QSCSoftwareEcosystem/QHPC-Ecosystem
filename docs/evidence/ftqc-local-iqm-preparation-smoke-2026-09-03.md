# FTQC Local IQM Preparation Smoke Evidence

- Date: 2026-09-03
- Private source: `https://github.com/QSCSoftwareEcosystem/FTQC`
- Admitted revision: `779216de8805ea0c1d473c640eaf17d6cbfa04e8`
- Host: macOS arm64
- Compiler: AppleClang 21.0.0
- LLVM/MLIR: Homebrew 20.1.2

## Runtime boundary

EQO built `ftqc_capi` and `qasm3-import` from the exact Git revision in an
isolated archive checkout. The locally installed native bundle is:

```text
Reference: qhpc-runtime://native/ftqc-779216de8805-darwin-arm64.zip
SHA-256: ab1b34d6a0a86a3d522061b00b4efdea253e2c77d64b5d27a52260e0740ba215
Size: 24,641,275 bytes
Contents: bin/qasm3-import, lib/libftqc.1.0.0.dylib, manifest.json
```

The bundle is installed under the ignored `.qhpc/runtimes` state directory.
It is not committed, attached to a release, or published as an image because
the FTQC repository does not provide explicit distributable license terms.

The current native build depends on Homebrew LLVM/MLIR 20.1.2 and is therefore
a macOS arm64 local-development runtime, not the future portable runtime.

## Workbench adapter smoke

The local worker invoked `ftqc_qasm_opt` through the pinned C API for three
source-repository inputs. The adapter extracted and validated the
`ftqc.iqm_json` module attribute, then wrote typed MLIR, IQM JSON, and
preparation-report artifacts.

| Input | Preparation | IQM loci | Instructions | Routing | Submission |
| --- | --- | ---: | ---: | --- | --- |
| Bell, measured | Direct device-qubit lowering | 2 | 9 | Not performed | Not submitted |
| `logical0` | One Steane logical qubit | 7 | 58 | Not performed | Not submitted |
| `logical0-H` | One Steane logical qubit with four logical H gates | 7 | 114 | Not performed | Not submitted |

The direct Bell path does not perform Steane expansion, even though the FTQC
intermediate retains ECC type metadata. The logical paths expand one
Steane `[[7,1,3]]` logical qubit to seven data-qubit loci.

## Claim boundary

This evidence verifies credential-free local compilation and IQM preparation.
It does not verify calibration compatibility, topology routing, hardware
submission, measurement results, logical correction, error suppression, or
fault-tolerant advantage. Routing remains a separate qiskit-iqm stage that
must receive credentials from a backend secret boundary rather than from the
browser or workflow document.
