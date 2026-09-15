# ChatQEC MCP Tools Inventory — 2026-09-11

This record inventories the sibling `chatqec-mcp-tools` checkout and records
the EQO candidate-operation boundary. It is not release, target-worker, or
developer-approval evidence.

## Inspected source

- Checkout: `../chatqec-mcp-tools`
- Remote: `git@github.com:QSCSoftwareEcosystem/chatqec-mcp-tools.git`
- Revision: `dd19a85b08637a61dc1afc124d2f4b32745b527b`
- Declared package version: `0.1.0`
- Declared license: Apache-2.0
- Checkout state at inspection: clean

The repository registers eight MCP tools: `code_params`, `stim_simulate`,
`stim_diagram`, `pymatching_decode`, `threshold_sweep`, `qec_circuit_build`,
`tsim_simulate`, and `glcb_visualize_url`.

## EQO boundary recorded here

All eight source tools have typed candidate operations in
[`integrations/chatqec-mcp-tools/interface.yaml`](../../integrations/chatqec-mcp-tools/interface.yaml)
and the internal pre-alpha capability
[`capabilities/ChatQEC/tools/qhpc-capability.yaml`](../../capabilities/ChatQEC/tools/qhpc-capability.yaml).
The adapters never start the MCP server. They accept only declared parameters
and artifact ports, create typed outputs, and run in source-pinned,
network-disabled Linux containers.

`code_params`, `stim_simulate`, `stim_diagram`, `pymatching_decode`,
`threshold_sweep`, and `glcb_visualize_url` share the base QEC candidate image.
`qec_circuit_build` uses a separate image carrying ChatQEC plus the exact
LightStim commit `47dd74976780192ae901d91958863cced1165354`. `tsim_simulate`
uses a separate pinned Tsim/JAX CPU image. All three candidate images passed
local OCI smoke tests on 2026-09-14; they are unpublished and are not accepted
for an HPC target.

Opening a generated GLCB URL is explicitly an external disclosure of the
encoded circuit. Link construction itself is offline and deterministic.

The canonical source authority was confirmed on 2026-09-14. The named project
maintainer/release owner, supply-chain acceptance, and target-worker acceptance
remain required before promotion from the internal candidate.
