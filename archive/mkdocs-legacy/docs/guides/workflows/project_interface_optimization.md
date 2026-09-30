# Interface Optimization Workflow (Workspace)

Run systematic follow-up analyses on interface prototypes: strain partition scans, registry searches, and energy evaluations.

## Overview

After identifying candidate prototypes, **follow-up optimization** refines them by:

- **Strain partition scanning** - Find optimal α (how strain is distributed)
- **Registry search** - Find optimal in-plane translation
- **Energy evaluation** - Compute interfacial energies with ML/DFT
- **Derived interfaces** - Create optimized interface structures

**Workspace benefits:**
- Automatic artifact organization
- Provenance tracking (prototype → scan → interface)
- Reproducible UIDs
- Batch processing support

## Complete Optimization Workflow

### Step 1: Select Prototype Candidates

Start with a completed prototype search:

```python
from calm.project import open_workspace

ws = open_workspace("my-interface-project")

# Get prototypes from search run
run_id = "r_a1b2c3d4"  # Your prototype search run
prototypes = ws.list_prototypes(
    run=run_id,
    pareto=True,  # Only Pareto-optimal
)

print(f"Found {len(prototypes)} Pareto candidates")

# Select top 5 for follow-up
selected = sorted(prototypes, key=lambda p: p.match_score)[:5]
proto_ids = [p.id_short for p in selected]

print(f"Selected {len(proto_ids)} for optimization:")
for i, pid in enumerate(proto_ids):
    proto = next(p for p in selected if p.id_short == pid)
    print(f"  {i+1}. {pid}: k_A={proto.k_A}, k_B={proto.k_B}, "
          f"d_cell={proto.d_cell:.3f}")
```

**Output:**

```
Found 15 Pareto candidates
Selected 5 for optimization:
  1. p_e1f2g3h4: k_{A}=2, k_{B}=2, d_cell=0.123
  2. p_i5j6k7l8: k_{A}=3, k_{B}=3, d_cell=0.145
  3. p_m9n0o1p2: k_{A}=2, k_{B}=3, d_cell=0.156
  4. p_q3r4s5t6: k_{A}=4, k_{B}=3, d_cell=0.167
  5. p_u7v8w9x0: k_{A}=4, k_{B}=4, d_cell=0.151
```

### Step 2: Strain Partition Scan

Find optimal strain distribution (α parameter):

```python
from calm.calculators import get_calculator

# Define strain partition values to scan
alphas = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]

# Configure calculator
calc_spec = {
    "family": "grace",
    "model": "GRACE-2L-OMAT",
    "device": "cpu",
}

# Start strain partition scan
scan_run = ws.start_strain_partition_scan(
    prototype_ids=proto_ids,
    alphas=alphas,
    calculator_spec=calc_spec,
    relax=True,           # Relax atomic positions
    fmax=0.05,            # eV/Å convergence
    label="strain_scan_top5",
    metadata={"note": "Scanning optimal strain partition"},
)

print(f"Started scan run: {scan_run.id_short}")
```

**Execute scan:**

```python
from calm.project.runner import run_until_empty

# This will create derived interfaces for each (prototype, alpha) pair
# and evaluate their energies
run_until_empty(ws)
```

**Output:**

```
Executing run r_x1y2z3w4: strain_partition_scan ...
  Processing prototype p_e1f2g3h4 (1/5) ...
    α=0.0: Building interface ... Relaxing ... E=-1325.234 eV
    α=0.1: Building interface ... Relaxing ... E=-1328.156 eV
    α=0.2: Building interface ... Relaxing ... E=-1331.892 eV
    ...
    α=1.0: Building interface ... Relaxing ... E=-1326.445 eV
  Processing prototype p_i5j6k7l8 (2/5) ...
    ...
Run completed in 145.3s
```

### Step 3: Analyze Strain Scan Results

**Query results:**

```python
# Get scan results for all prototypes
results = ws.list_derived_interfaces(
    run=scan_run.id_short,
)

print(f"Generated {len(results)} derived interfaces")

# Group by prototype
from collections import defaultdict
by_proto = defaultdict(list)

for result in results:
    by_proto[result.prototype_id].append(result)

# Find optimal alpha for each prototype
for proto_id, ifaces in by_proto.items():
    # Sort by energy
    ifaces.sort(key=lambda i: i.energy_total)
    best = ifaces[0]

    print(f"\nPrototype {proto_id}:")
    print(f"  Optimal α = {best.alpha:.1f}")
    print(f"  Energy = {best.energy_total:.3f} eV")
    print(f"  Interface ID: {best.id_short}")
```

