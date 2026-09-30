# Surface-cell matching and strain optimization

## Purpose

Surface-cell matching is the CALM algorithm that turns two already constructed slabs into candidate commensurate interface cells. The algorithm searches finite-index two-dimensional superlattices of each slab, reduces them to deterministic gauges, compares their intrinsic metrics, rejects matches outside a principal Hencky-strain window, and ranks the remaining candidates by a combined cell-mismatch and size objective.

This document specifies the mathematical problem, implemented algorithm, assumptions, correctness properties, and verification mapping for the current matching pipeline implemented in `calm.interface.matching` and its supporting 2D linear-algebra utilities.

## Ontology mapping

| Role | CALM ontology object or representation |
| --- | --- |
| Input scientific objects | Slab A and Slab B |
| Input representations | ASE-like slab cells with row-vector storage; CALM converts to column-vector cell matrices |
| Intermediate scientific object | Interface Candidate |
| Intermediate representations | Primitive in-plane bases, HNF supercell matrices, reduced supercell bases, Gram matrices, point-group canonical keys |
| Scientific morphism | Match |
| Representation morphisms | Row-to-column cell conversion, 3D-to-2D in-plane projection, integer supercell enumeration, 2D reduction, symmetry-key canonicalization |
| Output representation | Internal `Candidate` records containing reduced supercells and strain diagnostics |

The matching stage does not build an atomic interface structure and does not evaluate an interface energy. It produces candidate commensurate in-plane lattices and strain diagnostics that later morphisms consume.

## Mathematical problem

Let the two slabs have primitive in-plane column bases

\[
A \in \mathbb{R}^{2\times 2}, \qquad B \in \mathbb{R}^{2\times 2},
\]

with positive areas

\[
a_A = |\det A|, \qquad a_B = |\det B|.
\]

A finite-index supercell of slab A is represented by an integer matrix

\[
H_A \in \mathbb{Z}^{2\times 2}, \qquad \det H_A = k_A > 0,
\]

and similarly for slab B. The corresponding in-plane supercell bases are

\[
S_A = A H_A, \qquad S_B = B H_B.
\]

The matching problem is to find pairs \((H_A,H_B)\) such that the two supercell lattices are close under an allowed elastic deformation and are not redundant under in-plane lattice symmetries. CALM currently searches over bounded indices

\[
1 \le k_A \le k_{\max}, \qquad 1 \le k_B \le k_{\max},
\]

and rejects a pair if the maximum absolute principal Hencky strain exceeds a prescribed threshold.

## Supercell enumeration by HNF

CALM enumerates 2D supercells using canonical right Hermite normal form representatives. For each positive integer index \(k\), the enumerated HNF matrices are

\[
H =
\begin{pmatrix}
h_{11} & h_{12} \\
0 & h_{22}
\end{pmatrix},
\]

where

\[
h_{11} h_{22} = k, \qquad h_{11}>0, \qquad h_{22}>0, \qquad 0 \le h_{12} < h_{11}.
\]

These representatives enumerate sublattices of index \(k\) once modulo right multiplication by unimodular integer matrices. CALM uses this enumeration through `calm.math2d.enumerate_hnf_2d_by_index`.

The number of HNF representatives at index \(k\) is

\[
\sum_{d\mid k} d,
\]

because each divisor \(h_{11}=d\) contributes \(d\) choices for \(h_{12}\). Before pairwise comparison, each side is enumerated independently up to `k_max`.

## Area-band prefilter

A two-dimensional deformation with principal Hencky strains \(\varepsilon_1,\varepsilon_2\) changes area by

\[
\frac{\operatorname{area}(S_B)}{\operatorname{area}(S_A)}
= \exp(\varepsilon_1+\varepsilon_2).
\]

If the admissibility condition is

\[
|\varepsilon_i| \le \varepsilon_{\max} \quad \text{for } i=1,2,
\]

then the log-area mismatch must satisfy

\[
-2\varepsilon_{\max}
\le
\log\left(\frac{k_A a_A}{k_B a_B}\right)
\le
2\varepsilon_{\max}.
\]

CALM uses this as an inexpensive prefilter on HNF index pairs. It computes valid \((k_A,k_B)\) pairs by checking the equivalent multiplicative band

