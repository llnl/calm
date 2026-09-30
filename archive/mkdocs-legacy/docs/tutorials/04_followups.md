# Tutorial 4: Follow-up Analyses

Learn how to optimize interface prototypes through strain partition scanning and registry search to find the lowest energy configurations.

## What You'll Learn

- How to run strain partition scans to optimize strain distribution (α parameter)
- Understanding strain partition plots and energy landscapes
- Creating derived interfaces from scan results
- Running registry searches to optimize atomic alignment
- Interpreting followup results and selecting best configurations
- Exporting optimized interfaces for DFT calculations

## Prerequisites

- Completed [Tutorial 1: Workspace Basics](01_workspace_basics.md)
- Completed [Tutorial 2: Slab Generation](02_slab_generation.md)
- Completed [Tutorial 3: Prototype Search](03_prototype_search.md)
- Workspace with Pareto-optimal prototypes
- Calculator configured (ML potential or DFT)

## Background: Follow-up Optimization

### Why Follow-up Analyses?

After finding candidate interface geometries (prototypes), we need to optimize two key degrees of freedom:

1. **Strain Partition (α)** - How to distribute lattice mismatch between materials
2. **Registry Shift** - In-plane translation for optimal atomic alignment

**Prototype search** identifies compatible lattice geometries but uses **default values**:
- Default α = 0.5 (symmetric strain distribution)
- Default registry = (0, 0) (no shift)

**Follow-up analyses** optimize these parameters to **minimize interface energy**.

### Strain Partition Parameter (α)

The strain partition parameter α ∈ [0, 1] controls how lattice mismatch is distributed:

**α = 0.0**: All strain on material B
- Material A is unstrained
- Material B deforms fully to match A
- Use when A is much stiffer than B

**α = 0.5**: Symmetric distribution
- Both materials share strain equally
- Default for initial prototypes
- Often close to optimal for similar materials

**α = 1.0**: All strain on material A
- Material B is unstrained
- Material A deforms fully to match B
- Use when B is much stiffer than A

**Optimal α** depends on:
- Elastic moduli (stiffer material resists deformation)
- Interface chemistry (charge transfer, bonding)
- Surface reconstructions

### Registry Shift

The **registry** is the in-plane translation between slabs at the interface:

```
Slab A:  O O O O O     ← Top surface layer
         ↓ (shift)
Slab B:  ■ ■ ■ ■ ■     ← Bottom surface layer
```

Different shifts create different atomic alignments:
- **Top-site**: Atom A above atom B
- **Hollow-site**: Atom A above interstitial
- **Bridge-site**: Atom A between two B atoms

**Optimal registry** minimizes interface energy via:
- Favorable bonding (chemical compatibility)
- Avoiding high-energy overlaps
- Balancing electrostatics and Van der Waals

### Energy Landscape

Interface energy is a function of both parameters:

$$
E_interface(α, registry)
$$

**Typical behavior:**
- **α scan**: U-shaped or V-shaped curve (one minimum)
- **Registry scan**: Multiple local minima (discrete symmetry)
- **Coupling**: Optimal α may depend on registry (weak coupling)

## Step 1: Open Workspace and Select Prototypes

```python
from pathlib import Path
from calm.project import open_workspace
from calm.project import display_table

# Open workspace from Tutorial 03
root = Path("./my_workspace")
ws = open_workspace(root=root)

# Get Pareto-optimal prototypes
pareto_prototypes = ws.list_prototypes(pareto=True, limit=1000)
print(f"Found {len(pareto_prototypes)} Pareto-optimal prototypes")

# Display enriched prototypes
pareto_enriched = ws.enrichment.list_prototypes_enriched(pareto=True, limit=1000)
display_table(pareto_enriched[:10], table="prototypes")
```

**Expected output:**