**Output:**

```
Generated 55 derived interfaces

Prototype p_e1f2g3h4:
  Optimal α = 0.4
  Energy = -1332.156 eV
  Interface ID: d_a1b2c3d4

Prototype p_i5j6k7l8:
  Optimal α = 0.5
  Energy = -1889.234 eV
  Interface ID: d_e5f6g7h8
...
```

**Visualize energy landscape:**

```python
import matplotlib.pyplot as plt
import numpy as np

fig, axes = plt.subplots(2, 3, figsize=(15, 10))
axes = axes.flatten()

for idx, (proto_id, ifaces) in enumerate(list(by_proto.items())[:5]):
    ax = axes[idx]

    # Extract data
    alphas = [i.alpha for i in ifaces]
    energies = [i.energy_total for i in ifaces]

    # Sort by alpha
    sorted_pairs = sorted(zip(alphas, energies))
    alphas, energies = zip(*sorted_pairs)

    # Plot
    ax.plot(alphas, energies, 'o-', linewidth=2, markersize=8)
    ax.set_xlabel('Strain Partition α')
    ax.set_ylabel('Total Energy (eV)')
    ax.set_title(f'Prototype {proto_id[:8]}...')
    ax.grid(True, alpha=0.3)

    # Mark minimum
    min_idx = np.argmin(energies)
    ax.axvline(alphas[min_idx], color='red', linestyle='--', alpha=0.5)

# Hide empty subplot
axes[5].axis('off')

plt.tight_layout()

# Save as artifact
plot_path = ws.enrichment.put_plot(
    run_id=scan_run.id_short,
    fig=fig,
    filename="strain_landscapes.png"
)
plt.close()

print(f"Saved plot: {plot_path}")
```

### Step 4: Registry Search

Optimize in-plane translation for best interfaces:

```python
# Select best interface from each prototype
best_interface_ids = []
for proto_id, ifaces in by_proto.items():
    best = min(ifaces, key=lambda i: i.energy_total)
    best_interface_ids.append(best.id_short)

print(f"Selected {len(best_interface_ids)} interfaces for registry search")

# Start registry search
registry_run = ws.start_registry_search(
    derived_interface_ids=best_interface_ids,
    n_steps=400,           # Monte Carlo steps
    step_scale=0.25,       # Translation step size
    temperature=0.1,       # MC temperature
    n_seeds=5,             # Multiple random seeds
    calculator_spec=calc_spec,
    relax=True,
    fmax=0.05,
    label="registry_optimization",
)

print(f"Started registry search: {registry_run.id_short}")

# Execute
run_until_empty(ws)
```

**Output:**

```
Executing run r_p7q8r9s0: registry_search ...
  Interface d_a1b2c3d4 (1/5) ...
    Seed 0: 400 steps, accepted 168/400 (42%), best E=-1333.789 eV
    Seed 1: 400 steps, accepted 172/400 (43%), best E=-1333.812 eV
    Seed 2: 400 steps, accepted 165/400 (41%), best E=-1333.834 eV
    Seed 3: 400 steps, accepted 170/400 (43%), best E=-1333.798 eV
    Seed 4: 400 steps, accepted 167/400 (42%), best E=-1333.801 eV
    Best overall: E=-1333.834 eV (seed 2)
  Interface d_e5f6g7h8 (2/5) ...
    ...
Run completed in 892.4s
```

### Step 5: Extract Optimized Results

**Get final optimized interfaces:**

```python
# Query registry search results
optimized = ws.list_derived_interfaces(
    run=registry_run.id_short,
)

print(f"Registry search generated {len(optimized)} interfaces")

# Find best for each original interface
from collections import defaultdict
by_parent = defaultdict(list)

for iface in optimized:
    by_parent[iface.parent_interface_id].append(iface)

# Print results
print("\nOptimized interfaces:")
for parent_id, variants in by_parent.items():
    best = min(variants, key=lambda i: i.energy_total)

    print(f"\n  Parent: {parent_id}")
    print(f"    Best registry: t=({best.translation[0]:.3f}, {best.translation[1]:.3f})")
    print(f"    Energy: {best.energy_total:.3f} eV")
    print(f"    Improvement: {best.energy_total - variants[0].energy_total:.3f} eV")
    print(f"    Interface ID: {best.id_short}")
```

**Output:**

```
Registry search generated 25 interfaces (5 parents × 5 seeds)

Optimized interfaces:

  Parent: d_a1b2c3d4
    Best registry: t=(0.234, 0.567)
    Energy: -1333.834 eV
    Improvement: -1.678 eV
    Interface ID: d_y1z2a3b4

  Parent: d_e5f6g7h8
    Best registry: t=(0.145, 0.823)
    Energy: -1891.456 eV
    Improvement: -2.222 eV
    Interface ID: d_c5d6e7f8
...
```

