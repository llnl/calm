# Mathematical traceability inventory

This inventory is the repository-grounded control document for the Mathematical and Algorithmic Specification milestone. It records mathematically significant CALM transformations, their current implementation owners, the mathematical validity assessment of the method as implemented, and the verification or documentation gaps that should drive near-term work.

The inventory has two jobs:

1. identify the transformations that need formal mathematical and algorithmic specifications; and
2. audit whether each implemented transformation appears to realize the intended mathematics under its stated assumptions.

The status terms used here are intentionally conservative.

- **Specification present** means a mathematics page exists under `docs/mathematics/`.
- **Specification needed** means the implementation is mathematically significant but lacks a dedicated page.
- **Implementation appears valid** means the algorithm is mathematically coherent under the assumptions visible in the implementation and tests.
- **Implementation needs audit** means the algorithm is plausible but needs a focused derivation/test audit before being treated as normative.
- **Known documentation correction** means the code path appears internally coherent, but a docstring or specification statement conflicts with the implemented convention.

## Repository evidence reviewed

This inventory is based on the current repository snapshot and the following implementation owners:

- `calm.slab.ops.oriented_slab`
- `calm.slab.surface_primitive`
- `calm.slab.ops.primitive_surface_algorithm`
- `calm.interface.matching`
- `calm.interface.types`
- `calm.interface.strain`
- `calm.interface.strain_partition`
- `calm.interface.registry_search`
- `calm.interface.registry_search_geometry`
- `calm.interface.prototypes`
- `calm.interface.prototype_grouping`
- `calm.interface._build_kernel`
- `calm.interface._energy_kernel`
- `calm.interface.interface_energy`
- `calm.project.application.*`
- `calm.public.*`

The inventory also uses the existing mathematics pages:

- `docs/mathematics/algorithms/motif-compatible-surface-primitive-cells.md`
- `docs/mathematics/algorithms/surface-cell-matching-and-strain-optimization.md`
- `docs/mathematics/algorithms/deduplication-equivalence-and-canonicalization.md`

and the verification/test files under `tests/slab/`, `tests/public/`, and the top-level interface, registry-search, strain, energy, and workflow tests.

## Transformation inventory

