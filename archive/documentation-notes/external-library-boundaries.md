# ASE and spglib implementation boundaries

> Archived implementation note. This page is not part of the public MkDocs site or the live engineering surface.


CALM uses ASE for atomistic structure operations and geometry optimization, and
uses spglib for crystallographic symmetry recognition and cell
standardization. Those libraries perform substantial work, but their algorithms
are not CALM algorithms. CALM is responsible for choosing the inputs, recording
the settings, validating the returned objects, and deciding how the results fit
into the persistent scientific workflow.

This page records the conventions at those boundaries. The mathematical
background uses CALM's own notation and links here only when a library-specific
layout or setting matters.

## Division of responsibility

| Operation | Delegated operation | CALM's responsibility |
| --- | --- | --- |
| Atomic structure storage and motif expansion | ASE stores cells and positions and constructs atomistic supercells | define the intended lattice map, validate the cell and motif, and preserve transformation provenance |
| Geometry optimization | ASE supplies BFGS and the Fréchet cell filter | select allowed degrees of freedom, define the convergence contract, recompute the terminal residual, and persist calculator and software provenance |
| Symmetry recognition | spglib identifies symmetry operations and space-group data | validate the submitted crystal, pass explicit tolerances, validate returned operations, and record the library version |
| Conventional and primitive cells | spglib performs tolerance-dependent standardization | preserve the submitted structure as authoritative, validate returned cells and transformation data, and define CALM's structural-identity semantics |

The right-hand column is the part CALM records and validates in its persistent
workflow. The delegated algorithms remain defined by their respective
libraries.