### Step 6: Export for Production Calculations

**Export optimized structures:**

```python
from pathlib import Path
from ase.io import write

export_dir = Path("optimized_interfaces")
export_dir.mkdir(exist_ok=True)

for parent_id, variants in by_parent.items():
    best = min(variants, key=lambda i: i.energy_total)

    # Get full interface structure
    interface = ws.get_derived_interface(best.id_short)

    # Export POSCAR
    poscar_path = export_dir / f"POSCAR_{best.id_short}"
    write(poscar_path, interface.atoms, format="vasp")

    # Export metadata
    metadata = {
        "interface_id": best.id_short,
        "prototype_id": interface.prototype_id,
        "alpha": best.alpha,
        "translation": best.translation,
        "energy_ml": best.energy_total,
        "n_atoms": len(interface.atoms),
        "cell": interface.atoms.cell.tolist(),
    }

    import json
    meta_path = export_dir / f"metadata_{best.id_short}.json"
    with open(meta_path, 'w') as f:
        json.dump(metadata, f, indent=2)

    print(f"Exported {best.id_short}")
    print(f"  POSCAR: {poscar_path}")
    print(f"  Metadata: {meta_path}")
```

## Advanced Workflows

### Custom Energy Function

Define custom scoring beyond simple energy:

```python
def custom_energy_function(interface_atoms, calculator):
    """
    Custom scoring combining energy, forces, and structure metrics.
    """
    interface_atoms.calc = calculator

    # Basic energy
    energy = interface_atoms.get_potential_energy()

    # Force magnitude (prefer well-relaxed)
    forces = interface_atoms.get_forces()
    max_force = np.max(np.linalg.norm(forces, axis=1))

    # Bond analysis
    from ase.neighborlist import neighbor_list
    i, j, d = neighbor_list('ijd', interface_atoms, 2.5)
    n_bonds = len(i)
    avg_bond_length = np.mean(d) if len(d) > 0 else 0.0

    # Combined score (minimize)
    score = (
        energy / len(interface_atoms) +  # Energy per atom
        10.0 * max_force +                # Penalize high forces
        -0.1 * n_bonds                    # Favor more bonds
    )

    return {
        'score': score,
        'energy': energy,
        'max_force': max_force,
        'n_bonds': n_bonds,
        'avg_bond_length': avg_bond_length,
    }

# Use in registry search
# (requires custom wrapper - see workspace extension docs)
```

### Parallel Execution

For HPC environments with multiple nodes:

```python
# Submit multiple independent runs
registry_runs = []

for interface_id in best_interface_ids:
    run = ws.start_registry_search(
        derived_interface_ids=[interface_id],  # One per run
        n_steps=800,
        n_seeds=10,
        calculator_spec=calc_spec,
        label=f"registry_{interface_id}",
    )
    registry_runs.append(run)

# Each run can be executed independently on different nodes
# Use your HPC scheduler (SLURM, PBS, etc.)

# Example SLURM submission:
"""
#!/bin/bash
#SBATCH --array=0-4
#SBATCH --ntasks=1
#SBATCH --time=02:00:00

python -c "
from calm.project import open_workspace
from calm.project.runner import run_until_empty

ws = open_workspace('my-interface-project')
runs = ws.list_runs(status='pending')
run = runs[$SLURM_ARRAY_TASK_ID]

run_until_empty(ws, run_ids=[run.id_short])
"
"""
```

### Convergence Testing

Test convergence with respect to interface size:

```python
# Select a single prototype
proto_id = proto_ids[0]

# Test different k values (interface size)
k_values = [2, 3, 4, 5, 6]

energies_per_area = []

for k_mult in k_values:
    # Would need to manually create larger supercell
    # (or re-run prototype search with higher k_max)

    # Build interface
    interface = build_interface_at_k(proto_id, k_mult)

    # Evaluate energy
    energy = evaluate_energy(interface, calc_spec)

    # Normalize by area
    area = interface.get_interface_area()
    energy_per_area = energy / area

    energies_per_area.append(energy_per_area)

    print(f"k={k_mult}: E/A = {energy_per_area:.3f} eV/Ų")

# Check convergence
diffs = np.diff(energies_per_area)
print(f"\nConvergence check:")
print(f"  Max difference: {np.max(np.abs(diffs)):.3f} eV/Ų")
print(f"  Converged: {np.max(np.abs(diffs)) < 0.01}")
```

