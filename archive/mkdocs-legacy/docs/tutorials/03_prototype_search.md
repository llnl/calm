# Tutorial 3: Prototype Search and Pareto Analysis

Learn how to search for compatible interface prototypes, understand match metrics, and use Pareto analysis to find optimal candidates.

## What You'll Learn

- How to run targeted prototype searches between specific surfaces
- How to search all Miller index combinations comprehensively
- Understanding match metrics: d_cell, d_size, match_score
- Pareto front visualization and interpretation
- Helper methods for grouping and filtering results
- Selecting best candidates for follow-up studies

## Prerequisites

- Completed [Tutorial 1: Workspace Basics](01_workspace_basics.md)
- Completed [Tutorial 2: Slab Generation](02_slab_generation.md)
- Workspace with optimized bulks and generated slabs
- Understanding of crystallography basics (Miller indices)

## Background: Interface Matching Problem

### What is a Prototype?

An **interface prototype** is a candidate geometry where two slabs can be joined with commensurate (matching) lattices. Finding prototypes involves:

1. **Supercell enumeration** - Generate larger unit cells for both surfaces
2. **Lattice matching** - Find supercell pairs with similar in-plane lattices
3. **Strain analysis** - Quantify lattice mismatch
4. **Ranking** - Score candidates by quality metrics

### Match Metrics

CALM uses three key metrics to evaluate prototypes:

**d_cell - Lattice Mismatch Strain**

$$
d_cell = 2 × \|log(G_{A}^{-1/2} \cdot G_{B} \cdot G_{A}^{-1/2})\|_{F}
$$

- Affine-invariant metric (coordinate-independent)
- Measures how much strain is needed to make lattices match
- Lower is better (less strain = more stable)
- Typical values: 0.0-0.3 (0-30% effective strain)

**d_size - Interface Size Penalty**

$$
d_size = (N_total - N_target)²
$$

- Penalizes interfaces far from target atom count
- Smaller interfaces = cheaper computation
- Larger interfaces = better accuracy but expensive
- Trade-off depends on your computational budget

**match_score - Combined Weighted Score**

$$
match_score = w_match × d̃_cell + (1 - w_match) × d̃_size
$$

- Combines lattice match and size into single score
- d̃_cell and d̃_size are normalized to [0,1] range
- w_match controls trade-off:
  - w_match=0.0: Only minimize size (cheap interfaces)
  - w_match=0.5: Balance both objectives (default)
  - w_match=1.0: Only minimize strain (best lattice match)
- Lower match_score = better overall candidate

### Pareto Front

In multi-objective optimization, no single solution is "best" in all criteria. The **Pareto front** contains **non-dominated** solutions:

- **Dominated**: Another solution is better in all objectives
- **Non-dominated (Pareto optimal)**: No solution is better in all objectives

For interfaces, we typically plot:
- **X-axis**: Interface size (number of atoms)
- **Y-axis**: Lattice strain (hencky_norm)

**Pareto-optimal** interfaces are on the lower-left frontier:
- Moving left: smaller but higher strain
- Moving down: lower strain but larger
- Points inside: dominated (worse in both)

## Step 1: Open Workspace and Organize Slabs

```python
from pathlib import Path
from calm.project import open_workspace
from calm.project import display_table

# Open workspace from Tutorial 02
root = Path("./my_workspace")
ws = open_workspace(root=root)

# Get all available slabs
all_slabs = ws.list_slabs(limit=100)
print(f"Total slabs in workspace: {len(all_slabs)}")

# Group slabs by material for easy selection
slabs_by_material = ws.enrichment.group_slabs_by_material(all_slabs)

for material, slabs in slabs_by_material.items():
    print(f"  {material}: {len(slabs)} slabs")
```

**Helper methods:**
- $group_slabs_by_material(slabs)$ - Organize by bulk material
- $group_slabs_by_miller(slabs)$ - Organize by Miller index

**Expected output:**
```
Total slabs in workspace: 12
  LiF: 6 slabs
  Li2O: 6 slabs
```

## Step 2: Group Slabs by Miller Index

