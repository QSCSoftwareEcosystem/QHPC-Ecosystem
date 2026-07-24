# Initial Component Source Audit - 2026-07-22

This evidence record covers source-level integration decisions made before
adapter implementation and production containerization. Public source was
inspected at exact revisions. The audit does not claim project review,
production runtime verification, or target acceptance.

## TN-Sim Source Identification

- Source: `https://github.com/pnnl/NWQ-Sim/tree/tn_sim`
- Branch: `tn_sim`
- Verified branch head: `0f15b60012ccc62e2c9f71ceb2c411ad07d3b13b`
- Visibility: public upstream in `pnnl/NWQ-Sim`.
- Mirror decision: no QSC GitHub mirror is required because the component is
  already publicly available from its canonical upstream branch.
- Audit boundary at the time of this record: source identity only. The
  subsequent exact-tree code/interface audit, CPU iTensor MPS operation
  boundary, controlled adapter, and remaining runtime gates are recorded in
  [tn-sim-source-audit-2026-07-24.md](tn-sim-source-audit-2026-07-24.md).

## NWQEC

- Source: `https://github.com/pnnl/nwqec`
- Revision: `d93299c2a0fe47fb7758bff02b456acfb3ac4416`
- Package version: `0.1.2`
- License: MIT
- Platforms: documented macOS and Linux support with C++17, CMake, GMP, MPFR,
  and Python bindings.
- Evidence inspected: README, Python API reference, C++ CLI guide, package
  metadata, Python bindings, tests, and the checked-in OpenQASM fixture.
- Stable candidate: `load_qasm()` followed by `get_clifford_t_counts()`.
  The project documents this as exact counting without materializing the final
  Clifford and T circuit, and its Python tests exercise the path and invalid
  error-policy handling.
- Initial QHPC scope: OpenQASM 2.0 input to structured Clifford and T count
  output. Full circuit transformation, PBC conversion, and Tfuse remain later
  operations.

## FTPrimitiveBench

- Source: `https://github.com/ShuwenKan/FTPrimitiveBench`
- Revision: `ba15eba263ac6d641d225984fa074f4ee25bb462`
- Package version: `0.1.0`
- License: MIT, with documented CC-BY 4.0 attribution for identified adapted
  material.
- Platforms: pure Python package over `stim` and `numpy`; Python 3.10 through
  3.12 are declared.
- Evidence inspected: README, package metadata, public package exports,
  memory-circuit implementation, and focused package and memory tests.
- Stable candidate: `ft_primitive_bench.surface_code.circuits.memory()`.
  The public API returns a `stim.Circuit`; tests verify X and Z bases, detector
  and observable annotations, rectangular distances, noise compatibility, and
  invalid parameters.
- Initial QHPC scope: deterministic parameterized memory-circuit construction
  with detector-annotated Stim text output and the project's uniform
  depolarizing noise model. Additional primitives and noise models remain later
  operations.

## LightStim

- Source: `https://github.com/QuTone/LightStim`
- Revision: `b08d4c2f9cd69531a51b658e6f88089be69f16c0`
- Package version: `0.1.0`
- License: Apache-2.0
- Platforms: Python 3.10 through 3.12 are declared. Core dependencies include
  Stim, Sinter, PyMatching, NumPy, and pandas; optional decoders and GPU support
  are separate extras.
- Evidence inspected: README, package metadata, simulation API, repository
  tree, memory benchmark tests, and the optional FastAPI server contract.
- Stable candidate: `SimulationPipeline` with `DecoderConfig("pymatching")`.
  The documented pipeline accepts a `stim.Circuit` and returns shots,
  post-selected shots, logical errors, logical-error rate, Wilson error bar,
  elapsed time, and decoder identity.
- Initial QHPC scope: stochastic logical-error estimation from a
  detector-annotated Stim circuit using only the core PyMatching decoder. Other
  decoders, GPU execution, and LightStim's unauthenticated development HTTP
  server remain outside the initial boundary.

## Proposed FTPrimitiveBench To LightStim Boundary

FTPrimitiveBench documents its generated detector-annotated circuits as ready
for Sinter and PyMatching. LightStim's documented simulation pipeline consumes
`stim.Circuit` and provides a PyMatching decoder. The shared draft artifact
`qhpc.stim-circuit@1` therefore forms a source-supported candidate boundary:

```text
FTPrimitiveBench build-memory
        -> qhpc.stim-circuit@1
        -> LightStim estimate-logical-error
        -> qhpc.logical-error-estimate@1
```