### Batch Comparison

Compare multiple calculator backends:

```python
calculators = [
    {"family": "grace", "model": "GRACE-2L-OMAT", "device": "cpu"},
    {"family": "mace", "model": "medium-mpa-0", "device": "cpu"},
    {"family": "ase", "model": "emt"},
]

# Additional MLIP frameworks may be available in other conda environments under `environments/`,
# but are not yet exposed as first-class CALM calculator families.
results_by_calc = {}

for calc_spec in calculators:
    # Run strain scan with this calculator
    scan_run = ws.start_strain_partition_scan(
        prototype_ids=[proto_ids[0]],  # Test on one prototype
        alphas=[0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
        calculator_spec=calc_spec,
        label=f"calc_comparison_{calc_spec['family']}",
    )

    run_until_empty(ws)

    # Get results
    interfaces = ws.list_derived_interfaces(run=scan_run.id_short)
    results_by_calc[calc_spec['family']] = interfaces

# Compare energies
print("Calculator comparison:")
for calc_name, interfaces in results_by_calc.items():
    energies = [i.energy_total for i in interfaces]
    print(f"  {calc_name}:")
    print(f"    Mean: {np.mean(energies):.3f} eV")
    print(f"    Std: {np.std(energies):.3f} eV")
    print(f"    Min: {np.min(energies):.3f} eV")
```

## Visualization and Analysis

### Energy Correlation Plot

Compare ML vs DFT energies:

```python
import matplotlib.pyplot as plt

# Assume you have ML results and DFT results
ml_energies = [...]  # From ML calculator scan
dft_energies = [...]  # From DFT re-evaluation

fig, ax = plt.subplots(figsize=(8, 8))

ax.scatter(ml_energies, dft_energies, s=100, alpha=0.6)

# Perfect correlation line
min_e = min(min(ml_energies), min(dft_energies))
max_e = max(max(ml_energies), max(dft_energies))
ax.plot([min_e, max_e], [min_e, max_e], 'k--', alpha=0.3, label='y=x')

ax.set_xlabel('ML Energy (eV)')
ax.set_ylabel('DFT Energy (eV)')
ax.set_title('ML vs DFT Energy Correlation')
ax.legend()
ax.grid(True, alpha=0.3)

# Compute MAE
mae = np.mean(np.abs(np.array(ml_energies) - np.array(dft_energies)))
ax.text(0.05, 0.95, f'MAE: {mae:.3f} eV',
        transform=ax.transAxes, va='top',
        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

plt.tight_layout()
plt.savefig('ml_vs_dft.png', dpi=150)
```

### Registry Convergence Plot

Visualize MC convergence:

```python
# Get registry search results with traces
results = ws.list_derived_interfaces(
    run=registry_run.id_short,
    include_trace=True,  # Include MC trace data
)

fig, axes = plt.subplots(2, 1, figsize=(12, 8))

for result in results[:5]:  # Plot first 5
    if result.trace:
        steps = [t[0] for t in result.trace]
        best_energies = [t[2] for t in result.trace]  # Best energy so far

        axes[0].plot(steps, best_energies, alpha=0.7,
                     label=f'{result.id_short[:8]}...')

axes[0].set_xlabel('MC Step')
axes[0].set_ylabel('Best Energy (eV)')
axes[0].set_title('Registry Search Convergence')
axes[0].legend()
axes[0].grid(True, alpha=0.3)

# Acceptance rate distribution
acceptance_rates = [r.n_accepted / r.n_steps for r in results if r.n_steps > 0]
axes[1].hist(acceptance_rates, bins=20, alpha=0.7, edgecolor='black')
axes[1].axvline(0.4, color='red', linestyle='--', label='Target (40%)')
axes[1].set_xlabel('Acceptance Rate')
axes[1].set_ylabel('Count')
axes[1].set_title('MC Acceptance Rate Distribution')
axes[1].legend()

plt.tight_layout()
plt.savefig('registry_convergence.png', dpi=150)
```

## Best Practices

### 1. Progressive Refinement Strategy

```python
# Phase 1: Quick screening (coarse α grid, no registry)
alphas_coarse = [0.0, 0.25, 0.5, 0.75, 1.0]
scan_coarse = ws.start_strain_partition_scan(
    prototype_ids=proto_ids,
    alphas=alphas_coarse,
    optimize_registry=False,  # Skip for speed
    label="coarse_scan",
)

# Phase 2: Fine α scan around optimal (from coarse)
optimal_alpha_coarse = 0.5  # From phase 1 results
alphas_fine = [0.4, 0.45, 0.5, 0.55, 0.6]
scan_fine = ws.start_strain_partition_scan(
    prototype_ids=[best_proto_id],
    alphas=alphas_fine,
    optimize_registry=False,
    label="fine_scan",
)

# Phase 3: Registry optimization at optimal α
registry_run = ws.start_registry_search(
    derived_interface_ids=[best_interface_id],
    n_steps=800,
    n_seeds=10,
    label="final_registry",
)
```