| ID | Ontology morphism / transformation | Mathematical problem | Implementation owner(s) | Spec status | Implementation validity assessment | Verification status | Priority |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MAS-01 | Construct surface basis from Miller index | Given a reduced row vector `h = (h,k,l)`, construct a unimodular integer basis `S=[u v w]` with `hS=(0,0,1)` and `u,v` spanning the primitive integer kernel of `h·x=0`. | `calm.slab.ops.oriented_slab.surface_basis_S_from_hkl`, `_right_reduce_row_to_hnf`, `verify_surface_kernel_is_primitive` | Covered by 0202, but should be split into a transformation page. | Implementation appears valid: it uses right integer reduction, verifies determinant `+1`, and checks the kernel relation. | Good: `tests/slab/test_bezout_triplet_properties.py`, `tests/slab/test_miller_transforms.py`, `tests/slab/test_surface_basis_validation.py`. | High |
| MAS-02 | Surface-kernel metric reduction | Reduce the 2D in-plane integer kernel basis by a canonical 2D reduction while preserving the surface lattice. | `calm.slab.ops.oriented_slab._reduce_surface_kernel_by_metric`, `calm.symmetry.reduction.niggli_reduce_2d` | Partially covered by 0202. | Implementation appears valid if the delegated 2D reduction returns a unimodular integer matrix. The implementation embeds the 2D transform into a 3D column convention matrix and checks determinant preservation. | Moderate-good: slab transformation and basis-change tests cover invariants indirectly. | High |
| MAS-03 | Motif-compatible in-plane reduction | Use pure translational symmetry to reduce a geometrically valid in-plane cell to a motif-compatible primitive decorated surface cell. | `calm.slab.ops.oriented_slab._get_pure_translation_translations_frac`, `_find_inplane_motif_reduction_hnf`, `_reduce_inplane_by_motif_translations`, `_dedupe_atoms_by_scaled_positions` | Covered by 0202. | Implementation appears mathematically coherent for rationalized pure translations: it searches HNF matrices that map all detected in-plane translations to integer lattice coordinates. Correctness depends on spglib detecting the translation subgroup and on denominator/tolerance choices. | Good for current behavior: `tests/test_oriented_slab_motif_reduction.py`, `tests/slab/test_motif_preservation.py`. Needs explicit edge-case tests for denominator truncation and incomplete symmetry detection. | High |
| MAS-04 | Primitive surface cell search from primitive basis | Search candidate in-plane vectors from the primitive bulk basis and choose a small motif-compatible surface cell. | `calm.slab.ops.oriented_slab._find_primitive_surface_cell`, `_generate_inplane_vectors_from_primitive`, `_count_atoms_in_cell`, `_has_fractional_translations` | Partially covered by 0202. | Needs audit. The algorithm is a bounded heuristic: candidate vectors are generated with finite coefficients and sorted by length/area. It can be correct for the tested regime but does not constitute a complete primitive-cell enumeration unless the coefficient bound and motif checks are formally justified. | Moderate: primitive surface tests exist, but completeness guarantees need targeted tests or a documented bounded-search contract. | High |
| MAS-05 | Oriented slab construction | Construct an oriented slab from a bulk crystal and Miller index, including surface basis, layer stacking, gauge reduction, optional tilt reduction, optional physical shear, optional vacuum, and transform provenance. | `calm.slab.ops.oriented_slab.build_oriented_slab`, `build_oriented_slab_from_conventional`, `OrientedSlabTransforms`, `calm.slab.oriented_slab`, `calm.slab.slab.Slab` | Covered by 0213. | Implementation appears valid as a composition of sub-transformations. The 0213 specification records the mathematical distinction between integer basis operations, Cartesian rotations, physical shear orthogonalization, vacuum representation, wrapping, and provenance projection. The main remaining caveat is the bounded/tolerance-dependent nature of motif-compatible primitive reduction. | Good but distributed: `tests/test_slab_oriented_slab_kernel.py`, `tests/test_oriented_slab_r_align.py`, `tests/test_slab_tilt_ordering.py`, oriented-slab transform tests, and slab tests. Recommended addition: one end-to-end invariant test tied directly to the 0213 specification. | High |
| MAS-06 | Surface-cell matching | Enumerate candidate common in-plane supercells for two slabs using HNF determinant bounds, reduction, point-group-key deduplication, area-band filtering, and strain scoring. | `calm.interface.matching.enumerate_matches`, `compute_valid_hnf_index_pairs`, `calm.interface.types.ReducedSupercell2D`, `AffineInvariantStrain2D` | Covered by 0203. | Implementation appears valid as a bounded search. The area prefilter follows the log-area consequence of the principal Hencky-strain bound. Completeness is only within `k_max`, conditioning threshold, Niggli/gauge choices, and point-group dedupe policy. | Good: matching, enumeration audit, strain metrics, point-group, and public search-result tests. | High |
| MAS-07 | Affine-invariant strain diagnostics | Compare two 2D metric tensors using SPD matrix functions and principal logarithmic strain diagnostics. | `calm.interface.types.AffineInvariantStrain2D`, `calm.math2d.spd2x2`, `calm.interface.matching` | Partially covered by 0203; deserves a foundation/verification page. | Implementation appears mathematically valid for SPD inputs: it forms the relative metric, takes log eigenvalues, and exposes area/shape/cell norms. Need explicit specification of SPD regularization and degenerate-cell failure behavior. | Good: `tests/test_strain_metrics.py`; math2d tests likely cover kernels indirectly. | Medium-high |
| MAS-08 | Interface candidate deduplication and equivalence grouping | Choose representatives among lattice matches and group structurally similar prototypes by metric/contact signatures. | `ReducedSupercell2D.build_index`, `calm.interface.prototypes`, `calm.interface.prototype_grouping` | Covered by 0204. | Implementation is valid for representative selection and heuristic grouping, not for complete crystallographic isomorphism. The current specification correctly treats several signatures as conservative grouping aids rather than complete equivalence proofs. | Moderate-good: build-index dedupe, fingerprint determinism, prototype grouping tests. | High |
| MAS-09 | Interface construction / build morphism | Transform two strained slabs into a common interface cell, apply registry/z-padding choices, and form a built interface structure. | `calm.interface.pipeline.build_interface`, `calm.interface._build_kernel.build_interface_atoms`, `calm.interface.config.InterfaceBuildConfig` | Covered by 0209. | Implementation appears valid as deterministic geometry assembly when supplied a compatible prototype and strain state. The specification separates scientific deformation from representation adapters, registry translation, z-placement, and provenance projection. | Moderate-good: build-kernel, UID, registry-runner, and workflow tests exist. Recommended additions are explicit common-cell, layer-partition, and vacuum-default invariant tests. | High |
| MAS-10 | Monte Carlo registry alignment | Stochastically search relative in-plane translation and optional z-padding to minimize a caller-supplied scalar objective. | `calm.interface.registry_search.monte_carlo_registry_search`, `calm.interface.ops.registry_search_runner`, `calm.interface.registry_search_geometry` | Covered by 0207. | Implementation appears valid as a Metropolis-style stochastic optimization heuristic. It does not guarantee a global optimum; correctness is framed in terms of state-space handling, acceptance semantics, and reproducibility. | Good for API semantics: registry-search tests cover translation wrapping, z moves, seeds, runner behavior. | High |
| MAS-11 | Geodesic strain partitioning | Interpolate between two SPD(2) in-plane metrics and compute deformation gradients mapping both slabs to a common target metric. | `calm.interface.strain.compute_strain_2d`, `calm.interface.strain_partition.strain_partition_inplane`, `scan_geodesic_strain_partitions` | Covered by 0208. | Implementation appears mathematically valid for the SPD geodesic construction under nondegenerate in-plane bases. The corrected endpoint convention is documented: `alpha=0` chooses A's metric and leaves A unstrained, while `alpha=1` chooses B's metric and leaves B unstrained. | Good: strain metric and strain-partition endpoint tests exist. Additional scan-grid/tie-stability tests remain useful. | High |
| MAS-12 | Strain partition scan / scoring | Evaluate a finite alpha grid and select the best strain partition under an external scalar score. | `calm.interface.strain_partition.scan_geodesic_strain_partitions`, `calm.project.strain_partition_scan` | Covered by 0208 for the core finite-grid scan. | Implementation appears valid for finite-grid search. It is not a continuous optimizer unless the grid/refinement policy is extended. | Moderate: scan and persistence compatibility tests exist. Additional tie-stability and project-level scan persistence checks are useful. | Medium-high |
| MAS-13 | Interfacial energy evaluation | Compute bulk chemical potentials and interfacial energy from interface/slab/bulk energies with single- or double-sided denominator convention. | `calm.interface._energy_kernel.prepare_interfacial_energy_geometry`, `compute_interfacial_energy_from_energies`, `calm.interface.interface_energy` | Specification needed. | Implementation appears mathematically valid under the recorded convention: `gamma = (E_int - n_A mu_A - n_B mu_B) / denom`, with `denom = 2A` for double-sided interfaces and `A` otherwise. Requires a formal convention document because different interface-energy conventions are common. | Good scalar tests: energy hardening, scalar public API, wrapping, interfacial energy kernel, strained-bulk reference tests. | High |
| MAS-14 | Strained bulk reference construction | Map slab-frame deformation gradients back to conventional-cell coordinates and construct strained bulk references for energy subtraction. | `calm.interface.interface_energy.get_strained_bulk`, `get_ortho_map`, `_energy_kernel.prepare_interfacial_energy_geometry`, slab transform mapping helpers | Specification needed. | Needs audit. This is mathematically sensitive because it composes frame maps, deformation gradients, cell conventions, and scaled-position behavior. The implementation records the default unrelaxed scaled-position convention, but the reference-frame derivation should be specified explicitly. | Moderate-good: strained bulk construction and public API tests exist. | High |
| MAS-15 | Persistence and projection | Project scientific objects and results into datasets, sidecars, manifests, public rows, and reports while preserving identity/provenance fields. | `calm.project.application.*`, `calm.project.infrastructure.db.*`, `calm.public.*`, `calm.reporting` | Covered by 0211. | Implementation appears valid as a representation morphism when interpreted as typed persistence/projection rather than scientific-object creation. The specification records the lossy nature of public rows and reports, and the requirement that declared identity/provenance fields remain distinct. | Good: persistence/projection guardrails, candidate identity/projection tests, public sidecar tests, query/reporting contracts, and dataset manifest tests. Future work should add an end-to-end UID trace across persistence, sidecar, dataset, and report projections. | Medium |
| MAS-16 | Pareto and ranking utilities | Identify non-dominated candidates under minimization objectives and expose ranked views. | `calm.analysis.pareto`, `calm.project.ux._pareto`, result collection views | Specification needed. | Implementation appears mathematically simple and valid, but should be documented as an order/filtering operation rather than a scientific morphism. | Good: Pareto helper and result tests exist. | Low-medium |

