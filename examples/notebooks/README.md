# EQO Python and Jupyter examples

Every executable example connects through `EQOClient` to the same control API
used by the Workbench and CLI. A notebook does not import a project tool, pull
an image, start a container, or obtain a model or hardware credential. It
creates typed input artifacts and submits a published EQO workflow.

Start the local profile first:

```bash
eqo local up
python -m pip install -e ".[jupyter]"
jupyter lab examples/notebooks
```

Set `EQO_ENDPOINT` only when the API is not at `http://127.0.0.1:8080`.

| Notebook | Workflow or boundary | What it demonstrates |
| --- | --- | --- |
| `eqo_chatqec_fallback.ipynb` | ChatQEC assistant service | Cited canonical-corpus answer through EQO; no direct model, corpus, or MCP connection. |
| `eqo_chatqec_tools.ipynb` | All eight ChatQEC tools | Code parameters; LightStim → Stim simulation, diagram, and PyMatching; threshold sweep; Tsim; and opt-in GLCB link generation. |
| `eqo_openqevo_methods.ipynb` | OpenQEvo catalog, context, dense reference | Registered methods, one method's documented boundary, and a bounded numerical reference. |
| `eqo_openqevo_trotter.ipynb` | `openqevo-trotter-synthesis` | Pauli Hamiltonian to an attributed OpenQASM circuit. |
| `eqo_evolution_readiness.ipynb` | `showcase-evolution-readiness` | OpenQEvo → QASMTrans → STABSim, plus NWQEC resource counting. |
| `eqo_qec_memory_study.ipynb` | `qec-memory-estimation` | FTPrimitiveBench → LightStim logical-error estimate. |
| `eqo_ftqc_preparation.ipynb` | `ftqc-iqm-steane-preparation` | FTQC preparation boundary with no IQM submission. |
| `eqo_ftqc_iqm_experiment.ipynb` | `ftqc-iqm-bell-execution` | FTQC → IQM simulation or an admitted internal IQM worker; credentials remain worker-local. |
| `eqo_h6_qflow_boundary.ipynb` | H6 QFlow incubation blueprint | Evidence and ownership boundary only—no run exists yet. |

## Preconditions for container-backed examples

The default internal development profile validates its required core operation
images at startup. ChatQEC scientific-tool images are optional at startup so
the Workbench remains available on a minimal local installation. Before using
the ChatQEC tool gallery, install the exact image identities recorded in
[`docs/evidence/chatqec-tool-operations-oci-smoke-2026-09-14.md`](../../docs/evidence/chatqec-tool-operations-oci-smoke-2026-09-14.md), building each from its checksum-pinned runtime definition and source cache when it is absent. Never replace an admitted workflow with a host-side Python call.

The IQM experiment requires either `eqo local up --iqm-simulation` or an
admitted internal IQM worker. A notebook neither accepts nor transmits an IQM
token.

The H6/QFlow notebook has no runtime precondition because it is not an
executable integration. Its documented gates must be resolved before it can
become an EQO workflow.