```
Found 25 Pareto-optimal prototypes

id_short   | na_xyz | nb_xyz | natoms | hencky_norm | match_score
-----------|--------|--------|--------|-------------|-------------
p_a1b2c3d4 | (2,2)  | (2,2)  | 64     | 0.042       | 0.23
p_e5f6g7h8 | (3,1)  | (1,3)  | 72     | 0.038       | 0.25
...
```

### Select Candidates for Follow-up

```python
# Select top 3 prototypes by match_score for detailed analysis
selected_prototypes = pareto_prototypes[:3]
prototype_ids = [p.id_short for p in selected_prototypes]

print(f"\nSelected {len(selected_prototypes)} prototypes for analysis:")
for p in selected_prototypes:
    print(f"  {p.id_short}: strain={p.hencky_norm:.4f}, atoms={p.natoms}")
```

**Selection strategies:**
- **Top 1-3**: Best candidates for intensive study
- **Top 10**: Diverse set for comparison
- **Size series**: Multiple sizes (50, 100, 200 atoms) for convergence
- **Strain series**: Low, medium, high strain representatives

## Step 2: Strain Partition Scan

### Configure and Run Scan

```python
# Run strain partition scan
scan_run = ws.start_strain_partition_scan(
    prototype_ids,
    alphas=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],  # 11 values
)

print(f"Strain scan run: {scan_run.id_short}")
print(f"Status: {scan_run.status}")
```

**Parameter guide:**

| Parameter | Description | Typical Values | Effect |
|-----------|-------------|----------------|--------|
| `prototype_ids` | List of prototypes to analyze | 1-10 IDs | More = thorough but slower |
| `alphas` | α values to test | 5-11 values | More = finer resolution |

**Choosing α values:**

**Coarse scan (fast):**
```python
alphas=[0.0, 0.25, 0.5, 0.75, 1.0]  # 5 points
```
- Quick initial survey
- Good for screening many prototypes

**Standard scan (recommended):**
```python
alphas=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]  # 11 points
```
- Detailed energy landscape
- Sufficient for publication
- Default for most studies

**Fine scan (high resolution):**
```python
alphas=[i*0.05 for i in range(21)]  # 21 points (0.00, 0.05, ..., 1.00)
```
- Very detailed curve
- Use when energy landscape is complex
- Expensive for large interfaces

**Focused scan (near minimum):**
```python
alphas=[0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7]  # Zoom into α=0.4-0.7
```
- Refine after coarse scan
- High resolution near suspected minimum

### What Happens During Scan

For each prototype and each α value:

1. **Build interface structure**
   - Apply geodesic strain partition at α
   - Compute deformation gradients F_A, F_B
   - Deform atomic positions
   - Set up interface geometry (separation, vacuum)

2. **Compute energy**
   - Trace calculator provenance: Prototype → Slab → Bulk → Calculator
   - Use same calculator that relaxed the parent bulks
   - Evaluate single-point energy (no relaxation)
   - Return energy per interface area (eV/Å²)

3. **Store results**
   - Save derived interface structure
   - Record energy, α, provenance
   - Link to parent prototype

## Step 3: Query and Display Scan Results

```python
# Get scan results
followup_results = ws.enrichment.list_followup_results_enriched(
    run=scan_run.id_short,
    kind="strain_partition_scan"
)

print(f"\nStrain scan results: {len(followup_results)} configurations analyzed")

# Display results table
display_table(followup_results, table="followups", max_width=0)
```

**Expected output:**

```
Strain scan results: 33 configurations analyzed

id_short   | proto_id   | alpha | energy_per_area | score
-----------|------------|-------|-----------------|--------
f_abc123   | p_a1b2c3d4 | 0.0   | 0.452          | 0.452
f_def456   | p_a1b2c3d4 | 0.1   | 0.389          | 0.389
f_ghi789   | p_a1b2c3d4 | 0.2   | 0.312          | 0.312
f_jkl012   | p_a1b2c3d4 | 0.3   | 0.248          | 0.248
f_mno345   | p_a1b2c3d4 | 0.4   | 0.203          | 0.203  ← Minimum
f_pqr678   | p_a1b2c3d4 | 0.5   | 0.187          | 0.187  ← Near minimum
f_stu901   | p_a1b2c3d4 | 0.6   | 0.198          | 0.198
f_vwx234   | p_a1b2c3d4 | 0.7   | 0.245          | 0.245
...
```

