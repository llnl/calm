# Oriented slab construction

## Purpose

Oriented slab construction realizes the `Construct Slab` morphism for a bulk crystal and a Miller plane. Given a three-dimensional periodic bulk representation, a Miller index `(h,k,l)`, and a positive layer count, CALM constructs a slab-periodic block whose first two lattice vectors span the selected surface plane and whose third lattice vector advances through the slab stacking direction. Optional representation operations reduce the in-plane gauge, reduce residual `c`-tilt, attach vacuum, and record transformation provenance.

The procedure is not an interface search, strain optimization, or energy evaluation. It is a deterministic geometry constructor, subject to optional symmetry- and tolerance-dependent reductions.

## Ontology mapping

| Role | CALM object or representation |
| --- | --- |
| Input scientific object | Bulk crystal / crystal cell |
| Input representation | Conventional or primitive `ase.Atoms`, `Bulk`, Miller index, layer count, builder options |
| Output scientific object | Slab |
| Output representations | Periodic slab block, optional vacuum slab, `OrientedSlabTransforms` provenance |
| Scientific morphism | `Construct Slab` |
| Representation morphisms | integer basis transforms, ASE row/column adapter, Cartesian rotations, in-plane gauge fixing, JSON-native provenance projection |

The primary implementation owners are:

- `calm.slab.ops.oriented_slab.build_oriented_slab_from_conventional`;
- `calm.slab.ops.oriented_slab.build_oriented_slab`;
- `calm.slab.ops.oriented_slab.OrientedSlabTransforms`;
- `calm.slab.oriented_slab`, the public compatibility surface that attaches stable transform payloads;
- `calm.slab.slab.Slab`, the higher-level workflow representation.

## Mathematical problem

Let the conventional bulk lattice be represented by a basis `A` and let the Miller index be a nonzero integer row vector

```text
h = (h, k, l).
```

The crystallographic surface plane is the set of lattice vectors `x` satisfying

```text
h x = constant.
```

For a slab basis, CALM needs an integer matrix

```text
S = [u v w] in Z^(3 x 3)
```

such that

```text
h S = (0, 0, 1).
```

The first two columns `u` and `v` span the surface lattice kernel `ker_Z(h)`, while `w` advances by one interplanar step in the Miller-index direction. For `L` layers, the stacking column is scaled as

```text
S_L = [u v L w].
```

The slab-lattice construction is therefore an integer supercell operation followed by optional representation choices that make the resulting cell easier to compare, persist, and use downstream.

## Algorithmic workflow

The implemented conventional-cell path is compositionally organized as follows.

### 1. Miller-index reduction

The Miller index is reduced to a primitive integer vector. Multiplying `(h,k,l)` by a common integer factor does not change the geometric plane family, but it changes the step count. CALM records and uses the reduced index in transformation provenance.

### 2. Surface-basis construction

`surface_basis_S_from_hkl` constructs an integer basis satisfying the kernel and stacking conditions above. The mathematical core is the integer-kernel problem for the row vector `h`. The first two columns lie in the exact integer nullspace of `h`, and the third column is a Bezout-style stacking vector for which `h w = 1`.

This stage is exact over integer arithmetic up to the checks implemented around determinant sign, primitive kernel structure, and Miller-index validity.

### 3. Layer stacking and column-basis supercell construction

The layer count multiplies the third column of `S`, giving `S_L`. CALM uses column-basis convention internally, while ASE's `make_supercell` accepts a row-convention matrix. The adapter `make_supercell_col` performs the representation conversion and avoids manual transpose mistakes.

This step creates a fully periodic block. It does not insert vacuum and does not relax atoms.

### 4. Motif-compatible in-plane reduction

When `reduce_motif_inplane=True`, the code searches for pure in-plane translations that identify a smaller decorated surface cell. The reduction is motif-sensitive: it must preserve the atomic decoration, not merely the geometric lattice.

Mathematically, this is a quotient of the in-plane surface lattice by detected translational symmetries of the decorated motif. The current implementation depends on symmetry detection, rationalization tolerances, and a bounded HNF search. It is valid under the assumption that the detected pure translations are complete for the requested tolerance and denominator bounds.

### 5. Metric in-plane gauge reduction

When `reduce_inplane=True`, CALM applies a two-dimensional reduction to the in-plane lattice basis. This is a representation morphism: it changes the basis used to describe the same surface lattice, not the scientific slab itself.

The implementation records the in-plane unimodular transform and the associated gauge-fixing rotation `R_align` when applicable. This provenance is important because downstream strain and frame mappings must distinguish physical deformation from coordinate gauge choices.

