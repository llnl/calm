# Primitive surface generation mathematical audit

Update `0222-primitive-surface-generation-mathematical-audit.zip` records the first transformation-centric audit in the Mathematical and Algorithmic Specification milestone. It completes a single transformation across four axes: mathematical specification, implementation audit, verification status, and recommended engineering actions.

## Transformation identity

| Field | Value |
| --- | --- |
| Audit ID | MT-AUDIT-001 |
| Ontology morphism | `Construct Surface` / primitive surface-cell generation |
| Scientific input | Bulk crystal lattice with a conventional Miller covector `(h,k,l)` and a primitive cell representation |
| Scientific output | Primitive Bravais surface cell basis and stacking direction in primitive fractional coordinates |
| Primary implementation owner | `calm.slab.ops.primitive_surface_algorithm` |
| Secondary implementation owner | `calm.slab.ops.oriented_slab` for oriented-slab composition and motif/search helpers |
| Primary specification | `docs/mathematics/algorithms/motif-compatible-surface-primitive-cells.md` |
| Prior audit | `docs/mathematics/verification/primitive-surface-cell-completeness-audit.md` |
| Guardrail tests | `tests/slab/test_primitive_surface_completeness_guardrails.py` and existing slab primitive-surface tests |

## Repository evidence inspected

The audit is grounded in the current repository implementation and tests:

- `calm.slab.ops.primitive_surface_algorithm.primitive_miller_from_conventional`
- `calm.slab.ops.primitive_surface_algorithm._primitive_surface_triplet_from_m`
- `calm.slab.ops.primitive_surface_algorithm.compute_primitive_surface_basis`
- `calm.slab.ops.primitive_surface_algorithm.minimize_shear`
- `calm.slab.ops.primitive_surface_algorithm.build_oriented_primitive_slab`
- `calm.slab.ops.validate_surface_basis.validate_surface_basis`
- `calm.slab.ops.oriented_slab._find_primitive_surface_cell`
- `calm.slab.ops.oriented_slab._reduce_inplane_by_motif_translations`
- `tests/slab/test_primitive_surface_algorithm.py`
- `tests/slab/test_miller_transforms.py`
- `tests/slab/test_centered_miller_transforms.py`
- `tests/slab/test_exhaustive_millers.py`
- `tests/slab/test_bezout_triplet_properties.py`
- `tests/slab/test_basis_change_invariance.py`
- `tests/slab/test_negative_miller_semantics.py`
- `tests/slab/test_surface_basis_validation.py`
- `tests/slab/test_motif_preservation.py`
- `tests/slab/test_primitive_surface_completeness_guardrails.py`

## Mathematical problem

Given a conventional Miller covector

\[
q = (h,k,l) \in \mathbb{Z}^3 \setminus \{0\}
\]

and a primitive cell commensurate with the conventional cell, CALM must construct an integer primitive surface basis in primitive fractional coordinates. After converting the conventional covector to a primitive integer covector

\[
m \in \mathbb{Z}^3, \qquad \gcd(|m_1|, |m_2|, |m_3|)=1,
\]

the primitive Bravais surface lattice is the saturated rank-two integer kernel

\[
K_m = \{x \in \mathbb{Z}^3 : m^T x = 0\}.
\]

A primitive surface basis is a pair of integer vectors \((u,v)\) satisfying

\[
m^T u = 0, \qquad m^T v = 0, \qquad u \times v = \pm m.
\]

A stacking vector is an integer vector \(w\) satisfying the Bezout certificate

\[
m^T w = 1.
\]

For an integer layer count \(L\), the transformation matrix

\[
T_L = [u\; v\; Lw]
\]

must satisfy

\[
|\det T_L| = L.
\]

This determinant relation is the layer-count certificate: the third column adds exactly \(L\) primitive repeats in the stacking direction while the in-plane pair remains primitive.

## Mathematical validity audit

The mathematics of the exact Bravais-kernel construction is valid under the following assumptions:

1. the conventional and primitive cell matrices are nonsingular;
2. the conventional-to-primitive transform is rational within the configured denominator/tolerance domain;
3. the conventional Miller covector is nonzero;
4. the resulting primitive covector is reduced to a primitive integer vector;
5. floating-point reconstruction and parallelism checks pass within documented tolerances.

Under these assumptions, the exact kernel certificate is sufficient. The equality \(u \times v = \pm m\) proves that \((u,v)\) spans the saturated integer kernel of \(m\), not a finite-index sublattice. The equality \(m^T w = 1\) proves that \(w\) is a valid Bezout stacking vector. Together they imply the determinant/layer-count relation.

Metric-aware Gauss reduction of \((u,v)\) is mathematically admissible only when it preserves the exact cross-product certificate. CALM implements this as a certificate-preserving gauge operation: a reduced pair is accepted only if its cross product remains \(\pm m\). Otherwise the exact unreduced pair is retained.

Stacking-vector shear minimization changes

\[
w \mapsto w + p u + q v, \qquad p,q \in \mathbb{Z}.
\]

