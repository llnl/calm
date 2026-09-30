# Units and conventions

This page consolidates the most important conventions used by CALM to avoid
confusion for new users. It is intentionally concise and user-facing.

## Cell and lattice conventions

- ASE uses a row-major cell representation: the Atoms.cell is an array of shape
  (3, 3) whose rows are the lattice vectors in Cartesian coordinates. When
  setting cells programmatically, ASE expects `atoms.set_cell(cell, scale_atoms=...)`
  where `cell` is a 3x3 array of row vectors.
- Mathematical documentation in CALM sometimes uses column-vector math (matrix
  multiplications shown with column vectors). When translating formulas to ASE
  calls, take the matrix transpose if necessary. For example, if a docstring
  shows a column-matrix `A_column` then an ASE cell passed as rows is
  `A_column.T`.

## Surface and slab conventions

- Conventional vs primitive cells: a conventional cell is a standard crystallographic
  representation (often larger). The primitive cell is the smallest repeating unit.
- Miller indices (h,k,l) follow the usual crystallographic convention. CALM's
  slab-builder APIs accept Miller index tuples in the conventional sense.
- Primitive surface cell: this is the 2D smallest repeating net for a given surface
  orientation; it is the basis used for registry searches and in-plane lattice
  matching.
- Layers and vacuum: Slab constructions typically specify a number of atomic
  layers perpendicular to the surface and a vacuum spacing (Å) in the c-direction.
- Residual third-vector tilt/shear: due to crystallographic conventions, the
  constructed slab may include a small residual out-of-plane `c`-vector component
  (tilt). CALM tracks tilt separately from in-plane strain; users should not
  conflate the two.

## Strain conventions

- In-plane deformation gradients are commonly denoted `F_A` and `F_B` (3x3 with
  slab-normal treated as special); for in-plane-only operations CALM works with
  2x2 tangent-plane deformation gradients (affine maps on the surface net).
- Hencky (logarithmic) strain is used for geodesic strain partitioning on the
  SPD(2) manifold. Scalar strain norms reported in CALM are derived from the
  Hencky strain tensor and are useful for ranking, but they are not the same as
  residual tilt magnitude.

## Interface-energy convention

By default CALM uses an interfacial energy convention of the form

\[
\gamma(F_A,F_B)=\frac{E_{A|B}(F_A,F_B)-N_A\mu_A(F_A)-N_B\mu_B(F_B)}{2A},
\]

where

- \(E_{A|B}(F_A,F_B)\) is the total energy of the interface cell constructed
  with deformation gradients \(F_A, F_B\).
- \(N_A, N_B\) are the counts of formula units of materials A and B in the
  interface cell (as reported in the interface metadata).
- \(A\) is the single-interface area (the denominator uses \(2A\) for two
  equivalent interfaces in a periodic slab stack). If the two interfaces are
  inequivalent, interpretation is an average — consult the follow-up energy
  utilities for more advanced conventions.

Units:

- Energies are commonly stored in eV and areas in Å². The default reported unit
  for gamma in the code is eV/Å²; convert to J/m² with:

\[
1\ \mathrm{eV/\AA^2} = 16.02176634\ \mathrm{J/m^2}.
\]

## Current strained-bulk reference convention

The current default behavior for strained-bulk references is:

```
strained_bulk_reference_mode = "unrelaxed_scaled_positions"
bulk_reference_relaxed = False
gamma_reference_convention = "strained_unrelaxed_bulk_subtraction"
```

In plain terms this means:

- The strained bulk reference is constructed by applying the in-plane
  deformation gradient to the conventional bulk cell vectors (affine scaling)
  and scaling atomic positions accordingly.
- No ionic relaxations or out-of-plane relaxations are performed on the strained
  bulk reference by default (it is an unrelaxed, affine-scaled reference).

Pseudocode illustration:

```
# convert column-based math to ASE row-based cell when needed
F_conv = Q @ F_slab @ Q.T
A_strained_column = F_conv @ A_bulk_column
ase_cell_rows = A_strained_column.T
strained_bulk.set_cell(ase_cell_rows, scale_atoms=True)
```

Relaxed strained-bulk references (where ionic positions and/or out-of-plane
degrees of freedom are relaxed) are an advanced workflow and are not the default.

For scalar arithmetic when `E_interface`, `N_A`, `N_B`, `mu_A`, `mu_B`, and the
area are already known, use
`calm.compute_interface_energy_from_scalars(...)`. That helper performs only the
gamma arithmetic and records the same default reference-convention metadata, but
it does not build or relax strained bulk references.

To inspect the affine, unrelaxed strained-bulk reference energies separately
from the full interface-energy workflow, use the helper
`calm.compute_strained_bulk_reference_energies(prototype, calculator)`. This
pedagogical helper follows the same default convention:

```
strained_bulk_reference_mode = "unrelaxed_scaled_positions"
bulk_reference_relaxed = False
gamma_reference_convention = "strained_unrelaxed_bulk_subtraction"
```

It returns a :class:`calm.interface.results.StrainedBulkReferenceResult` with
fields including `mu_A_eV_per_fu`, `mu_B_eV_per_fu`, and provenance. Use this
helper when you want to preview or validate strained-bulk references without
running the full `run_interface_energy(...)` workflow.

## SQLite and payload conventions

- Workspaces persist records in an SQLite database (typically `calm.sqlite` in
  the workspace root) and store artifacts under the workspace `out/` directory.
- Many structured metadata fields are stored as JSON payloads in dedicated
  columns; payload JSON keys and naming conventions are documented alongside the
  corresponding reference pages (e.g., oriented-slab transforms, interface
  metadata).
- Tilt metadata is stored separately from scalar strain metrics: don't assume
  that a scalar strain value includes residual tilt.

## Where to read next

- Tutorials: `docs/tutorials/01_workspace_basics.md` and `docs/tutorials/02_slab_generation.md`.
- API contract: `public_api.md` (repository root) and `docs/reference/public_api.md` (generated).
Example scripts are listed in the Example Scripts guide: `docs/guides/examples/index.md`.
  hand-checkable walkthrough of the gamma convention and ranking arithmetic.