## Highest-priority validity findings

### 1. Correct the strain-partition alpha convention documentation

The implementation of `compute_strain_2d` constructs

```text
G(alpha) = G_A^{1/2} (G_A^{-1/2} G_B G_A^{-1/2})^alpha G_A^{1/2}.
```

Therefore `alpha = 0` gives `G(alpha)=G_A`, and `alpha = 1` gives `G(alpha)=G_B`. In terms of applied strain, `alpha = 0` leaves side A at its original in-plane metric and maps side B to A's metric, while `alpha = 1` leaves side B at its original in-plane metric and maps side A to B's metric.

The docstring in `scan_geodesic_strain_partitions` currently states the opposite applied-strain interpretation. This should be corrected before the strain-partition specification is treated as normative.

Recommended near-term update: a small source/documentation/test patch that fixes the docstring and adds an endpoint-convention test if the existing tests do not already assert it.

### 2. Audit primitive surface-cell completeness

The motif-compatible primitive-cell specification is mostly grounded in integer-lattice arguments. However, `_find_primitive_surface_cell` uses a bounded candidate-vector search from primitive-basis combinations. The code is useful and likely correct in the tested regimes, but the completeness of this bounded search is not yet mathematically established.

Recommended near-term update: write a focused audit/specification addendum distinguishing the exact integer-kernel/HNF method from the bounded primitive-basis vector search. Either prove the chosen bound under explicit assumptions or document the routine as a heuristic with fallback behavior.

