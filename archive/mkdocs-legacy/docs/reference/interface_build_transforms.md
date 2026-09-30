# Interface Build Transforms

CALM records the crystallographic transformations used to construct an interface supercell directly on the generated ASE `Atoms` object (via `atoms.info`).

This provenance is written by `calm.interface.build_interface_atoms(...)` and is intended to make interface construction reproducible and auditable without introducing a separate database-level transform ledger.

## Where it is stored

On any `Atoms` instance produced by the interface builder, CALM sets:

- **`atoms.info["calm_interface_build_transforms_json"]`**

The value is a compact JSON string.

## JSON schema

The JSON string decodes to a mapping with the following keys:

- `N_A`, `N_B`
  - 3×3 integer matrices.
  - Interpreted as **supercell transforms** applied to slab A / slab B.

- `R_A`, `R_B`
  - 3×3 float matrices.
  - Interpreted as **rotations** applied to slab A / slab B.

- `F_A`, `F_B`
  - 3×3 float matrices.
  - Interpreted as **strain transforms** applied to slab A / slab B after rotation.

- `translation`
  - Length-2 list of floats.
  - The in-plane translation of slab B relative to slab A, expressed in **fractional coordinates of the final interface cell**.

- `shift`
  - Float.
  - The z-shift applied to slab B (in Å).

- `vacuum`
  - Float.
  - Symmetric vacuum padding used when constructing the two-interface periodic model (in Å).

## Conventions

All matrices are stored using CALM’s **column-vector lattice convention**:

- A lattice matrix `L` is 3×3 with lattice vectors as columns.
- Applying a transform matrix `M` produces `L' = L @ M`.

This is the same convention used in the oriented slab transforms reference (`docs/reference/oriented_slab_transforms.md`).

## Reading the provenance

You can parse the metadata directly:

```python
import json

payload = json.loads(atoms.info["calm_interface_build_transforms_json"])
print(payload["N_A"], payload["F_A"], payload["translation"])
```

If you already have an atoms-payload dict (as stored in CALM records), the provenance lives under the `info` sub-dict:

```python
import json

payload = json.loads(atoms_dict["info"]["calm_interface_build_transforms_json"])
```

Note: CALM also includes an internal convenience helper (`calm.project.provenance.get_interface_build_transforms_payload(...)`) that accepts either an `Atoms` instance or an atoms-payload dict and returns the parsed mapping.

## Relationship to slab provenance

Slabs produced by CALM’s slab builder record a separate provenance blob:

- `atoms.info["calm_oriented_slab_transforms_json"]`

That provenance describes the transformations used to orient a slab from bulk.

The interface-build provenance described here records the subsequent transformations used to construct the **interface supercell** from two (already oriented) slabs.
