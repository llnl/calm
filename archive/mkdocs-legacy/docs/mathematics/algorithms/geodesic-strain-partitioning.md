# Geodesic strain partitioning

## Purpose

Geodesic strain partitioning chooses a common in-plane target metric for two lattice-matched slabs. The construction lets CALM distribute in-plane mismatch between the two sides of an interface rather than assigning the full deformation to one slab. The implemented model is an affine-invariant interpolation on the symmetric positive-definite matrix manifold SPD(2), followed by deterministic construction of deformation gradients that map each slab's in-plane basis to the selected target basis.

This page is normative for the implemented metric-level convention. It distinguishes the mathematical strain-partition construction from later scientific operations such as interface construction, registry alignment, and energy evaluation.

## Ontology mapping

| Role | CALM object or representation |
| --- | --- |
| Input scientific objects | Two slabs or matched in-plane slab cells |
| Input representations | Column-basis lattice matrices `S_A_3D`, `S_B_3D` or 2x2 in-plane bases `S_A`, `S_B` |
| Mathematical space | SPD(2) metric space of in-plane Gram tensors |
| Representation morphism | Extract in-plane Cartesian bases; form Gram tensors; lift a target Gram tensor to a deterministic basis |
| Scientific morphism using this helper | Build interface / evaluate strain-partition candidates |
| Output representation | A target in-plane basis and deformation gradients for slabs A and B |

The strain-partition helper does not, by itself, create a new ontology object. It supplies the target representation used by later interface-construction and evaluation steps.

## Mathematical problem

Let the in-plane column bases of two matched slabs be

```text
S_A, S_B in R^{2 x 2}, det(S_A) != 0, det(S_B) != 0.
```

Their Gram tensors are

```text
G_A = S_A^T S_A,
G_B = S_B^T S_B.
```

Assuming both bases are nondegenerate, `G_A` and `G_B` lie in SPD(2). The problem is to choose a target metric `G(alpha)` along a geometrically meaningful path from `G_A` to `G_B`, then compute deformation gradients

```text
F_A S_A = X(alpha),
F_B S_B = X(alpha),
```

where `X(alpha)` is a deterministic basis whose Gram tensor is `G(alpha)`:

```text
X(alpha)^T X(alpha) = G(alpha).
```

## Affine-invariant geodesic

CALM uses the affine-invariant geodesic on SPD(2). With `alpha in [0, 1]`, the target metric is

```text
G(alpha) = G_A^{1/2}
           (G_A^{-1/2} G_B G_A^{-1/2})^alpha
           G_A^{1/2}.
```

The endpoint convention is therefore:

```text
alpha = 0 -> G(alpha) = G_A
alpha = 1 -> G(alpha) = G_B
```

In applied-strain language:

```text
alpha = 0 -> slab A is unstrained; slab B is strained to A
alpha = 1 -> slab B is unstrained; slab A is strained to B
alpha = 0.5 -> affine-invariant midpoint metric
```

This is the convention implemented by `calm.interface.strain.compute_strain_2d`, `calm.interface.strain_partition.strain_partition_inplane`, and `calm.interface.strain_partition.scan_geodesic_strain_partitions`.

## Traditional approach (limitations)

Legacy or naive approaches commonly perform arithmetic interpolation of column-basis lattice matrices:

```text
X_arith(alpha) = (1-alpha) * S_A + alpha * S_B
```

This interpolation is gauge-dependent and not affine-invariant: rotating or shearing the input bases changes the interpolated cell. Such arithmetic schemes therefore lack a consistent physical interpretation for strain distribution and are sensitive to the chosen coordinate representation. The affine-invariant geodesic on SPD(2) avoids these issues by working with Gram (metric) tensors.

## Implementation notes (concise)

The canonical implementation is intentionally dependency-light and uses small, numerically robust SPD helpers. Below are compact, appendix-style snippets that summarize the helper interfaces and the core computation pattern used by CALM. These are intended as immediate implementation mapping and examples — full implementations live in `calm.math2d` and `calm.interface` modules.

```python
def geodesic_spd(G_A, G_B, t):
    """Geodesic on SPD(2) at parameter t ∈ [0,1]."""
    G_A_inv_sqrt = invsqrt_spd(G_A)
    M = sym2(G_A_inv_sqrt @ G_B @ G_A_inv_sqrt)
    M_t = power_spd(M, t)             # eigenvalue power on SPD matrix
    G_A_sqrt = sqrt_spd(G_A)
    return sym2(G_A_sqrt @ M_t @ G_A_sqrt)

def strain_partition_inplane(S_A, S_B, *, alpha):
    """Partition in-plane mismatch via geodesic interpolation.

    Returns a compact `StrainPartitionInplane` with fields:
    alpha, G_target, X (chol upper), F_A, F_B.
    """
    G_A = gram_2d(S_A)
    G_B = gram_2d(S_B)
    G_target = geodesic_spd(G_A, G_B, alpha)
    X = chol_upper(G_target)   # deterministic upper-triangular lift
    F_A = X @ inv2(S_A)
    F_B = X @ inv2(S_B)
    return StrainPartitionInplane(alpha=alpha, G_target=G_target, X=X, F_A=F_A, F_B=F_B)
```

Notes:
- Use `np.linalg.eigh` on small 2×2 SPD matrices for stable eigen-decompositions.
- Prefer `chol_upper` (upper-triangular Cholesky with positive diagonal) as the deterministic gauge.
- Regularize near-singular Gram matrices by projecting small negative eigenvalues to a tiny positive floor.
- For reproducibility, ensure deterministic ordering of alpha grids and tie-breaking (first-occurrence wins).