```python
# Get LiF and Li2O slabs from material grouping
lif_slabs = slabs_by_material.get("LiF", [])
li2o_slabs = slabs_by_material.get("Li2O", [])

# Further group by Miller index for targeted searches
lif_by_miller = ws.enrichment.group_slabs_by_miller(lif_slabs)
li2o_by_miller = ws.enrichment.group_slabs_by_miller(li2o_slabs)

print(f"LiF Miller indices: {sorted(lif_by_miller.keys())}")
print(f"Li2O Miller indices: {sorted(li2o_by_miller.keys())}")
```

**Expected output:**
```
LiF Miller indices: ['(1, 0, 0)', '(1, 1, 0)', '(1, 1, 1)']
Li2O Miller indices: ['(1, 0, 0)', '(1, 1, 0)', '(1, 1, 1)']
```

This organization makes it easy to select specific surface orientations for targeted searches.

## Step 3: Targeted Prototype Search

### Select Specific Miller Index Pair

```python
# Select LiF-(100) and Li2O-(110) for targeted search
lif_100 = lif_by_miller.get("(1, 0, 0)", [None])[0]
li2o_110 = li2o_by_miller.get("(1, 1, 0)", [None])[0]

if lif_100 and li2o_110:
    print(f"Selected slabs:")
    print(f"  LiF: {lif_100.id_short}, Miller: {lif_100.miller}")
    print(f"  Li2O: {li2o_110.id_short}, Miller: {li2o_110.miller}")
```

### Configure Search Parameters

```python
# Run targeted prototype search
run_targeted = ws.start_prototype_search(
    lif_100.id_short,
    li2o_110.id_short,
    n_candidates=500,            # Return top 500 prototypes
    k_max=12,                    # Search up to 12×12 supercells
    w_match=0.5,                 # Balance lattice match and size
    eps_principal_max=0.15,      # Accept up to 15% principal strain
    N_at_max=1000,               # Limit interface size to 1000 atoms
    label="LiF-100 vs Li2O-110"  # Optional label for organization
)

print(f"Started prototype search: {run_targeted.id_short}")
```

**Parameter guide:**

| Parameter | Description | Typical Values | Effect |
|-----------|-------------|----------------|--------|
| `n_candidates` | Max prototypes to return | 100-500 | Higher = more options but slower |
| `k_max` | Max supercell determinant | 8-15 | Higher = larger supercells, more exhaustive |
| `w_match` | Weight for match score | 0.0-1.0 | 0=size, 0.5=balanced, 1=strain |
| `eps_principal_max` | Max principal strain (ln) | 0.10-0.20 | Larger = accept higher strain |
| `N_at_max` | Max total atoms | 500-2000 | Depends on computational budget |

**Choosing k_max:**
- **k_max = 8**: Fast, finds most common matches
- **k_max = 10**: Standard, good balance
- **k_max = 12**: Thorough, recommended for publication
- **k_max = 15+**: Very exhaustive, may find rare high-quality matches

**Choosing w_match:**
- **w_match = 0.0**: Prioritize small interfaces (fast DFT)
- **w_match = 0.5**: Balanced (default, recommended)
- **w_match = 0.7**: Emphasize lattice quality (less strain)
- **w_match = 1.0**: Only lattice match (ignore size)

## Step 4: Query and Display Results

```python
# Query all prototypes from this search
protos_all = ws.list_prototypes(run=run_targeted.id_short)
protos_pareto = ws.list_prototypes(run=run_targeted.id_short, pareto=True)

print(f"Results:")
print(f"  Total prototypes: {len(protos_all)}")
print(f"  Pareto optimal: {len(protos_pareto)}")

# Get enriched prototypes with computed properties
enriched = ws.enrichment.list_prototypes_enriched(
    run=run_targeted.id_short,
    limit=500
)

# Sort by match_score (lower is better)
enriched_sorted = sorted(enriched, key=lambda p: p.get("match_score", float("inf")))

# Display top 10
print("\nTop 10 prototypes by match_score:")
display_table(enriched_sorted[:10], table="prototypes")
```

**Expected output:**

