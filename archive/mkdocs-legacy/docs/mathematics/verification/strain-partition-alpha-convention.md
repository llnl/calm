# Strain partition alpha convention

## Purpose

This note fixes the endpoint convention for CALM's geodesic strain-partition parameter and records the implementation-level invariant that should be used by documentation and tests.

## Ontology mapping

The relevant scientific morphism is interface construction from two slab/interface-cell representations to a built interface structure. The strain partition is a representation-level choice of common in-plane target metric used during that construction; it does not create a distinct ontology object by itself.

## Mathematical convention

Let `G_A` and `G_B` be the in-plane Gram matrices for slabs A and B. CALM uses the affine-invariant geodesic on SPD(2), parameterized from A to B. The target metric satisfies:

- `alpha = 0`: `G_target = G_A`. Slab A is unstrained; slab B is deformed to match A.
- `alpha = 1`: `G_target = G_B`. Slab B is unstrained; slab A is deformed to match B.
- `alpha = 0.5`: `G_target` is the affine-invariant geodesic midpoint.

This is the convention implemented by `calm.interface.strain.compute_strain_2d` and the scan helper `calm.interface.strain_partition.scan_geodesic_strain_partitions`.

## Correctness property

For non-identical positive-definite in-plane metrics, endpoint evaluations must satisfy:

- At `alpha = 0`, `E_A_rms == 0` up to floating-point tolerance and `E_B_rms` contains the full mismatch.
- At `alpha = 1`, `E_B_rms == 0` up to floating-point tolerance and `E_A_rms` contains the full mismatch.

The scan helper must preserve this convention because it delegates endpoint evaluation to `compute_strain_2d`.

## Implementation mapping

- `calm/interface/strain.py::compute_strain_2d`
- `calm/interface/strain_partition.py::scan_geodesic_strain_partitions`
- `calm/interface/strain_partition.py::strain_partition_inplane`

## Verification mapping

- `tests/public/test_strain_partition_alpha_convention.py`

## Audit note

The traceability review found that one scan-helper docstring reversed the applied-strain interpretation of the endpoints. This page records the corrected convention and provides the endpoint invariant used for regression testing.
