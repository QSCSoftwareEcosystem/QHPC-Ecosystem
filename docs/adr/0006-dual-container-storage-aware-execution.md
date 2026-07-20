# ADR 0006: Dual Container Model And Storage-Aware Execution

- Status: Accepted
- Date: 2026-07-14

## Context

QHPC currently provides shared Apptainer development images, a verified Python
wheel, and Darwin native bundles. These prove local integration but are not
tool-specific Linux production runtimes. HPC feedback also identified storage
and RDMA performance as an architectural concern. A container image can be
reproducible while still performing poorly when it is repeatedly loaded from a
parallel filesystem, uses a writable overlay, generates metadata-heavy I/O, or
cannot access compatible host communication libraries and devices.

## Decision

QHPC uses two container models:

1. Developer environments provide Distrobox-like shell and command access,
   share toolchains by environment class, and bind source at `/workspace`.
2. Operation runtimes are tool-specific immutable Linux images used by workers
   for workflow execution. They use digest-pinned references and the applicable
   signature, SBOM, attestation, and release evidence.

QHPC retains Apptainer for HPC execution. Storage and RDMA behavior is defined
by an approved execution-target storage profile rather than embedded as
site-specific paths or kernel components in an image.

The worker uses only administrator-defined logical binds. It may stage the SIF
and inputs to node-local storage, uses node-local scratch for temporary data
when appropriate, binds approved parallel filesystems directly, and collects
only declared outputs. Host MPI, UCX, libfabric, RDMA, GPU, and GPUDirect
components are exposed according to target policy and ABI compatibility.

Production jobs do not build or pull images at execution time. Native and
container I/O and application performance are measured on each target before
approval.

## Consequences

- Developer convenience does not determine production runtime identity.
- A new container technology is not required to address storage delay.
- Rebuilding an image is necessary only for application packaging or user-space
  ABI compatibility; staging and bind-path problems are corrected in the
  target runner.
- Execution-target contracts must add storage topology, staging, and RDMA
  capabilities in a future schema revision.
- Slurm integration must persist staging and external-job state and must not
  rely on unrestricted user-provided host paths.
- Production approval requires measured native-versus-container acceptance on
  the actual target system.