\[
\exp(-2\varepsilon_{\max})
\le
\frac{k_A a_A}{k_B a_B}
\le
\exp(2\varepsilon_{\max}),
\]

with a small widening tolerance to avoid dropping boundary cases because of floating-point roundoff. This is implemented by `compute_valid_hnf_index_pairs`.

This prefilter is necessary but not sufficient: a pair can have compatible area but incompatible shape.

## Deterministic reduction and gauge selection

Raw supercell bases are not unique. If \(U\in GL(2,\mathbb{Z})\), then

\[
S \quad \text{and} \quad S U
\]

represent the same 2D lattice with a different integer basis. CALM therefore reduces each enumerated supercell into a deterministic 2D gauge before comparing it to supercells from the other slab.

For a raw basis \(S = A H\), CALM applies 2D Niggli/Gauss reduction:

\[
(S_{\mathrm{red}}, U_{\mathrm{sup}}, R_{\mathrm{sup}})
= \operatorname{reduce}_{2D}(S),
\]

where

\[
S_{\mathrm{lat}} = S U_{\mathrm{sup}},
\qquad
S_{\mathrm{red}} = R_{\mathrm{sup}} S_{\mathrm{lat}}.
\]

Here \(U_{\mathrm{sup}}\) is an integer unimodular basis transform and \(R_{\mathrm{sup}}\) is a proper embedding rotation in Cartesian space. The reduced Gram matrix is

\[
G_{\mathrm{red}} = S_{\mathrm{red}}^T S_{\mathrm{red}}.
\]

The total integer map from primitive surface basis to reduced supercell basis is recorded as

\[
N_{\mathrm{tot}} = H U_{\mathrm{sup}}.
\]

CALM discards raw supercells whose condition number exceeds `cond_max`. This is a numerical admissibility gate rather than a scientific equivalence rule.

## Surface point-group deduplication

Each slab may admit in-plane surface point-group operations that map one integer supercell embedding to an equivalent embedding. CALM canonicalizes the reduced integer map under the slab's surface point group:

\[
\operatorname{key}_{\mathrm{pg}}(N_{\mathrm{tot}})
= \min_{P\in PG} \operatorname{key}(N_{\mathrm{tot}} P),
\]

where the exact keying convention is implemented by `calm.keys.hnf.canonical_hnf_key_under_pg`.

When `dedupe_by_key=True`, CALM keeps at most one reduced supercell per pair \((k,\operatorname{key}_{\mathrm{pg}})\), selecting the representative with the lowest raw-basis condition number. This removes symmetry-equivalent embeddings before cross-side comparison.

Metric-based deduplication is intentionally disabled by default because equal reduced metrics do not imply equal sublattice embeddings. This preserves distinct scientific candidates that happen to have the same in-plane metric.

## Affine-invariant strain metric

For two reduced supercell Gram matrices

\[
G_A = S_A^T S_A, \qquad G_B = S_B^T S_B,
\]

CALM computes the relative metric

\[
M = G_A^{-1/2} G_B G_A^{-1/2}.
\]

The matrix \(M\) is symmetric positive definite for valid full-rank cells. Its eigenvalues \(\mu_i\) are the squared principal stretches between the two intrinsic metrics:

\[
\lambda_i = \sqrt{\mu_i},
\qquad
\varepsilon_i = \log \lambda_i = \frac{1}{2}\log\mu_i.
\]

The Hencky strain tensor in this intrinsic metric comparison is

\[
E = \frac{1}{2}\log M.
\]

CALM records the isotropic and deviatoric components

\[
E_{\mathrm{iso}} = \frac{\operatorname{tr}E}{2}I,
\qquad
E_{\mathrm{dev}} = E - E_{\mathrm{iso}}.
\]

The primary cell mismatch distance is

\[
d_{\mathrm{cell}} = 2\|E\|_F = 2\sqrt{\varepsilon_1^2+\varepsilon_2^2}.
\]

The factor of two matches the current internal distance convention used by `AffineInvariantStrain2D.d_cell` and `enumerate_matches`.

A candidate is rejected if

\[
\max_i |\varepsilon_i| > \varepsilon_{\max}.
\]

## Size penalty and combined objective

