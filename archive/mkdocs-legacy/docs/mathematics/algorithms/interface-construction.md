# Interface construction

## Purpose

Interface construction is the scientific morphism that turns an interface prototype and an in-plane strain state into an atomistic built interface structure. In CALM, this operation is implemented as deterministic geometry assembly: each slab is converted to the selected matched supercell, rotated into its reduced gauge, deformed to the common in-plane target basis, translated in registry space, separated along the out-of-plane direction, and combined into a periodic structure with provenance metadata.

This page specifies the mathematics and algorithm implemented by the current interface-build path. It intentionally distinguishes the scientific morphism **Build** from representation helpers such as 2D-to-3D matrix embedding, translation wrapping, ASE supercell adaptation, and UID/provenance projection.

## Ontology mapping

| Role | CALM object or representation |
| --- | --- |
| Input scientific object | `InterfacePrototype` containing slab A, slab B, reduced supercell recipes, and prototype UID |
| Input representation | `StrainState` containing deformation gradients `F_A`, `F_B` and strain-model UID |
| Build parameters | `InterfaceBuildConfig` containing fractional translation, z-padding, optional vacuum padding, and translation rounding |
| Scientific morphism | `Build: InterfacePrototype x StrainState x BuildConfig -> Built Interface Structure` |
| Representation morphisms | Embed 2D supercell/rotation matrices in 3D; adapt CALM column-basis supercells to ASE; wrap/round registry translation; project provenance into `atoms.info` |
| Output scientific object | Built interface structure represented by `calm.interface.model.Interface` with atoms, layer indices, prototype, strain state, and build config |

## Mathematical problem

Let two slabs have atomistic structures with Cartesian positions and cells. Let their matched in-plane supercell recipes provide integer matrices `N_A`, `N_B` and in-plane rotations `R_A`, `R_B`. Let a strain-state calculation provide Cartesian deformation gradients `F_A` and `F_B` that map each slab's post-supercell, post-rotation in-plane basis to the selected common target basis.

The build problem is to construct a periodic atomistic structure whose lower layer is slab A and whose upper layer is slab B such that:

1. both slabs share the same in-plane cell vectors after supercell construction, rotation, and deformation;
2. the upper slab is shifted by a registry translation on the in-plane torus;
3. the slabs are separated by a nonnegative inter-slab z-padding;
4. the final cell has periodic boundary conditions in all three directions;
5. provenance records identify the prototype, strain model, strained-interface state, build parameters, and layer membership.

The build operation is not a strain optimizer, registry optimizer, matcher, or energy evaluator. It consumes the outputs of those earlier transformations and realizes one concrete atomistic structure.

## Coordinate and matrix conventions

CALM's lattice and supercell recipes use a column-basis convention for mathematical derivations. ASE's `make_supercell` interface uses row-oriented cell conventions. The implementation therefore routes supercell construction through `calm.ase_adapter.make_supercell_col`, which applies the required adapter rather than exposing transposition logic at call sites.

Two-dimensional supercell and rotation matrices are embedded into 3D as

```text
embed(M) = [[M_11, M_12, 0],
            [M_21, M_22, 0],
            [0,    0,    1]].
```

The z direction is not strained by this embedding. Out-of-plane placement is handled separately by z-coordinate translation and final cell construction.

## Algorithmic workflow

The implementation owner is `calm.interface._build_kernel.build_interface_atoms`, with workflow orchestration in `calm.interface.pipeline.build_interface`.

Inputs:

- slab A atoms and slab B atoms;
- 3D supercell matrices `N_A3`, `N_B3`;
- 3D rotation matrices `R_A3`, `R_B3`;
- 3D deformation gradients `F_A`, `F_B`;
- fractional registry translation `(t1, t2)`;
- nonnegative `z_padding`;
- optional nonnegative `vacuum_padding`.

Workflow:

1. Validate matrix shapes and translation dimensionality.
2. Copy slab atoms so the input slabs are not mutated.
3. Construct slab supercells using CALM's column-basis ASE adapter.
4. Rotate both slabs in Cartesian coordinates.
5. Apply the slab-specific Cartesian deformation gradients to positions and cells.
6. Extract the strained in-plane basis vectors `c1` and `c2` from slab A's cell.
7. Convert the fractional registry translation to Cartesian form:

   ```text
   t_cart = t1 c1 + t2 c2.
   ```

8. Translate slab B by `t_cart` in plane.
9. Shift slab A so its minimum z coordinate is zero.
10. Shift slab B so its minimum z coordinate is `zmax(A) + z_padding`.
11. Set the out-of-plane cell length:

    ```text
    L_z = h_A + h_B + z_padding + vacuum_padding,
    ```

    where `vacuum_padding` defaults to `z_padding` when omitted.
12. Set both slab cells to the composite cell with rows `(c1, c2, [0, 0, L_z])` without scaling atom positions.
13. Concatenate the lower and upper slabs.
14. Record lower- and upper-layer atom indices.
15. Set periodic boundary conditions to `(True, True, True)` and wrap atoms into the final cell.
16. Return the built structure and geometric bookkeeping.

