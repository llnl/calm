# Tutorial 2: Slab Generation

Learn how to generate surface slabs from bulk crystal structures, control slab parameters, and handle polar surface terminations.

## What You'll Learn

- How to build surface slabs from bulk structures
- How Miller indices specify surface orientations
- How to control slab thickness and vacuum spacing
- How to handle polar surface terminations automatically
- How to query, filter, and export slabs

## Prerequisites

- Completed [Tutorial 1: Workspace Basics](01_workspace_basics.md)
- Workspace with optimized bulk structures
- Understanding of Miller indices (basic crystallography)

## Background: Surface Slabs

A **surface slab** is a finite-thickness crystal with:
- Two surfaces (top and bottom)
- Periodic boundary conditions in-plane (x, y)
- Vacuum spacing in the perpendicular direction (z)

### Miller Indices

**Miller indices (hkl)** specify crystallographic planes:
- **(100)** - Face of cubic cell (perpendicular to a-axis)
- **(110)** - Diagonal plane through two axes
- **(111)** - Plane cutting all three axes equally

**Common low-index surfaces** for cubic crystals:
- (100), (110), (111) - Most stable, lowest energy
- (210), (211), (310) - Higher index, stepped surfaces

### Polar vs Non-Polar Surfaces

**Non-polar surfaces:**
- Symmetric stacking (no net dipole)
- Single termination
- Example: Si(111), Al(111)

**Polar surfaces:**
- Asymmetric stacking (net dipole perpendicular to surface)
- Multiple possible terminations
- Example: LiF(100) can be Li-terminated or F-terminated

CALM **automatically detects** polar surfaces and **enumerates terminations**.

## Step 1: Open Workspace

```python
from pathlib import Path
from calm.project import open_workspace

# Open workspace from Tutorial 01
root = Path("./my_workspace")
ws = open_workspace(root=root)
```

**Important:** This assumes you've completed Tutorial 01 and have optimized bulk structures in the workspace.

## Step 2: Find Optimized Bulks

```python
# Find optimized bulks using helper method
lif_bulk = ws.find_bulk_by_material("LiF", kind="optimized")
li2o_bulk = ws.find_bulk_by_material("Li2O", kind="optimized")

if not lif_bulk or not li2o_bulk:
    print("Error: Run Tutorial 01 first to create optimized bulks")
    exit(1)

print(f"Found optimized bulks:")
print(f"  LiF: {lif_bulk.id_short} - {lif_bulk.label}")
print(f"  Li2O: {li2o_bulk.id_short} - {li2o_bulk.label}")
```

**Helper method:** $find_bulk_by_material(material, kind)$
- Searches bulk labels for `material` string
- Filters by `kind` ("reference" or "optimized")
- Returns first match or `None`

**Alternative:** Direct query
```python
bulks = ws.list_bulks(kind="optimized")
lif_bulk = [b for b in bulks if "LiF" in b.label][0]
```

## Step 3: Configure Slab Parameters

```python
slab_params = {
    "vacuum": 15.0,      # Vacuum spacing in Ångströms
    "layers": 4,         # Number of atomic layers
    "periodic": True,    # Maintain periodicity
}
```

**Key parameters:**

| Parameter | Description | Typical Values |
|-----------|-------------|----------------|
| `vacuum` | Vacuum thickness (Å) | 10-20 Å (DFT), 15-30 Å (charged systems) |
| `layers` | Number of atomic layers | 3-6 layers (surface), 8-12 layers (bulk-like) |
| `periodic` | In-plane periodicity | `True` (almost always) |

**Choosing vacuum spacing:**
- **Too small** - Surface interactions across vacuum (spurious)
- **Too large** - Wasted computation
- **DFT:** 10-15 Å typically sufficient
- **Charged systems:** 20-30 Å (long-range electrostatics)

**Choosing number of layers:**
- **Surface properties:** 3-6 layers (sufficient for surface relaxation)
- **Bulk convergence:** 8-12 layers (approach bulk behavior)
- **Trade-off:** More layers = more accurate but more expensive

## Step 4: Build Slabs

```python
# Build slabs for multiple Miller indices
lif_slabs = ws.build_slabs(
    bulk=lif_bulk.id_short,
    millers=[(1, 0, 0), (1, 1, 0), (1, 1, 1)],  # 100, 110, 111
    params=slab_params,
    enumerate_terminations=True,  # Auto-detect and enumerate terminations
)

li2o_slabs = ws.build_slabs(
    bulk=li2o_bulk.id_short,
    millers=[(1, 0, 0), (1, 1, 0), (1, 1, 1)],
    params=slab_params,
    enumerate_terminations=True,
)

print(f"Created {len(lif_slabs)} LiF slabs and {len(li2o_slabs)} Li2O slabs")
```