## Target-basis lift

A metric tensor does not uniquely define a basis: if `Q` is orthogonal, then `(QX)^T(QX) = X^T X`. CALM fixes a deterministic representation gauge by using an upper-triangular Cholesky lift for the 2D helper:

```text
X(alpha) = chol_upper(G(alpha)),
X(alpha)^T X(alpha) = G(alpha).
```

The `compute_strain_2d` path similarly factors the target metric using CALM's dependency-light SPD routines. This lift is a representation choice, not a change in the scientific target metric.

## Deformation gradients

Given a selected target basis `X`, the in-plane deformation gradients satisfy

```text
F_A = X S_A^{-1},
F_B = X S_B^{-1}.
```

The implementation stores 3D embedded transforms for the public `StrainState` result. The z direction is left as the identity in the embedded 3x3 matrices because this helper models only the in-plane metric partition.

## Hencky strain diagnostics

For each deformation gradient, CALM computes a polar decomposition

```text
F = R U,
```

where `R` is rotational and `U` is the symmetric stretch. The logarithmic Hencky strain is

```text
E = log(U).
```

The reported scalar RMS diagnostic is

```text
E_rms = sqrt(1/2) ||E||_F,
```

which is equivalent to the root-mean-square of the two principal logarithmic strains in the in-plane block.

## Scan algorithm

`scan_geodesic_strain_partitions` evaluates a finite set of `alpha` values and selects the best candidate according to a user-supplied scoring function.

Inputs:

- two 3D column-basis surface-cell matrices;
- a sequence of alpha values, or the default monotone grid;
- a score function mapping `StrainState` to a scalar;
- a minimization/maximization flag;
- numerical tolerance parameters.

Workflow:

1. Normalize alpha values, preserving order and removing duplicates.
2. For each alpha, call `compute_strain_2d` to construct the target metric and strain state.
3. Evaluate the score function.
4. Select the minimum score when `minimize=True`, otherwise the maximum score.
5. Break ties by first occurrence in the alpha list because the scan updates only on strict improvement.
6. Optionally retain a compact `(alpha, score)` trace.

The scan is a finite grid search. It is deterministic for deterministic score functions and deterministic input alpha ordering. It does not prove global optimality over the continuum unless the chosen grid and objective are separately analyzed.

## Correctness properties

Under nondegenerate in-plane bases and successful SPD operations, the implementation should satisfy:

1. **Endpoint property**: `alpha=0` gives the A metric and `alpha=1` gives the B metric.
2. **Common-target property**: `F_A S_A` and `F_B S_B` agree up to the configured common-lattice tolerance.
3. **SPD path property**: all target metrics along the path remain positive definite.
4. **Deterministic gauge property**: repeated evaluations with the same inputs return the same target-basis representation.
5. **In-plane-only property**: embedded 3D transforms modify the in-plane block and leave the out-of-plane identity component unchanged.
6. **Tie stability**: scan ties preserve the earliest alpha in the normalized sequence.

## Numerical considerations

The construction relies on SPD matrix square roots, inverse square roots, powers, polar factors, and logarithms. The main numerical risks are nearly singular in-plane cells, poorly conditioned relative metrics, and small negative eigenvalues introduced by floating-point roundoff. CALM mitigates these risks with symmetric projection, small SPD regularization parameters, and explicit shape/determinant checks.

The alpha scan itself inherits the numerical behavior of `compute_strain_2d`; it does not add an independent optimization tolerance beyond score comparison.

## Limitations

- The model partitions only in-plane metric mismatch.
- The finite alpha scan is not a continuous optimizer.
- The selected best alpha depends on the supplied score function.
- The target-basis lift is a deterministic representation gauge, not a unique scientific basis.
- Endpoint interpretations must be stated in terms of the target metric and applied deformation; reversing the applied-strain description changes the physical interpretation.

## Implementation mapping

| Mathematical object or operation | Implementation |
| --- | --- |
| In-plane basis extraction | `calm.interface.strain._extract_inplane_cols` |
| SPD geodesic strain state | `calm.interface.strain.compute_strain_2d` |
| 2D in-plane geodesic helper | `calm.interface.strain_partition.strain_partition_inplane` |
| Default alpha grid | `calm.interface.strain_partition.default_alpha_grid` |
| Finite alpha scan | `calm.interface.strain_partition.scan_geodesic_strain_partitions` |
| SPD kernels | `calm.math2d`, `calm.math2d.spd2x2` |
| Public result type | `calm.interface.types.StrainState` |

## Verification mapping

Current and recommended verification targets include:

- endpoint convention tests for `alpha=0` and `alpha=1`;
- common-target equality of `F_A S_A` and `F_B S_B`;
- monotone/default alpha-grid behavior;
- duplicate alpha normalization;
- tie stability in scans;
- error behavior for invalid alpha values and degenerate cells;
- consistency between the 2D helper and the public 3D `StrainState` path.

Relevant existing or expected tests include:

- `tests/public/test_strain_partition_alpha_convention.py`
- `tests/test_strain_metrics.py`
- strain-partition scan tests where present in the repository

## References

The construction is based on standard affine-invariant geometry of the SPD matrix manifold and the polar/Hencky strain decomposition commonly used in finite strain theory. CALM's implementation should be interpreted as a 2D in-plane specialization of these constructions for interface-cell matching and building.
