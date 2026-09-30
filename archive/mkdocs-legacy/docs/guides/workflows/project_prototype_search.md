# Prototype Search in a Workspace

Run systematic prototype searches with database persistence, provenance tracking, and artifact management.

## Overview

A **workspace-backed prototype search** provides:

> Note: For runnable example scripts that demonstrate these workflows, see the Example Scripts guide: `docs/guides/examples/index.md`.

- **Persistence** - Results stored in SQLite database
- **Provenance** - Full lineage from bulk → slab → prototype
- **Artifacts** - Plots, structures, logs organized automatically
- **UIDs** - Stable, reproducible identifiers
- **Reproducibility** - Same inputs → same UIDs → same results
- **Querying** - Rich SQL-backed queries for filtering/analysis

**Use workspace when:**
- Running production campaigns
- Need to share results with collaborators
- Want reproducibility guarantees
- Multiple related searches
- Long-running workflows

## Basic Workflow

### Step 1: Create Workspace

```python
from calm.project import open_workspace

# Create new workspace (or reopen existing)
ws = open_workspace(root="my-interface-project")
```

**Workspace structure created:**
```
my-interface-project/
├── calm.sqlite           # Database
├── out/                  # Artifacts
│   ├── bulks/           # Bulk structure files
│   ├── slabs/           # Slab structure files
│   └── runs/            # Run-specific artifacts
└── .calm/               # Internal workspace metadata
```

### Step 2: Add Bulk Structures

**From ASE Atoms:**

```python
from ase.build import bulk as ase_bulk

# Create bulk
lif_atoms = ase_bulk("LiF", crystalstructure="rocksalt", a=4.03, cubic=True)

# Add to workspace
bulk_lif = ws.add_bulk(
    atoms=lif_atoms,
    label="LiF",
    metadata={"source": "ASE", "structure": "rocksalt"},
)

print(f"Added bulk: {bulk_lif.id_short}")
print(f"  Formula: {bulk_lif.formula}")
print(f"  Space group: {bulk_lif.space_group}")
```

**Output:**

```
Added bulk: b_a1b2c3d4
  Formula: LiF
  Space group: Fm-3m (225)
```

**From POSCAR file:**

```python
from pathlib import Path

# Add from file
bulk_li2o = ws.add_bulk_from_poscar(
    path=Path("structures/Li2O.poscar"),
    label="Li2O",
    metadata={"source": "POSCAR", "structure": "antifluorite"},
)

print(f"Added bulk: {bulk_li2o.id_short}")
```

**From Materials Project:**

```python
# If you have MP (pymatgen) API key
from pymatgen.ext.matproj import MPRester

with MPRester("YOUR_API_KEY") as mpr:
    # Get structure from MP database
    structure = mpr.get_structure_by_material_id("mp-1009")  # LiF

    # Convert to ASE Atoms
    from pymatgen.io.ase import AseAtomsAdaptor
    adaptor = AseAtomsAdaptor()
    atoms = adaptor.get_atoms(structure)

    # Add to workspace
    bulk = ws.add_bulk(
        atoms=atoms,
        label="LiF_MP",
        metadata={"source": "MP database", "mp_id": "mp-1009"},
    )
```

### Step 3: Build Slabs

**Basic slab generation:**

```python
# Build slabs for common low-index surfaces
slabs_lif = ws.build_slabs(
    bulk_id=bulk_lif.id_short,
    millers=[(1, 0, 0), (1, 1, 0), (1, 1, 1)],
    params={
        "vacuum": 15.0,     # Å vacuum above slab
        "layers": 5,        # Number of atomic layers
    },
)

print(f"Built {len(slabs_lif)} LiF slabs")
for slab in slabs_lif:
    print(f"  {slab.id_short}: {slab.miller} - {slab.n_atoms} atoms")
```

**Output:**

```
Built 3 LiF slabs
  s_e1f2g3h4: (1, 0, 0) - 40 atoms
  s_i5j6k7l8: (1, 1, 0) - 56 atoms
  s_m9n0o1p2: (1, 1, 1) - 60 atoms
```

**Advanced: Automatic enumeration:**