**Column descriptions:**
- `id_short` - Followup result identifier
- `proto_id` - Parent prototype
- `alpha` - Strain partition parameter
- `energy_per_area` - Interface energy (eV/Å²)
- `score` - Same as energy_per_area for strain scans

**Energy interpretation:**

| Energy (eV/Å²) | Quality | Interpretation |
|----------------|---------|----------------|
| < 0.05 | Excellent | Very stable, strong bonding |
| 0.05-0.15 | Good | Stable interface |
| 0.15-0.30 | Moderate | Acceptable for study |
| 0.30-0.50 | Poor | High energy, strain dominates |
| > 0.50 | Very poor | Likely unstable |

**Note:** Absolute values depend on calculator and materials. **Compare relative values** within a scan.

## Step 4: Visualize Strain Partition Plot

```python
# Generate strain partition plot
plot_artifact = ws.visualization.strain_partition_plot(
    scan_run.id_short,
    filename="strain_partition.png"
)

plot_path = root / plot_artifact.uri.replace("file://", "")
print(f"Strain partition plot saved: {plot_path}")
```

**Plot interpretation:**

```
Energy
  ^
  |
  |     ●                              ●     ← High energy at extremes
  |       ●                          ●       (All strain on one material)
  |         ●                      ●
  |           ●                  ●
  |             ●              ●
  |               ●          ●
  |                 ●      ●
  |                   ★★★★              ← Minimum (optimal α)
  |
  +----------------------------------------> α
  0.0           0.5           1.0
  (All on B)  (Symmetric)  (All on A)
```

**Common patterns:**

1. **V-shaped (symmetric materials)**
   - Minimum at α ≈ 0.5
   - Materials have similar elastic properties
   - Symmetric distribution is optimal

2. **U-shaped (skewed minimum)**
   - Minimum at α ≠ 0.5 (e.g., α = 0.3 or 0.7)
   - Materials have different stiffness
   - More strain on softer material

3. **Asymmetric (one steep side)**
   - Steep increase on one side
   - One material strongly resists deformation
   - Optimal to load softer material

4. **Flat minimum (insensitive)**
   - Broad, shallow minimum
   - Energy relatively insensitive to α
   - Many α values acceptable

**Key insights:**
- **Minimum α**: Lowest energy strain distribution
- **Curvature**: Sharpness indicates sensitivity
- **Asymmetry**: Reveals which material prefers strain
- **Energy range**: Total variation shows importance of optimization

## Step 5: Create Derived Interfaces

After identifying optimal α values, create interface structures:

```python
# Create derived interfaces from scan results
interfaces = ws.derive_interfaces_from_strain_partition_scan(
    scan_run.id_short,
    label="Strain-optimized"
)

print(f"Created {len(interfaces)} derived interfaces")

# Display interface information
for iface in interfaces:
    print(f"  {iface.id_short}: α={iface.strain_alpha}, parent={iface.prototype_id_short}")
```

**What this does:**
1. Identifies optimal α for each prototype (minimum energy)
2. Creates derived interface record with optimized α
3. Links to parent prototype for provenance
4. Stores interface structure (atoms object)
5. Ready for further analysis or export

**Derived interface properties:**
- `strain_alpha` - Optimized strain partition parameter
- `prototype_id_short` - Parent prototype
- `slab_a_id_short`, `slab_b_id_short` - Component slabs
- `label` - User-specified label for organization

## Step 6: Registry Search

Now optimize atomic alignment for the derived interfaces:

### Configure and Run Registry Search

