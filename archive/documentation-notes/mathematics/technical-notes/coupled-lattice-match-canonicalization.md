> **Archived implementation note:** This document preserves implementation and qualification detail from the documentation redesign. It is not part of the public user manual or the live engineering surface.

# Coupled lattice-match canonicalization and primitive pair identity

The main matching chapters explain surface enumeration, coherent strain, and
candidate selection. This note records the exact integer relation used by the
authoritative coupled matcher. It is the definition owner for primitive pair
identity; it is not a second definition of the strain metric.

## The match is one coupled integer object

Let \(\mathbf B_A\) and \(\mathbf B_B\) be the primitive in-plane bases of the
two selected surfaces. One surface-orbit member contributes integer maps
\(\mathbf N_A\) and \(\mathbf N_B\). A basis correspondence
\(\mathbf U_B\in\mathrm{GL}(2,\mathbb Z)\) places the B-side cell in the same
abstract interface coordinates as the A-side cell. CALM then forms

\[
\mathbf C_{\mathrm{src}}
=
\begin{bmatrix}
\mathbf N_A\\
\mathbf N_B\mathbf U_B
\end{bmatrix}
\in\mathbb Z^{4\times2}.
\]

The two columns of this stacked matrix name one common abstract interface-cell
basis. They must therefore be changed together. Reducing the two \(2\times2\)
blocks independently would permit different right basis changes on A and B and
could destroy the correspondence that made the cells commensurate.

## Surface orbits retain their members

One-sided point-group canonicalization is still useful, but only as a
comparison-space organization. For every HNF index CALM stores a deterministic
orbit representative **and all admitted orbit members with their exact
witnesses**. The representative may be used by a safe shape prefilter. A
prefilter limit failure is inconclusive and causes exact member expansion; it
is never a scientific rejection.

For each retained A/B member pair, CALM enumerates every integer basis
correspondence admitted by the strain bound. The finite entry bounds are derived
from the two positive-definite surface metrics. The default high-level policy
uses no caller-imposed entry cap, so the proven finite correspondence domain is
enumerated completely. An explicit positive cap is an advanced fail-closed
control: exceeding it raises rather than truncating the search.

`correspondence_orientation="proper"` admits determinant \(+1\)
correspondences. The optional `"all"` policy also admits determinant \(-1\).
This is separate from the point-group policy used for final pair identity.

## Local primitiveization

A source correspondence can be a repeated presentation of a smaller relation.
For a rank-two \(4\times2\) matrix, define the second determinantal divisor

\[
\delta_2(\mathbf C)
=
\gcd\{\text{all six }2\times2\text{ row minors of }\mathbf C\}.
\]

CALM computes the exact factorization

\[
\mathbf C_{\mathrm{src}}
=
\mathbf C_{\mathrm{prim}}\mathbf R,
\qquad
\mathbf R\in\mathbb Z^{2\times2},
\qquad
|\det\mathbf R|=\delta_2(\mathbf C_{\mathrm{src}}),
\]

with

\[
\delta_2(\mathbf C_{\mathrm{prim}})=1.
\]

The primitive matrix is the saturation of the paired column lattice. The right
factor records the exact source repetition and reconstructs the source without
rounding. Directional repeats such as \(\operatorname{diag}(2,1)\) and
isotropic repeats such as \(2\mathbf I\) are handled by the same local
factorization.

Primitiveization occurs for every source correspondence before the exact atom
cap, final strain diagnostics, score, or scientific aggregation. Consequently,
a source found at a larger HNF index can collapse immediately to an earlier
primitive relation instead of requiring a later pairwise refinement-pruning
pass.

## Exact primitive pair equivalence

After primitiveization, CALM identifies matrices under

\[
\mathbf C'
=
\operatorname{diag}(\mathbf P_A,\mathbf P_B)\,
\mathbf C\,\mathbf U,
\]

where

- \(\mathbf P_A\) and \(\mathbf P_B\) are independently admitted integer
  operations of the two parent surface point groups; and
- the **same** \(\mathbf U\in\mathrm{GL}(2,\mathbb Z)\) acts on both blocks from
  the right.

The common right action changes the abstract interface-cell basis without
changing the A/B correspondence. Independent right actions are not an allowed
pair equivalence.

The `pair_symmetry_policy` is explicit:

- `proper` uses only determinant \(+1\) parent-surface operations;
- `full` also uses admitted determinant \(-1\) operations.

Material exchange is not inferred from equal composition or equal metrics.
A/B exchange participates in identity only when
`identify_material_exchange=True`.

CALM chooses a deterministic lexicographic representative of this declared
orbit and stores its exact integer tuple as the primitive pair key. Equality of
independent one-sided keys is insufficient, and Smith invariant factors alone
are insufficient: both discard information about the coupled embedding and
basis correspondence.

## Identity gauge and build gauge are different

The lexicographically canonical integer matrix is an identity certificate, not
necessarily the most convenient physical basis for constructing atoms. CALM
therefore derives a separate build gauge by reducing the affine-invariant
midpoint of the two primitive physical metrics. One orientation-preserving
common right transform is then applied to both primitive blocks.

This separation preserves exact identity while giving the builder a symmetric,
deterministic, and physically well-conditioned common coordinate gauge. The
stored witnesses reconstruct both the primitive relation and the source
presentation.

## Recompute, then aggregate by the exact key

All authoritative size and strain quantities are recomputed from the primitive
A/B blocks. The primitive atom count, principal strains, affine-invariant cell
distance, and weighted score do not inherit stale values from a repeated source
cell.

Candidates are aggregated online by the exact primitive pair key. Additional
sources update bounded provenance such as discovery index pairs and repeat
indices; they do not create new scientific candidates. Rounded strain values,
area, score, independent surface keys, and numerical grouping keys never replace
the exact pair key.

Pareto membership is calculated only after the complete admitted primitive
class population has been formed, and before `max_results` truncation.

## Completeness and audit interpretation

Within the declared HNF index bound, the authoritative search is complete over

1. admitted one-sided orbit members;
2. the proven finite basis-correspondence domains;
3. local exact primitiveizations; and
4. the declared pair-identity symmetry action.

The production audit therefore need not be monotone. Surface point-group
canonicalization reduces comparison work, then member and correspondence
expansion deliberately increases the number of states, and exact pair-key
aggregation reduces those states to primitive scientific classes. Those are
three different operations, not successive approximate deduplication passes.

## Related definition owners

- [Symmetry reduction and canonical supercell
  enumeration](../../../../docs/scientific-background/surface-cells-and-supercells.md) owns one-sided HNF
  enumeration, orbit bundles, and optional numerical grouping.
- [Coherent misfit and strain-based
  matching](../../../../docs/scientific-background/coherent-matching-strain-pareto.md) owns the strain diagnostics and
  feasibility limits.
- [Canonical interface matches and the strain--size
  tradeoff](../../../../docs/scientific-background/coherent-matching-strain-pareto.md) owns the reader-facing pair and
  selection narrative.
- [Search, construction, and refinement
  API](../../../../docs/user-guide/interface-searches-and-candidates.md) owns operational
  result and Pareto semantics.
