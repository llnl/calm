# Primitive surface-cell completeness audit

This audit evaluates the mathematical and implementation validity of CALM's primitive surface-cell construction machinery. It focuses on the distinction between three related but different claims:

1. an **exact primitive surface kernel** in the primitive Bravais lattice;
2. a **motif-compatible decorated surface cell** for the atomic basis;
3. a **bounded or heuristic search** for a reduced representative after a slab has already been built.

Only the first claim is currently supported by a strong mathematical certificate in the core implementation. The latter two are implementation-dependent and should be described with bounded or best-effort language unless additional exhaustive search or proof machinery is added.

## Repository evidence inspected

Primary implementation owners inspected for this audit:

- `calm.slab.ops.primitive_surface_algorithm.primitive_miller_from_conventional`
- `calm.slab.ops.primitive_surface_algorithm._primitive_surface_triplet_from_m`
- `calm.slab.ops.primitive_surface_algorithm.compute_primitive_surface_basis`
- `calm.slab.ops.primitive_surface_algorithm.minimize_shear`
- `calm.slab.ops.primitive_surface_algorithm._reduce_2d_basis`
- `calm.slab.ops.oriented_slab.build_oriented_slab`
- `calm.slab.ops.oriented_slab._reduce_inplane_by_motif_translations`
- `calm.slab.ops.oriented_slab._generate_inplane_vectors_from_primitive`
- `calm.slab.ops.oriented_slab._find_primitive_surface_cell`

Relevant tests inspected include:

- `tests/slab/test_primitive_surface_algorithm.py`
- `tests/slab/test_miller_transforms.py`
- `tests/slab/test_centered_miller_transforms.py`
- `tests/slab/test_exhaustive_millers.py`
- `tests/slab/test_bezout_triplet_properties.py`
- `tests/slab/test_basis_change_invariance.py`
- `tests/slab/test_surface_basis_validation.py`
- `tests/slab/test_motif_preservation.py`
- `tests/slab/test_negative_miller_semantics.py`
- `tests/slab/test_large_miller_regression.py`
- `tests/slab/test_skew_cells_and_failures.py`
- `tests/slab/test_validate_scale_aware.py`

Related specifications inspected:

- `docs/mathematics/algorithms/motif-compatible-surface-primitive-cells.md`
- `docs/mathematics/algorithms/oriented-slab-construction.md`
- `docs/mathematics/verification/mathematical-audit-inventory.md`
- `docs/reference/surface_primitive_cell_generation.md`
- `docs/primitive_surface_cells.md`

## Mathematical statement

Let the primitive Bravais lattice be represented by a full-rank column-basis matrix
\(A_p \in \mathbb{R}^{3 \times 3}\). A surface orientation is given by conventional Miller indices \(h_c \in \mathbb{Z}^3\). After conversion to primitive reciprocal coordinates, CALM obtains a primitive integer Miller vector \(m \in \mathbb{Z}^3\) with \(\gcd(m_1,m_2,m_3)=1\).

The primitive surface lattice in primitive fractional coordinates is the rank-two integer kernel

\[
K_m = \{x \in \mathbb{Z}^3 : m^T x = 0\}.
\]

A primitive surface basis is an integer pair \((u,v)\) such that

\[
m^T u = 0, \qquad m^T v = 0, \qquad u \times v = \pm m.
\]

The cross-product certificate implies that \((u,v)\) spans the saturated integer kernel of \(m\), not merely a finite-index sublattice. A stacking vector \(w \in \mathbb{Z}^3\) is valid when

\[
m^T w = 1.
\]

The integer matrix

\[
T = [u\; v\; Lw]
\]

then defines a slab-periodic supercell with \(L\) layer repeats in the stacking direction. The determinant magnitude \(|\det T| = L\) when \(u \times v = \pm m\) and \(m^T w=1\), up to the sign convention for \((u,v)\).

## Validity of the exact kernel construction