```python
# Enumerate all surfaces up to Miller index 2
slabs_li2o = ws.build_slabs(
    bulk_id=bulk_li2o.id_short,
    max_miller=2,               # (±2, ±2, ±2) range
    params={
        "thickness": 12.0,      # Target thickness (Å)
        "vacuum": 15.0,
        "min_layers": 3,        # Minimum layers
    },
    enumerate_terminations=True,  # Enumerate unique terminations
)

print(f"Built {len(slabs_li2o)} Li₂O slabs (with termination enumeration)")
```

### Step 4: Start Prototype Search

**Basic search:**

```python
# Select slabs for matching
slab_a = slabs_lif[0]  # LiF(100)
slab_b = slabs_li2o[0]  # Li2O(100)

# Start prototype search
run = ws.start_prototype_search(
    slab_a.id_short,
    slab_b.id_short,
    n_candidates=100,    # Keep top 100 matches
    k_max=12,            # Maximum supercell index
    label="LiF_Li2O_search",
    metadata={"note": "Initial screening"},
)

print(f"Started run: {run.id_short}")
print(f"  Status: {run.status}")
```

**Output:**

$$
Started run: r_a1b2c3d4
  Status: pending
$$

**With custom parameters:**

```python
run = ws.start_prototype_search(
    slab_a.id_short,
    slab_b.id_short,
    n_candidates=200,
    k_max=15,
    w_match=0.7,             # Prioritize low strain (70% weight)
    eps_principal_max=0.12,   # Strict strain gate (12%)
    cond_max=8.0,            # Stricter conditioning
    label="LiF_Li2O_strict",
)
```

### Step 5: Execute Run Queue

**Synchronous execution:**

```python
from calm.project.runner import run_until_empty

# Execute all pending runs
run_until_empty(ws)
```

**Output:**

```
Executing run r_a1b2c3d4: prototype_search ...
  Enumerating supercells for slab A (LiF) ...
  Enumerating supercells for slab B (Li2O) ...
  Matching supercells ...
  Found 142 candidate interfaces
  Pruning refinements ...
  Kept 89 unique prototypes
  Computing Pareto front ...
  Found 15 Pareto-optimal candidates
Run r_a1b2c3d4 completed in 2.3s
```

**Check run status:**

```python
run_updated = ws.get_run(run.id_short)
print(f"Status: {run_updated.status}")
print(f"Completed: {run_updated.completed_at}")
```

### Step 6: Query Results

**List all prototypes:**

```python
# Get all prototypes for this run
prototypes = ws.list_prototypes(run=run.id_short)

print(f"Found {len(prototypes)} prototypes")
for i, proto in enumerate(prototypes[:5]):
    print(f"{i+1}. {proto.id_short}: "
          f"k_A={proto.k_A}, k_B={proto.k_B}, "
          f"d_cell={proto.d_cell:.3f}, "
          f"match_score={proto.match_score:.3f}")
```

**Output:**

```
Found 89 prototypes
1. p_e1f2g3h4: k_{A}=2, k_{B}=2, d_cell=0.123, match_score=0.27
2. p_i5j6k7l8: k_{A}=3, k_{B}=3, d_cell=0.145, match_score=0.32
3. p_m9n0o1p2: k_{A}=2, k_{B}=3, d_cell=0.156, match_score=0.34
4. p_q3r4s5t6: k_{A}=4, k_{B}=3, d_cell=0.167, match_score=0.38
5. p_u7v8w9x0: k_{A}=4, k_{B}=4, d_cell=0.151, match_score=0.36
```

**Filter Pareto-optimal:**

```python
# Only Pareto-optimal prototypes
pareto_protos = ws.list_prototypes(
    run=run.id_short,
    pareto=True,  # Filter to Pareto front
)

print(f"Pareto front has {len(pareto_protos)} candidates")
```

**Tabular view:**

```python
import pandas as pd

import pandas as pd

prototypes = ws.list_prototypes(run=run.id_short, limit=20)

df = pd.DataFrame([
    {
        "id_short": p.id_short,
        "natoms": p.natoms,
        "interface_area": p.interface_area,
        "hencky_norm": p.hencky_norm,
        "match_score": p.match_score,
        "is_pareto": p.is_pareto,
    }
    for p in prototypes
])

print(df[["id_short", "natoms", "interface_area", "hencky_norm", "match_score"]])
```

**Output:**

$$
      id_short  k_{A}  k_{B}  d_cell  d_size  match_score