**Parameters:**
- `bulk` - ID of bulk structure to slice
- `millers` - List of (h, k, l) tuples for surfaces
- `params` - Dictionary of slab parameters
- `enumerate_terminations` - If `True`, create separate slabs for each termination

**What happens:**
1. For each Miller index:
   - Extract primitive surface lattice
   - Detect if surface is polar
   - If polar: identify unique terminations
   - Create slab(s) with specified thickness and vacuum
2. Store each slab in workspace with unique ID
3. Return list of created slab objects

**Example output:**
```
Created 6 LiF slabs and 6 Li2O slabs
```

For LiF(100) (polar), you might get:
- LiF(100) Li-terminated
- LiF(100) F-terminated

For LiF(111) (non-polar), you get:
- LiF(111) (single termination)

## Step 5: Query and Display Slabs

```python
from calm.project import display_table

# Query all slabs
all_slabs = ws.list_slabs(limit=100)
print(f"Total slabs in workspace: {len(all_slabs)}")

# Get enriched slabs (with computed properties)
enriched_slabs = ws.enrichment.list_slabs_enriched(limit=100)

# Display formatted table
display_table(enriched_slabs, table="slabs")
```

**Expected output:**

```
Total slabs in workspace: 12

id_short   | bulk_label | miller | termination | layers | area    | n_atoms
-----------|------------|--------|-------------|--------|---------|--------
s_a1b2c3d4 | LiF        | (100)  | Li-term     | 4      | 16.2 Ų | 8
s_e5f6g7h8 | LiF        | (100)  | F-term      | 4      | 16.2 Ų | 8
s_i9j0k1l2 | LiF        | (110)  | -           | 4      | 22.9 Ų | 12
s_m3n4o5p6 | LiF        | (111)  | -           | 4      | 19.8 Ų | 9
...
```

**Column descriptions:**
- `id_short` - Unique slab identifier
- `bulk_label` - Parent bulk material
- `miller` - Surface orientation (h k l)
- `termination` - Surface termination (for polar surfaces)
- `layers` - Number of atomic layers
- `area` - Surface area (Ų)
- `n_atoms` - Number of atoms in slab

### Enriched vs Regular Queries

**Regular query** (`list_slabs`):
- Returns raw database records
- Fast (no computation)
- Basic fields only

**Enriched query** (`list_slabs_enriched`):
- Computes additional properties
- Slightly slower (but cached)
- Includes area, volume, density, etc.

## Step 6: Filter and Group Slabs

### Filter by Material

```python
# Get only LiF slabs
lif_slabs = [s for s in all_slabs if "LiF" in s.bulk_label]

# Or use query parameter
lif_slabs = ws.list_slabs(bulk_uid=lif_bulk.uid_full)
```

### Group by Miller Index

```python
# Group slabs by material and Miller index
grouped = ws.enrichment.group_slabs_by_material()

for material, slabs_dict in grouped.items():
    print(f"\n{material}:")
    for miller_str, slabs in slabs_dict.items():
        print(f"  {miller_str}: {len(slabs)} slabs")
```

**Expected output:**
```
LiF:
  (100): 2 slabs  # Li-term and F-term
  (110): 1 slab
  (111): 1 slab

Li2O:
  (100): 2 slabs
  (110): 1 slab
  (111): 1 slab
```

### Filter by Number of Atoms

```python
# Get small slabs (≤ 10 atoms)
small_slabs = [s for s in enriched_slabs if s.n_atoms <= 10]

# Get large slabs (> 20 atoms)
large_slabs = [s for s in enriched_slabs if s.n_atoms > 20]
```

## Step 7: Export Slabs

```python
# Export all slabs as POSCAR files
slab_dir = Path("./exported_slabs")
exported_files = ws.export_slabs_as_poscar(output_dir=slab_dir)

print(f"Exported {len(exported_files)} POSCAR files to: {slab_dir}")
```

**Filename format:**

$$
{id_short}_{bulk_label}_{miller}_{termination}.vasp
$$

**Examples:**
- $s_a1b2c3d4_LiF_100_Li-term.vasp$
- $s_e5f6g7h8_LiF_100_{F}-term.vasp$
- $s_i9j0k1l2_LiF_110.vasp$

**Export options:**

```python
# Export only LiF slabs
ws.export_slabs_as_poscar(
    slab_uids=[s.uid_full for s in lif_slabs],
    output_dir=slab_dir,
)

# Export with custom naming
ws.export_poscar(
    atoms=slab.atoms,
    filepath=slab_dir / f"my_custom_name_{slab.id_short}.vasp"
)
```

## Understanding Polar Surface Terminations

### Example: LiF(100)

LiF has rock salt structure (Fm-3m). The (100) surface is **polar**.

**Two possible terminations:**

1. **Li-terminated:**
```
   ... Li - F - Li - F - Li |  (surface)
```
   - Last layer is Li⁺ (cation)
   - Positive surface charge