The public pipeline also constructs deterministic UIDs. It wraps and rounds `translation_frac`, computes the strained-interface UID from the prototype and strain-model UIDs, computes the build UID from the strained UID and build parameters, and stamps provenance into `atoms.info`.

## Correctness properties

Subject to valid input slabs and nonsingular transformations, the build kernel is expected to satisfy:

1. **Input immutability**: input slab atoms are copied before mutation.
2. **Common in-plane cell**: both slabs are assigned the same final in-plane vectors `c1` and `c2`.
3. **Registry interpretation**: `(t1, t2)` is interpreted as a fractional translation in the strained in-plane target basis.
4. **Layer separation**: the lower slab's minimum z coordinate is zero and the upper slab is placed at least `z_padding` above the lower slab's maximum z coordinate before wrapping.
5. **Cell-height accounting**: `L_z` equals the two slab heights plus inter-slab padding plus vacuum padding, with backward-compatible default `vacuum_padding = z_padding`.
6. **Layer-index preservation**: returned lower and upper index arrays partition the concatenated atoms by source slab.
7. **Deterministic provenance**: deterministic inputs yield deterministic build UIDs and provenance metadata after translation quantization.
8. **Representation separation**: 2D-to-3D embedding, ASE adapter transposition, and UID projection are representation morphisms, not independent scientific morphisms.

## Numerical considerations

The build algorithm is deterministic but inherits numerical conditioning from earlier matching and strain-state calculations. Important numerical boundaries are:

- deformation gradients must be finite 3x3 matrices;
- rotation matrices are assumed to be valid outputs from the matching/reduction pipeline;
- fractional translation is wrapped and rounded before UID generation in the public pipeline;
- z-padding and vacuum-padding must be nonnegative;
- final wrapping can move atoms by lattice vectors, so downstream layer queries should use the returned layer indices rather than reconstructing membership from z coordinates alone.

The kernel currently validates shapes and nonnegative z-padding values. It does not prove physical contact quality or registry optimality; those are responsibilities of registry search and energy/evaluation steps.

## Complexity

Let `n_A` and `n_B` be atom counts after supercell expansion. Geometry operations are linear in the number of atoms. Supercell construction dominates practical runtime and memory use through the determinant of the supercell matrices. After supercells are made, rotations, deformation gradients, translations, concatenation, and wrapping are `O(n_A + n_B)` in time and memory.

## Implementation mapping

| Mathematical or algorithmic role | Implementation |
| --- | --- |
| Public workflow build morphism | `calm.interface.pipeline.build_interface` |
| Geometry assembly kernel | `calm.interface._build_kernel.build_interface_atoms` |
| Private built-structure return record | `calm.interface._build_kernel.BuiltInterfaceStructure` |
| 2D-to-3D matrix embedding | `calm.interface._build_kernel._embed_2x2_in_3x3` |
| Translation wrapping/rounding | `calm.interface._build_kernel.quantize_translation_frac` |
| Column-basis ASE adapter | `calm.ase_adapter.make_supercell_col` |
| Build configuration | `calm.interface.config.InterfaceBuildConfig` |
| Built interface model | `calm.interface.model.Interface` |
| Build UID projection | `calm.keys.uid.build_uid` |
| Strained-interface UID projection | `calm.keys.uid.strained_uid` |

There is also a legacy static helper at `calm.interface.interface.Interface.build_interface`. The current workflow build path is the pipeline/model path above; specifications and new verification should preferentially target the pipeline path and the shared build kernel.

## Verification mapping

Relevant current and recommended tests include:

- build-kernel tests for input immutability, layer-index partitioning, z-padding semantics, and periodic-cell construction;
- UID-stability tests for wrapped/rounded translations and build UID determinism;
- workflow tests that call `calm.interface.pipeline.build_interface` from a prototype and strain state;
- registry-search tests that confirm optimized translation/z-padding are converted into build configs correctly;
- future property tests checking common in-plane cell equality, nonnegative z separation before wrapping, and preservation of source-slab atom counts.

The specification suggests adding explicit mathematical guardrails for the common in-plane cell, layer partition, and `vacuum_padding=None -> z_padding` default if these are not already covered by dependency-light tests.

## Limitations

- The build algorithm assembles one candidate structure; it does not search over matches, strain partitions, or registries.
- It assumes the supplied strain state is mathematically compatible with the prototype supercell recipes.
- It uses the lower slab's strained in-plane basis as the final composite-cell gauge.
- Physical plausibility after wrapping depends on upstream registry and z-padding choices.
- Legacy build helpers remain compatibility surfaces and are not the normative workflow owner.

## References

The build algorithm is primarily a deterministic computational realization of CALM's ontology and earlier matching/strain specifications. Its mathematical ingredients are the supercell, rotation, deformation-gradient, and registry-translation constructions documented elsewhere in the CALM mathematics reference.
