# Tutorial 1: Workspace Basics

Learn the fundamentals of CALM by creating a workspace, loading crystal structures, and performing structure optimization.

## What You'll Learn

- How to create and open a CALM workspace
- How to load crystal structures from POSCAR files
- How to relax structures with machine learning potentials
- How to export optimized structures

## Prerequisites

- CALM installed with GRACE calculator support
- Basic familiarity with ASE (Atomic Simulation Environment)
- Example structures: `LiF.poscar` and `Li2O.poscar`

## Understanding the Workspace

A CALM workspace is a **persistent project directory** containing:

- **`calm.sqlite`** - SQLite database storing all records (bulks, slabs, runs, results)
- **`out/`** - Artifact directory for plots, logs, and exported structures
- **`.calm/`** - Internal metadata (automatically managed)

The workspace provides:

- ✅ **Persistent storage** - All data survives between sessions
- ✅ **Provenance tracking** - Every result links back to its inputs
- ✅ **Artifact management** - Organized output directory structure
- ✅ **Querying** - Search and filter results efficiently

## Step 1: Create a Workspace

```python
from pathlib import Path
from calm.project import open_workspace

# Create or open workspace at specified location
ws = open_workspace(root=Path("./my_workspace"))
```

**What happens:**
- If directory doesn't exist → creates it with SQLite database
- If directory exists → opens existing workspace
- Returns a `Workspace` object with query/mutation facades

## Step 2: Load Crystal Structures

```python
from ase.io import read

# Load structures from POSCAR files
structures_dir = Path("./Structures")
atoms_lif = read(structures_dir / "LiF.poscar")
atoms_li2o = read(structures_dir / "Li2O.poscar")
```

**About the structures:**
- **LiF** - Rock salt structure (Fm-3m, cubic)
- **Li2O** - Anti-fluorite structure (Fm-3m, cubic)
- Both are ionic crystals with simple cubic unit cells

## Step 3: Add Structures to Workspace

```python
# Add reference (unoptimized) bulks
bulk_lif_ref = ws.add_bulk(
    structure=atoms_lif,
    label="LiF (reference)",
    kind="reference",
)

bulk_li2o_ref = ws.add_bulk(
    structure=atoms_li2o,
    label="Li2O (reference)",
    kind="reference",
)

print(f"Added LiF: {bulk_lif_ref.id_short}")
print(f"Added Li2O: {bulk_li2o_ref.id_short}")
```

**Key parameters:**
- `structure` - ASE `Atoms` object with atomic positions and cell
- `label` - Human-readable name for queries and display
- `kind` - Either `"reference"` (original) or `"optimized"` (relaxed)

**What you get:**
Each bulk is assigned a unique ID (e.g., `b_a1b2c3d4`) for referencing throughout the workspace.

## Step 4: Configure a Calculator

```python
from calm.calculators import CalculatorSpec

# Configure GRACE machine learning potential
calc_spec = CalculatorSpec(
    family="grace",
    model="GRACE-1L-OMAT",
    device="cpu",
)
```

**Calculator options:**
- `family="grace"` - GRACE / GraceMaker foundation model
- `family="mace"` - MACE-MP foundation model
- `family="lammps"` - Classical potentials via LAMMPS (through ASE)
- `family="ase"` - ASE reference calculators (e.g. EMT)

**Device selection:**
- `device="cpu"` - Run on CPU (slower but always available)
- `device="cuda"` - Run on GPU (faster, requires CUDA)

## Step 5: Relax Structures

```python
# Relax LiF bulk structure
bulk_lif_opt = ws.relax_bulk(
    bulk_lif_ref.id_short,
    optimized_with=calc_spec,
    label="LiF (optimized)",
    fmax=0.03,           # Converge to 0.03 eV/Å
    steps=200,           # Max 200 optimization steps
    reuse_existing=True, # Reuse if already computed
)

# Relax Li2O bulk structure
bulk_li2o_opt = ws.relax_bulk(
    bulk_li2o_ref.id_short,
    optimized_with=calc_spec,
    label="Li2O (optimized)",
    fmax=0.03,
    steps=200,
    reuse_existing=True,
)
```

**Relaxation parameters:**
- `fmax` - Force convergence criterion (eV/Å)
  - Smaller = more accurate, but slower
  - Typical values: 0.01-0.05 eV/Å
- `steps` - Maximum optimization steps
  - Prevents runaway optimizations
  - Typical values: 200-500 steps
- `reuse_existing` - Skip if already optimized
  - Saves computation time
  - Useful for rerunning scripts

**What happens:**
1. Calculator creates forces and stresses
2. ASE optimizer updates atomic positions and cell
3. Process repeats until forces < `fmax` or `steps` reached
4. Optimized bulk is stored with provenance links

## Step 6: Query Results

```python
# List all bulks
bulks = ws.list_bulks(limit=200)
print(f"Workspace contains {len(bulks)} bulk structures")

# Display formatted table
from calm.project import display_table
display_table(bulks)
```

