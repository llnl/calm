> **Archived implementation note:** This document preserves implementation and qualification detail from the documentation redesign. It is not part of the public user manual or the live engineering surface.

# Exact checks for canonical surface lattices

The main chapters explain the physical meaning of CALM's integer lattice objects. This note collects the exact algebraic checks used to verify those objects without becoming a second definition site.

The authoritative conventions are:

- [right Hermite normal form and fixed-index enumeration](../../../../docs/scientific-background/surface-cells-and-supercells.md);
- [Smith normal form and quotient translation classes](../../../../docs/scientific-background/surface-cells-and-supercells.md);
- [exact integer right quotients](../../../../docs/scientific-background/surface-cells-and-supercells.md);
- [the primitive surface kernel and stacking translation](../../../../docs/scientific-background/surfaces-and-terminations.md).

## Right-HNF certificate

Using the right-HNF convention defined in the main text, a full-rank integer
matrix \(\mathbf P\) and its canonical representative \(\mathbf H\) satisfy

\[
\mathbf H
=
\mathbf P\mathbf U_{\mathbb Z},
\qquad
|\det\mathbf U_{\mathbb Z}|=1.
\]

Exact multiplication verifies the returned relation. Because the unimodular
factor changes only the basis of the embedded sublattice,

\[
|\det\mathbf H|=|\det\mathbf P|
\]

is the same sublattice index.

The certificate is stronger than agreement of determinant or Smith factors: it
verifies the embedded sublattice in the fixed parent basis.

## Fixed-index completeness

For positive index \(k\), the definition owner parameterizes the right-HNF set
by

\[
h_{11}\mid k,
\qquad
h_{22}=\frac{k}{h_{11}},
\qquad
h_{12}=0,1,\ldots,h_{11}-1.
\]

For each positive divisor \(h_{11}\), there are \(h_{11}\) admitted values of
\(h_{12}\). Therefore

\[
N_{\mathrm{HNF}}(k)
=
\sum_{h_{11}\mid k}h_{11}
=
\sigma_1(k).
\]

Verifying that an enumerator returns exactly this count, with unique canonical
matrices and the requested determinant, certifies completeness at fixed index.
Summing over \(1\le k\le k_{\max}\) then certifies the finite HNF search domain.

## Smith invariant factors

For a full-rank \(2\times2\) integer matrix \(\mathbf P\), the invariant factors
from the [Smith normal form](../../../../docs/scientific-background/surface-cells-and-supercells.md)
can be checked directly:

\[
d_1=\gcd(\text{entries of }\mathbf P),
\qquad
d_2=\frac{|\det\mathbf P|}{d_1}.
\]

They satisfy \(d_1\mid d_2\), meaning that \(d_1\) divides \(d_2\), and

\[
d_1d_2=|\det\mathbf P|.
\]

These values certify the quotient structure. They do not certify the direction
of the embedded sublattice or of a refinement in the fixed parent basis.

## Exact right quotient

To test whether

\[
\mathbf P_2=\mathbf P_1\mathbf Q
\]

for an integer \(\mathbf Q\), CALM computes the quotient through integer
adjugate and divisibility relations, preserves the sign of
\(\det\mathbf P_1\), and verifies

\[
\mathbf P_1\mathbf Q=\mathbf P_2
\]

exactly. A floating inverse followed by rounding is not an exact certificate.

This quotient is the primitive object used by [simultaneous-refinement
pruning](../../../../docs/scientific-background/coherent-matching-strain-pareto.md). Smith
factors can screen quotient structure, but the exact pair relation compares
canonical right-HNF signatures across the admitted surface-symmetry orbits.

## Primitive surface-kernel certificate

For the primitive Miller covector \(\mathbf m\), CALM constructs integer vectors
\(\mathbf u\), \(\mathbf v\), and \(\mathbf w\) satisfying

\[
\mathbf m^{\mathsf T}\mathbf u
=
\mathbf m^{\mathsf T}\mathbf v
=0,
\]

\[
\mathbf u\times\mathbf v=\mathbf m,
\qquad
\mathbf m^{\mathsf T}\mathbf w=1.
\]

Then

\[
\det
\begin{pmatrix}
\mathbf w & \mathbf u & \mathbf v
\end{pmatrix}
=
\mathbf w^{\mathsf T}(\mathbf u\times\mathbf v)
=
1.
\]

The three columns form a right-handed integer basis of \(\mathbb Z^3\). Any integer vector
in the kernel of \(\mathbf m^{\mathsf T}\) has zero coefficient along
\(\mathbf w\) in this basis and is therefore an integer combination of
\(\mathbf u\) and \(\mathbf v\). This proves that the generated surface lattice
is saturated.

## Translation classes

For a full-rank supercell map \(\mathbf H\), the quotient

\[
\mathbb Z^2/\mathbf H\mathbb Z^2
\]

contains exactly \(|\det\mathbf H|\) classes. CALM can enumerate every class,
transform an integer contact record under each translation, and select the
numerically lexicographically minimal canonical signature.

The quotient is exact. A species-resolved motif signature built from Cartesian
heights and quantized positions is a separate tolerance-dependent comparison.
The distinction is discussed in [Bravais match, contact translation, and
atomistic prototype](../../../../docs/scientific-background/coherent-matching-strain-pareto.md).

## Where exact certificates stop

Exact integer relations do not make the complete workflow exact. Basis
reduction, point-group discovery from floating structures, Gram tensors, SPD
logarithms, metric bins, atomistic motif grouping, calculator energies, and
relaxation are numerical or tolerance dependent.

CALM records this boundary rather than promoting a deterministic numerical
grouping to an exact crystallographic invariant.

## Related pages

- [Crystal lattices, surface nets, and canonical
  supercells](../../../../docs/scientific-background/surface-cells-and-supercells.md) owns the definitions used
  here.
- [Symmetry reduction and canonical supercell
  enumeration](../../../../docs/scientific-background/surface-cells-and-supercells.md) applies the HNF
  certificates in the bounded search.
- [Canonical interface matches and the strain--size
  tradeoff](../../../../docs/scientific-background/coherent-matching-strain-pareto.md) applies the exact quotient at the
  pair level.
- [Algorithmic overview](../../../../docs/scientific-background/index.md) shows where the exact
  certificates sit among bounded and numerical stages.
