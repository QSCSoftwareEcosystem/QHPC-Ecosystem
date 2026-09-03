---
topic_slug: lattice-surgery
title: "Lattice Surgery"
aliases:
  - "surface code lattice surgery"
  - "merge and split"
see_also:
  - surface-code
  - code-deformation
  - magic-state-injection
authority_tier: canonical
last_reviewed: 2026-07-10
maintainers:
  - sharmin
---

# Lattice Surgery

Lattice surgery is the standard way to perform two-qubit logical operations
between [[surface-code]] patches using only **local, 2D** operations. Instead of
transversal gates (which require moving qubits or long-range coupling), it
realizes logical measurements by temporarily merging and splitting code patches
along their boundaries.

## Merge and split

Two surface-code patches placed side by side are **merged** by turning on the
stabilizer checks in the gap between them. Measuring those new checks projects the
pair into an eigenstate of a joint logical operator — a merge along a $Z$
(rough) boundary measures $Z_L \otimes Z_L$; a merge along an $X$ (smooth)
boundary measures $X_L \otimes X_L$.

**Splitting** turns the boundary checks back off, separating the patches again.
The product of the boundary-check outcomes gives the parity of the joint
measurement, which is the logical result.

## Building a CNOT

A logical CNOT is assembled from joint $XX$ and $ZZ$ measurements plus an ancilla
patch and single-patch measurements — the same primitive set as measurement-based
computation. Because every step is a local 2D operation on nearest-neighbor
qubits, lattice surgery is the preferred model for a planar superconducting
architecture (see [[superconducting-qec]]).

## Relationship to code deformation

Merging and splitting are special cases of [[code-deformation]] — moving code
boundaries by changing which stabilizers are measured. The joint measurements
lattice surgery provides are exactly what is needed to consume magic states via
[[magic-state-injection]], making it the connective tissue of a surface-code
fault-tolerant processor.

## Cost

Each merge takes $d$ rounds of syndrome extraction (to protect the new checks
against measurement error), so lattice-surgery operations are the dominant
space-time cost in surface-code resource estimates.

## See also

- [[surface-code]] — the code lattice surgery operates on
- [[code-deformation]] — the general framework it belongs to
- [[magic-state-injection]] — consumes magic states through surgery
