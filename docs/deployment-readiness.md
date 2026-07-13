# HPC and DOE Deployment Readiness

- Last updated: 2026-07-11
- Local MVP status: implemented and verified
- Production deployment status: blocked on institutional services and review

## Implemented Boundaries

- Immutable OCI, Apptainer, reproducible Python-wheel, and native-bundle
  runtime contracts.
- Controlled local runner with an explicit operation allowlist.
- Slurm submission, state classification, accounting fallback, and cancellation
  primitives.
- Apptainer batch-script rendering from validated argument tokens with resource
  limits and no user-supplied shell body.
- Default-deny role/action policy definitions.
- Secret-reference validation that excludes embedded credentials.
- Append-only SHA-256 chained audit records with tamper verification.
- Persistent workflow, run, task, artifact, checksum, log, retry, cancellation,
  lease, and export behavior.

## External Decisions Required

The following cannot be selected or certified from this development workspace:

1. Approved institutional identity provider and trusted authentication headers
   or token validation boundary.
2. Group-to-role mappings and resource ownership policy.
3. Internal OCI registry or Apptainer image cache, signing, and retention.
4. Artifact storage service, encryption, quotas, retention, and backup.
5. Target Slurm clusters, partitions, accounts, QoS, modules, and launch policy.
6. Allowed egress, proxy, repository, package-index, and quantum-backend routes.
7. Secrets provider and workload identity mechanism.
8. Central audit sink, retention period, access controls, and incident process.
9. SBOM, vulnerability, attestation, export-control, and release gates.
10. Availability, restore, monitoring, maintenance, and operations ownership.

These decisions block `production-approved` status. They do not block local
contract, workflow, API, workbench, or controlled-runner development.

## Target Acceptance Tests

- Submit, poll, cancel, timeout, and classify a controlled Slurm job.
- Run the same pinned operation locally and through Slurm with equivalent
  artifact contracts.
- Verify Apptainer image digest and signature before execution.
- Demonstrate denied publication and execution for unauthorized identities.
- Verify secret values never appear in workflows, logs, exports, or images.
- Forward and verify chained audit events in the approved central sink.
- Restore registry, workflow state, and artifact metadata from backup.