### 3. Specify interface build as a composition of transformations

Interface construction currently combines scientific deformations with representation-only frame operations and atom-placement operations. The next mathematical specification should split these into:

- metric/strain target selection;
- deformation-gradient application;
- Cartesian/frame representation changes;
- registry translation;
- out-of-plane placement and z-padding;
- provenance projection.

Recommended near-term update: an interface-construction transformation specification and an invariant checklist for built-interface structures.

### 4. Specify Monte Carlo registry search as stochastic optimization

The registry search implementation is clear and dependency-light, but its mathematics must be framed as stochastic search, not deterministic optimization. The specification should state that correctness means correct state-space handling, proposal/acceptance semantics, bounds enforcement, seeding reproducibility, and objective-call semantics, not guaranteed global minimization.

Recommended near-term update: Monte Carlo registry alignment specification.

### 5. Formalize interfacial-energy conventions

The energy kernel implements a standard strained-bulk subtraction formula with explicit double-sided denominator handling. The documentation should make the denominator convention, formula-unit counting, strained-bulk reference mode, and unit conversion normative.

Recommended near-term update: interfacial-energy evaluation specification.


## Built-interface construction audit status

Update `0220` adds a focused validity audit for the canonical built-interface construction path. The audit finds the build morphism mathematically coherent as deterministic geometry assembly under the documented upstream compatibility assumptions for matching and strain-state construction. The remaining work is verification hardening: dependency-light guardrails should assert matrix validation, z-placement, default vacuum behavior, lower/upper index partitions, and provenance continuity.