$$
Results:
  Total prototypes: 147
  Pareto optimal: 23

Top 10 prototypes by match_score:
id_short   | na_xyz | nb_xyz | natoms | hencky_norm | match_score | pareto
-----------|--------|--------|--------|-------------|-------------|--------
p_a1b2c3d4 | (2,2)  | (2,2)  | 64     | 0.042       | 0.23        | True
p_e5f6g7h8 | (3,1)  | (1,3)  | 72     | 0.038       | 0.25        | True
p_i9j0k1l2 | (2,3)  | (3,2)  | 96     | 0.035       | 0.28        | True
...
$$

**Column descriptions:**
- `na_xyz`, `nb_xyz` - Supercell transformations (HNF matrices)
- `natoms` - Total atoms in interface
- `hencky_norm` - Strain magnitude (Frobenius norm)
- `match_score` - Weighted score (lower is better)
- `pareto` - Is this prototype on the Pareto front?

## Step 5: Visualize Pareto Front

```python
# Generate Pareto plot
plot_artifact = ws.visualization.pareto_plot(
    run_targeted.id_short,
    filename="pareto_LiF100_Li2O110.png",
    x="natoms",        # X-axis: number of atoms (size)
    y="hencky_norm"    # Y-axis: Hencky strain (quality)
)

plot_path = root / plot_artifact.uri.replace("file://", "")
print(f"Pareto plot saved: {plot_path}")
```

**Plot interpretation:**

```
         Low Strain (good)
                 ^
                 |
   Pareto front: █---█
                /     \
               /       \
              █         █
             /           \
          ● ● ● ● ● ● ● ● ●  ← Dominated points
          |               |
      Small             Large
    (cheap)          (expensive)
```

**Key insights:**
- **Red squares (█)**: Pareto-optimal prototypes (non-dominated)
- **Blue circles (●)**: Dominated prototypes (worse in both)
- **Lower-left is ideal**: Small size + low strain
- **Trade-off curve**: Moving left increases strain, moving down increases size

**Selecting from Pareto front:**
1. **Smallest Pareto**: Fastest DFT, acceptable strain
2. **Best lattice match**: Lowest strain, larger system
3. **Balanced**: Middle of Pareto front

## Step 6: Comprehensive Search Across All Miller Indices

For a complete study, search all Miller index combinations:

### Filter Slabs by Provenance

```python
# Find optimized bulks to ensure consistent provenance
lif_bulk = ws.find_bulk_by_material("LiF", kind="optimized")
li2o_bulk = ws.find_bulk_by_material("Li2O", kind="optimized")

# Get all slabs from these specific bulks
lif_slabs_all = [s for s in all_slabs
                 if getattr(s, "bulk_id_short", None) == lif_bulk.id_short]
li2o_slabs_all = [s for s in all_slabs
                  if getattr(s, "bulk_id_short", None) == li2o_bulk.id_short]

print(f"Slabs from optimized bulks:")
print(f"  LiF: {len(lif_slabs_all)} slabs")
print(f"  Li2O: {len(li2o_slabs_all)} slabs")
```

**Why filter by bulk?**
- Ensures all slabs use same calculator
- Consistent lattice parameters across searches
- Enables fair comparison between Miller index pairs

### Run Comprehensive Search

```python
# Run searches for all (slab_a, slab_b) combinations
comprehensive_runs = ws.run_miller_combination_search(
    lif_slabs_all,
    li2o_slabs_all,
    n_candidates=500,
    k_max=12,
    w_match=0.5,
    eps_principal_max=0.15,
    N_at_max=1000,
    generate_plots=True,    # Auto-generate individual plots
    x="natoms",
    y="hencky_norm",
)

print(f"Completed {len(comprehensive_runs)} searches")
```

**What this does:**
1. For each LiF slab, pair with each Li2O slab
2. Run prototype search for each pair
3. Generate individual Pareto plot for each pair
4. Return list of all run records

**Example:**
- 3 LiF Miller indices × 3 Li2O Miller indices = 9 searches
- Each search finds 100-300 prototypes
- Total: 900-2700 prototypes across all combinations

