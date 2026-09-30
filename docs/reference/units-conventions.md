# Units and conventions

<p class="calm-lede">
Use one consistent set of units, coordinate conventions, strain definitions, and normalization rules when reading CALM settings, tables, figures, and exported results.
</p>

## Purpose

This page is the canonical lookup for conventions used throughout the user manual. A field whose name contains a unit, such as `energy_eV` or `area_A2`, should be interpreted literally. When an object documents a more specific convention, that object takes precedence.

## Canonical import or convention

CALM uses the following primary units unless a public field states otherwise.

| Quantity | Unit or convention |
| --- | --- |
| Cartesian length, slab thickness, gap, vacuum, and cell-vector magnitude | Å |
| Area | Å² |
| Volume | Å³ |
| Total energy | eV |
| Energy per formula unit | eV per formula unit |
| Force and force-convergence threshold | eV/Å |
| Energy per area | eV/Å², with J/m² supplied as a secondary representation where supported |
| Strain | Dimensionless natural logarithmic strain |
| Strain-partition coordinate | Dimensionless `alpha` in `[0, 1]` |
| Registry translation | Fractional coordinates of the final common in-plane cell, reduced periodically to `[0, 1)` |
| Fractional atomic position | Fraction of the corresponding cell vectors |
| Miller orientation | Integer triplet `(h, k, l)` |
| Dataset units | The explicit string declared for each feature or target |

The energy-per-area conversion used by CALM is

\[
1\ \mathrm{eV/\AA^2}=16.02176634\ \mathrm{J/m^2}.
\]

## Exact behavior

### Basis-vector layout

CALM stores basis vectors as **columns** in the equations used throughout this manual. This is the canonical basis-vector convention for the documentation. For example,

\[
\mathbf A=
\begin{bmatrix}
\mathbf a_1 & \mathbf a_2 & \mathbf a_3
\end{bmatrix}.
\]

ASE stores the same cell vectors as rows in `atoms.cell.array`. Transposing between these layouts changes the array convention; it does not rotate, stretch, or shear the crystal.

### Surface and interface axes

After surface orientation:

- the first two cell directions span the periodic surface plane;
- the third cell direction is the stacking direction normal to the surface; and
- slab models are nonperiodic in the stacking direction unless a specific exported structure states otherwise.

For in-plane vectors \(\mathbf a\) and \(\mathbf b\), the realized interface area is

\[
A=\|\mathbf a\times\mathbf b\|.
\]

Side A contributes its selected **top** face to the contact. Side B contributes its selected **bottom** face.

### Fractional coordinates and periodic equivalence

Fractional coordinates are coefficients of the current cell vectors. A registry coordinate

\[
\mathbf q=(q_1,q_2)^{\mathsf T}
\]

represents the Cartesian translation \(\mathbf t=\mathbf X\mathbf q\) in the final common cell \(\mathbf X\). Adding an integer pair produces the same periodic registry. CALM therefore reports registry coordinates in a representative interval such as `[0, 1)`.

### Strain convention

CALM reports principal logarithmic, or Hencky, strains. If \(\mu_i\) are the eigenvalues of the relative metric, the principal strains are

\[
\varepsilon_i=\frac12\ln\mu_i.
\]

These values are dimensionless. A reported value of `0.02` means a logarithmic strain of 0.02; it is not stored as the percentage `2`.

`max_principal_strain` limits the largest absolute principal strain admitted by an interface search. Other mismatch fields combine the principal strains as described in [Coherent matching, strain, and Pareto selection](../understand/coherent-matching.md).

### Strain partition

The partition coordinate satisfies

\[
0\le\alpha\le1.
\]

The endpoint meanings are:

- `alpha = 0`: side A has zero in-plane stretch;
- `alpha = 1`: side B has zero in-plane stretch;
- intermediate values share the coherent mismatch.

The midpoint is geometric. It is not automatically the elastic-energy minimum.

### Raw and derived energy quantities

A calculator energy is stored as a total energy in eV. CALM does not reinterpret that number as an interface energy.

A derived interfacial quantity additionally requires:

- one explicit `EnergyConvention.formula`;
- a normalization area selected by `area_source`;
- an exact positive `n_interfaces`; and
- compatible reference energies.

The public `area_source` values are:

| Value | Meaning |
| --- | --- |
| `authoritative_interface_area` | Use the realized atomistic interface cell |
| `prototype_interface_area` | Use the area stored with the crystallographic search prototype |

The phrase `authoritative_interface_area` is an exact public enum value. In normal prose, the documentation calls it the **realized interface area**.

### Interface multiplicity

`n_interfaces` is the number of equivalent interfaces represented by the periodic atomistic cell. CALM does not infer it. The value belongs to the physical model and boundary conditions, not merely to the number of slabs visible in a plotting window.

### Formula units and composition

Bulk-reference energies are expressed per reduced chemical formula unit where the selected convention requires them. Formula-unit counts must be exact integers for the supported strained-bulk workflow. CALM does not infer non-stoichiometric reservoir chemical potentials.

### Dataset declarations

Feature and target units are declared explicitly through `DatasetFeature.units` and `DatasetTarget.units`. CALM preserves those strings but does not perform general dimensional conversion between arbitrary dataset columns. Use one consistent unit for each declared quantity across all rows.

## Related workflow

- [Materials](../use/materials.md) explains cell and periodicity checks.
- [Surfaces and terminations](../use/surfaces.md) applies the surface-axis and contact-face conventions.
- [Coherent matching, strain, and Pareto selection](../understand/coherent-matching.md) defines CALM's strain measures.
- [Strain partitioning and registry](../understand/strain-registry.md) defines `alpha` and fractional translations.
- [Relaxation, energy, and reference conventions](../understand/energetics.md) defines the supported derived quantities.
- [Inputs and settings](api/inputs-settings.md) gives the exact public fields and defaults.
