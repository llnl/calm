# Mathematical audit inventory

This page opens the audit phase of the Mathematical and Algorithmic Specification milestone. Earlier pages specify major CALM algorithms. This inventory changes the emphasis from adding standalone specifications to auditing whether each implemented transformation has valid mathematics, an accurate specification, and implementation behavior consistent with that specification.

The audit answers two separate questions for each transformation:

1. **Mathematical validity**: whether the stated problem, assumptions, derivation, invariants, and limitations are mathematically sound.
2. **Implementation validity**: whether the implementation realizes the stated mathematics under the documented representation conventions and numerical tolerances.

A transformation can have a valid mathematical specification but incomplete implementation verification. Conversely, an implementation can be useful and tested while still lacking a complete mathematical proof or clearly documented assumptions.

## Audit status vocabulary

| Status | Meaning |
| --- | --- |
| Complete | Specification, implementation mapping, and verification are strong enough to serve as current authority. |
| Audit needed | The transformation has a specification or implementation, but a focused validity audit is still needed. |
| Specification gap | The implementation contains mathematically significant behavior that is not yet specified at the required level. |
| Verification gap | The mathematics is documented, but tests do not yet directly assert the expected invariants. |
| Correction needed | Documentation or implementation behavior is known to be inconsistent and needs an explicit corrective update. |

## Current transformation audit inventory