### 2. Resource Management

```python
# Estimate computational cost
n_prototypes = len(proto_ids)
n_alphas = len(alphas)
n_registry_steps = 400
n_seeds = 5

# Strain scan cost
strain_scan_evals = n_prototypes * n_alphas
print(f"Strain scan: {strain_scan_evals} energy evaluations")

# Registry search cost
registry_evals = n_prototypes * n_registry_steps * n_seeds
print(f"Registry search: {registry_evals} energy evaluations")

# Total
total_evals = strain_scan_evals + registry_evals
print(f"Total: {total_evals} energy evaluations")

# Estimate time (assuming 1s per eval with GRACE)
estimated_time = total_evals * 1.0  # seconds
print(f"Estimated time: {estimated_time/60:.1f} minutes")
```

### 3. Checkpointing

```python
# Save intermediate results
checkpoint = {
    'run_id': scan_run.id_short,
    'completed_prototypes': [],
    'timestamp': datetime.now().isoformat(),
}

# After each prototype
for proto_id in proto_ids:
    # Process prototype...
    checkpoint['completed_prototypes'].append(proto_id)

    # Save checkpoint
    import json
    with open('checkpoint.json', 'w') as f:
        json.dump(checkpoint, f)

# Resume from checkpoint if interrupted
if Path('checkpoint.json').exists():
    with open('checkpoint.json') as f:
        checkpoint = json.load(f)
    remaining = [p for p in proto_ids if p not in checkpoint['completed_prototypes']]
else:
    remaining = proto_ids
```

## Troubleshooting

### High Energy Interfaces

**Symptom:** All interfaces have high positive energies

**Causes:**
1. Poor registry (atomic overlap)
2. Insufficient relaxation
3. Wrong strain partition

**Solutions:**
```python
# Enable registry optimization
build_config = InterfaceBuildConfig(
    optimize_registry=True,
    n_registry_steps=800,  # More steps
)

# Tighter relaxation
energy_config = EnergyConfig(
    fmax=0.01,  # Stricter (default 0.05)
    max_steps=500,  # More steps (default 200)
)

# Test multiple strain partitions
alphas = np.linspace(0.0, 1.0, 21)  # Finer grid
```

### Registry Search Not Improving

**Symptom:** All seeds give similar energies, no improvement

**Causes:**
1. Step size too small (not exploring)
2. Temperature too low (no uphill moves)
3. Already at optimal registry

**Solutions:**
```python
# Larger exploration
registry_config = {
    'step_scale': 0.5,      # Larger steps (default 0.25)
    'temperature': 0.2,     # Higher temperature (default 0.1)
    'n_steps': 800,         # More steps
}
```

### Inconsistent Results Across Seeds

**Symptom:** Large energy variance across different random seeds

**Cause:** Energy landscape has multiple deep minima

**Solution:**
```python
# Run more seeds to sample better
n_seeds = 20  # Increase from default 5

# Or use systematic grid search
from itertools import product
t1_values = np.linspace(0, 1, 10)
t2_values = np.linspace(0, 1, 10)

for t1, t2 in product(t1_values, t2_values):
    # Evaluate at grid point
    interface = build_interface_at_translation(proto_id, (t1, t2))
    energy = evaluate_energy(interface)
```

## Related Documentation

- [Tutorial 04: Follow-up Analyses](../../tutorials/04_followups.md) - Detailed walkthrough
- [Tutorial 05: Strain Analysis](../../tutorials/05_strain_analysis.md) - Strain decomposition
- [Algorithm: Strain Partitioning](../../mathematics/algorithms/geodesic-strain-partitioning.md) - Geodesic interpolation
- [Algorithm: Monte Carlo registry alignment](../../mathematics/algorithms/monte-carlo-registry-alignment.md) - MC details
- [Workspace Prototype Search](project_prototype_search.md) - Initial search workflow
- [One-Off Interface Workflow](one_off_interface.md) - Non-persistent alternative

## See Also

See the canonical Example Scripts listing at `docs/guides/examples/index.md` for the current runnable scripts.
- [Public API Reference](../../reference/public_api.md) - Workspace methods
- [Concepts: Calculators](../../concepts/calculators.md) - Calculator integration