The external software publications are [Larsen et al. for
ASE](https://doi.org/10.1088/1361-648X/aa680e) and
[Togo, Shinohara, and Tanaka for
spglib](https://doi.org/10.1080/27660400.2024.2384822).

## ASE cell and position layout

The mathematical background writes lattice vectors as columns of

\[
\mathbf A=
\begin{bmatrix}
\mathbf a & \mathbf b & \mathbf c
\end{bmatrix}.
\]

ASE stores the same vectors as rows in `Atoms.cell.array`. Denoting that array
by \(\mathbf C\),

\[
\boxed{\mathbf C=\mathbf A^{\mathsf T}}.
\]

ASE also stores Cartesian positions as an \(N\times3\) row array. If a scaled
position is the row \(\mathbf s=\mathbf f^{\mathsf T}\), then

\[
\mathbf p=\mathbf s\mathbf C=\mathbf x^{\mathsf T}.
\]

The transpose changes only the array convention. It does not rotate or deform the crystal.

### Supercells

CALM defines a column-basis supercell by

\[
\mathbf A'=\mathbf A\mathbf P,
\]

where \(\mathbf P\) is an integer matrix. Transposing the relation gives the
row-oriented form expected at the ASE boundary:

\[
\boxed{\mathbf C'=\mathbf P^{\mathsf T}\mathbf C}.
\]

ASE performs the motif expansion associated with this cell transformation.
CALM checks that the returned cell, atom count, handedness, and transformation
provenance agree with the intended construction.

### Cartesian maps

For a Cartesian column vector,

\[
\mathbf x'=\mathbf M\mathbf x.
\]

The same map applied to an \(N\times3\) row array of positions is

\[
\boxed{\mathbf X'=\mathbf X\mathbf M^{\mathsf T}}.
\]

The ASE row cell follows the same rule:

\[
\mathbf C'=\mathbf C\mathbf M^{\mathsf T}.
\]

When CALM has already transformed positions explicitly, changing the cell must
not rescale those positions a second time.

### Periodicity and wrapping

ASE stores periodic-boundary flags separately from the cell. CALM validates the
three flags at boundaries where full three-dimensional periodicity is required.
Fractional coordinates are wrapped before canonicalization so values
numerically equal to the upper boundary are represented at zero rather than at
one.

## ASE optimization

ASE supplies the optimizer used by the authoritative relaxation backend. CALM
does not claim BFGS or the Fréchet cell filter as package mathematics.

CALM does define the optimization protocol around them:

- fixed-cell relaxation varies atomic positions while preserving the cell;
- interface-cell relaxation permits the in-plane strain components while
  holding the interface-normal direction fixed;
- calculator identity, optimizer controls, software versions, and the final
  structure are persisted;
- the terminal generalized residual is recomputed and must satisfy the declared
  threshold before the result is accepted.

For ASE's six-component cell mask, the ordering is

```text
(xx, yy, zz, yz, xz, xy)
```

and CALM's interface-cell mask is

```text
(True, True, False, False, False, True)
```

so \(xx\), \(yy\), and \(xy\) may vary while the normal and out-of-plane shear
components remain fixed.

The optimizer establishes convergence under that recorded protocol. It does not
prove global minimality or uniqueness.

## The spglib cell tuple

The Python spglib interface receives a tuple containing

```text
(lattice_rows, scaled_position_rows, type_numbers)
```

with an optional fourth magnetic-moment array for supported operations. CALM
constructs this tuple from a validated, fully periodic crystal, wraps the
fractional positions, and checks that type numbers and array shapes are
consistent.

spglib then supplies the tolerance-dependent symmetry dataset, symmetry
operations, and standardized conventional and primitive cells.
CALM does not reimplement the search by which spglib finds them.

## Surface-symmetry discovery

For surface-supercell identities, CALM asks spglib for fractional point-group
rotations and retains the subgroup that preserves the selected Cartesian
surface normal and the fractional in-plane subspace. The resulting two-by-two
integer operations are not trusted merely because they came from the backend.
CALM independently verifies exact integrality, determinant \(\pm1\), explicit
identity, closure, inverses, and preservation of the selected surface metric.

The default controls are:

- `surface_symmetry_mode="discover"`;
- `surface_symprec=1e-5` for spglib discovery;
- `surface_angle_tolerance=1e-8` for the dimensionless normal mismatch
  \(1-\widehat{\mathbf z}'\!\cdot\widehat{\mathbf z}\), not an angle in
  degrees or radians; and
- `surface_metric_tolerance=1e-5` for the scale-free Frobenius residual.

`surface_symmetry_mode="identity_only"` is a separate explicit policy. It skips
spglib and uses only the identity operation. A discovery or validation failure
never selects this policy automatically. Successful results record the selected mode, tolerances, operation count, residual, and spglib version. A discovery or validation failure raises rather than silently changing the requested mode.

## Standardization settings and provenance

CALM passes and records the settings that materially affect the result:

- `symprec`, the positive Cartesian distance tolerance;
- `angle_tolerance=-1.0`, which selects spglib's internal angle-tolerance
  handling;
- `no_idealize`, which controls whether standardization may idealize lengths,
  angles, and atomic positions; and
- the installed spglib version.

Changing a tolerance or library version can change the recognized symmetry and
the selected standardized representation. A standardized cell is therefore a
parameterized result, not a tolerance-free identity certificate.

CALM treats the submitted structure as the authoritative representation. The
conventional and primitive cells returned by spglib are supplemental
representations with recorded provenance. In column-basis notation, the
reported change of basis is checked as

\[
\mathbf A_{\mathrm{conv}}
=\mathbf R_{\mathrm{applied}}
 \mathbf A_{\mathrm{input}}\mathbf P^{-1},
\]

where \(\mathbf P\) is spglib's transformation matrix and
\(\mathbf R_{\mathrm{applied}}=\mathbf I\) when `no_idealize=True`; otherwise
it is the reported proper Cartesian rotation. CALM then records and checks the
conventional-to-primitive relation

\[
\mathbf A_{\mathrm{prim}}
=\mathbf A_{\mathrm{conv}}\mathbf P_{\mathrm c}.
\]

Both relations carry maximum absolute and scale-normalized residuals. CALM also
validates finite cells and positions, composition and atom-count relations,
volume multiplicity, and the reported transformation data. It does not
independently prove that spglib selected the unique or universally preferred
crystallographic setting.

## Related topics

- [Surface cells and supercells](../../docs/scientific-background/surface-cells-and-supercells.md)
- [Surface orientation and terminations](../../docs/scientific-background/surfaces-and-terminations.md)
- [Relaxation and interfacial energetics](../../docs/scientific-background/relaxation-and-interfacial-energetics.md)
- [Units and conventions](../../docs/reference/units-and-conventions.md)

## User-visible failures

CALM does not retry an external operation by changing its scientific meaning. A missing optional dependency, invalid provider configuration, calculator construction failure, calculator execution failure, geometry failure, and validation failure remain distinct so the corrective action is clear.
