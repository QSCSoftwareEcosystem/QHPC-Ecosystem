# FTQC IQM One-Logical-Qubit Hardware Demonstration Candidate

- Audit date: 2026-07-29
- Claim status: developer-reported and source-supported; result evidence pending
- Admitted FTQC revision: `947fd0a067f15a9f9d6e7418742080cf34cfb51a`
- IQM branch revision contained by the admitted revision:
  `74510158980077c6e5b08ec6d075954b964a4add`
- Promotion effect: none; this record does not verify an executable FTQC
  runtime or production hardware target

## Reported demonstration

The FTQC developers reported to the ecosystem maintainer that the compiler
path ran one logical qubit on an IQM system at ORNL. The source tree strongly
supports the existence and intended use of that path, but the repository does
not preserve the execution receipt or measurement result needed to accept the
run as verified hardware evidence.

This distinction matters: executing an encoded one-logical-qubit circuit does
not by itself demonstrate fault-tolerant logical performance, error
suppression, or an advantage over a physical-qubit baseline.

## Source-backed path

The admitted revision contains a complete development path:

```text
OpenQASM 3
  -> FTQC logical MLIR
  -> Steane [[7,1,3]] physical expansion
  -> IQM-native JSON
  -> qiskit-iqm device routing
  -> ORNL IQM submission
  -> physical counts
  -> raw and syndrome-corrected logical-bit summaries
```

The relevant source facts are:

- `test/Integration/logical0.qasm` declares one input qubit and one
  measurement. Its SHA-256 is
  `22eae76bf1e22fc50b0dc2604b186ed726647196c6c34baf14e2f025fa8ab21c`.
- `test/Integration/logical0-H.qasm` applies four logical Hadamard gates before
  measurement. Its SHA-256 is
  `eb1994012307ba6468f3e63c36ab6b295fa9d64661c924d9c3f4cf436f451325`.
- `demo.sh` submits both fixtures with physical Steane expansion and 512
  shots. Its SHA-256 is
  `3bd7ce173d0aa08a1e0b6195eb2e28e36a6bcd787d212dfd5c98b169ddb21c65`.
- `ftqc_iris_task.py` implements the QASM-to-MLIR tasks, seven-data-qubit
  Steane expansion, IQM JSON lowering, topology-aware routing, submission, and
  raw/corrected logical-bit reporting. Its SHA-256 is
  `df9d6ee40df9b5f2cf17007f7f7f99134beb1ab91130ddef8f7e68acaf6b5c92`.
- The tracked `topology/crystal_topology.json` snapshot describes 20 available
  qubits, 30 connections, and calibration
  `M194_F0W1388_P08_Q12 @ 2026-07-07 07:23 UTC`. Its SHA-256 is
  `c858cb8d2eeb3aaeb58d6a1703234d986db592dab58a482e3863cbfba0246312`.
- The commit history explicitly introduces scripts for a real IQM system,
  names an ORNL IQM/Crystal topology, adds IQM task submission, adds
  topology-aware routing, and adds the two one-logical-qubit demo fixtures
  between 2026-06-29 and 2026-07-08.

ORNL publicly announced that its 20-qubit IQM Radiance system, Pathfinder,
launched on 2026-06-16 for QSC and QHPC software-stack research:
<https://www.olcf.ornl.gov/2026/07/08/ornl-deploys-new-iqm-quantum-computer/>.
The repository calls its live 20-qubit backend `Crystal`/`default`; EQO-QSC
does not assume that this is identical to Pathfinder until the FTQC developers
confirm the device identity.

## Evidence still required

The repository does not contain a tracked hardware job receipt, job identifier,
submission and completion timestamps, generated IQM JSON for either
one-logical-qubit fixture, selected physical layout, raw counts, corrected
logical histogram, run log, or screenshot.

To promote the candidate to accepted hardware evidence, preserve a
developer-approved packet containing:

1. FTQC revision and clean-tree state.
2. Device identity, endpoint class, and calibration identifier without
   credentials.
3. Input fixture and generated IQM JSON digests.
4. Compiler and routing parameters, selected physical qubits, shot count, and
   decoder/post-processing settings.
5. Hardware job identifier, timestamps, terminal state, and redacted receipt.
6. Raw physical counts and raw/corrected logical-bit summaries.
7. A stated acceptance rule and, if fault-tolerance is claimed, a physical
   baseline or error-suppression comparison.

Until that packet is attached, the Workbench may describe the demonstration as
developer-reported and source-supported, but must not label it verified,
reproducible, production-approved, or fault-tolerant hardware evidence.

## Workbench representation

Compose exposes this path as **One logical qubit on IQM**, a non-executable
hardware-evidence blueprint. It mirrors the source-backed compiler, encoding,
IQM lowering, routing, submission, and logical-result stages while keeping
**Run unavailable**. The blueprint is an inspection and promotion-planning
surface; its presence does not change FTQC's runtime, validation, or hardware
evidence status.