| ID | Ontology role | Transformation or algorithm | Implementation owners | Specification status | Mathematical-validity assessment | Implementation-validity assessment | Verification status | Priority |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MA-001 | Construct Surface | Conventional Miller index to primitive Miller index and primitive surface kernel construction | `calm.slab.ops.primitive_surface_algorithm.primitive_miller_from_conventional`, `smith_normal_form_1x3`, `_primitive_surface_triplet_from_m`, `compute_primitive_surface_basis`; related oriented-slab helpers in `calm.slab.ops.oriented_slab` | Specified in `motif-compatible-surface-primitive-cells.md` and partly in `oriented-slab-construction.md` | Integer-kernel formulation is mathematically sound when the lattice transformation is nonsingular and rationalization assumptions are satisfied. | Implementation appears consistent for tested cases. Bounded candidate searches and rationalization tolerances require explicit audit before claiming unconditional completeness. | Transformation-centric audit complete for the exact Bravais-kernel path; bounded motif/search gaps remain tracked separately. | Complete for exact Bravais kernel; follow-up for bounded motif/search paths |
| MA-002 | Construct Slab | Oriented slab construction from bulk cell, Miller index, layer count, and gauge options | `calm.slab.ops.oriented_slab.build_oriented_slab_from_conventional`, `build_oriented_slab`, `calm.slab.slab.Slab`, `OrientedSlabTransforms` | Specified in `oriented-slab-construction.md` | Valid as a composition of integer basis changes, metric reduction, rotations, optional physical shear, vacuum insertion, wrapping, and provenance projection when each step's assumptions hold. | Implementation records provenance and exposes transform helpers. The remaining risk is verifying that all composed transforms preserve the intended surface plane, motif, and metric semantics across options. | Moderate to good; needs invariant-oriented end-to-end tests. | High |
| MA-003 | Match | HNF supercell enumeration and surface-cell matching | `calm.interface.matching.enumerate_matches`, `calm.keys.hnf`, `calm.math2d.normal_forms`, `calm.interface._surface_symmetry` | Specified in `surface-cell-matching-and-strain-optimization.md` | HNF enumeration and reduced-metric comparison are valid for finite-index 2D lattice supercells under the documented area and determinant bounds. | Implementation appears consistent with the finite search problem; completeness is only within configured bounds. | Good architecture/public tests; could add tests that explicitly tie HNF determinant bounds to expected candidate counts. | Medium-high |
| MA-004 | Match / Evaluate | Affine-invariant strain diagnostics and Hencky strain scoring | `calm.interface.strain`, `calm.interface.strain_analysis`, `calm.math2d.spd2x2`, `calm.math2d.polar2x2` | Specified across matching and geodesic strain docs | SPD log/metric formulation is mathematically valid for positive-definite in-plane Gram matrices. | Implementation should be audited for degenerate or nearly singular cells and tolerance behavior. | Moderate; add explicit SPD-domain and degeneracy tests. | Medium-high |
| MA-005 | Evaluate / Build precondition | Geodesic strain partitioning on SPD(2) | `calm.interface.strain.compute_strain_2d`, `calm.interface.strain_partition.strain_partition_inplane`, `scan_geodesic_strain_partitions`, `calm.math2d.spd2x2` | Specified in `geodesic-strain-partitioning.md`; alpha correction recorded in `strain-partition-alpha-convention.md` | The affine-invariant geodesic convention is valid. Endpoint semantics are now documented as `alpha=0` target `G_A` and `alpha=1` target `G_B`. | Implementation appears consistent with the corrected convention. Finite alpha scanning is not a continuous optimizer. | Endpoint guardrail tests exist; tie behavior and scan persistence remain useful additions. | Medium |
| MA-006 | Build | Interface construction from prototype, strain state, build config, registry translation, and z placement | `calm.interface.pipeline.build_interface`, `calm.interface._build_kernel.build_interface_atoms`, `InterfaceBuildConfig`, `Interface`, `calm.ase_adapter.make_supercell_col` | Specified in `interface-construction.md` | Valid as deterministic geometry assembly when deformation-gradient, frame, periodicity, and placement assumptions are satisfied. | Implementation should be audited against invariants: cell metric, layer indices, registry translation wrapping, z padding, and provenance preservation. | Moderate; built-interface invariant audit is a high-value next step. | High |
| MA-007 | Registry optimization | Monte Carlo registry alignment over in-plane fractional translation and optional z padding | `calm.interface.registry_search`, `registry_search_geometry`, `registry_search_runner`, `calm.project.optimize_interface` | Specified in `monte-carlo-registry-alignment.md` | Valid as stochastic search, not as a guaranteed global optimizer. Correctness concerns state-space handling, proposal semantics, seeding, acceptance, and objective calls. | Implementation appears consistent with a finite stochastic optimizer. Needs audit for reproducibility and boundary behavior across project/workspace wrappers. | Moderate; existing MC tests should be mapped directly to specification invariants. | Medium |
| MA-008 | Deduplicate / Project | Equivalence, grouping, canonicalization, and duplicate removal | `calm.interface.prototype_grouping`, `calm.interface.prototypes`, `calm.interface.results`, `calm.slab.ops.oriented_slab._dedupe_atoms_by_scaled_positions`, public collection layers | Specified in `deduplication-equivalence-and-canonicalization.md` | Valid when framed as a mixture of exact equivalence, representative selection, and heuristic signatures. | Implementation should avoid claiming heuristic group keys are complete equivalence relations unless proven. Current documentation makes this distinction. | Moderate; add examples/tests distinguishing true duplicates from heuristic groups. | Medium |
| MA-009 | Evaluate | Interfacial-energy scalar evaluation and strained-bulk reference convention | `calm.interface._energy_kernel`, `calm.interface.interface_energy`, `calm.interface.refs` | Specified in `interfacial-energy-evaluation.md` | Formula is valid under documented strained-bulk reference, formula-unit, area, and denominator conventions. | Implementation appears aligned; remaining risk is cross-checking single- versus double-sided denominator semantics through public workflows. | Good scalar tests; workflow-level energy provenance tests still useful. | Medium-high |
| MA-010 | Persist / Project | Persistence, public sidecar projection, dataset manifest, and report projection | `calm.project.application.*`, `calm.project.infrastructure.*`, `calm.public.*`, `calm.reporting` | Specified in `persistence-report-projection.md` | Valid as a representation morphism, not a scientific morphism. It is intentionally lossy outside identity/provenance and declared projection fields. | Implementation has strong guardrails for public rows, manifests, and helper boundaries. | Good local guardrails; end-to-end trace across dataset/report remains desirable. | Medium |
| MA-011 | Workflow composition | Crystal -> Surface -> Slab -> Interface Candidate -> Built Interface Structure -> Evaluation Result -> Dataset -> Report | Cross-package composition of bulk, slab, interface, project, public, and reporting layers | Specified in `end-to-end-workflow-traceability.md` | Composition is coherent if each morphism preserves its declared identity, metric, strain, energy, and provenance invariants. | Implementation validity must be judged by workflow-level tests rather than isolated unit tests alone. | Main remaining gap: continuous identity/provenance/metric/energy trace across the whole chain. | High |
| MA-012 | Rank / View | Pareto ranking, filtering, and workspace views | `calm.analysis.pareto`, `calm.project.ux._pareto`, public result collections | Specification gap; partly covered by implementation conformance tests | Mathematically simple as partial-order filtering under minimization, but should be recorded as a view/projection operation rather than a scientific morphism. | Implementation appears valid for tested minimization semantics. | Local tests exist; mathematical page optional unless ranking becomes central to scientific claims. | Low-medium |

