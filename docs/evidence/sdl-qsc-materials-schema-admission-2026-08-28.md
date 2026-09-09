# SDL QSC Materials Schema Admission

- Date: 2026-08-28
- Component: `qsc-materials-db`
- Capability: `qsc-materials-db-schema@0.1.0`
- Status: static, non-executable data-service admission

## Source Check

The static record was derived from the local SDL workspace at
`../sdl/intersect-sdl-workspace`.

Observed source revisions:

- `deployments`: `51373be831a94cc06c669346ca5d1fccc3a6ed76`
- `sdl-schema`: `66399f74a2419dc650ad1d8ba1036ed5d05464c3`

Observed source paths:

- `deployments/QSC/data/README.md`
- `deployments/QSC/data/repositories.json`
- `deployments/QSC/data/materials-db/README.md`
- `deployments/QSC/data/materials-db/example-json/README.md`
- `deployments/QSC/data/materials-db/example-json/KCuF3_Hamiltonian.json`
- `implementation/schemas/README.md`
- `implementation/schemas/schemas/sdl.yaml`

## Admission Decision

QHPC admits a static `data-service` capability for discovery in the Workbench
Data area. The record publishes the QSC materials repository contract, the
phase-1 materials schema summary, the KCuF3 seed payload references, and the
SDL schema/provenance pointers.

The record intentionally does not:

- call SDL workspace-service APIs;
- call object storage or publish credentials;
- expose a QHPC workflow operation;
- claim that a generated materials-domain LinkML module exists.

Future promotion to a live `materials-db` integration should add a concrete SDL
service contract, authenticated endpoint policy, data egress review, and target
deployment approval.
