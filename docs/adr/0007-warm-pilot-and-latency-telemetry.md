# ADR 0007: Warm Pilot Execution And Stage Latency Telemetry

- Status: Accepted
- Date: 2026-07-20

## Context

Submitting every short operation as a new Slurm job can make scheduler queue
time and repeated runtime or input staging dominate scientific execution. A
long-lived service allocation can reduce that delay, but it must not bypass
site scheduling, accounting, isolation, or software-approval controls. QHPC
also needs to distinguish scheduler delay from container startup, storage,
execution, and output-collection delay instead of reporting only total run
time.

## Decision

Each execution target publishes the execution classes it supports:

1. `interactive-local` uses an already-running controlled worker for approved,
   low-resource local operations.
2. `interactive-hpc-pilot` dispatches eligible short operations to workers
   inside a site-approved warm Slurm pilot allocation.
3. `batch-hpc` submits an independently scheduled job for ordinary or
   large-resource HPC work.

A pilot is capacity acquired through the scheduler under an approved account,
partition, QoS, resource ceiling, lifetime, and idle timeout. It runs no user
shell and accepts only authorized, allowlisted operations with immutable
runtime digests. Every task receives an isolated workspace and repeats artifact
authorization, input verification, output collection, and audit processing.
The allocation and verified immutable caches may remain warm, but each task's
operation starts in a fresh resource-isolated job step and clean container
process; scientific process state is never reused across tasks.

The dispatcher uses operation and target policy to determine eligibility. When
no suitable warm capacity is available, it falls back to `batch-hpc` unless the
request explicitly requires interactive service and policy permits failure
instead.

QHPC persists an append-only execution event stream scoped to a run, task
attempt, or pilot allocation. Events include a run ID, optional attempt or
pilot ID, sequence, stage name, source component, `occurred_at`, `recorded_at`,
execution class, target handle, and correlation ID. Completed stages also
retain a duration measured with a monotonic clock. The canonical run and task
events are:

```text
request_received             authorized                 run_accepted
task_queued                  task_leased
image_stage_started          image_ready
input_stage_started          inputs_ready
target_submitted             target_started
operation_started            operation_finished
output_collection_started    outputs_ready
attempt_finished | attempt_failed | attempt_canceled | attempt_timed_out
```

Terminal events identify the active stage at failure, cancellation, or timeout.
Stage ordering may vary by runner because node-local staging can occur only
after a batch allocation starts. Derived metrics separately report API,
dispatch, scheduler, image-staging, input-staging, operation,
output-collection, finalization, and end-to-end latency. `pilot_requested`,
`pilot_ready`, `pilot_draining`, and `pilot_terminated` record the capacity
lifecycle independently of task attempts.

Cross-component timestamps require target-approved clock synchronization and
retain both event and receipt time so clock uncertainty is visible. Telemetry
dimensions must not contain secret values, sensitive paths, or uncontrolled
high-cardinality data.

The Workbench displays stage state and timing without presenting warm capacity
as guaranteed queue-free execution.

## Consequences

- Short approved operations can avoid per-task scheduler acquisition and reuse
  verified image caches while preserving Slurm accounting and target policy.
- Warm capacity is optional per target and requires facility decisions about
  ownership, quota, cost, maintenance, draining, and incident response.
- The worker and runner contracts need execution-class selection, pilot
  lifecycle, capacity, fallback, and stage-event interfaces.
- Performance acceptance must compare cold batch, warm pilot, cached and
  uncached images, and verify telemetry completeness.
- SLOs remain target-specific and cannot be claimed until measured on the
  production facility.
