# Surface matching mathematical audit

Update: `0223-surface-matching-mathematical-audit.zip`

This audit evaluates CALM's surface-cell matching transformation as a complete transformation-centric unit. It consolidates the existing algorithm specification and validity audit into an explicit judgement about mathematical validity, implementation validity, and verification coverage.

The audited transformation is the finite-index lattice-matching stage that maps two slab in-plane lattices to a ranked list of internal interface match candidates.

```text
Slab_A, Slab_B
    -> primitive in-plane bases
    -> bounded HNF supercells
    -> reduced supercell representatives
    -> affine-invariant strain diagnostics
    -> ranked internal Candidate records
```

The audit intentionally evaluates CALM's implemented finite search problem, not the ideal unbounded commensurability problem over all possible two-dimensional superlattices.

## Implementation scope

Primary implementation owners:

| Role | Owner |
| --- | --- |
| Match enumeration entry point | `calm.interface.matching.enumerate_matches` |
| HNF index-pair area prefilter | `calm.interface.matching.compute_valid_hnf_index_pairs` |
| Primitive in-plane extraction | `calm.interface.matching._prim_inplane_basis_2d` |
| HNF enumeration | `calm.math2d.enumerate_hnf_2d_by_index` |
| Reduced supercell construction | `calm.interface.types.ReducedSupercell2D` |
| Point-group-key representative selection | `calm.keys.hnf.canonical_hnf_key_under_pg` |
| 2D deterministic reduction | `calm.symmetry.reduction.niggli_reduce_2d` |
| Affine-invariant strain diagnostics | `calm.interface.types.AffineInvariantStrain2D` |
| Zur--McGill-style diagnostic summary | `calm.interface.types.ZMStrain2D` |
| Enumeration audit bookkeeping | `calm.interface.audit.PrototypeEnumerationAudit` |

Primary mathematical specifications and prior audits:

- [Surface-cell matching and strain optimization](../algorithms/surface-cell-matching-and-strain-optimization.md)
- [Surface matching validity audit](surface-matching-validity-audit.md)
- [Mathematical traceability inventory](mathematical-traceability-inventory.md)
- [Mathematical audit inventory](mathematical-audit-inventory.md)

## Mathematical problem

Given two primitive in-plane bases

\[
A, B \in \mathbb{R}^{2 \times 2},
\]

with nonzero oriented area, CALM searches for integer supercell matrices

\[
H_A, H_B \in \mathbb{Z}^{2 \times 2}, \qquad
\det(H_A) = k_A, \qquad \det(H_B) = k_B,
\]

within configured determinant bounds. Each pair defines two candidate supercell bases

\[
S_A = A H_A, \qquad S_B = B H_B.
\]

The implemented matching problem is:

1. enumerate admissible finite-index supercells up to `k_max`;
2. discard impossible determinant pairs using a necessary area-band condition induced by the principal Hencky-strain bound;
3. reduce each supercell to a deterministic two-dimensional gauge;
4. compare reduced Gram tensors using an affine-invariant SPD metric;
5. keep representatives after point-group canonicalization;
6. rank candidates by a weighted strain/size objective.

The mathematical object produced by this stage is an internal match candidate, not yet a fully built interface structure and not yet a persisted public candidate record.

## Mathematical validity

### HNF enumeration

Every finite-index sublattice of a rank-two lattice can be represented by a Hermite normal form integer matrix of determinant `k`. Enumerating HNF matrices for each determinant `k <= k_max` is therefore mathematically valid for the bounded superlattice search problem.

This is a completeness result only inside the configured determinant bound. CALM does not claim global completeness over all possible commensurate supercells.

Judgement: **valid under bounded finite-index semantics**.

### Area-band prefilter

Let the two candidate supercell areas be

\[
\Omega_A = k_A |\det A|, \qquad
\Omega_B = k_B |\det B|.
\]

If a later principal Hencky-strain gate requires

\[
|\varepsilon_1| \leq \varepsilon_{\max}, \qquad
|\varepsilon_2| \leq \varepsilon_{\max},
\]

then the area ratio must satisfy

\[
\exp(-2\varepsilon_{\max}) \leq
\frac{\Omega_A}{\Omega_B}
\leq
\exp(2\varepsilon_{\max}).
\]

This follows because the logarithmic area change is the trace of the Hencky strain,

\[
\log\left(\frac{\Omega_B}{\Omega_A}\right)
= \varepsilon_1 + \varepsilon_2,
\]

and the sum of two principal strains bounded in absolute value lies in the interval
\([-2\varepsilon_{\max}, 2\varepsilon_{\max}]
\).

The implemented `compute_valid_hnf_index_pairs` uses this as a necessary prefilter. It is not sufficient for match acceptance because a determinant pair that passes the area bound can still fail the shape/principal-strain bound.

