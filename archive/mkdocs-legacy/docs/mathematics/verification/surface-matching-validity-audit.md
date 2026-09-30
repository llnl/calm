# Surface matching validity audit

This audit evaluates the mathematical and implementation validity of CALM's surface-cell matching stage. It focuses on the finite search problem implemented by `calm.interface.matching.enumerate_matches`, rather than on an ideal unbounded lattice matching problem.

The main conclusion is that the implemented search is mathematically valid as a bounded enumeration of two-dimensional superlattice pairs, with a necessary area-band prefilter and an affine-invariant Hencky-strain gate. It is not, and should not be documented as, a globally complete search over all commensurate interface cells unless the determinant bounds, conditioning bounds, and deduplication policies are explicitly included in the statement of completeness.

## Repository evidence inspected

Primary implementation owners inspected for this audit:

- `calm.interface.matching.enumerate_matches`
- `calm.interface.matching.compute_valid_hnf_index_pairs`
- `calm.interface.matching._prim_inplane_basis_2d`
- `calm.interface.types.ReducedSupercell2D`
- `calm.interface.types.AffineInvariantStrain2D`
- `calm.interface.types.ZMStrain2D`
- `calm.math2d.normal_forms.enumerate_hnf_2d_by_index`
- `calm.keys.hnf.canonical_hnf_key_under_pg`
- `calm.interface._surface_symmetry.surface_pointgroup_ops_2d`

Relevant tests inspected include:

- `tests/test_unimodular_invariance.py`
- `tests/test_niggli_reduction_2d.py`
- `tests/test_niggli_reduction_audit.py`
- `tests/test_C2_symmetry_orbit_keys_and_pruning.py`
- `tests/test_C2_refinement_gauge_invariance.py`
- `tests/test_C3_build_index_dedupe_order_invariance.py`
- `tests/test_strain_metrics.py`
- `tests/arch/test_interface_matching_typing_modernization.py`
- `tests/arch/test_interface_types_typing_modernization.py`

Related specifications inspected:

- `docs/mathematics/algorithms/surface-cell-matching-and-strain-optimization.md`
- `docs/mathematics/verification/mathematical-audit-inventory.md`
- `docs/mathematics/verification/mathematical-traceability-inventory.md`
- `docs/mathematics/foundations/strain-theory.md`

## Mathematical statement

Let two oriented slabs have primitive in-plane column bases

\[
A, B \in \mathbb{R}^{2 \times 2}, \qquad \det A \ne 0, \quad \det B \ne 0.
\]

A finite-index supercell of index \(k\) is represented by a right Hermite normal form matrix

\[
H = \begin{pmatrix} h_{11} & h_{12} \\ 0 & h_{22} \end{pmatrix},
\quad h_{11} h_{22}=k,
\quad h_{11},h_{22}>0,
\quad 0 \le h_{12}<h_{11}.
\]

CALM enumerates such matrices for each side and forms supercell bases

\[
S_A = A H_A, \qquad S_B = B H_B.
\]

The implemented search is bounded by

\[
1 \le k_A \le k_{\max,A}, \qquad 1 \le k_B \le k_{\max,B},
\]

plus conditioning, point-group deduplication, area-band, and principal-strain gates.

After deterministic two-dimensional reduction, CALM compares reduced Gram matrices

\[
G_A = S_A^T S_A, \qquad G_B = S_B^T S_B
\]

through the relative SPD metric

\[
M = G_A^{-1/2} G_B G_A^{-1/2}.
\]

If \(\mu_i>0\) are eigenvalues of \(M\), the principal Hencky strains are

\[
\varepsilon_i = \frac{1}{2}\log \mu_i.
\]

The match gate accepts only candidates satisfying

\[
\max_i |\varepsilon_i| \le \varepsilon_{\max}.
\]

The cell-distance diagnostic is

\[
d_{cell} = 2 \sqrt{\varepsilon_1^2 + \varepsilon_2^2}.
\]

## Area-band validity

The area ratio of two reduced supercells is encoded in the determinant of the relative metric. Since

\[
\det G_A = \operatorname{area}(S_A)^2,
\qquad
\det G_B = \operatorname{area}(S_B)^2,
\]

we have

\[
\det M = \frac{\det G_B}{\det G_A}
       = \left(\frac{\operatorname{area}(S_B)}{\operatorname{area}(S_A)}\right)^2.
\]

Therefore

\[
\varepsilon_1 + \varepsilon_2
= \frac{1}{2}\log \det M
= \log\left(\frac{\operatorname{area}(S_B)}{\operatorname{area}(S_A)}\right).
\]

If the candidate can pass the principal-strain gate \(|\varepsilon_i|\le\varepsilon_{\max}\), then necessarily

\[
\exp(-2\varepsilon_{\max})
\le
\frac{\operatorname{area}(S_B)}{\operatorname{area}(S_A)}
\le
\exp(2\varepsilon_{\max}).
\]

`compute_valid_hnf_index_pairs` implements this necessary area-band filter using primitive areas and determinant indices. This is mathematically sound as a prefilter: it cannot prove a match is acceptable, but it can rule out index pairs that cannot satisfy the later principal-strain bound.

## HNF enumeration validity

`enumerate_hnf_2d_by_index(k)` enumerates canonical right-HNF representatives for all rank-two integer sublattices of index \(k\) in a fixed primitive in-plane gauge. This is the standard finite-index sublattice parametrization for column-basis supercells. The enumeration is deterministic and complete for the chosen index \(k\).

The bounded search over \(k\le k_{\max}\) is therefore complete only within the configured determinant limits. The implementation should continue to describe completeness as bounded completeness, not as completeness over all possible commensurate interface cells.