## Near-term milestone candidates

The current Mathematical and Algorithmic Specification milestone should proceed in two interleaved tracks.

### Track A: correctness corrections and audits

1. **Strain partition alpha convention correction**: fix documentation/test coverage for the endpoint convention.
2. **Primitive surface-cell completeness audit**: clarify which parts are exact and which are bounded/heuristic.
3. **Built-interface invariant audit**: identify required invariants for a built interface structure.

### Track B: substantive specifications

1. **Monte Carlo registry alignment**.
2. **Geodesic strain partitioning**. Covered by 0208; remaining work is scan persistence/traceability hardening if needed.
3. **Interface construction**. Covered by 0209; remaining work is invariant-test hardening if needed.
4. **Interfacial-energy evaluation**.
5. **Strained-bulk reference construction**.
6. **Persistence/projection provenance**.

## End-to-end workflow status

The end-to-end workflow map is now documented in `docs/mathematics/verification/end-to-end-workflow-traceability.md`. The composition appears mathematically coherent under the assumptions documented by the individual algorithm specifications. The remaining gap is workflow-level verification: local invariants are covered more strongly than continuity of identity, provenance, metric, strain, energy, dataset, and report fields across the whole chain.

## Documentation status summary

| Specification page | Current state | Recommended action |
| --- | --- | --- |
| `motif-compatible-surface-primitive-cells.md` | Present | Add completeness/heuristic caveat for bounded primitive-basis search. |
| `oriented-slab-construction.md` | Present | Add end-to-end invariant tests and primitive-surface completeness audit. |
| `surface-cell-matching-and-strain-optimization.md` | Present | Keep; later add more detailed proof of point-group-key dedupe invariants if needed. |
| `deduplication-equivalence-and-canonicalization.md` | Present | Keep; later add examples distinguishing equivalence from heuristic grouping. |
| Monte Carlo registry alignment | Missing | Write next or after strain doc correction. |
| Geodesic strain partitioning | Present | Keep; add scan-grid/tie-stability verification if needed. |
| Interface construction | Present | Keep; add built-interface invariant tests if needed. |
| Interfacial energy evaluation | Missing | High priority because conventions affect scientific interpretation. |
| Persistence/projection provenance | Present | Add end-to-end identity traceability tests across durable persistence, sidecar, manifests, and reports. |

## Verification status summary

The repository has strong architectural and public-boundary tests, and several algorithm-level tests. The remaining verification gap is not the absence of tests in general, but the lack of a one-to-one chain from mathematical specification to implementation invariant.

Recommended verification additions:

- endpoint tests for strain-partition alpha semantics;
- explicit tests for bounded primitive-surface search fallback behavior;
- built-interface invariant tests tied to the interface-construction specification;
- Monte Carlo registry tests expressed in terms of state-space and acceptance-rule invariants;
- interfacial-energy tests that explicitly check single-sided versus double-sided denominator conventions.

## 0222 primitive surface generation audit

[Primitive surface generation mathematical audit](primitive-surface-generation-mathematical-audit.md) completes the first transformation-centric audit. The exact primitive Bravais-kernel construction is accepted as mathematically valid and implementation-conformant in its admissible domain; decorated motif minimality and bounded fallback primitive-vector search remain separate audit targets.

## 0223 surface matching mathematical audit

The surface matching transformation is accepted as mathematically valid and implementation-conformant for CALM's documented finite search problem: bounded HNF enumeration, necessary area-band filtering, deterministic reduced-cell gauge selection, point-group representative selection, affine-invariant Hencky-strain gating, and heuristic size/strain ranking. The audit explicitly rejects unbounded global-completeness claims and identifies residual synthetic matching guardrails as the next verification target.
