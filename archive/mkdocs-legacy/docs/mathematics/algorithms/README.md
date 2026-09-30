# Algorithms

Algorithm pages describe concrete computational procedures used to realize mathematical transformations. A single scientific transformation may have multiple algorithms, and a single algorithm may support multiple transformations.

## Current algorithm specifications

- [Motif-compatible surface primitive unit-cell generation](motif-compatible-surface-primitive-cells.md): integer-lattice and decorated-motif specification for primitive surface-cell construction.

- [Surface-cell matching and strain optimization](surface-cell-matching-and-strain-optimization.md)
- [Deduplication, equivalence, and canonicalization](deduplication-equivalence-and-canonicalization.md): HNF supercell enumeration, area-band filtering, reduced-cell matching, affine-invariant Hencky-strain diagnostics, and score ranking.

- [Monte Carlo registry alignment](monte-carlo-registry-alignment.md): stochastic optimization over the interface registry torus with optional z-padding geometry updates.

- [Geodesic strain partitioning](geodesic-strain-partitioning.md): affine-invariant SPD(2) target-metric interpolation, endpoint convention, deformation-gradient construction, Hencky diagnostics, and finite alpha-scan selection.

- [Interface construction](interface-construction.md): deterministic assembly of a built atomistic interface from a prototype, strain state, registry translation, z-padding, and provenance projection.
- [Oriented slab construction](oriented-slab-construction.md): construction of slab-periodic blocks from Miller indices, including integer surface bases, in-plane gauge reductions, Cartesian slab-frame orientation, optional c-tilt reduction, optional shear orthogonalization, vacuum insertion, and transform provenance.
- [Interfacial-energy evaluation](interfacial-energy-evaluation.md): strained-bulk reference construction, formula-unit normalization, scalar gamma reduction, denominator convention, and provenance mapping.
- [Persistence, public projection, and reporting](persistence-report-projection.md): representation-morphism specification for durable persistence rows, public sidecar records, dataset manifests, and report tables.
 
---

## Implementation notes (migration)

Small implementation-oriented notes and short examples previously lived under docs/algorithms/. During consolidation we will preserve minimal implementation pointers here and in the individual algorithm pages under this subtree as "Implementation notes" subsections. The full legacy how-to content will be migrated and/or removed in subsequent PRs.

Primary implementation modules referenced across the algorithms subtree include:

- calm.slab.ops.primitive_surface_algorithm
- calm.slab.ops.oriented_slab
- calm.math2d.normal_forms
- calm.math2d.spd2x2
- calm.interface.matching
- calm.interface.strain_partition
- calm.interface.registry_search
- calm.interface.pruning

When removing legacy materials, implementation snippets should be condensed into short practical-note subsections and appendix examples only.