## Reduction and gauge validity

`ReducedSupercell2D.build` applies a deterministic two-dimensional reduction to the raw supercell basis. The reduction changes the representative basis but preserves the represented lattice when the returned integer transform is unimodular. The reduced Gram matrix is then used for affine-invariant comparison.

The validity of this step relies on `niggli_reduce_2d` returning a lattice-equivalent reduced basis and associated integer transform. Existing tests exercise handedness, gauge invariance, and reduced-Gram invariance under unimodular changes. This is a strong local verification base.

The reduction is a representation morphism. It changes gauge, not the scientific superlattice.

## Point-group deduplication validity

`canonical_hnf_key_under_pg` canonicalizes the total integer map `N_tot = H @ U_sup` under the slab's two-dimensional surface point group. This is valid as a symmetry deduplication in a fixed canonical primitive surface gauge.

The implementation documentation correctly warns that the point-group HNF key is not meant to be invariant under arbitrary primitive-basis gauge changes, because the point-group representation itself changes under gauge conjugation. Cross-gauge checks should use the SNF-based orbit signature where appropriate.

The audit conclusion is that point-group-key deduplication is valid as representative selection within the implemented gauge. It is not a proof that all geometrically equivalent interface candidates have been removed across arbitrary gauge choices.

## Strain metric validity

The affine-invariant strain diagnostic is mathematically valid for SPD Gram matrices. For full-rank in-plane bases, \(G_A\) and \(G_B\) are SPD, and therefore the relative metric \(M\) is SPD in exact arithmetic. The implementation checks for nonpositive eigenvalues and raises an error, which is appropriate because such a condition indicates an invalid or numerically degenerate state.

The Zur-McGill-style diagnostic in `ZMStrain2D` is a reporting/comparison diagnostic based on lengths and non-obtuse angles. It should not be treated as the primary mathematical admissibility metric; the implemented hard strain gate is the affine-invariant principal Hencky bound.

## Scoring validity

The implemented score is a weighted combination of normalized cell strain and normalized size penalty. This is a deterministic ranking objective, not a mathematical equivalence or admissibility proof. Candidate admissibility comes from the determinant/index bounds, conditioning gates, SPD domain, and principal-strain gate. The score orders candidates after those gates.

This distinction should remain explicit in documentation: a lower `match_score` indicates preference within the implemented finite search, not a theorem of global optimality over unbounded interface cells.

## Implementation-validity assessment

| Component | Mathematical status | Implementation status | Audit conclusion |
| --- | --- | --- | --- |
| HNF enumeration | Complete for each fixed positive index | `enumerate_hnf_2d_by_index` implements canonical right-HNF enumeration | Strongly conformant for bounded search |
| Index bounds | Define a finite admissible search domain | `k_max` applied to both sides | Complete only within configured bounds |
| Area-band prefilter | Necessary consequence of principal Hencky bound | `compute_valid_hnf_index_pairs` compares indexed areas without forming explicit ratios | Mathematically valid prefilter; not sufficient by itself |
| Conditioning gate | Numerical admissibility criterion | Raw supercell condition checked before reduction | Valid numerical guard; may exclude mathematically valid but ill-conditioned cells |
| 2D reduction | Gauge change preserving superlattice | `niggli_reduce_2d` result stored with integer transform | Conformant subject to reduction invariants |
| Point-group deduplication | Representative selection under fixed-gauge surface symmetry | Canonical key from `N_tot` under surface point group | Valid within gauge; not arbitrary-gauge equivalence |
| Affine-invariant strain | Valid SPD metric/Hencky diagnostic | Computes eigenvalues of relative metric and gates principal log strains | Strongly conformant for nondegenerate in-plane bases |
| Candidate scoring | Ranking heuristic after admissibility gates | Weighted normalized strain/size score | Valid preference score; not global optimality proof |

## Documentation or implementation corrections identified

Two small follow-up corrections are worth considering.

1. The `compute_valid_hnf_index_pairs` error message says `k_max_A and k_max_B must be greater than 1`, while the implemented admissible condition is `>= 1`. The message should say `must be at least 1` or `must be positive`.
2. The area-band logic is mathematically important and should have a direct boundary-focused unit test. Existing tests cover matching behavior broadly, but a small dependency-light test for the exact necessary area-band condition would make the mathematical specification executable.

Neither item changes runtime semantics.

## Recommended guardrail tests

Future tests should verify:

- `enumerate_hnf_2d_by_index(k)` emits exactly \(\sum_{d|k} d\) HNF matrices;
- `compute_valid_hnf_index_pairs` includes exact boundary pairs at \(\exp(\pm2\varepsilon_{\max})\) within tolerance;
- candidate area ratios that violate the area band cannot pass the principal-strain gate;
- affine-invariant strain diagnostics are invariant under common orthogonal rotation and integer unimodular basis changes after reduction;
- point-group deduplication keeps one deterministic representative per fixed-gauge orbit;
- dedupe-by-metric remains documented as optional representative collapsing rather than as sublattice-equivalence preservation.

## Current conclusion

Surface-cell matching is mathematically valid and implementation-conformant as a bounded finite-index search with representation-gauge reduction, fixed-gauge point-group deduplication, and affine-invariant Hencky-strain gating. The main correctness caveat is the scope of the claim: CALM should claim bounded completeness under declared determinant, conditioning, symmetry, and tolerance settings, not global completeness over all commensurate interface cells.

The next small corrective update should adjust the `compute_valid_hnf_index_pairs` error message and add boundary-focused guardrail tests for HNF enumeration and the area-band prefilter.