0  p_e1f2g3h4    2    2   0.123   0.693        0.270
1  p_i5j6k7l8    3    3   0.145   1.099        0.320
2  p_m9n0o1p2    2    3   0.156   0.916        0.340
...
$$

### Step 7: Visualization

**Pareto front plot:**

```python
# Generate Pareto plot artifact
plot_path = ws.enrichment.pareto_plot(
    run_id=run.id_short,
    filename="pareto_front.png",
)

print(f"Saved plot: {plot_path}")
```

**Output:**

$$
Saved plot: my-interface-project/out/runs/r_a1b2c3d4/plots/pareto_front.png
$$

**Custom plot:**

```python
import matplotlib.pyplot as plt

# Get prototype data
prototypes = ws.list_prototypes(run=run.id_short)

# Extract data
d_cell = [p.d_cell for p in prototypes]
d_size = [p.d_size for p in prototypes]
pareto_flags = [p.is_pareto for p in prototypes]

# Plot
fig, ax = plt.subplots(figsize=(10, 6))

# All candidates (gray)
ax.scatter(
    [d for d, p in zip(d_cell, pareto_flags) if not p],
    [s for s, p in zip(d_size, pareto_flags) if not p],
    c='gray', alpha=0.5, s=30, label='All candidates'
)

# Pareto front (red)
ax.scatter(
    [d for d, p in zip(d_cell, pareto_flags) if p],
    [s for s, p in zip(d_size, pareto_flags) if p],
    c='red', s=100, marker='*', label='Pareto front', zorder=10
)

ax.set_xlabel('Affine-Invariant Strain ($d_{cell}$)')
ax.set_ylabel('Size Penalty ($d_{size}$)')
ax.set_title(f'LiF/Li₂O Interface Candidates (n={len(prototypes)})')
ax.legend()
ax.grid(True, alpha=0.3)

# Save as artifact
plot_path = ws.enrichment.put_plot(
    run_id=run.id_short,
    fig=fig,
    filename="custom_pareto.png"
)
plt.close(fig)

print(f"Saved custom plot: {plot_path}")
```

## Advanced Workflows

### Multiple Interface Systems

Search multiple material combinations systematically:

```python
# Define material pairs
pairs = [
    ("LiF", (1, 0, 0), "Li2O", (1, 1, 0)),
    ("LiF", (1, 1, 0), "Li2O", (1, 0, 0)),
    ("LiF", (1, 1, 1), "Li2O", (1, 1, 1)),
]

runs = []

for mat_a, miller_a, mat_b, miller_b in pairs:
    # Get slabs via helper: find bulk then list slabs
    def find_slab_by_material_and_miller(ws, material: str, miller: tuple[int, int, int]):
        bulk = ws.find_bulk_by_material(material)
        if bulk is None:
            raise KeyError(f"No bulk found for material {material!r}")

        for slab in ws.list_slabs(bulk=bulk.id_short):
            if tuple(slab.miller) == tuple(miller):
                return slab

        raise KeyError(f"No slab found for material {material!r} with Miller index {miller!r}")

    slab_a = find_slab_by_material_and_miller(ws, mat_a, miller_a)
    slab_b = find_slab_by_material_and_miller(ws, mat_b, miller_b)

    # Start search
    run = ws.start_prototype_search(
        slab_a.id_short,
        slab_b.id_short,
        n_candidates=100,
        label=f"{mat_a}{miller_a}_{mat_b}{miller_b}",
    )
    runs.append(run)

# Execute all
run_until_empty(ws)

# Compare results
for run in runs:
    protos = ws.list_prototypes(run=run.id_short, pareto=True)
    print(f"{run.label}: {len(protos)} Pareto candidates")
```

### Batch Export for DFT

Export top candidates for external DFT calculations:

```python
from pathlib import Path

# Get Pareto-optimal prototypes
prototypes = ws.list_prototypes(
    run=run.id_short,
    pareto=True,
)

# Sort by match score
prototypes.sort(key=lambda p: p.match_score)

# Export top 5
export_dir = Path("dft_inputs")
export_dir.mkdir(exist_ok=True)

for i, proto in enumerate(prototypes[:5]):
    # Get prototype details
    proto_detail = ws.get_prototype(proto.id_short)

    # Build interface at optimal strain partition (α=0.5)
    # from calm.interface.builder import build_interface_from_prototype
# Note: Internal API shown for illustration

    interface = build_interface_from_prototype(
        prototype=proto_detail,
        alpha=0.5,
        translation=(0.0, 0.0),
        z_padding=2.5,
    )

    # Export as POSCAR
    from ase.io import write
    poscar_path = export_dir / f"POSCAR_{i+1}_{proto.id_short}"
    write(poscar_path, interface, format="vasp")

    print(f"Exported {poscar_path}")
    print(f"  k_A={proto.k_A}, k_B={proto.k_B}")
    print(f"  d_cell={proto.d_cell:.3f}")
    print(f"  Atoms: {len(interface)}")
    print()
```