Judgement: **valid necessary filter, not a sufficient acceptance criterion**.

### Deterministic reduced-cell gauge

For each raw supercell basis, `ReducedSupercell2D.build` applies deterministic two-dimensional reduction and records both the reduced basis and the integer transform. When the returned integer transform is unimodular, the represented lattice is preserved while the basis gauge changes.

The matching comparison is performed on reduced Gram tensors. This is mathematically valid as a deterministic representative-selection strategy provided that reduction is deterministic under the configured tolerances and that downstream claims remain about representative candidates rather than about all unreduced embeddings.

Judgement: **valid as gauge fixing; not an independent physical transformation**.

### Point-group-key deduplication

`ReducedSupercell2D.build_index` optionally deduplicates by the point-group canonical key of the total integer supercell transform. This selects one representative from a symmetry orbit defined by the supplied surface point-group operations.

This is valid as representative selection under the chosen surface symmetry group. It is not a proof of full crystallographic equivalence of all decorated interfaces because decorated motifs, terminations, registry choices, and later atomic geometry may break or refine the lattice-level symmetry.

Judgement: **valid representative selection for lattice supercells; not a complete decorated-interface equivalence relation**.

### Affine-invariant strain metric

For reduced Gram tensors `G_A` and `G_B`, CALM constructs

\[
M = G_A^{-1/2} G_B G_A^{-1/2}.
\]

The eigenvalues of `M` are positive when both Gram matrices are SPD. Principal Hencky strains are

\[
\varepsilon_i = \frac{1}{2}\log \mu_i,
\]

where `mu_i` are the eigenvalues of `M`. This is a standard affine-invariant comparison of SPD metric tensors and is appropriate for basis-independent two-dimensional lattice-shape comparison.

The total cell distance used internally is

\[
d_{cell} = 2\sqrt{\varepsilon_1^2 + \varepsilon_2^2},
\]

matching the current `AffineInvariantStrain2D.d_cell` convention.

Judgement: **mathematically valid SPD metric diagnostic**.

### Size penalty and ranking

The size penalty depends on the logarithm of the atom-count expansion relative to the primitive slab atom counts. The combined objective is a ranking functional, not a physical energy. It is valid as a deterministic prioritization heuristic, provided that documentation does not represent it as a thermodynamic or variational objective.

Judgement: **valid heuristic ranking objective**.

## Implementation validity

The implementation is broadly consistent with the mathematical formulation.

| Component | Implementation finding | Judgement |
| --- | --- | --- |
| Primitive basis extraction | Uses the first two Cartesian components of column-oriented slab cells. This assumes slab cells have been oriented so the interface plane is represented in the global xy block. | Valid under the slab-frame convention; should remain explicitly documented. |
| HNF enumeration | `ReducedSupercell2D.build_index` enumerates all HNFs for each determinant up to `k_max`. | Conformant. |
| Area-band filter | `compute_valid_hnf_index_pairs` compares indexed areas without explicitly forming ratios and widens boundaries by `rtol`. | Conformant; boundary tests added in prior guardrails. |
| Conditioning gate | Raw supercells with large condition number are discarded before reduction. | Valid numerical admissibility filter; reduces mathematical completeness beyond determinant bounds. |
| Reduction | `niggli_reduce_2d` is used as the deterministic gauge. | Valid if deterministic and unimodular/invariant properties hold under tests. |
| Point-group dedupe | Keeps one minimum-condition representative per `(k, key_pg)` before pair comparison. | Conformant representative selection; not complete decorated equivalence. |
| Metric comparison | Uses `G_A^{-1/2} G_B G_A^{-1/2}` and principal log strains. | Conformant. |
| Principal-strain gate | Applies max absolute principal Hencky strain bound. | Conformant. |
| Candidate ranking | Sorts by `(match_score, d_cell)`. | Deterministic and documented as ranking. |
| Audit bookkeeping | Records generated, symmetry-removed, kept, and interface-attempt counts by determinant. | Useful but should not be treated as proof of scientific completeness. |

## Correctness properties

The following properties should hold for every accepted candidate:

1. `k_A` and `k_B` are positive integers within configured bounds.
2. `H_A` and `H_B` are integer supercell matrices with determinants equal to their indices.
3. Reduced bases represent the same sublattices as the raw supercells up to unimodular basis change and rigid in-plane rotation.
4. Reduced Gram tensors are symmetric positive definite.
5. The relative metric `M` is SPD.
6. Principal Hencky strains are real and finite.
7. The maximum absolute principal strain is no larger than `eps_principal_max` for stored candidates.
8. The area-band prefilter never excludes a determinant pair that could satisfy the later principal-strain bound under exact arithmetic.
9. Point-group deduplication preserves at least one representative from each retained canonical key orbit.
10. Sorting is deterministic for a fixed input, configuration, and numerical backend.

