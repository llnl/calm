# Interfacial-energy evaluation and strained-bulk references

## Purpose

Interfacial-energy evaluation is the scientific morphism that assigns an excess-energy density to a built interface structure by subtracting strained-bulk reference energies from the total interface energy and normalizing by interface area. In CALM, this evaluation is implemented in two separable layers:

1. a calculator-free geometry and bookkeeping preparation step, and
2. a scalar energy reduction once the interface and reference energies are known.

This page specifies the mathematical convention and algorithm implemented by the current evaluation path. It intentionally distinguishes the scientific evaluation from representation helpers such as formula-unit counting, deformation-gradient frame mapping, calculator invocation, UID construction, and persistence projection.

## Ontology mapping

| Role | CALM object or representation |
| --- | --- |
| Input scientific object | Built interface structure represented by `calm.interface.model.Interface` |
| Input representation | `EnergyConfig` and an ASE-compatible calculator or callable energy function |
| Scientific morphism | `Evaluate: Built Interface Structure x Calculator x EnergyConfig -> Evaluation Result` |
| Reference scientific objects | Strained bulk reference structures for the A and B materials |
| Representation morphisms | Build slab supercells; map slab-frame deformation gradients to conventional-cell frame; compute formula-unit counts; project provenance into `EnergyResult` |
| Output scientific object | `EnergyResult` containing gamma, reference energies, formula-unit counts, identifiers, and reference-convention provenance |

## Mathematical problem

Let a built interface contain material slabs A and B in a common periodic cell. Let

- `E_int` be the total energy of the built interface cell;
- `E_A^bulk` and `E_B^bulk` be total energies of strained bulk reference cells for A and B;
- `n_A^bulk` and `n_B^bulk` be the number of formula units in those strained bulk reference cells;
- `n_A^slab` and `n_B^slab` be the number of formula units of A and B represented in the interface slab supercells;
- `A` be the single-interface area;
- `n_int` be the number of equivalent interfaces contributing to the denominator.

CALM first computes strained-bulk chemical potentials per formula unit,

```text
mu_A = E_A^bulk / n_A^bulk,
mu_B = E_B^bulk / n_B^bulk.
```

The excess interface energy is

```text
E_excess = E_int - n_A^slab * mu_A - n_B^slab * mu_B.
```

The interfacial-energy density is

```text
gamma = E_excess / (n_int * A).
```

The default public workflow uses `n_int = 2` through `EnergyConfig.double_sided=True`, corresponding to a periodic stack with two equivalent interfaces. A single-interface denominator is obtained by setting `double_sided=False`, which makes `n_int = 1`.

## Strained-bulk reference convention

The current default reference convention is recorded as

```text
strained_bulk_reference_mode = "unrelaxed_scaled_positions"
bulk_reference_relaxed = False
gamma_reference_convention = "strained_unrelaxed_bulk_subtraction"
```

For each material, CALM takes the slab-frame deformation gradient used to build the interface and maps it into the conventional bulk-cell frame. If `F_slab` is the slab-frame deformation gradient and `Q` is the orthogonal map from slab frame to conventional-cell frame, the conventional-frame deformation gradient is

```text
F_conv = Q F_slab Q^T.
```

If `C` is the conventional bulk cell written as a column-basis matrix, the strained reference cell is

```text
C_strained = F_conv C.
```

The corresponding ASE operation sets the new cell and scales atomic positions. No ionic relaxation is performed by default. The resulting potential energy is therefore a strained, unrelaxed bulk reference energy. This is an implementation convention and a scientific modeling assumption: it subtracts the elastic cost of deforming each bulk material consistently with the built interface, but it does not subtract any separately relaxed strained-bulk state unless a future energy pathway explicitly implements that convention and records different provenance.

## Formula-unit normalization

Reference subtraction uses formula-unit-normalized bulk energies. CALM counts formula units using reduced chemical formulas for

1. the interface slab supercells, and
2. the conventional bulk reference cells.

With `EnergyConfig.require_stoichiometric=True`, the reduced formulas of the slab supercell and the bulk conventional cell must match for each material. This guardrail prevents subtracting a bulk chemical potential from a non-stoichiometric slab whose composition cannot be represented by the same reduced formula.

## Algorithmic workflow

The implementation owner for calculator-free preparation and scalar arithmetic is `calm.interface._energy_kernel`. The public runner is `calm.interface.pipeline.compute_interfacial_energy`. Legacy arithmetic-only and full-workflow helpers also exist in `calm.interface.interface_energy`.

Inputs:

- a built `Interface` with atoms, prototype, strain state, and build UID;
- an `EnergyConfig`;
- a calculator or callable energy function.

Workflow:

1. Validate that the interface has atoms.
2. Extract slab A and slab B from the interface prototype and the deformation gradients from the strain state.
3. Compute the interface area from the built interface cell.
4. Select the denominator `A` or `2A` depending on `EnergyConfig.double_sided`.
5. Build slab supercells using the prototype supercell recipes.
6. Count formula units in the slab supercells and conventional bulk cells.
7. If `require_stoichiometric=True`, reject slab/bulk formula mismatches.
8. Construct strained bulk reference structures by mapping each slab-frame deformation gradient to the conventional-cell frame and applying it to the conventional bulk cell.
9. Record reference-convention provenance, deformation gradients, and strained-cell matrices.
10. Evaluate the strained bulk reference energies and the interface energy with the provided calculator or callable.
11. Reduce total reference energies to per-formula-unit values.
12. Compute `gamma_eV_per_A2` and convert to `gamma_J_per_m2` using the canonical factor `16.02176634`.
13. Return an `EnergyResult` with scalar values, UIDs, formulas, counts, configuration, and reference provenance.