The runtime-free interface is implemented by controlled adapters and has been
exercised end to end against the pinned project revisions. Registry publication
still requires an accepted immutable runtime and executable capability
descriptor.

## Adapter Verification

The pinned public sources were installed into an isolated temporary Python
environment. This did not modify the project environment and did not build or
exercise a production container.

- NWQEC's default isolated build failed when the unconstrained build process
  selected a newer `scikit-build-core` release that rejects the deprecated
  `cmake.minimum-version` key in the upstream `pyproject.toml`. Repeating the
  source build with the compatible `scikit-build-core==0.10.7` backend
  succeeded. The resulting local wheel had SHA-256
  `5c1af79f8a75f48de4a57b811a3bb753f10e56aae26a833502f52a5469caca57`.
- `tools/verify_nwqec.py` exercised the controlled adapter against the pinned
  NWQEC source. The representative three-qubit OpenQASM input produced exact
  counts of 5 CX, 77 H, 3 measurement, 36 S, 75 T, 1 T-dagger, and 2 X gates;
  the structured result reported 76 total T/T-dagger gates with the `total`
  error policy and epsilon `0.01`.
- `tools/verify_ftprimitivebench_lightstim.py` passed a circuit generated by
  the pinned FTPrimitiveBench source directly into the pinned LightStim
  PyMatching pipeline. The deterministic circuit contained 24 detectors and
  one observable, serialized to 3,643 bytes, and had SHA-256
  `0d01683a4aadd43074e730f12e96d4ad8739c76c8c6c38bd574e40a16e94779c`
  on repeated construction.
- The LightStim result contained the contracted shots, post-selected shots,
  errors, logical-error rate, Wilson error bar, elapsed time, and decoder
  identity fields. Exact statistical values and elapsed time are intentionally
  not acceptance criteria because the operation is stochastic.

These checks establish the source-to-adapter and FTPrimitiveBench-to-LightStim
boundaries only. They do not establish a production runtime, HPC target
compatibility, project endorsement, or DOE deployment acceptance.

## ChatQEC

- QHPC working source: `https://github.com/QSCSoftwareThrust/ChatQEC`
- Revision: `4c017510511f835001bfe5901a9d59e86cc130cd`
- Package version: `0.1.0`
- License: Apache-2.0
- Platforms: Python 3.11 and 3.12 are declared.
- Authentication: GitHub SSH access was verified without recording a
  credential in this repository. The existing dedicated GitLab key was also
  authenticated for secondary-mirror inspection.
- Source identity: `QSCSoftwareThrust/ChatQEC` GitHub `main` and secondary
  `qsc-as/chatqec` GitLab `main` both resolved to the audited revision. On
  2026-07-24 the ecosystem maintainer selected GitHub as the QHPC working
  source. The separate `QSCSoftware/chatqec` GitLab copy resolves to older
  revision `7d1dd580956fe05b33c8ac382a8422f27c44968c` and must not overwrite the
  GitHub source.
- Evidence inspected: package metadata, README, design records, configuration,
  public Python API, CLI builder, Streamlit application, Qdrant store, provider
  adapters, conversation memory, image handling, MCP client, guards, tracing,
  and focused tests.
- Stable candidate: the public `ChatQEC.ask()` and `ask_stream()` behavior,
  adapted behind a new versioned internal service API. The current repository
  has no HTTP service interface; Streamlit and the CLI build the Python object
  directly.
- Initial QHPC scope: authenticated, cited text answers over a versioned
  read-only corpus. Corpus ingestion, image input, web fallback, direct MCP
  execution, and workflow execution remain outside the first boundary.

ChatQEC currently uses Qdrant hybrid retrieval, a canonical wiki, external or
serverless model providers, optional Tavily search, and optional subprocess MCP
tools. Production cannot retain its automatic provider failover because that
can change the data recipient. The Streamlit resource cache also shares one
`ChatQEC` instance with in-memory conversation state, so it is not a multi-user
service boundary. Verbose tracing records full payloads, and the development
Compose file publishes unauthenticated Qdrant ports to the host.

[ADR 0008](../adr/0008-chatqec-internal-service-boundary.md) records the
accepted internal boundary. The shorter
[service-boundary explanation](../chatqec-service-boundary.md) is the primary
future-facing summary. This was a source and architecture audit only; project
dependencies, model calls, corpus queries, and the upstream test suite were not
executed.
