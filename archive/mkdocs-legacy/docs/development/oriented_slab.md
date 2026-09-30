# Oriented slab construction

This page describes CALM's **oriented slab kernel** implemented in $calm.slab.ops.oriented_slab$.
The goal is to construct an *oriented, surface-primitive* periodic slab block directly from a **conventional 3D bulk cell** while emitting a complete, auditable set of transforms that relate:

- the conventional bulk frame (cartesian and lattice),
- the oriented slab frame (cartesian and lattice), and
- any *physical* deformation applied to remove residual tilt.

The kernel is used as a geometry/provenance constructor: it does **not** infer the layer count from a target thickness.

## Key design constraints

- **Deterministic surface lattice basis**: all integer basis choices are canonicalized (Niggli-reduced in 2D) and are compatible with CALM's in-plane gauge conventions.
- **Motif-minimality before lattice matching**: when enabled, the in-plane cell is reduced using *pure translation symmetries* so the surface cell is minimal with respect to the atomic motif.
- **Explicit physical vs non-physical operations**: the transform record distinguishes:
  - *integer lattice basis changes* (not physical strain),
  - *cartesian rotations* (change of frame), and
  - *physical shears* used to orthogonalize the slab `c` vector.

## Construction pipeline

The primary entry point is:

- $build_oriented_slab_from_conventional(conv, hkl=..., layers=..., ...) -> OrientedSlabResult$

The algorithm proceeds as follows.

1. **Start from a conventional bulk cell**

   Input `conv` must be fully 3D-periodic (`pbc=True`) and (by convention) is the standardized conventional bulk cell.

2. **Build the integer surface kernel**

   Construct `S_conv_to_surface_col` (3×3 integer, *column convention*) from the reduced Miller index `hkl_reduced`.
   Then multiply the third column by `layers` to thicken the block along the step direction.

3. **Make a periodic block supercell**

   Use ASE's `make_supercell` with the corresponding row-convention matrix $P_supercell_row = S_layers.T$.

4. **Optional motif-minimality in-plane reduction**

   If `reduce_motif_inplane=True`, identify *pure translation* symmetry operations (rotation = identity) using spglib.
   Restrict to translations with negligible `z` component (in fractional coordinates) and find a minimal in-plane reduction
   `M_motif_inplane_col` such that the atomic motif is preserved under the reduced in-plane lattice.

   This step is a **lattice basis reduction**, not a physical strain.

5. **Optional metric (2D Niggli) in-plane reduction**

   If `reduce_inplane=True`, apply CALM's canonical `niggli_reduce_2d`-based reduction to the in-plane lattice to obtain
   `U_inplane_col` (3×3 integer, identity in the `c` direction). This step enforces a canonical 2D Niggli-reduced basis
   and repairs handedness when necessary.

   This step is also a **lattice basis reduction**, not a physical strain.

6. **Rotate into the oriented slab cartesian frame**

   Compute `R_conv_to_slab` so that:

   - the slab surface normal is aligned with the cartesian `+z` (or `-z` if $normal_sign=-1$), and
   - the in-plane lattice vector `a` is aligned with cartesian `+x`.

   After this step, the oriented block satisfies (within tolerance): $a_{z} ≈ 0$ and $b_{z} ≈ 0$.

7. **Optional integer c-tilt reduction**

   If `reduce_c_tilt=True`, apply an integer (row-convention) basis change `L_c_tilt_row` that reduces the in-plane
   projection of the `c` lattice vector. This reduces tilt *representation* but does not physically strain the slab.

8. **Optional physical shear to orthogonalize c**

   If `orthogonalize_c=True`, apply a **physical shear** (a deformation gradient) to remove any residual in-plane
   component of `c`, ensuring the final block has $c_xy ≈ 0$. The applied deformation gradient is tracked in
   `F_orthogonalize_c_slab` (slab cartesian frame).

9. **Optional vacuum insertion**

   If `vacuum` is provided, non-physically extend the cell along cartesian `z` and optionally center the slab.

## Transform record

`OrientedSlabResult.transforms` (`OrientedSlabTransforms`) is the authoritative provenance object. Key fields:

- `S_conv_to_surface_col`: integer surface kernel (including layer thickening)
- `M_motif_inplane_col`: in-plane motif-minimality reduction (integer; identity if disabled)
- `U_inplane_col`: in-plane metric/Niggli reduction (integer; identity if disabled)
- `P_supercell_row`: the row-convention matrix passed to ASE `make_supercell`
- `R_conv_to_slab`, `R_slab_to_conv`: cartesian rotation between frames
- `L_c_tilt_row`, `c_tilt_mn`: optional integer c-tilt reduction
- `F_orthogonalize_c_slab`: optional physical shear used to orthogonalize `c`
- `vacuum_info`: optional non-physical vacuum metadata

### Mapping deformation gradients back to the conventional frame

If an interface-matching step produces a deformation gradient `F_slab` in the **slab cartesian frame**, use:

- $map_deformation_gradient_slab_to_conv(F_slab, transforms)$

This accounts for the cartesian frame change (`R_conv_to_slab`) and any *physical* shear applied during
`orthogonalize_c`. Integer-only basis reductions (motif / Niggli / c-tilt) are intentionally excluded because they do not
represent physical strain.

## Known limitations / future work

- **Termination selection** is not yet implemented in the kernel (CALM currently follows ASE's conventional termination
  choice behavior elsewhere). A deterministic termination-selection policy can be added on top of the oriented block.
- **End-to-end integration**: the kernel is exposed via $calm.slab.ops.oriented_slab$ and is now the
  **default** slab construction pathway in the high-level `Slab` builder. Transform provenance is persisted to
  $Atoms.info["calm_oriented_slab_transforms_json"]$ and is accessible programmatically via
  $Slab.oriented_slab_transforms$.
  The slab UID includes `SlabSpec.builder` (default: `oriented_slab_kernel_v1`) to avoid collisions with
  legacy slab records.