**Expected output:**

```
Workspace contains 4 bulk structures

id_short   | label              | kind      | space_group | volume
-----------|--------------------|-----------|-------------|---------
b_a1b2c3d4 | LiF (reference)    | reference | Fm-3m (225) | 32.5 Å³
b_e5f6g7h8 | LiF (optimized)    | optimized | Fm-3m (225) | 31.8 Å³
b_i9j0k1l2 | Li2O (reference)   | reference | Fm-3m (225) | 65.2 Å³
b_m3n4o5p6 | Li2O (optimized)   | optimized | Fm-3m (225) | 64.1 Å³
```

**Facade-based querying:**
- `ws.*` - Read-only operations (list, get, search)
- `ws.*` - Create/update operations (add, build, start)
- `ws.*` - Export operations (POSCAR, JSON, etc.)

## Step 7: Export Structures

```python
# Export all bulks as POSCAR files
output_dir = Path("./exported_bulks")
ws.export_bulks_as_poscar(
    output_dir=output_dir,
    include_reference=True,  # Include unoptimized structures
    include_optimized=True,  # Include optimized structures
)

print(f"Exported POSCARs to: {output_dir}")
```

**Filename format:**
- ${id_short}_{label}.vasp$
- Example: $b_a1b2c3d4_LiF_reference.vasp$

**What's included:**
- Atomic positions and species
- Unit cell vectors
- POSCAR header with label

## Complete Example

This tutorial includes a full example script in the repository examples/. For
current runnable example scripts and their intended usage, see the Example
Scripts guide: `docs/guides/examples/index.md`.

```python
from pathlib import Path
from ase.io import read
from calm.calculators import CalculatorSpec
from calm.project import open_workspace
from calm.project import display_table

# Create workspace
root = Path("./my_workspace")
ws = open_workspace(root=root)

# Load structures
structures_dir = Path("./Structures")
atoms_lif = read(structures_dir / "LiF.poscar")
atoms_li2o = read(structures_dir / "Li2O.poscar")

# Add reference bulks
bulk_lif_ref = ws.add_bulk(
    structure=atoms_lif,
    label="LiF (reference)",
    kind="reference",
)
bulk_li2o_ref = ws.add_bulk(
    structure=atoms_li2o,
    label="Li2O (reference)",
    kind="reference",
)

# Configure calculator
calc_spec = CalculatorSpec(family="grace", model="GRACE-1L-OMAT", device="cpu")

# Relax structures
bulk_lif_opt = ws.relax_bulk(
    bulk_lif_ref.id_short,
    optimized_with=calc_spec,
    label="LiF (optimized)",
    fmax=0.03,
    steps=200,
    reuse_existing=True,
)
bulk_li2o_opt = ws.relax_bulk(
    bulk_li2o_ref.id_short,
    optimized_with=calc_spec,
    label="Li2O (optimized)",
    fmax=0.03,
    steps=200,
    reuse_existing=True,
)

# Query and display
bulks = ws.list_bulks(limit=200)
print(f"\\nWorkspace contains {len(bulks)} bulk structures")
display_table(bulks)

# Export
output_dir = Path("./exported_bulks")
ws.export_bulks_as_poscar(
    output_dir=output_dir,
    include_reference=True,
    include_optimized=True,
)
print(f"\\nExported POSCARs to: {output_dir}")
```

## Key Takeaways

1. **Workspace = Persistent Project**
   - All data stored in SQLite database
   - Artifacts organized in `out/` directory
   - Survives between Python sessions

2. **Facade-Based API**
   - `ws.*` for reading
   - `ws.*` for creating/updating
   - `ws.*` for exporting

3. **Calculator Integration**
   - Use `CalculatorSpec` to configure calculators
   - CALM supports multiple ML potential families
   - Relaxation with ASE optimizers

4. **Provenance Tracking**
   - Every result links to its inputs
   - Optimized bulks remember which calculator was used
   - Query relationships with `ws.list_edges()`

## Next Steps

- **[Tutorial 2: Slab Generation](02_slab_generation.md)** - Generate surface slabs from bulks
- **[Tutorial 3: Prototype Search](03_prototype_search.md)** - Find compatible interface candidates
- **[API Reference: Workspace](../reference/workspace.md)** - Complete API documentation

## Troubleshooting

**Calculator not found:**
```python
# Check available calculators
from calm.calculators import list_providers
providers = list_providers()
for p in providers:
    print(f"{p.family}: available={p.available}")
```

**Import error:**
```bash
# Install CALM with extras
pip install -e ".[dev]"
```

**Slow optimization:**
- Use GPU: `device="cuda"` (requires CUDA)
- Increase fmax: `fmax=0.05` (less accurate but faster)
- Reduce steps: `steps=100`

## Related Documentation

- [Calculators Concept](../concepts/calculators.md)
- [Workspace Layout](../concepts/project_layout.md)
- [Public API Reference](../reference/public_api.md)