Let \(N_A\) and \(N_B\) be the primitive slab atom counts. The total atom count of the paired supercell before interface construction is approximated as

\[
N_{\mathrm{at}} = k_A N_A + k_B N_B.
\]

CALM defines the size penalty

\[
d_{\mathrm{size}}
= \max\left(0,\log\frac{N_{\mathrm{at}}}{N_A+N_B}\right).
\]

The normalized mismatch terms are

\[
\widehat{d}_{\mathrm{cell}}
= \frac{d_{\mathrm{cell}}}{2\sqrt{2}\varepsilon_{\max}},
\qquad
\widehat{d}_{\mathrm{size}}
= \frac{d_{\mathrm{size}}}{d_{\mathrm{size,max}}},
\]

where `d_size_max` is computed from `N_at_max`. The final match score is

\[
J = w_{\mathrm{match}}\widehat{d}_{\mathrm{cell}}
+ (1-w_{\mathrm{match}})\widehat{d}_{\mathrm{size}}.
\]

Smaller scores are better. CALM sorts returned candidates by

\[
(J, d_{\mathrm{cell}}).
\]

## Algorithm implemented in CALM

The current implementation follows this workflow.

1. Extract each slab's primitive in-plane 2D basis from the 3D cell.
2. Obtain surface point-group operations for each slab.
3. Enumerate HNF supercells by index for each side up to `k_max`.
4. Reject ill-conditioned raw supercell bases using `cond_max`.
5. Reduce surviving supercells by 2D Niggli/Gauss reduction.
6. Compute point-group canonical keys and optionally deduplicate per side.
7. Compute valid \((k_A,k_B)\) index pairs from the area-band prefilter.
8. For each valid index pair, compare all reduced supercells from side A and side B.
9. Compute the affine-invariant relative metric, principal Hencky strains, and cell mismatch.
10. Reject pairs outside the principal-strain window.
11. Compute the combined score with the size penalty.
12. Keep at most one best candidate per pair of point-group canonical keys.
13. Return candidates sorted by score and cell mismatch.

## Implementation notes (migrated from legacy algorithm guide)

This section contains practical implementation notes and a short worked example that were previously maintained as legacy documentation. They are preserved here as concise implementation guidance and a small appendix example. Per project policy, longer examples were kept in appendix-style form and implementation notes were limited to short, actionable recommendations.

### Practical implementation snippets

1. Area-band prefilter — code sketch (migrate from legacy implementation):

```python
def compute_valid_hnf_index_pairs(areaA_prim, areaB_prim, k_max_A, k_max_B, eps_principal_max):
    eps_area = 2.0 * eps_principal_max
    kA = np.arange(1, k_max_A + 1)[:, None]
    kB = np.arange(1, k_max_B + 1)[None, :]
    lhs = kA * areaA_prim
    rhs = kB * areaB_prim
    lo_bound = np.exp(-eps_area)
    hi_bound = np.exp(+eps_area)
    mask = (lhs >= lo_bound * rhs) & (lhs <= hi_bound * rhs)
    iA, iB = np.where(mask)
    return np.column_stack((iA + 1, iB + 1))
```

2. Affine-invariant strain computation sketch (2×2 SPD case):

```python
X_A = invsqrt_spd(G_A)  # efficient 2x2 inverse sqrt
M = X_A @ G_B @ X_A
mu = eigvals_spd(M)
eps = 0.5 * np.log(mu)
if np.max(np.abs(eps)) > eps_principal_max:
    reject()
d_cell = 2.0 * np.linalg.norm(eps)
```

3. Deduplication: best-by-key-pair (pseudocode)

```text
best_by_pair = {}
for sc_A in scell_A_list:
  for sc_B in scell_B_list:
    key_pair = (sc_A.key_pg, sc_B.key_pg)
    if is_better((d_cell, match_score), best_by_pair.get(key_pair)):
       best_by_pair[key_pair] = candidate
```

### Practical notes

- Cache `invsqrt_spd(G)` per reduced supercell to avoid repeated SPD operations.
- Precompute `d_size` per (k_A,k_B) pair — it's constant for the pair.
- Symmetrize `M` explicitly (`M = 0.5*(M+M.T)`) before eigenvalue/log computations to avoid tiny numerical asymmetries.
- Use exact 2×2 analytical eigenvalue routines where possible for speed/stability.