2. **F-terminated:**
```
   ... F - Li - F - Li - F |  (surface)
```
   - Last layer is F⁻ (anion)
   - Negative surface charge

**CALM automatically:**
1. Detects polar character (via spglib)
2. Identifies unique terminations
3. Creates separate slabs for each
4. Labels with termination type

### Example: Al(111)

Al has FCC structure. The (111) surface is **non-polar**.

**Single termination:**
```
... Al - Al - Al - Al |  (surface)
```
- Symmetric stacking
- No dipole
- One slab generated

## Complete Example

```python
from pathlib import Path
from calm.project import open_workspace
from calm.project import display_table

# 1. Open workspace
root = Path("./my_workspace")
ws = open_workspace(root=root)

# 2. Find optimized bulks
lif_bulk = ws.find_bulk_by_material("LiF", kind="optimized")
li2o_bulk = ws.find_bulk_by_material("Li2O", kind="optimized")

# 3. Configure slab parameters
slab_params = {
    "vacuum": 15.0,
    "layers": 4,
    "periodic": True,
}

# 4. Build slabs
lif_slabs = ws.build_slabs(
    bulk=lif_bulk.id_short,
    millers=[(1, 0, 0), (1, 1, 0), (1, 1, 1)],
    params=slab_params,
    enumerate_terminations=True,
)

li2o_slabs = ws.build_slabs(
    bulk=li2o_bulk.id_short,
    millers=[(1, 0, 0), (1, 1, 0), (1, 1, 1)],
    params=slab_params,
    enumerate_terminations=True,
)

print(f"Created {len(lif_slabs)} LiF slabs and {len(li2o_slabs)} Li2O slabs")

# 5. Query and display
enriched_slabs = ws.enrichment.list_slabs_enriched(limit=100)
display_table(enriched_slabs, table="slabs")

# 6. Export
slab_dir = root / "exported_slabs"
exported = ws.export_slabs_as_poscar(output_dir=slab_dir)
print(f"Exported {len(exported)} POSCAR files to: {slab_dir}")
```

## Key Takeaways

1. **Miller Indices Specify Surfaces**
   - (100), (110), (111) are common low-index surfaces
   - Different surfaces have different properties

2. **Polar Surfaces Have Multiple Terminations**
   - CALM auto-detects polar character
   - `enumerate_terminations=True` creates all variants
   - Each termination has different chemistry

3. **Slab Parameters Matter**
   - Vacuum spacing: 10-20 Å (DFT), 15-30 Å (charged)
   - Layers: 3-6 (surface), 8-12 (bulk convergence)
   - More layers = more accurate but expensive

4. **Facade-Based Querying**
   - `ws.*` for raw database queries
   - `ws.enrichment.*` for computed properties
   - `ws.*` for file export

5. **Provenance Tracking**
   - Every slab links to parent bulk
   - Query relationships: `ws.list_edges()`

## Troubleshooting

**"Bulk not found" error:**
```python
# Check available bulks
bulks = ws.list_bulks()
print([b.label for b in bulks])

# Use exact ID instead of label search
ws.build_slabs(bulk="b_abc123", millers=[(1,1,1)])
```

**Too many atoms:**
```python
# Reduce layers
slab_params["layers"] = 3  # instead of 4

# Use smaller supercell
# (handled automatically in slab building)
```

**No slabs created:**
```python
# Check Miller indices are valid
# For cubic: (h k l) where h,k,l are integers
# Make sure bulk is optimized (not distorted)
```

**Polar surface but only one slab:**
- Check `enumerate_terminations=True`
- Some surfaces appear polar but have only one stable termination
- Use `ws.get_slab(slab_id)` to check metadata

## Next Steps

- **[Tutorial 3: Prototype Search](03_prototype_search.md)** - Find compatible interface candidates
- **[Tutorial 6: Surface Terminations](06_terminations.md)** - Deep dive into polar surfaces
- **[How-To: Slab Workflows](../guides/workflows/project_prototype_search.md)** - Advanced slab recipes

## Related Documentation

- [Concepts: UIDs and Records](../concepts/uids_and_records.md)
- [API Reference: SlabSpec](../reference/public_api.md)
See runnable examples in the Example Scripts guide: `docs/guides/examples/index.md`.

## Further Reading

**Crystallography:**
- Miller indices: Wikipedia - [Miller Index](https://en.wikipedia.org/wiki/Miller_index)
- Surface science: Woodruff & Delchar, "Modern Techniques of Surface Science"

**Polar surfaces:**
- Tasker classification: Tasker, P. W. (1979). "The stability of ionic crystal surfaces." J. Phys. C: Solid State Physics.
- Noguera review: Noguera, C. (2000). "Polar oxide surfaces." J. Phys.: Condens. Matter.