## Step 7: Aggregate Pareto Analysis

Combine results from all searches into single plot:

```python
# Extract run IDs
run_ids = [run.id_short for run in comprehensive_runs]

# Create aggregate Pareto plot
agg_plot = ws.visualization.pareto_plot_aggregate(
    run_ids,
    filename="pareto_aggregate_lif_li2o.png",
    x="natoms",
    y="hencky_norm",
)

agg_path = root / agg_plot.uri.replace("file://", "")
print(f"Aggregate Pareto plot: {agg_path}")
print(f"  Combines {len(comprehensive_runs)} Miller index combinations")
print(f"  Red squares show global Pareto front")
```

**Aggregate plot features:**
- **All prototypes** from all searches in one view
- **Global Pareto front** (red) - best across all Miller combinations
- **Per-run Pareto** (other colors) - best within each combination
- Identifies which Miller pair gives best interfaces

## Step 8: Pareto Summary Table

Display comprehensive analysis with helper method:

```python
# Display Pareto analysis with single call
ws.display_pareto_summary(
    run_ids,
    x="natoms",
    y="hencky_norm",
    show_per_run=True,   # Show Pareto prototypes from each search
    show_global=True,    # Show global Pareto front
)
```

**Expected output:**

```
====================================================================
PARETO ANALYSIS SUMMARY
====================================================================

Per-Run Pareto Fronts:
----------------------------------------------------------------------
Run: LiF-(100) vs Li2O-(100)
  Pareto prototypes: 12

  id_short   | natoms | hencky_norm | match_score
  -----------|--------|-------------|-------------
  p_abc123   | 48     | 0.051       | 0.22
  p_def456   | 64     | 0.042       | 0.23
  ...

----------------------------------------------------------------------
Run: LiF-(100) vs Li2O-(110)
  Pareto prototypes: 18
  ...

====================================================================
Global Pareto Front (Across All Searches):
====================================================================
  Total global Pareto optimal: 25

  id_short   | run_label           | natoms | hencky_norm | match_score
  -----------|---------------------|--------|-------------|-------------
  p_xyz789   | LiF-111 vs Li2O-111 | 56     | 0.035       | 0.19
  p_uvw012   | LiF-100 vs Li2O-100 | 64     | 0.038       | 0.21
  ...
```

**Key insights:**
- **Per-run Pareto**: Best interfaces within each Miller combination
- **Global Pareto**: Best interfaces across all combinations
- Identifies which Miller pairs produce highest quality matches

## Step 9: Select Candidates for Follow-up

Based on Pareto analysis, select candidates for optimization:

```python
# Get global Pareto front
global_pareto = ws.get_global_pareto_prototypes(run_ids)

# Select top 5 candidates by match_score
candidates_sorted = sorted(global_pareto, key=lambda p: p.match_score)
top_5 = candidates_sorted[:5]

print("Selected candidates for follow-up:")
for i, proto in enumerate(top_5, 1):
    print(f"  {i}. {proto.id_short}")
    print(f"     Slabs: {proto.slab_a_id_short} ↔ {proto.slab_b_id_short}")
    print(f"     Atoms: {proto.natoms}, Strain: {proto.hencky_norm:.3f}")
    print(f"     Interface area: {proto.interface_area:.3f}")
    print(f"     Match score: {proto.match_score:.3f}")
```

**Selection strategies:**

1. **Best overall**: Lowest match_score (balanced)
2. **Smallest**: Lowest natoms (fastest DFT)
3. **Best lattice match**: Lowest hencky_norm (lowest strain)
4. **Diverse set**: One from each Miller combination
5. **Size series**: Multiple sizes for convergence testing

**Next steps after selection:**
- [Tutorial 4: Follow-up Analyses](04_followups.md) - Optimize α and registry
- [Tutorial 5: Strain Analysis](05_strain_analysis.md) - Decompose strain tensors
- Export to POSCAR for DFT calculations

## Complete Example

