# ADR 0002: Independent DOE-Controlled Workbench

- Status: Accepted
- Date: 2026-07-10

## Context

Scientific workflow platforms demonstrate useful interaction patterns such as
tool discovery, typed workflow composition, execution histories, artifact
inspection, and reproducibility. DOE constraints require the QHPC platform to
be independently developed and controlled.

## Decision

QHPC will implement its own workflow contracts, engine, APIs, interface, visual
design, runners, and deployment. Galaxy may inform product requirements, but
QHPC will not incorporate Galaxy source code, schemas, wrappers, API design,
visual assets, or page layouts.

The initial workbench will run against a controlled local runner. Slurm,
Apptainer, institutional identity, authorization, auditing, secrets, registry,
storage, and network controls will be added through explicit interfaces and
reviewed deployment decisions.

## Consequences

- QHPC can model quantum-HPC artifacts, resources, backends, and project
  ownership directly.
- The team owns the cost of workflow-engine correctness, UI behavior,
  provenance, operations, and security maintenance.
- Standard third-party frameworks and libraries may be used only after the
  applicable dependency and deployment review; they do not alter the clean
  platform boundary.
- Workbench implementation should not begin by reproducing another platform's
  screens. It begins with QHPC contracts, engine behavior, and user workflows.