The scalar kernel `compute_interfacial_energy_from_energies` performs only steps 11 and 12. It does not build structures, invoke calculators, relax atoms, or inspect chemistry. This separation is important for verification because the arithmetic can be tested independently from ASE and calculator behavior.

## Correctness properties

For valid inputs, the evaluation is expected to satisfy the following properties.

1. **Dimensional consistency**: `gamma_eV_per_A2` has units of eV per square Angstrom and `gamma_J_per_m2` is obtained by multiplying by the canonical conversion factor.
2. **Positive denominator**: the denominator is strictly positive; nonpositive interface area or denominator is invalid.
3. **Positive bulk formula-unit counts**: bulk reference energies cannot be converted to chemical potentials when either bulk formula-unit count is nonpositive.
4. **Composition compatibility**: under the default stoichiometric guardrail, each slab supercell must have the same reduced formula as its bulk reference.
5. **Reference provenance**: the result records the reference mode, relaxation flag, gamma convention, slab-frame deformation gradients, conventional-frame deformation gradients, and strained bulk cells when available.
6. **Arithmetic separability**: the scalar gamma computation is independent of calculator side effects and can be verified from scalar inputs alone.
7. **Compatibility preservation**: `EnergyResult` preserves established public field names and compatibility aliases while adding reference provenance additively.

## Numerical considerations

The scalar reduction is well conditioned except when the denominator is small or when large nearly cancelling energy terms produce a small excess energy. Those cases are physically important and should be interpreted with the usual caution for subtractive energy calculations. CALM validates denominator and reference formula-unit counts but does not estimate uncertainty in calculator energies.

The frame map `Q` used for strained-bulk references should be orthogonal. The implementation exposes guardrails in `EnergyConfig`, including strict reference-frame handling, fallback warnings, and tolerance checks. If the preferred primitive-basis mapping cannot be constructed, the implementation may use a slab cell-vector fallback unless strict mode forbids it. The fallback is documented because it may be less appropriate for anisotropic materials.

## Complexity

The scalar reduction is constant time. The geometry preparation is dominated by supercell construction, formula counting, reference-frame mapping, and calculator evaluations. In practical workflows, calculator calls dominate runtime. The documentation therefore treats the energy runner as an orchestration algorithm around expensive external energy evaluations.

## Implementation mapping

| Concept | Implementation owner |
| --- | --- |
| Public evaluation runner | `calm.interface.pipeline.compute_interfacial_energy` |
| Geometry/reference preparation | `calm.interface._energy_kernel.prepare_interfacial_energy_geometry` |
| Scalar energy reduction | `calm.interface._energy_kernel.compute_interfacial_energy_from_energies` |
| Arithmetic-only public helper | `calm.interface.interface_energy.compute_interface_energy_from_scalars` |
| Strained bulk construction | `calm.interface.interface_energy.get_strained_bulk` |
| Reference-frame mapping | `calm.interface.interface_energy.get_ortho_map` |
| Evaluation result container | `calm.interface.results.EnergyResult` |
| Scalar result container | `calm.interface.results.InterfaceEnergyScalarResult` |
| Energy configuration | `calm.interface.config.EnergyConfig` |

## Verification mapping

Existing verification covers the scalar arithmetic, denominator choice, unit conversion, invalid reference denominators, public scalar helper behavior, provenance-field round trips, and public API boundary placement.

Important tests include:

- `tests/test_interfacial_energy_kernel.py`
- `tests/test_interface_energy_hardening.py`
- `tests/test_interface_energy_scalar_public_api.py`
- `tests/public/test_interface_model_energy_references.py`
- `tests/public/test_interface_model_energy_and_relax.py`
- architecture tests guarding public/project boundary placement

Recommended future verification:

1. dependency-light tests for `EnergyConfig.double_sided` propagation from the public runner into the geometry denominator;
2. small ASE-backed fixtures checking that strained-bulk cells record `F_conv C` consistently with `get_strained_bulk`;
3. strict-mode tests for reference-frame fallback behavior;
4. end-to-end workflow tests connecting interface construction, energy evaluation, dataset persistence, and report projection;
5. numerical regression cases for small excess energies where cancellation is expected.

## Limitations

The current default convention is an unrelaxed strained-bulk subtraction. It is not a general thermodynamic interface free energy, and it does not account for temperature, entropy, non-stoichiometric chemical potentials, charged interfaces, external reservoirs, or separately relaxed strained-bulk references. Those variants require explicit new conventions and provenance fields before they should be compared with the default gamma values.

## References

- CALM ontology documents for the distinction between scientific morphisms and representation morphisms.
- CALM engineering records on energy provenance and reference conventions.
- Standard atomistic interface-energy practice using excess-energy subtraction against compatible bulk references.