### Appendix: Short worked example

See the canonical example in the legacy page: a compact Al(111)/Si(111) worked example has been migrated to this appendix to illustrate parameter choices and numerical outcomes. It includes the area-band selection, a rejected candidate example (excessive strain), and a successful 2×2 candidate with computed `d_cell`, `d_size`, and `match_score`.

### HNF enumeration notes (migrated from legacy supercell enumeration guide)

Practical enumeration guidance:

- Use the right/column HNF canonical representatives for 2×2 integer sublattices: \(H = [[h_{11}, h_{12}],[0,h_{22}]]\) with constraints \(h_{11}h_{22}=k\) and \(0\le h_{12}<h_{11}\).
- Enumerate divisors of the index \(k\) in sorted order and iterate \(h_{12}=0..h_{11}-1\) to obtain a deterministic, platform-stable enumeration.
- Sanity-check the enumerated count with \(count(k)=\sum_{d|k} d\) for small k during tests.

### Conditioning gate notes

Early rejection guidance:

- Compute the conditioning number for the raw supercell \(S=A_2 H\) and reject when `cond > cond_max` to avoid expensive reduction on numerically degenerate supercells.
- Treat non-finite or singular `np.linalg.cond` results as failures and skip those HNFs.
- The conditioning gate is a search-control heuristic: `cond_max` is a tunable parameter, not a canonical invariant. Prefer conservative defaults and expose it as a configuration parameter.

### Reduced-supercell transform notes

Notes on reduced outputs and total transform:

- After reduction, the implementation should expose the triple `(S_red, U_sup, R_sup)` where `U_sup` is the unimodular integer basis transform and `R_sup` is the embedding rotation.
- Compute `N_tot = H @ U_sup` as the integer map used for orbit canonicalization and downstream comparisons. Preserve `N_tot` as an integer matrix (determinant = index `k`).
- Do not use the raw HNF alone for symmetry keying once reduction has been applied; always form keys from `N_tot`.


## Inputs and outputs

### Inputs

| Parameter | Meaning |
| --- | --- |
| `slab_A`, `slab_B` | Slab-like objects with `atoms.cell.array` and `n_atoms` |
| `k_max` | Maximum HNF determinant/index considered on each side |
| `cond_max` | Maximum allowed raw-basis condition number |
| `w_match` | Weight between cell mismatch and size penalty |
| `eps_principal_max` | Maximum admissible absolute principal Hencky strain |
| `N_at_max` | Normalization scale for size penalty |
| `niggli_kwargs` | Reduction options forwarded to 2D reduction |
| `dedupe_by_key` | Whether to deduplicate by point-group canonical keys |
| `audit` | Optional enumeration-audit object |

### Outputs

The output is a sorted list of internal `Candidate` objects. Each candidate contains:

- reduced supercell information for side A and side B,
- affine-invariant strain diagnostics,
- Zur-McGill-style strain diagnostics,
- size penalty,
- combined match score,
- and the score weight used.

## Complexity

For index \(k\), the number of 2D HNF representatives is \(\sigma_1(k)=\sum_{d\mid k}d\). Before deduplication, each side enumerates

\[
\sum_{k=1}^{k_{\max}} \sigma_1(k)
\]

raw supercells. Pairwise comparison cost is proportional to the number of retained reduced supercells for valid index pairs:

\[
O\left(\sum_{(k_A,k_B)\in \mathcal{K}}
R_A(k_A)R_B(k_B)\right),
\]

where \(R_A(k_A)\) and \(R_B(k_B)\) are the retained reduced-supercell counts after conditioning and point-group deduplication, and \(\mathcal{K}\) is the area-band-valid index-pair set.

Each comparison uses constant-size 2D SPD operations, so the dominant cost is enumeration and pairwise candidate comparison, not matrix algebra.

## Correctness properties

The implemented algorithm is expected to satisfy the following properties within numerical tolerances.