### Filtering and Analysis

**Filter by criteria:**

```python
# Get prototypes with specific properties
filtered = ws.list_prototypes(
    run=run.id_short,
    filters={
        'd_cell__lt': 0.15,      # Strain < 0.15
        'd_size__lt': 1.5,       # Size penalty < 1.5
        'k_A__lte': 6,           # k_A ≤ 6
        'k_B__lte': 6,           # k_B ≤ 6
    },
)

print(f"Found {len(filtered)} prototypes matching criteria")
```

**Aggregate statistics:**

```python
import numpy as np

prototypes = ws.list_prototypes(run=run.id_short)

d_cell_values = [p.d_cell for p in prototypes]
d_size_values = [p.d_size for p in prototypes]

print("Strain (d_cell) statistics:")
print(f"  Mean: {np.mean(d_cell_values):.3f}")
print(f"  Median: {np.median(d_cell_values):.3f}")
print(f"  Min: {np.min(d_cell_values):.3f}")
print(f"  Max: {np.max(d_cell_values):.3f}")

print("\nSize (d_size) statistics:")
print(f"  Mean: {np.mean(d_size_values):.3f}")
print(f"  Median: {np.median(d_size_values):.3f}")
print(f"  Min: {np.min(d_size_values):.3f}")
print(f"  Max: {np.max(d_size_values):.3f}")
```

### Cross-Run Queries

Compare results across multiple searches:

```python
# Get all prototype search runs
all_runs = ws.list_runs(kind="prototype_search")

print(f"Found {len(all_runs)} prototype search runs:")
for run in all_runs:
    protos = ws.list_prototypes(run=run.id_short)
    pareto = ws.list_prototypes(run=run.id_short, pareto=True)

    print(f"\n{run.label} ({run.id_short}):")
    print(f"  Completed: {run.completed_at}")
    print(f"  Total prototypes: {len(protos)}")
    print(f"  Pareto optimal: {len(pareto)}")

    if protos:
        best = min(protos, key=lambda p: p.match_score)
        print(f"  Best match_score: {best.match_score:.3f}")
```

## Workspace Organization

### Artifact Structure

```text
my-interface-project/
├── calm.sqlite                    # Database
├── out/
│   ├── bulks/
│   │   ├── b_a1b2c3d4/
│   │   │   ├── conventional.cif   # Standardized structure
│   │   │   ├── primitive.cif
│   │   │   └── metadata.json
│   │   └── b_e5f6g7h8/
│   ├── slabs/
│   │   ├── s_i9j0k1l2/
│   │   │   ├── slab.cif
│   │   │   ├── oriented.cif       # Rotated with z-normal
│   │   │   └── metadata.json
│   │   └── ...
│   └── runs/
│       ├── r_m3n4o5p6/           # Prototype search run
│       │   ├── logs/
│       │   │   └── run.log
│       │   ├── plots/
│       │   │   ├── pareto_front.png
│       │   │   └── histogram.png
│       │   ├── structures/
│       │   │   └── top_candidates.xyz
│       │   ├── tables/
│       │   │   └── prototypes.csv
│       │   └── metadata.json
│       └── ...
└── .calm/
    └── workspace.json             # Workspace metadata
```

### Querying Workspace Metadata

```python
# Workspace info (use properties and stats)
print(f"Workspace root: {ws.root}")
print(f"Database: {ws.db_path}")
print(f"Output directory: {ws.out_dir}")

stats = ws.get_workspace_stats()
print(f"\nRecord counts:")
print(f"  Bulks: {stats.get('bulks', 0)}")
print(f"  Slabs: {stats.get('slabs', 0)}")
print(f"  Prototypes: {stats.get('prototypes', 0)}")
print(f"  Runs: {stats.get('runs', 0)}")
```

## Best Practices

