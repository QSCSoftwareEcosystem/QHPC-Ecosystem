# NWQ-Sim CPU State-Vector Source Audit

Date: 2026-09-16

This admission creates a narrow EQO development operation from the NWQ-Sim
mainline source. It does not activate the TN-Sim MPS record, the QFlow VQE
plugin, a QFw workflow, or an HPC execution target.

## Pinned source

- Canonical source: `https://github.com/pnnl/NWQ-Sim`
- Revision: `b35763d846e6512ed817d3f88ac8ce79a7e82a7e`
- Git archive digest: `sha256:87ece7adc6b991eb8f1b5fb35a1825be77abdfb9cdf0f83f9ccd460a9f383589`
- Source commit time: `1776445008`
- Observed submodule revisions: NLopt `7a7587e5ef1cb15f412515d852d1fc261c863e96`; pybind11 `e6984c805ec09c0e5f826e3081a32f322a6bfe63`.

## Admitted boundary

The source `qasm/nwq_qasm.cpp` builds as a portable C++17 CPU runner without
the optional VQE, CUDA, HIP, MPI, or iTensor TN-Sim dependencies. The EQO
wrapper fixes `--backend cpu --sim sv`, accepts only an OpenQASM 2.0 circuit
mounted at `/inputs/circuit.qasm`, and emits normalized counts at
`/outputs/measurements.json`. It admits one qreg of at most sixteen qubits,
at most one million shots, and an explicit random seed.

The pinned source was compiled and run locally against a two-qubit Bell
circuit with 128 shots and seed 42. It returned only `00` and `11` counts,
which summed to 128. OCI smoke and reproducibility evidence follows only
after the sealed operation context is built.

## Explicit exclusions

- TN-Sim's iTensor-backed MPS operation remains non-executable pending its
  separate reproducible runtime work.
- The QFlow VQE plugin remains an uncommitted qiris-qflow development patch.
- MPI, GPU, noise, initial/dumped state files, Qobj input, benchmarks, and
  arbitrary CLI arguments are not part of this operation.
- This evidence is local development evidence, not facility-HPC validation.