```python
from pathlib import Path
from calm.project import open_workspace
from calm.project import display_table

# 1. Open workspace
root = Path("./my_workspace")
ws = open_workspace(root=root)

# 2. Organize slabs
all_slabs = ws.list_slabs(limit=100)
slabs_by_material = ws.enrichment.group_slabs_by_material(all_slabs)

lif_slabs = slabs_by_material.get("LiF", [])
li2o_slabs = slabs_by_material.get("Li2O", [])

# 3. Group by Miller index
lif_by_miller = ws.enrichment.group_slabs_by_miller(lif_slabs)
li2o_by_miller = ws.enrichment.group_slabs_by_miller(li2o_slabs)

# 4. Targeted search
lif_100 = lif_by_miller.get("(1, 0, 0)", [None])[0]
li2o_110 = li2o_by_miller.get("(1, 1, 0)", [None])[0]

run_targeted = ws.start_prototype_search(
    lif_100.id_short,
    li2o_110.id_short,
    n_candidates=500,
    k_max=12,
    w_match=0.5,
    eps_principal_max=0.15,
    N_at_max=1000,
    label="LiF-100 vs Li2O-110"
)

# 5. Query results
enriched = ws.enrichment.list_prototypes_enriched(
    run=run_targeted.id_short,
    limit=500
)
enriched_sorted = sorted(enriched, key=lambda p: p.get("match_score", float("inf")))
display_table(enriched_sorted[:10], table="prototypes")

# 6. Generate Pareto plot
plot_artifact = ws.visualization.pareto_plot(
    run_targeted.id_short,
    filename="pareto_targeted.png",
    x="natoms",
    y="hencky_norm"
)

# 7. Comprehensive search (optional)
lif_bulk = ws.find_bulk_by_material("LiF", kind="optimized")
li2o_bulk = ws.find_bulk_by_material("Li2O", kind="optimized")

lif_slabs_all = [s for s in all_slabs
                 if getattr(s, "bulk_id_short", None) == lif_bulk.id_short]
li2o_slabs_all = [s for s in all_slabs
                  if getattr(s, "bulk_id_short", None) == li2o_bulk.id_short]

comprehensive_runs = ws.run_miller_combination_search(
    lif_slabs_all,
    li2o_slabs_all,
    n_candidates=500,
    k_max=12,
    w_match=0.5,
    eps_principal_max=0.15,
    N_at_max=1000,
    generate_plots=True,
    x="natoms",
    y="hencky_norm",
)

# 8. Aggregate analysis
run_ids = [run.id_short for run in comprehensive_runs]

agg_plot = ws.visualization.pareto_plot_aggregate(
    run_ids,
    filename="pareto_aggregate.png",
    x="natoms",
    y="hencky_norm",
)

ws.display_pareto_summary(
    run_ids,
    x="natoms",
    y="hencky_norm",
    show_per_run=True,
    show_global=True,
)
```

## Key Takeaways

1. **Two Search Modes**
   - **Targeted**: Specific Miller index pair (fast, focused)
   - **Comprehensive**: All combinations (thorough, complete)

2. **Match Metrics Matter**
   - `d_cell`: Lattice mismatch (affine-invariant)
   - `d_size`: Interface size penalty
   - `match_score`: Weighted combination (tunable via w_match)

3. **Pareto Analysis is Powerful**
   - Identifies non-dominated solutions
   - No single "best" - trade-off between size and strain
   - Global Pareto shows best across all Miller pairs

4. **Helper Methods Simplify Workflow**
   - $group_slabs_by_material()$ - Organize by bulk
   - $group_slabs_by_miller()$ - Organize by surface
   - $run_miller_combination_search()$ - Comprehensive search
   - $display_pareto_summary()$ - One-liner analysis

5. **Provenance Filtering is Important**
   - Filter slabs by bulk_id to ensure consistency
   - Ensures same calculator across all searches
   - Enables fair comparison

6. **Parameter Tuning**
   - Start with defaults (k_max=10, w_match=0.5)
   - Increase k_max for more exhaustive search
   - Adjust w_match based on priorities (size vs strain)

## Troubleshooting