1. **Finite bounded search.** For finite `k_max`, the enumerated HNF search space is finite.
2. **Index completeness.** For each index \(k\), canonical 2D HNF enumeration covers all index-\(k\) sublattices modulo right unimodular basis changes.
3. **Gauge invariance of metric comparison.** The affine-invariant comparison depends on Gram matrices and is invariant under common orthogonal rotations of the reduced bases.
4. **Principal-strain admissibility.** Every returned candidate satisfies the configured maximum absolute principal Hencky-strain bound.
5. **Symmetry-key uniqueness.** When key deduplication is enabled, at most one retained candidate is kept for each pair of side-specific point-group canonical keys.
6. **Deterministic ordering.** Given deterministic inputs and reduction behavior, returned candidates are sorted deterministically by score and cell mismatch.
7. **Separation from build/evaluate morphisms.** Matching returns candidate cells and strain diagnostics only; it does not construct atomic interfaces or evaluate energies.

## Numerical considerations

The matching algorithm relies on several numerical guards.

- Degenerate primitive in-plane bases are rejected by positive-area checks.
- Ill-conditioned raw supercells are rejected before reduction.
- SPD operations require positive relative-metric eigenvalues; non-SPD relative metrics are treated as invalid states.
- The area-band prefilter is widened slightly by a relative tolerance to avoid excluding boundary cases because of roundoff.
- Niggli/Gauss reduction has handedness and invariant guardrails in `calm.symmetry.reduction`.
- The finite search may miss physically useful large supercells if `k_max` or `N_at_max` is too restrictive; this is a search-truncation limitation, not a mathematical equivalence failure.

## Design decisions and limitations

### Deterministic reduction before comparison

CALM compares reduced bases rather than raw HNF bases so that the strain metric reflects intrinsic 2D cell geometry rather than arbitrary basis choices.

### Point-group key deduplication

Symmetry-key deduplication reduces redundant candidates while preserving embedding distinctions better than metric-only deduplication. Metric-only deduplication is not the default because two embeddings can have the same metric but different registry consequences.

### Principal Hencky-strain gate

The principal Hencky-strain gate is stronger than an area-only gate. The area gate is used only to avoid unnecessary pairwise comparisons.

### Finite search

The algorithm is complete only within the configured HNF index bounds, conditioning gate, and strain window. It does not claim global completeness over all possible interface supercells.

## Implementation mapping

| Specification element | Implementation owner |
| --- | --- |
| Public matching entry point | `calm.interface.matching.enumerate_matches` |
| HNF index-pair area prefilter | `calm.interface.matching.compute_valid_hnf_index_pairs` |
| Primitive in-plane basis extraction | `calm.interface.matching._prim_inplane_basis_2d` |
| HNF enumeration | `calm.math2d.enumerate_hnf_2d_by_index` |
| Reduced supercell construction | `calm.interface.types.ReducedSupercell2D` |
| 2D Niggli/Gauss reduction | `calm.symmetry.reduction.niggli_reduce_2d` |
| Point-group key canonicalization | `calm.keys.hnf.canonical_hnf_key_under_pg` |
| Affine-invariant strain diagnostics | `calm.interface.types.AffineInvariantStrain2D` |
| Zur-McGill-style diagnostics | `calm.interface.types.ZMStrain2D` |
| Enumeration audit records | `calm.interface.audit.PrototypeEnumerationAudit` |
| User-facing configuration | `calm.interface.config.PrototypeSearchConfig` |

## Verification mapping

Existing and future tests should cover:

- HNF enumeration count and determinant invariants,
- valid index-pair area-band inclusion and exclusion,
- rejection of degenerate primitive in-plane bases,
- point-group deduplication preserving one representative per canonical key,
- affine-invariant strain diagnostics for known rectangular and sheared examples,
- principal-strain gate behavior,
- deterministic candidate ordering,
- audit-count consistency,
- and optional-dependency fallback behavior for slab-like test doubles.

The current implementation already has architecture and public guardrail tests around the matching public API and representation-helper boundaries. A future verification-hardening milestone should add direct mathematical regression tests for the equations specified here.

## References

- Hermite normal form enumeration of finite-index sublattices.
- Smith and Hermite normal forms for integer lattices.
- 2D Gauss/Minkowski/Niggli-style lattice reduction.
- Affine-invariant metrics on symmetric positive-definite matrices.
- Hencky logarithmic strain theory.
- Zur, A. and McGill, T. C. Lattice match: an application to heteroepitaxy. *Journal of Applied Physics* 55, 378 (1984).