Since \(m^T u = m^T v = 0\), this operation preserves \(m^T w=1\). It is therefore a representation-gauge choice within the same stacking coset, not a change to the scientific surface plane or layer count.

## Implementation validity audit

The implementation is strongly aligned with the valid mathematics for the exact Bravais-kernel path.

| Implementation step | Mathematical requirement | Audit result |
| --- | --- | --- |
| Conventional-to-primitive Miller conversion | verified rational reciprocal-index transform | Conformant within bounded denominator/tolerance assumptions |
| Primitive covector reduction | nonzero primitive integer \(m\) | Conformant; invalid zero/singular cases fail explicitly |
| Exact in-plane basis construction | \(m^T u=m^T v=0\), \(u\times v=\pm m\) | Conformant; `_primitive_surface_triplet_from_m` verifies certificate |
| Exact stacking vector construction | \(m^T w=1\) | Conformant; Bezout certificate verified |
| 2D metric reduction | gauge operation preserving primitive kernel | Conformant; reduction accepted only if certificate survives |
| Shear minimization | coset representative preserving layer certificate | Conformant; certificate is checked after minimization |
| Layer transform | \(|\det[u,v,Lw]|=L\) | Conformant for tested cases; explicit guardrails now cover simple and centered lattices |

The implementation should be described as exact and complete only for the primitive Bravais surface lattice under the stated rational-transform/tolerance assumptions. It should not be described as globally complete for decorated motif minimality or for bounded fallback searches.

## Motif and bounded-search validity

The decorated motif problem is distinct from the primitive Bravais-kernel problem. Atomic species and fractional coordinates can admit additional translations that reduce the decorated surface motif, or can prevent reductions that are valid for the Bravais lattice alone.

CALM contains motif-aware and post-hoc primitive-vector search utilities in `calm.slab.ops.oriented_slab`. These routines are useful implementation tools, but their completeness depends on symmetry-derived translations, denominator bounds, finite coefficient windows, and numerical tolerances. They should be documented as bounded or tolerance-dependent unless a separate proof supplies a complete finite search bound.

Therefore this audit marks the exact Bravais-kernel path as mathematically complete in its domain, and marks decorated motif reduction/fallback primitive-vector search as bounded implementation machinery.

## Verification audit

Existing tests provide strong local evidence for the exact path:

- small Miller-index examples;
- centered-cell conversions;
- exhaustive small Miller-index scans;
- Bezout triplet properties;
- basis-change invariance;
- negative Miller-index semantics;
- scale-aware validation failures;
- motif preservation examples;
- determinant/layer-count certificates for simple and centered cells.

The key invariants now covered include:

\[
\gcd(|m|)=1, \quad m^T u=0, \quad m^T v=0, \quad u\times v=\pm m, \quad m^T w=1, \quad |\det[u,v,Lw]|=L.
\]

Remaining verification gaps are narrower and should be tracked separately:

1. a direct monkeypatch/property test proving that any failed Gauss-reduction certificate falls back to the exact pair;
2. explicit tests that distinguish primitive Bravais completeness from decorated motif minimality;
3. bounded-search tests documenting `_find_primitive_surface_cell` behavior when the coefficient bound is insufficient;
4. optional end-to-end slab tests, where optional dependencies permit, that connect primitive surface basis certificates to atom counts and transform provenance.

## Correctness classification

| Claim | Status | Notes |
| --- | --- | --- |
| Exact primitive Bravais surface kernel is valid | Accepted | Proven by integer kernel and cross-product certificates |
| Conventional-to-primitive conversion is valid | Accepted with assumptions | Requires nonsingular commensurate cells and bounded rationalization success |
| Shear minimization preserves surface/layer identity | Accepted | Coset operation preserving \(m^T w=1\) |
| Layer count determinant is correct | Accepted | Follows algebraically and is tested |
| Decorated motif minimality is globally complete | Not accepted | Requires motif-specific proof and tolerance/bound domain |
| Fallback primitive-vector search is globally complete | Not accepted | Current implementation is bounded search |

## Engineering actions from this audit

Completed or already present:

- The `compute_primitive_surface_basis` docstring now describes the certificate-based implementation rather than stale SNF/HNF wording.
- Determinant/layer-count guardrail tests are present.
- The mathematics reference distinguishes exact Bravais-kernel construction from bounded motif/search machinery.

Recommended next actions:

1. Add fallback-specific tests for bounded primitive-vector search semantics.
2. Add a small verification page or test note for decorated motif minimality limits.
3. Continue the transformation-centric audit sequence with surface matching or oriented slab construction, using the same four-axis template: specification, implementation audit, verification, engineering actions.

## Audit conclusion

Primitive surface generation is sufficiently specified and verified to serve as the current mathematical authority for CALM's exact primitive Bravais surface-cell construction. The implementation realizes the mathematics under the documented admissibility assumptions. Remaining risks are not in the exact integer-kernel construction; they are in terminology and in bounded decorated-motif/search paths that should not inherit unconditional completeness claims.