### 6. Cartesian orientation to slab frame

After integer and in-plane reductions, CALM constructs a Cartesian rotation `R_conv_to_slab` so that the surface plane lies in the `xy` plane. The first two slab lattice vectors must satisfy

```text
a_z ~= 0,    b_z ~= 0,
```

within the configured `z_tolerance`. The resulting slab-frame normal is aligned with the `z` axis, with sign selected by `normal_sign`.

This rotation is a representation change between Cartesian frames. It preserves distances and angles. It is not a strain.

## Implementation notes (migrated from legacy surface preprocessing guide)

### Slab-frame rotation and z-alignment notes

When constructing an oriented slab from a primitive surface cell, the implementation should:

- compute a Cartesian rotation `R` that aligns the surface normal with `+z` so that the first two lattice vectors have negligible `z` components within a configured `z_tolerance`;
- record `R` and apply it only as a representation change (it is not a strain) so downstream strain/deformation helpers can distinguish gauge rotations from physical deformations;
- if `R` is numerically near identity, prefer returning the original Cartesian frame to avoid unnecessary numeric jitter in provenance.

### Gauge provenance and in-plane reduction notes

Reduction and gauge-fixing are representation operations. Practical guidance:

- record unimodular in-plane transforms and gauge-fixing rotations in `OrientedSlabTransforms` provenance payloads so later steps can reconstruct the exact mapping between original and reduced bases;
- ensure in-plane metric reduction (Niggli/Gauss) is accepted only when it preserves integer certificates for primitives; otherwise keep the exact integer basis and record that reduction failed certification;
- use deterministic tie-breaking and consistent tolerance parameters (`symprec`, `tol`) so that repeated runs produce identical provenance.

### Tolerance and fallback notes

Implementation-level robustness:

- rationalize conventional→primitive transforms with bounded denominators before integerization and verify reconstruction of conventional cell within a scale-aware tolerance;
- for near-degenerate inputs, fail loudly rather than silently returning a possibly invalid slab; provide clear diagnostics for tolerance adjustments;
- distinguish integer `c`-tilt reductions (basis change) from physical `c` orthogonalization (shear) in provenance and tests; the latter changes metrics and must be recorded as a deformation.

### 7. Optional integer `c`-tilt reduction

When `reduce_c_tilt=True`, CALM searches integer combinations of the in-plane basis vectors that reduce the in-plane projection of the third lattice vector. Algebraically, this replaces

```text
c <- c + m a + n b
```

for bounded integers `(m,n)` chosen to reduce the in-plane tilt.

This is a lattice-basis operation, not a physical shear. It preserves the periodic lattice and atomic structure represented by the block.

### 8. Optional physical shear orthogonalization

When `orthogonalize_c=True`, CALM applies a Cartesian shear that makes the third lattice vector orthogonal to the surface plane. Unlike integer `c`-tilt reduction, this is a physical deformation of the represented cell geometry. The shear information is recorded in `shear_info`, and the transform helper methods include it when mapping deformation gradients between conventional and slab frames.

This option must therefore be interpreted differently from basis reduction: it changes the metric of the represented slab block.

### 9. Optional vacuum insertion

When `vacuum` is positive, CALM creates a vacuum-padded slab representation from the periodic block. The block remains the fully periodic object; the slab may include nonphysical vacuum spacing for atomistic simulations or visualization.

Vacuum insertion is a representation/geometry preparation operation. It should not be confused with layer construction or interface matching.

### 10. Wrapping and provenance

The final step wraps fractional positions into the periodic cell, clamps near-boundary numerical artifacts, and packages transformation provenance in `OrientedSlabTransforms`. The provenance records the reduced Miller index, layer count, integer surface basis, row-convention ASE supercell matrix, rotations, in-plane reductions, optional `c`-tilt reduction, shear information, and vacuum information.

## Correctness properties

A valid oriented slab construction should satisfy the following properties under the selected tolerances.

1. **Miller-plane correctness.** The in-plane slab lattice vectors lie in the integer kernel of the reduced Miller index before Cartesian orientation.
2. **Layer-count correctness.** The third surface-basis vector advances through the Miller stacking direction by the requested layer count.
3. **Surface-frame correctness.** After Cartesian orientation, the first two lattice vectors have zero `z` component within `z_tolerance`.
4. **Gauge provenance correctness.** Basis reductions and gauge-fixing rotations are recorded as provenance rather than silently folded into scientific strain.
5. **Rotation correctness.** Pure rotations are orthogonal with determinant `+1` within tolerance.
6. **Integer-basis correctness.** Metric and `c`-tilt basis changes preserve the lattice as representation changes.
7. **Shear explicitness.** If `orthogonalize_c=True`, the physical shear is recorded and included in frame mappings.
8. **Persistence readiness.** Public transform payloads are JSON-native projections of the kernel transform bundle.

