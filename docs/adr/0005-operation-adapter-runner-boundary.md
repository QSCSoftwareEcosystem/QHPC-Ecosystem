# ADR 0005: Separate Operation Adapters From Target Runners

- Status: Accepted
- Date: 2026-07-14

## Context

The local adapters currently combine project-specific invocation, subprocess
execution, runtime resolution, result parsing, and artifact creation. Extending
that pattern to every project and execution target would duplicate transport
logic and couple scientific integrations to Slurm or local host behavior.

## Decision

QHPC separates operation adapters from execution-target runners.

An adapter translates a validated operation request into a fixed invocation,
declared relative inputs, and an output manifest. The default adapter is
declarative and executes an argument vector without a shell. A custom adapter
is allowed only for a versioned, allowlisted project API or result format.

A runner owns transport and lifecycle behavior: prepare, submit, poll,
heartbeat, cancel, and collect. Local, Slurm, and quantum runners implement the
same lifecycle and persist an external execution handle where applicable.

The worker owns staging and artifact ingestion. It verifies inputs before
execution and computes output checksums after collecting declared files. An
adapter cannot designate an arbitrary host URI as a trusted artifact.

## Consequences

- One project adapter can run on every compatible target.
- Slurm scheduling logic is not repeated in scientific integrations.
- Target policy controls host paths, devices, libraries, networks, and secrets.
- Custom adapters become release artifacts with versions, tests, evidence, and
  immutable runtime identities.
- The current synchronous `Runner.execute` protocol remains an MVP interface
  and must evolve before production Slurm integration.