```python
# Select interfaces for registry optimization
interface_ids = [iface.id_short for iface in interfaces[:3]]

# Run registry search
registry_run = ws.start_registry_search(
    interface_ids,
    grid_config={"n_steps": 100},  # 100 search steps
)

print(f"Registry search run: {registry_run.id_short}")
print(f"Status: {registry_run.status}")
```

**Parameter guide:**

| Parameter | Description | Typical Values | Effect |
|-----------|-------------|----------------|--------|
| `interface_ids` | List of interfaces to optimize | 1-5 IDs | More = slower |
| `n_steps` | Number of search steps | 50-200 | More = thorough but expensive |

**Choosing n_steps:**

- **n_steps = 25**: Quick test (may miss minimum)
- **n_steps = 50**: Reasonable for initial screening
- **n_steps = 100**: Standard for publication (recommended)
- **n_steps = 200**: Very thorough (diminishing returns)

**Algorithm:** Deterministic sampling with energy evaluation
1. Sample registry grid points (n_steps total)
2. For each point:
   - Translate slab B relative to slab A
   - Build interface structure
   - Evaluate energy with calculator
3. Return optimal shift (minimum energy)

### Query Registry Search Results

```python
# Get registry search results
registry_results = ws.enrichment.list_followup_results_enriched(
    run=registry_run.id_short,
    kind="registry_search"
)

print(f"\nRegistry search results: {len(registry_results)} interfaces analyzed")
display_table(registry_results, table="followups", max_width=0)
```

**Expected output:**

```
Registry search results: 3 interfaces analyzed

id_short   | interface_id | shift_{a} | shift_{b} | energy_per_area | score
-----------|--------------|---------|---------|-----------------|--------
f_abc123   | i_xyz789     | 0.125   | 0.333   | 0.082          | 0.082
f_def456   | i_uvw012     | 0.250   | 0.500   | 0.095          | 0.095
f_ghi789   | i_rst345     | 0.000   | 0.000   | 0.103          | 0.103
```

**Column descriptions:**
- `shift_a`, `shift_b` - Optimal registry shift in fractional coordinates [0, 1)
- `energy_per_area` - Minimum interface energy found (eV/Å²)
- `score` - Same as energy_per_area for registry searches

**Shift interpretation:**
- **(0.0, 0.0)**: No shift (default stacking)
- **(0.5, 0.5)**: Half-cell shift (bridge sites)
- **(0.33, 0.67)**: Fractional shift (complex registry)

**Typical energy improvement:**
- 10-30% reduction vs default registry
- Larger for systems with strong directionality
- Small for systems with weak interface interactions

## Step 7: Examine All Derived Interfaces

```python
# Get all derived interfaces
all_interfaces = ws.enrichment.list_derived_interfaces_enriched(limit=100)
print(f"Total derived interfaces in workspace: {len(all_interfaces)}")

# Display detailed information
for iface in all_interfaces[:5]:
    print(f"\n{iface['id_short']}: {iface['label']}")
    if iface['strain_alpha'] is not None:
        print(f"  → Strain α = {iface['strain_alpha']:.3f}")
    if iface['registry_shift_frac_a'] is not None:
        shift_a = iface['registry_shift_frac_a']
        shift_b = iface['registry_shift_frac_b']
        print(f"  → Registry shift = ({shift_a:.3f}, {shift_b:.3f})")
    print(f"  → Atoms: {iface['natoms']}")
    print(f"  → Parent: {iface['prototype_id_short']}")
```

### Display Interface Table

```python
# Query interface objects
interfaces_obj = ws.list_derived_interfaces(limit=10)
display_table(interfaces_obj, table="interfaces")
```

**Expected output:**

```
id_short   | proto_id   | alpha | shift_{a} | shift_{b} | natoms | label
-----------|------------|-------|---------|---------|--------|------------------
i_abc123   | p_xyz789   | 0.45  | 0.125   | 0.333   | 64     | Strain-optimized
i_def456   | p_uvw012   | 0.50  | 0.250   | 0.500   | 72     | Strain-optimized
i_ghi789   | p_rst345   | 0.40  | 0.000   | 0.000   | 96     | Strain-optimized
```