The exact kernel construction in `_primitive_surface_triplet_from_m` is mathematically valid for primitive nonzero \(m\). The implementation explicitly verifies:

- `m` is shape `(3,)`;
- `m` is nonzero;
- `gcd(abs(m)) == 1`;
- `cross(u, v) == m` or `cross(u, v) == -m`;
- `m @ w == 1`.

These are sufficient certificates for a primitive surface kernel and a Bezout stacking vector. The construction is not merely heuristic: it constructs and verifies the algebraic certificates that define the object.

## Validity of conventional-to-primitive Miller conversion

`primitive_miller_from_conventional` computes the basis transform from the primitive basis to the conventional basis, rationalizes it using bounded denominators, and verifies that the rationalized transform reconstructs the conventional basis within scale-aware tolerances. It then applies the reciprocal-index transform, reduces the result to a primitive integer vector, and verifies parallelism back against the conventional Miller vector.

This is mathematically valid under the following admissibility assumptions:

- `A_conv` and `A_prim` are full-rank column-basis matrices;
- the conventional-to-primitive transform is rational with denominators representable under `max_denominator`;
- the scale-aware reconstruction and parallelism tolerances are appropriate for the supplied floating-point cells;
- the conventional Miller vector is nonzero.

The implementation fails explicitly when these assumptions are violated. Therefore the conversion should be documented as an exact-rational reconstruction with bounded denominator verification, not as an unconditional symbolic transform for arbitrary floating-point cells.

## Validity of Gauss reduction and shear minimization

`compute_primitive_surface_basis` applies a metric-aware 2D Gauss reduction to the exact pair \((u,v)\). The reduced pair is accepted only if the cross-product certificate remains valid. If not, the implementation returns the exact unreduced pair.

This preserves kernel completeness. The reduction is a gauge choice on the same surface lattice, not a change to the scientific surface plane.

`minimize_shear` changes the stacking vector by

\[
w \mapsto w + p u + q v, \qquad p,q \in \mathbb{Z}.
\]

Because \(m^T u = m^T v = 0\), this preserves the Bezout layer certificate \(m^T w=1\). The implementation additionally checks the triple-product invariant before accepting the minimized vector. This is mathematically valid as a representative choice within the stacking-vector coset.

## Motif compatibility audit

The exact Bravais-kernel certificate does not, by itself, prove that the decorated atomic motif is minimal under all pure translations. Motif compatibility depends on species labels and fractional coordinates, not only on the Bravais lattice.

CALM contains two motif-related mechanisms:

1. `compute_primitive_surface_basis` and `build_oriented_slab` construct the primitive Bravais surface cell directly from the primitive bulk cell and Miller transform. For primitive bulk inputs and ordinary crystallographic motifs, this is the intended production path.
2. `_reduce_inplane_by_motif_translations` and `_find_primitive_surface_cell` provide additional motif or post-hoc search machinery. These routines depend on symmetry-derived translations, denominator bounds, coefficient bounds, and tolerances.

The audit conclusion is that CALM may claim a proven primitive **Bravais surface lattice** for the exact kernel path, but should avoid claiming globally complete **decorated motif minimality** for every possible floating-point decorated structure unless the claim is restricted to the documented symmetry/tolerance domain.

## Bounded search audit

`_generate_inplane_vectors_from_primitive` enumerates integer combinations of primitive vectors with coefficients bounded by `max_coeff` and accepts vectors whose slab-frame `z` component is below a fixed tolerance. `_find_primitive_surface_cell` then evaluates pairs of such vectors by area, fractional-translation checks, and atom-count heuristics.

This is useful fallback/search machinery, but it is not a complete enumeration of all primitive in-plane vectors unless a bound is proven that guarantees the desired pair lies inside `|n_i| <= max_coeff`. The current implementation does not encode such a proof. Therefore these routines should be documented as bounded searches or best-effort motif reductions.

## Implementation-validity assessment