## Limitations and assumptions

Surface matching remains intentionally bounded and tolerance-dependent:

- determinant bounds limit completeness;
- conditioning gates discard mathematically valid but numerically undesirable cells;
- surface point-group operations are representation-dependent and can be sensitive to slab symmetry detection;
- reduced-cell gauge choices depend on tolerance conventions;
- lattice-level supercell equivalence does not imply decorated-interface equivalence;
- the ranking score is a search heuristic, not a physical objective;
- the xy-block primitive basis extraction assumes upstream slab orientation has already canonicalized the surface plane.

These limitations are mathematically acceptable when stated explicitly. They would become correctness problems only if CALM claimed unbounded global completeness, full decorated-interface equivalence, or physical optimality from this matching score alone.

## Verification coverage

Existing or recent tests provide coverage for several components:

| Property | Current coverage status |
| --- | --- |
| HNF enumeration and determinant behavior | Good; existing HNF/unit tests and architecture tests exercise enumeration helpers. |
| 2D reduction and handedness | Good; Niggli/reduction tests exercise reduction properties. |
| Unimodular invariance | Good; existing tests cover reduced-supercell invariance under basis changes. |
| Point-group-key deduplication | Moderate-good; C2/C3 tests cover key/orbit behavior. |
| Area-band boundary behavior | Good after the HNF/area-band guardrails. |
| Affine-invariant SPD strain diagnostics | Moderate-good; covered indirectly through matching and strain tests. |
| End-to-end match candidate acceptance | Moderate; stronger synthetic slab tests could explicitly assert expected candidate counts under simple lattice pairs. |
| Optional-dependency-free matching tests | Partial; many tests remain dependent on available slab/ASE construction pathways. |

## Residual verification gaps

The next most useful tests would be dependency-light synthetic matching tests that avoid requiring full slab construction. They should verify:

1. square-vs-square matching gives a zero-strain `k_A=k_B=1` candidate;
2. scaled-square matching requires determinant pairs consistent with the area band;
3. rectangular cells with known aspect ratio produce expected principal strains;
4. `dedupe_by_key=True` keeps a deterministic representative per canonical key;
5. `dedupe_by_key=False` exposes the larger unreduced candidate set;
6. conditioning gates remove deliberately ill-conditioned supercells;
7. audit counts agree with direct HNF enumeration for small `k_max`.

## Audit conclusion

CALM's surface-cell matching transformation is mathematically valid and implementation-conformant for the documented finite search problem:

```text
bounded HNF enumeration
+ area-band necessary filtering
+ deterministic 2D reduction
+ point-group representative selection
+ affine-invariant Hencky strain gating
+ heuristic size/strain ranking
```

The implementation should not be described as a globally complete unbounded commensurability solver. Its correctness claim is bounded by determinant cutoffs, conditioning thresholds, symmetry/key choices, reduction tolerances, and the upstream slab-frame convention.

## Recommended next action

Add dependency-light synthetic matching guardrails for the residual verification gaps above, then continue the transformation-centric audit sequence with oriented slab construction or bounded decorated-motif semantics.

## 0226 invariant-audit refinement

Update `0226` tightens the audit around three implementation-level mathematical distinctions.

### Area admissibility is only a necessary condition

The area-band filter follows from the trace bound on principal Hencky strain, but it does not constrain deviatoric shape strain. A unit square and a high-aspect-ratio rectangle can have equal area, so the pair `(k_A, k_B) = (1, 1)` is admissible under the area prefilter while still failing the later principal-strain gate. The implementation realizes this separation correctly: `compute_valid_hnf_index_pairs` admits determinant pairs by area, while `enumerate_matches` performs the SPD principal-strain acceptance check.

### Reduction is a representation morphism

`ReducedSupercell2D.build` may change basis gauge through an integer unimodular transform and a proper embedding rotation. The audited invariant is therefore not equality of raw basis matrices, but preservation of the finite-index sublattice: the total integer map has determinant magnitude equal to `k`, and the reduced basis area remains `k` times the primitive area. This confirms that deterministic reduction is a representation morphism used for comparison, not a scientific deformation of the surface lattice.

### Exact lattice match is not equivalent to zero composite score

The mathematical exact-match invariant for the cell comparison is zero affine-invariant cell distance, up to floating-point tolerance. The aggregate `match_score` is a normalized ranking functional that can reflect tiny residual floating-point normalization or size/ranking terms. Tests should therefore assert `d_cell` and principal-strain invariants directly and should not require the composite heuristic score to vanish.

### Audit action

The added guardrails in `tests/public/test_surface_matching_mathematical_invariants.py` encode these three distinctions. This converts the audit finding into executable verification without changing runtime behavior.
