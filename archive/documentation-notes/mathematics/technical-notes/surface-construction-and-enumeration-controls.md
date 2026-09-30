> **Archived implementation note:** This document preserves implementation and qualification detail from the documentation redesign. It is not part of the public user manual or the live engineering surface.

# Numerical controls for surface construction and enumeration

The main chapters define the crystallographic objects constructed by CALM. This
note collects the finite bounds, tolerances, and tie-breaking rules that users
may need when interpreting or reproducing a calculation.

Definition owners:

- [From Miller planes to oriented slabs](../../../../docs/scientific-background/surfaces-and-terminations.md)
  defines the surface kernel, stacking translation, and termination.
- [Lattices, bases, and canonical surface
  supercells](../../../../docs/scientific-background/surface-cells-and-supercells.md) defines HNF, SNF, and
  exact right quotients.
- [Symmetry reduction and canonical supercell
  enumeration](../../../../docs/scientific-background/surface-cells-and-supercells.md) defines the
  reduction hierarchy.

## Bounded construction gauges

Several construction steps choose one compact representative from an infinite
family. CALM searches a declared finite neighborhood and verifies the selected
result.

| Control | Default | Meaning |
| --- | ---: | --- |
| `primitive_max_denominator` | `12` | Largest denominator admitted while recovering the conventional-to-primitive Miller transformation |
| `primitive_reduction_max_iter` | `100` | Maximum integer-shear updates during primitive in-plane reduction |
| `stacking_search_radius` | `2` | Integer search radius around the continuous stacking-vector estimate |
| `c_tilt_search` | `6` | Integer search radius around the continuous c-axis tilt estimate |
| `c_tilt_singular_tolerance` | `1e-12` | Lower bound for rejecting a nearly singular in-plane solve |

The c-axis tilt diagnostic is

\[
\rho_{ab}
=
\frac{\left|\det[\mathbf a_{xy}\;\mathbf b_{xy}]\right|}
{\|\mathbf a_{xy}\|_2\,\|\mathbf b_{xy}\|_2}.
\]

CALM requires \(\rho_{ab}\) to exceed the declared tolerance. The ratio is
dimensionless and unchanged by independent positive rescaling of the two
in-plane vectors.

For the stacking and c-axis gauges, every integer point in the declared square
neighborhood is evaluated. Ties are resolved by total coefficient magnitude,
then individual magnitudes, then signed lexicographic order. A selected point on
the search boundary is not accepted as certified; increase the corresponding
radius and rerun.

These finite searches establish the optimum inside the declared neighborhood.
They do not prove a global shortest-vector result over an infinite lattice.

## Periodic precursors and finite-vacuum slabs

A crystallographic stacking sequence can leave a fractional in-plane component
in the third translation of a periodic precursor. The one-third shift of an fcc
(111) stacking sequence is a standard example.

For a finite slab with positive vacuum, CALM represents the boundary vector as

\[
\mathbf c=(0,0,L_c),
\]

while leaving the Cartesian atomic positions unchanged. This is a boundary
representation choice, not a physical strain.

A deliberate physical c-axis shear is different because it transforms the
atoms with the cell. That construction deformation remains part of later
interface and reference-state accounting. The definitions, frame changes,
composition order, and variable-cell extension are owned by [Frames, gauges,
and deformation accounting](../../../../docs/scientific-background/coherent-matching-strain-pareto.md).

## Canonical two-dimensional Gauss reduction

The reduced domain is

\[
0\leq2\,\mathbf s_1\!\cdot\!\mathbf s_2
\leq\|\mathbf s_1\|^2
\leq\|\mathbf s_2\|^2.
\]

CALM fixes the remaining discrete choices as follows:

- the first vector points along positive Cartesian x;
- the second lies in the upper half-plane;
- half-integer shear ties are resolved toward zero;
- equal-norm ties retain the current first vector within tolerance;
- the final inner product is nonnegative; and
- the final basis is right-handed.

Tolerance, determinant threshold, and iteration limit must be finite and
positive. A repeated state, exhausted budget, nonfinite intermediate, or failed
postcondition is an error rather than an unverified result.

## Surface-symmetry validation

Let the admitted in-plane operation set be

\[
\mathcal P\subset\mathrm{GL}(2,\mathbb Z).
\]

It must contain the identity, contain inverses, be closed under composition, and
contain only integer matrices with determinant \(\pm1\).

For surface metric \(\mathbf G_s=\mathbf S^{\mathsf T}\mathbf S\), every
operation must satisfy

\[
\frac{\|\mathbf P^{\mathsf T}\mathbf G_s\mathbf P-\mathbf G_s\|_F}
{\|\mathbf G_s\|_F}
\leq\varepsilon_{\mathrm{metric}}.
\]

The transformed positive surface normal must also remain aligned within the
normal tolerance.

`surface_symmetry_mode="discover"` invokes spglib and validates the returned
operations. `surface_symmetry_mode="identity_only"` deliberately uses the
one-element identity group. A discovery failure does not silently switch modes.

## Conditioning gate

CALM evaluates conditioning on the right-HNF embedded surface cell before
canonical reduction. For singular values \(\sigma_{\max}\) and
\(\sigma_{\min}\),

\[
\kappa_2(\mathbf S)=\frac{\sigma_{\max}}{\sigma_{\min}}.
\]

The default bound is `cond_max=1e6`, with the boundary included. Singular,
malformed, or nonfinite cells are rejected.

This is a numerical-stability gate for the selected representation. It is not a
statement that the rejected abstract lattice is crystallographically invalid.

## Optional numerical grouping

After exact symmetry reduction, users may group retained candidates by
quantized cell metrics and contact motifs for exploratory analysis. The metric
key bins the canonical reduced Gram tensor with a declared positive step. The
contact-motif key selects atoms near each outer surface and compares quantized
species-labelled fractional motifs modulo periodic translations.

These keys are approximate grouping tools:

- distinct structures can fall in the same numerical bin;
- grouping does not change candidate identity;
- grouping does not remove candidates from the search;
- grouping does not change Pareto membership or ranking; and
- grouping is not a crystallographic equivalence proof.

## Interpretation boundary

The controls in this note make finite numerical procedures explicit and
reproducible. They do not convert tolerance-dependent symmetry discovery,
conditioning gates, metric bins, or motif comparisons into exact physical
invariants.