### 1. Descriptive Labels and Metadata

```python
# Good: Descriptive labels
bulk = ws.add_bulk(
    atoms=lif_atoms,
    label="LiF_rocksalt_exp",  # Clear, specific
    metadata={
        "source": "experimental",
        "reference": "DOI:10.1103/PhysRev.123.456",
        "lattice_param": 4.03,
        "temperature": "300K",
    },
)

# Better than: generic "bulk_1"
```

### 2. Systematic Miller Index Exploration

```python
# Start with low-index surfaces
low_index = [(1, 0, 0), (1, 1, 0), (1, 1, 1)]

# Then expand systematically
medium_index = [(2, 0, 0), (2, 1, 0), (2, 1, 1), (2, 2, 1)]

# High-index for special studies
high_index = [(3, 1, 0), (3, 1, 1), (3, 2, 1)]
```

### 3. Progressive Refinement

```python
# Phase 1: Quick screening (permissive)
run_screen = ws.start_prototype_search(
    slab_a.id_short,
    slab_b.id_short,
    k_max=10,
    eps_principal_max=0.20,  # Permissive
    n_candidates=50,
    label="screening",
)

# Phase 2: Focused search (strict)
run_refined = ws.start_prototype_search(
    slab_a.id_short,
    slab_b.id_short,
    k_max=15,
    eps_principal_max=0.12,  # Strict
    n_candidates=200,
    label="refined",
)
```

### 4. Version Control Workspace Configuration

```python
# workspace_config.py
WORKSPACE_ROOT = "my-project"

BULK_CONFIGS = {
    "LiF": {"source": "examples/Structures/LiF.poscar"},
    "Li2O": {"source": "examples/Structures/Li2O.poscar"},
}

SLAB_PARAMS = {
    "vacuum": 15.0,
    "layers": 5,
}

SEARCH_PARAMS = {
    "k_max": 12,
    "n_candidates": 100,
    "eps_principal_max": 0.15,
}

# Use in scripts
ws = open_workspace(WORKSPACE_ROOT)
# ...
```

## Troubleshooting

### Run Stuck in "pending" Status

**Symptom:** Run shows `status="pending"` after `run_until_empty`

**Cause:** Run executor not called or run failed silently

**Solution:**
```python
# Check run status
run = ws.get_run(run.id_short)
print(f"Status: {run.status}")
print(f"Error: {run.error_message}")

# Re-execute
run_until_empty(ws)
```

### Database Locked Error

**Symptom:** `sqlite3.OperationalError: database is locked`

**Cause:** Multiple processes accessing workspace simultaneously

**Solution:**
```python
# Use with context manager for proper cleanup
with open_workspace("my-project") as ws:
    # Do work
    pass

# Or ensure single process access
# (SQLite does not support concurrent writes well)
```

### Missing Pareto Front

**Symptom:** `pareto=True` filter returns empty

**Cause:** Pareto computation not run or failed

**Solution:**
```python
# Manually trigger Pareto computation
ws.enrichment.compute_pareto_front(run.id_short)

# Then query
pareto_protos = ws.list_prototypes(run=run.id_short, pareto=True)
```

### Large Workspace Size

**Symptom:** Workspace directory grows very large

**Solution:**
```python
# Clean up old artifacts
ws.maintenance.clean_artifacts(older_than_days=30)

# Vacuum database
ws.maintenance.vacuum_database()

# Archive old runs
ws.maintenance.archive_runs(run_ids=[...], archive_path="archive.tar.gz")
```

## Related Documentation

- [Tutorial 03: Prototype Search](../../tutorials/03_prototype_search.md) - Detailed walkthrough
- [One-Off Interface Workflow](one_off_interface.md) - Non-persistent alternative
- [Workspace Interface Optimization](project_interface_optimization.md) - Follow-up analyses
- [Algorithm: Surface-cell matching and strain optimization](../../mathematics/algorithms/surface-cell-matching-and-strain-optimization.md) - Mathematical details
- [Concepts: UIDs and Records](../../concepts/uids_and_records.md) - Database model
- [Concepts: Workspace Layout](../../concepts/project_layout.md) - File organization

## See Also

See the canonical Example Scripts listing at `docs/guides/examples/index.md` for runnable examples.
- [Public API Reference](../../reference/public_api.md) - Workspace methods
- [Glossary](../../glossary.md) - Terminology reference