## Step 8: Export Optimized Interfaces

```python
# Export derived interfaces as POSCAR files
interface_dir = root / "derived_interfaces"

exported_files = ws.export_derived_interfaces_as_poscar(
    interface_dir,
    interface_ids=[iface.id_short for iface in interfaces_obj],
    include_metadata=True,
)

print(f"\nExported {len(exported_files)} POSCAR files to: {interface_dir}")
print("\nThese files can be:")
print("  • Visualized in VESTA, OVITO, or other structure viewers")
print("  • Used as input for DFT calculations (VASP, QE, etc.)")
print("  • Further analyzed with ASE or pymatgen")
```

**Filename format:**

$$
{id_short}_{label}_{proto_id}.vasp
$$

**Examples:**
- $i_abc123_Strain-optimized_p_xyz789.vasp$
- $i_def456_Strain-optimized_p_uvw012.vasp$

**Metadata sidecar files** (if `include_metadata=True`):
- JSON files with provenance, α, registry shift
- `{id_short}_metadata.json`

## Step 9: Basic Strain Analysis

Analyze strain tensors for selected prototypes:

```python
# Analyze strain for first prototype at optimal α
proto_id = selected_prototypes[0].id_short
alpha_opt = 0.5  # Or use optimal α from scan

print(f"Analyzing strain for {proto_id} at α={alpha_opt}:\n")

strain_info = ws.analysis.analyze_prototype_strain(proto_id, alpha=alpha_opt)

# Display strain metrics for both slabs
for slab_name in ['slab_A', 'slab_B']:
    slab = strain_info[slab_name]

    print(f"{slab_name}:")
    print(f"  Principal strains: ε₁={slab['principal_strains'][0]:+.5f}, "
          f"ε₂={slab['principal_strains'][1]:+.5f}")
    print(f"  Frobenius norms:")
    print(f"    ||E||_F       = {slab['norm_E']:.5f}  (total strain)")
    print(f"    ||E_area||_F  = {slab['norm_E_area']:.5f}  (area component)")
    print(f"    ||E_shape||_F = {slab['norm_E_shape']:.5f}  (shape component)")
    print(f"  Trace(E) = {slab['trace_E']:+.5f}  (ln of area ratio)\n")
```

**Expected output:**

```
Analyzing strain for p_abc123 at α=0.5:

slab_{A}:
  Principal strains: ε₁=+0.0326, ε₂=+0.0326
  Frobenius norms:
    \|E\|_{F}       = 0.04612  (total strain)
    \|E_area\|_{F}  = 0.04612  (area component)
    \|E_shape\|_{F} = 0.00000  (shape component)
  Trace(E) = +0.0652  (ln of area ratio)

slab_{B}:
  Principal strains: ε₁=-0.0320, ε₂=-0.0320
  Frobenius norms:
    \|E\|_{F}       = 0.04525  (total strain)
    \|E_area\|_{F}  = 0.04525  (area component)
    \|E_shape\|_{F} = 0.00000  (shape component)
  Trace(E) = -0.0640  (ln of area ratio)
```

**Strain interpretation:**
- **Principal strains** (ε₁, ε₂): Eigenvalues of strain tensor
  - Positive: Tensile (stretching)
  - Negative: Compressive (squeezing)
- **||E||_F**: Total Frobenius norm (overall magnitude)
- **||E_area||_F**: Isotropic component (area change)
- **||E_shape||_F**: Deviatoric component (shape distortion)
- **Trace(E)**: Sum of principal strains (area ratio)

**Note:** See [Tutorial 5: Strain Analysis](05_strain_analysis.md) for comprehensive strain decomposition.

## Complete Example