## Validity audit

The implementation is mathematically valid as a composition of integer surface-basis construction, decorated-motif reduction, gauge reduction, Cartesian frame orientation, optional integer tilt reduction, optional shear deformation, and optional vacuum insertion.

The most important validity caveat is that motif-compatible in-plane reduction and primitive-surface-cell search are tolerance- and bound-dependent. These routines are effective and tested for the supported regimes, but their completeness depends on symmetry detection and finite search parameters. Therefore the oriented-slab construction specification should treat motif reduction as a conditional representation reduction, not as an unconditional proof of global primitive minimality.

The second important caveat is that `orthogonalize_c=True` introduces a physical shear, while `reduce_c_tilt=True` performs an integer basis change. The implementation distinguishes these in provenance; the mathematical specification should preserve that distinction.

## Complexity

The core integer basis construction is small fixed-dimension integer linear algebra. The dominant costs are:

- supercell construction, scaling approximately with the number of generated atoms;
- motif-compatible reduction, which depends on symmetry detection and bounded HNF search;
- in-plane metric reduction, which is fixed-dimension but may call canonicalization routines;
- optional `c`-tilt search over `(2r+1)^2` integer candidates for search radius `r`;
- wrapping and duplicate-handling operations over generated atoms.

For typical CALM slab construction, atom-count scaling dominates once the integer search bounds are modest.

## Numerical considerations

- Integer relations should be verified before conversion to floating Cartesian representations.
- `z_tolerance` controls whether the oriented cell is accepted as lying in the slab frame.
- `symprec`, motif translation tolerance, and denominator limits determine which motif translations are recognized.
- Near-boundary fractional coordinates are wrapped and clamped to avoid numerical artifacts in downstream comparisons and persistence.
- Deformation-gradient frame mappings should use `transforms=...` rather than only a raw rotation when orthogonalization shear may be present.

## Implementation mapping

| Mathematical component | Implementation |
| --- | --- |
| Miller reduction | `_reduce_hkl` |
| Integer surface basis | `surface_basis_S_from_hkl`, `verify_surface_kernel_is_primitive` |
| Column-basis supercell adapter | `make_supercell_col`, `supercell_matrix_ase_from_col` |
| Motif-compatible reduction | `_reduce_inplane_by_motif_translations` |
| 2D metric reduction / gauge fixing | `_reduce_inplane_by_metric`, `niggli_reduce_2d` |
| Slab-frame rotation | `_compute_R_from_ab_to_xy`, `_apply_cartesian_rotation` |
| Integer `c`-tilt reduction | `_reduce_c_tilt_integer` |
| Physical `c` orthogonalization | `_orthogonalize_c_by_shear` |
| Vacuum insertion | `_add_vacuum_along_cartesian_z` |
| Transform provenance | `OrientedSlabTransforms`, public transform payload helpers |

## Verification mapping

Current verification is distributed across the slab tests rather than gathered under a single oriented-slab specification test. Existing coverage includes:

- surface-basis and Bezout properties;
- Miller transform and kernel validation;
- motif preservation and motif reduction behavior;
- oriented-slab kernel construction tests;
- `R_align` capture and rotation-decomposition tests;
- tilt-ordering and c-tilt behavior tests;
- transform JSON projection guardrails;
- deformation-gradient frame round-trip tests.

Recommended future verification:

1. a single end-to-end oriented-slab invariant test tying Miller-kernel, orientation, transform provenance, and optional vacuum behavior together;
2. explicit tests distinguishing integer `c`-tilt reduction from physical shear orthogonalization;
3. a bounded-search contract test for motif-compatible primitive reduction failure/fallback behavior;
4. transform round-trip tests that include `orthogonalize_c=True` and verify that shear is included in frame mappings.

## References

- CALM ontology and transformation references in `docs/engineering/ontology/`.
- Surface primitive-cell and motif compatibility specification in `docs/mathematics/algorithms/motif-compatible-surface-primitive-cells.md`.
- Strain and deformation-gradient conventions in `docs/mathematics/algorithms/geodesic-strain-partitioning.md`.