## Near-term audit sequence

The next updates should be audit deliverables rather than new broad specifications.

1. **Primitive surface-cell completeness audit**: distinguish exact integer-kernel construction from bounded primitive-basis searches and motif-translation reductions. Decide which claims are proven, bounded, heuristic, or implementation-dependent.
2. **Built-interface invariant audit**: derive and check invariants for cell metric, deformation-gradient application, registry translation, z placement, layer provenance, and periodic wrapping.
3. **Oriented slab invariant audit**: verify surface-plane preservation, in-plane metric semantics, physical shear semantics, vacuum semantics, and transform-provenance consistency.
4. **Interfacial-energy convention audit**: tie scalar formulas to public workflows, denominator conventions, unit conversion, and strained-bulk provenance.
5. **Workflow traceability audit**: add a single executable path, where optional dependencies permit, that traces identity/provenance/metric/energy fields from input crystal representation through report projection.

## Audit deliverable template

Each audit should contain:

1. repository evidence inspected;
2. mathematical statement of the transformation;
3. assumptions and admissibility domain;
4. proof sketch or validity argument;
5. implementation mapping;
6. implementation-validity assessment;
7. invariants that should be tested;
8. current verification coverage;
9. documentation or implementation corrections required;
10. recommended next action.

## Current conclusion

The repository is now ready for mathematical audits. The existing specification pages cover the major CALM transformations, but not all claims have the same evidentiary strength. The highest-value next step is the primitive surface-cell completeness audit because it sits at the beginning of the slab/interface workflow and controls whether later transformations inherit a true primitive, motif-compatible surface representation or only a bounded-search representative.

## 0215 primitive surface-cell completeness audit result

The primitive surface-cell completeness audit is now recorded in [Primitive surface-cell completeness audit](primitive-surface-cell-completeness-audit.md). Its conclusion is that the exact Bravais-kernel path is mathematically valid and implementation-conformant under the documented rational-transform and tolerance assumptions, while motif-reduction and fallback primitive-vector searches remain bounded/tolerance-dependent and should not be documented as globally complete without further proof. The next corrective work should update the stale `compute_primitive_surface_basis` docstring and add determinant/layer-count guardrail tests.
## 0217 surface matching validity audit result

The surface matching validity audit is now recorded in [Surface matching validity audit](surface-matching-validity-audit.md). Its conclusion is that CALM's matching implementation is mathematically valid as a bounded finite-index HNF search with a necessary area-band prefilter, deterministic two-dimensional reduction, fixed-gauge point-group deduplication, and affine-invariant Hencky-strain gating. Completeness claims should remain explicitly bounded by determinant, conditioning, symmetry, and tolerance settings. The next corrective work should update the positive-index error message in `compute_valid_hnf_index_pairs` and add boundary-focused HNF/area-band guardrail tests.

## 0222 primitive surface generation mathematical audit result

The transformation-centric audit is recorded in [Primitive surface generation mathematical audit](primitive-surface-generation-mathematical-audit.md). It marks the exact primitive Bravais surface-cell construction as mathematically valid and implementation-conformant under the documented rational-transform/tolerance assumptions. It explicitly reserves global completeness claims for that exact Bravais-kernel path and keeps decorated motif minimality and fallback primitive-vector searches classified as bounded or tolerance-dependent.

## 0223 surface matching mathematical audit

The surface matching transformation is accepted as mathematically valid and implementation-conformant for CALM's documented finite search problem: bounded HNF enumeration, necessary area-band filtering, deterministic reduced-cell gauge selection, point-group representative selection, affine-invariant Hencky-strain gating, and heuristic size/strain ranking. The audit explicitly rejects unbounded global-completeness claims and identifies residual synthetic matching guardrails as the next verification target.