```python
from pathlib import Path
from calm.project import open_workspace
from calm.project import display_table

# 1. Open workspace and get Pareto prototypes
root = Path("./my_workspace")
ws = open_workspace(root=root)

pareto_prototypes = ws.list_prototypes(pareto=True, limit=1000)
selected_prototypes = pareto_prototypes[:3]
prototype_ids = [p.id_short for p in selected_prototypes]

print(f"Selected {len(selected_prototypes)} prototypes for analysis")

# 2. Run strain partition scan
scan_run = ws.start_strain_partition_scan(
    prototype_ids,
    alphas=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
)

# 3. Query scan results
followup_results = ws.enrichment.list_followup_results_enriched(
    run=scan_run.id_short,
    kind="strain_partition_scan"
)
display_table(followup_results, table="followups")

# 4. Generate strain partition plot
plot_artifact = ws.visualization.strain_partition_plot(
    scan_run.id_short,
    filename="strain_partition.png"
)

# 5. Create derived interfaces from scan
interfaces = ws.derive_interfaces_from_strain_partition_scan(
    scan_run.id_short,
    label="Strain-optimized"
)

print(f"Created {len(interfaces)} derived interfaces")

# 6. Run registry search
interface_ids = [iface.id_short for iface in interfaces[:3]]
registry_run = ws.start_registry_search(
    interface_ids,
    grid_config={"n_steps": 100},
)

# 7. Query registry results
registry_results = ws.enrichment.list_followup_results_enriched(
    run=registry_run.id_short,
    kind="registry_search"
)
display_table(registry_results, table="followups")

# 8. Export optimized interfaces
interface_dir = root / "derived_interfaces"
exported = ws.export_derived_interfaces_as_poscar(
    interface_dir,
    interface_ids=[iface.id_short for iface in interfaces],
    include_metadata=True,
)

print(f"Exported {len(exported)} interfaces to {interface_dir}")

# 9. Analyze strain for selected prototype
proto_id = selected_prototypes[0].id_short
strain_info = ws.analysis.analyze_prototype_strain(proto_id, alpha=0.5)

for slab_name in ['slab_A', 'slab_B']:
    slab = strain_info[slab_name]
    print(f"{slab_name}: ε₁={slab['principal_strains'][0]:+.5f}, "
          f"ε₂={slab['principal_strains'][1]:+.5f}")
```

## Key Takeaways

1. **Two-Stage Optimization**
   - **Stage 1**: Optimize strain partition (α)
   - **Stage 2**: Optimize registry shift
   - Sequential approach is efficient

2. **Strain Partition Matters**
   - 10-50% energy variation across α range
   - Optimal α depends on material properties
   - Symmetric (α=0.5) often near optimal for similar materials

3. **Registry Optimization is Critical**
   - 10-30% energy reduction possible
   - Multiple local minima common
   - Requires sufficient sampling (n_steps ≥ 100)

4. **Calculator Integration is Seamless**
   - Automatic provenance tracing
   - Uses same calculator as bulk relaxation
   - No manual configuration needed

5. **Derived Interfaces are Production-Ready**
   - Optimized for both strain and registry
   - Exportable to standard formats
   - Ready for DFT refinement or analysis

6. **Energy-Driven Selection**
   - Compare energies across prototypes
   - Select lowest energy configurations
   - Consider computational cost vs accuracy

## Troubleshooting

**Scan takes too long:**
```python
# Reduce number of prototypes
prototype_ids = prototype_ids[:1]  # Just analyze 1

# Use coarser α scan
alphas=[0.0, 0.25, 0.5, 0.75, 1.0]  # 5 points instead of 11

# Reduce registry search steps
grid_config={"n_steps": 50}  # Instead of 100
```

**Energy values seem wrong:**
```python
# Check calculator provenance
proto = ws.get_prototype(proto_id)
slab_a = ws.get_slab(proto.slab_a_uid)
bulk_a = ws.get_bulk(slab_a.bulk_uid)
print(f"Calculator: {bulk_a.optimized_with}")

# Verify calculator is still available
calc_spec = bulk_a.optimized_with
# Check that calculator family/model are valid
```