**No prototypes found:**
```python
# Check if slabs exist and have compatible Miller indices
print(f"Slab A: {slab_a.id_short}, Miller: {slab_a.miller}")
print(f"Slab B: {slab_b.id_short}, Miller: {slab_b.miller}")

# Check search parameters
# Try increasing k_max (more supercells)
# Try relaxing eps_principal_max (accept more strain)
```

**Too many prototypes (slow queries):**
```text
# Reduce n_candidates
run = ws.start_prototype_search(
    slab_a, slab_b,
    n_candidates=100,  # instead of 500
    ...
)

# Query with limit
protos = ws.list_prototypes(run=run.id_short, limit=50)
```

**Search takes too long:**
```python
# Reduce k_max (fewer supercells)
k_max=8  # instead of 12

# Reduce N_at_max (reject large interfaces early)
N_at_max=500  # instead of 1000
```

**Pareto front looks empty:**
```python
# Check that prototypes exist
protos = ws.list_prototypes(run=run.id_short)
print(f"Total prototypes: {len(protos)}")

# Check if axes are appropriate
# Try different axes: "cell_area", "aspect_ratio", "eps_max"
plot = ws.visualization.pareto_plot(
    run.id_short,
    x="cell_area",  # instead of natoms
    y="eps_max",    # instead of hencky_norm
)
```

**Aggregate plot is cluttered:**
```python
# Filter to only include specific runs
selected_runs = [run.id_short for run in comprehensive_runs[:5]]

# Use stricter Pareto filtering
agg_plot = ws.visualization.pareto_plot_aggregate(
    selected_runs,
    filename="pareto_filtered.png",
    x="natoms",
    y="hencky_norm",
    pareto_only=True,  # Only show Pareto points
)
```

## Understanding Strain Metrics

### Hencky Strain Norm

The `hencky_norm` is the **Frobenius norm** of the Hencky (logarithmic) strain tensor:

$$
\|E\|_{F} = sqrt(ε₁² + ε₂²)
$$

where ε₁ and ε₂ are principal strains.

**Interpretation:**
- $hencky_norm = 0.00$: Perfect lattice match (no strain)
- $hencky_norm = 0.05$: Small strain (~5% effective)
- $hencky_norm = 0.10$: Moderate strain (~10% effective)
- $hencky_norm = 0.15$: Large strain (~15% effective)
- $hencky_norm > 0.20$: Very large strain (may be unstable)

**Typical thresholds:**
- **Excellent**: hencky_norm < 0.05
- **Good**: hencky_norm < 0.10
- **Acceptable**: hencky_norm < 0.15
- **Questionable**: hencky_norm > 0.15

### Principal Strains

Individual principal strains are reported as:
- `eps_max`: Maximum principal strain
- `eps_min`: Minimum principal strain

These can have different signs:
- Both positive: Biaxial tension
- Both negative: Biaxial compression
- Opposite signs: One direction stretched, other compressed

## Next Steps

- **[Tutorial 4: Follow-up Analyses](04_followups.md)** - Optimize strain partition and registry
- **[Tutorial 5: Strain Analysis](05_strain_analysis.md)** - Decompose strain tensors
- **[Algorithm: Surface-cell matching and strain optimization](../mathematics/algorithms/surface-cell-matching-and-strain-optimization.md)** - Algorithm details

## Related Documentation

- 

- [API Reference: start_prototype_search](../reference/public_api.md)
- 

- [Glossary: Pareto Front](../glossary.md#pareto-front)

## Further Reading

**Multi-objective optimization:**
- Deb, K. (2001). "Multi-Objective Optimization using Evolutionary Algorithms." Wiley.
- Pareto efficiency: Wikipedia - [Pareto efficiency](https://en.wikipedia.org/wiki/Pareto_efficiency)

**Interface matching:**
- Zur & McGill (1984). "Lattice match: An application to heteroepitaxy." J. Appl. Phys.
- Romanov et al. (2003). "Strain-induced virtualization of interfaces in epitaxial layer structures." J. Appl. Phys.

**Strain metrics:**
- CALM manuscript (in preparation) - Affine-invariant strain metrics
 - [Algorithm: Strain Partitioning](../mathematics/algorithms/geodesic-strain-partitioning.md) - Mathematical details
