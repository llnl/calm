> **Archived implementation note:** This document preserves implementation and qualification detail from the documentation redesign. It is not part of the public user manual or the live engineering surface.

# Numerical controls for coherent matching and interface assembly

The main matching and construction chapters define the physical quantities.
This note collects the finite filters, conditioning checks, and assembly choices that users may need when interpreting a result. It is not a second definition site.

## Matching prefilters and conditioning

The principal-strain limit implies the necessary area band

\[
\left|\log
\frac{k_A\mathcal A_{A,0}}
{k_B\mathcal A_{B,0}}
\right|
\leq2\varepsilon_{\max}.
\]

CALM applies this inexpensive filter before evaluating the complete relative
metric. Passing it does not establish shape compatibility.

Both in-plane cells must be finite, nonsingular, right-handed, and expressed in
the same oriented Cartesian plane. A condition-number gate rejects nearly
singular cells before inverse square roots and matrix logarithms amplify
floating-point error.

## Cell-size and angle diagnostics

CALM can report relative edge-length and included-angle differences for human
inspection. These values are diagnostics only. Hard admissibility, ranking,
Pareto membership, and exact pair identity use the affine-invariant matching
quantities described in [Coherent misfit and strain-based
matching](../../../../docs/scientific-background/coherent-matching-strain-pareto.md).

## Target-basis gauge and verification

The target metric \(\mathbf G_\alpha\) is lifted to an upper-triangular basis
with positive diagonal,

\[
\mathbf X_\alpha=
\begin{pmatrix}
x_{11}&x_{12}\\
0&x_{22}
\end{pmatrix},
\qquad x_{11}>0,\;x_{22}>0.
\]

CALM verifies the reconstruction residual

\[
\frac{\|\mathbf X_\alpha^{\mathsf T}\mathbf X_\alpha-
\mathbf G_\alpha\|_F}
{\|\mathbf G_\alpha\|_F}
\]

and confirms that both deformed surface cells reach the same target:

\[
\mathbf F_A\mathbf S_A
=
\mathbf F_B\mathbf S_B
=
\mathbf X_\alpha.
\]

A failed reconstruction or common-target check raises instead of returning an
unverified deformation.

## Assembly and wrapping

Integer replication, Cartesian orientation, and physical coherent deformation
are applied in their declared order. The common cell must remain finite,
nonsingular, right-handed, and consistent with the fixed surface normal.

The interface gap and boundary vacuum are separate controls. CALM wraps only the
periodic in-plane coordinates during assembly. Registry coordinates are
represented in the periodic interval \([0,1)^2\).

## Related definitions

- [Coherent misfit and strain-based matching](../../../../docs/scientific-background/coherent-matching-strain-pareto.md)
  defines the strain measures.
- [Strain partitioning and atomistic interface
  assembly](../../../../docs/scientific-background/strain-partitioning-and-registry.md) defines the
  common metric and construction sequence.
- [Canonical interface matches and the strain-size
  tradeoff](../../../../docs/scientific-background/coherent-matching-strain-pareto.md) defines Pareto selection.
- [Interfacial registry and rigid-body
  refinement](../../../../docs/scientific-background/strain-partitioning-and-registry.md) defines the periodic translation space.