**No clear minimum in α scan:**
```python
# Check energy range
energies = [r['energy_per_area'] for r in followup_results]
print(f"Energy range: {min(energies):.4f} - {max(energies):.4f}")

# If range is very small (< 0.01), energy is insensitive to α
# This is OK - any α near minimum is acceptable

# Try finer scan near suspected minimum
alphas=[0.4, 0.42, 0.44, 0.46, 0.48, 0.5, 0.52, 0.54, 0.56, 0.58, 0.6]
```

**Registry search finds default (0, 0):**
```python
# Increase sampling
grid_config={"n_steps": 200}

# Check if interface has strong periodicity
# If energy landscape is very flat, (0,0) may be correct

# Verify structure is reasonable
iface = ws.get_derived_interface(interface_id)
atoms = iface.atoms
# Visualize to check for overlaps or gaps
```

**Derived interfaces not created:**
```python
# Check scan completed successfully
scan_run = ws.get_run(scan_run.id_short)
print(f"Status: {scan_run.status}")

# If status != "done", scan may have failed
# Check for error messages in payload

# Manually create a persisted derived-interface record for α=0.5
interface = ws.create_derived_interface(
    prototype=proto_id,
    strain_alpha=0.5,
    label="Manual",
)
```

## Understanding Energy Values

### Absolute vs Relative Energies

**Important:** Interface energies from ML potentials are **relative** predictions:

- ✅ **Valid**: Comparing energies within same material system
- ✅ **Valid**: Identifying optimal α or registry
- ✅ **Valid**: Ranking candidates
- ❌ **Invalid**: Comparing different material pairs
- ❌ **Invalid**: Predicting absolute formation energies

**Example:**

```
System LiF/Li2O:
  α=0.3: 0.203 eV/Å²  ← Best for this system
  α=0.5: 0.187 eV/Å²
  α=0.7: 0.245 eV/Å²

System MgO/Al2O3:
  α=0.4: 0.156 eV/Å²  ← Cannot compare to LiF/Li2O
  α=0.5: 0.142 eV/Å²
```

### Energy Components

Total interface energy includes:
- **Elastic strain** - Deformation energy
- **Chemical bonding** - Interface bonds
- **Electrostatics** - Charge redistribution
- **Surface energy** - Free surface contributions

ML potentials approximate total energy but may have systematic errors.

**Best practice:** Use DFT to refine final candidates.

## Next Steps

- **[Tutorial 5: Strain Analysis](05_strain_analysis.md)** - Comprehensive strain decomposition
- **DFT Refinement** - Export interfaces and run ab initio calculations
-- **[Algorithm: Strain Partitioning](../mathematics/algorithms/geodesic-strain-partitioning.md)** - Mathematical details

## Related Documentation

- <!-- [Concepts: Derived Interfaces](../concepts/derived_interfaces.md) (TODO: create derived_interfaces.md) -->
- [API Reference: start_strain_partition_scan](../reference/public_api.md)
- [API Reference: start_registry_search](../reference/public_api.md)
See runnable examples in the Example Scripts guide: `docs/guides/examples/index.md`.

## Further Reading

**Strain partitioning:**
- CALM manuscript (in preparation) - Geodesic strain distribution
-- [Algorithm: Geodesic Strain Partitioning](../mathematics/algorithms/geodesic-strain-partitioning.md)

**Registry optimization:**
- Batyrev & Kleinman (1994). "Ab initio calculations of the electronic and geometric structure of the Ge-GaAs(001) interface." Phys. Rev. B.
- Zunger (1997). "First-principles statistical mechanics of semiconductor alloys and intermetallic compounds." NATO ASI Series.

**Interface energy:**
- Shang et al. (2010). "First-principles thermodynamics from phonon and Debye model: Application to Ni and Ni3Al." Comput. Mater. Sci.