| Component | Mathematical status | Implementation status | Audit conclusion |
| --- | --- | --- | --- |
| Primitive Miller conversion | Valid under rational-transform and tolerance assumptions | Verifies reconstruction and reciprocal parallelism | Sound for admissible inputs; document bounded denominator domain |
| Exact primitive triplet | Valid for primitive nonzero integer `m` | Verifies cross-product and Bezout certificates | Strongly conformant |
| 2D basis reduction | Valid as lattice-gauge reduction when certificate preserved | Accepts reduction only if certificate survives | Strongly conformant |
| Shear minimization | Valid coset representative choice | Checks triple-product invariant and `m @ w` | Strongly conformant |
| `build_oriented_slab` exact path | Valid composition of exact surface basis, layer scaling, supercell construction, rotation, and optional gauges | Uses exact `compute_primitive_surface_basis` path | Conformant, but needs end-to-end motif/layer invariants |
| Symmetry-based motif reduction | Valid as tolerance-dependent motif reduction | Uses pure translations and bounded denominators | Bounded/tolerance-dependent, not unconditional |
| Primitive-vector fallback search | Bounded heuristic unless search radius is justified | Uses fixed coefficient and area/atom-count priorities | Useful, but should not carry global completeness claims |

## Documentation corrections identified

The docstring of `compute_primitive_surface_basis` still describes the algorithm as using Smith normal form and conventional surface-vector/HNF adjustment steps. The current implementation instead converts the Miller vector, constructs an exact primitive triplet, optionally applies certificate-preserving Gauss reduction, and minimizes the stacking-vector shear coset.

Recommended correction: update the docstring and any mirrored algorithm notes to reflect the implemented certificate-based construction. This can be a small source/documentation patch after this audit.

## Verification status

Existing verification is strong for local algebraic certificates:

- Miller conversion on simple and centered cells;
- exhaustive small Miller-index checks;
- Bezout triplet properties;
- basis-change invariance;
- negative Miller semantics;
- skew-cell and failure behavior;
- motif preservation examples;
- scale-aware validation.

Remaining verification gaps:

1. an explicit test that `compute_primitive_surface_basis` never accepts a Gauss-reduced pair unless the cross-product certificate is preserved;
2. direct tests for the determinant/layer-count relation `abs(det([u v Lw])) == L`;
3. end-to-end tests that connect exact Bravais primitivity to atom counts for representative primitive, centered, and decorated cases;
4. tests documenting the bounded nature of `_find_primitive_surface_cell`, including fallback behavior when the coefficient bound is insufficient;
5. tests that distinguish primitive Bravais lattice completeness from decorated motif minimality.

## Correctness properties for future tests

For admissible inputs, the exact primitive surface basis path should satisfy:

- `gcd(abs(m)) == 1`;
- `m @ u == 0` and `m @ v == 0`;
- `cross(u, v) == m` or `cross(u, v) == -m`;
- `m @ w == 1`;
- `abs(round(det(column_stack([u, v, layers*w])))) == layers`;
- adding integer combinations of `u` and `v` to `w` preserves `m @ w == 1`;
- the in-plane Cartesian basis spans a plane normal to the primitive reciprocal normal associated with `m`;
- optional gauge reductions must preserve the exact integer-kernel certificate or explicitly record themselves as representation gauges.

For motif-reduction/search paths, tests should assert bounded-search semantics rather than global completeness unless additional proof machinery is introduced.

## Audit conclusion

The exact primitive surface-cell kernel used by CALM's primary oriented-slab path is mathematically valid and well aligned with the implementation. The strongest evidence is the explicit cross-product and Bezout certificate checking in `_primitive_surface_triplet_from_m` and `compute_primitive_surface_basis`.

The main conformance risk is terminology. Documentation should reserve “complete” or “guaranteed primitive” language for the exact Bravais-kernel path and use bounded, tolerance-dependent, or best-effort language for decorated motif reductions and fallback primitive-vector searches. The next implementation-facing update should correct the stale `compute_primitive_surface_basis` docstring and add the determinant/layer-count guardrail tests identified above.
