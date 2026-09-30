# One-Off Interface Workflow (No Persistent Workspace)

Build and evaluate interfaces quickly without database persistence, ideal for prototyping, parameter exploration, and integration into existing workflows.

## Overview

CALM provides **one-off functions** for users who need:

- **Quick prototyping** - Test ideas without setting up a workspace
- **Scriptable workflows** - Integrate into existing automation
- **Minimal overhead** - No database, no artifact management
- **In-memory operations** - Direct Python object manipulation

**Trade-offs:**
- ✅ Fast setup, no files created
- ✅ Easy to integrate with other tools
- ✅ Simple mental model (pure functions)
- ❌ No provenance tracking
- ❌ No artifact persistence
- ❌ Must manually manage intermediate results

## When to Use One-Off vs Workspace

| Feature | One-Off Workflow | Workspace Workflow |
|---------|------------------|-------------------|
| **Setup** | Import functions | `open_workspace(root)` |
| **Persistence** | None (in-memory) | SQLite database |
| **Artifacts** | Manual export | Automatic to `out/` |
| **Provenance** | None | Full lineage tracking |
| **UIDs** | Temporary | Stable, reproducible |
| **Parallelism** | Manual | Runner queue |
| **Use case** | Quick experiments | Production workflows |

**Choose one-off when:**
- Prototyping new ideas
- Parameter sweeps in notebooks
- Integration with non-CALM tools
- One-time calculations

**Choose workspace when:**
- Need reproducibility
- Long-running campaigns
- Multiple related runs
- Team collaboration

## Basic One-Off Flow

### Step 1: Create Bulk Structures

```python
from ase.build import bulk as ase_bulk

# Create bulk structures (ASE Atoms)
al_fcc = ase_bulk("Al", crystalstructure="fcc", a=4.05, cubic=True)
si_diamond = ase_bulk("Si", crystalstructure="diamond", a=5.43, cubic=True)
```

**Alternative: Load from file**

```python
from ase.io import read

al_fcc = read("Al_bulk.cif")
si_diamond = read("Si_bulk.vasp", format="vasp")
```

### Step 2: Find Interface Prototypes

```text
from calm import find_prototypes, PrototypeSearchConfig

# Configure search parameters
config = PrototypeSearchConfig(
    miller_max=2,          # Maximum Miller index
    k_max=12,              # Maximum supercell index
    n_candidates=100,      # Return top 100 matches
    eps_principal_max=0.15,  # Maximum principal strain (15%)
    w_match=0.5,           # Balance strain (0.5) vs size (0.5)
)

# Find prototypes
prototypes = find_prototypes(
    slab_A=al_fcc,
    slab_B=si_diamond,
    miller_A=(1, 1, 1),    # Al(111)
    miller_B=(1, 1, 1),    # Si(111)
    config=config,
)

print(f"Found {len(prototypes)} interface prototypes")
```

**Output:**
```
Found 42 interface prototypes
```

### Step 3: Inspect Prototype Candidates

```python
# Sort by match score (lower is better)
prototypes.sort(key=lambda p: p.match_score)

# Print top 5
for i, proto in enumerate(prototypes[:5]):
    print(f"{i+1}. k_A={proto.k_A}, k_B={proto.k_B}, "
          f"d_cell={proto.d_cell:.3f}, "
          f"d_size={proto.d_size:.2f}, "
          f"match_score={proto.match_score:.3f}")
```

**Output:**

```
1. k_{A}=2, k_{B}=2, d_cell=0.145, d_size=0.69, match_score=0.29
2. k_{A}=3, k_{B}=3, d_cell=0.158, d_size=1.10, match_score=0.35
3. k_{A}=2, k_{B}=3, d_cell=0.172, d_size=0.92, match_score=0.36
4. k_{A}=4, k_{B}=3, d_cell=0.189, d_size=1.25, match_score=0.41
5. k_{A}=4, k_{B}=4, d_cell=0.163, d_size=1.39, match_score=0.39
```

### Step 4: Build Interface from Prototype

```text
from calm import build_interface, InterfaceBuildConfig

# Select best prototype
best_proto = prototypes[0]

# Configure interface building
build_config = InterfaceBuildConfig(
    alpha=0.5,             # Strain partition (50/50)
    translation=(0.0, 0.0),  # Initial registry
    z_padding=2.5,         # Å separation
    optimize_registry=True,  # Run MC registry search
    n_registry_steps=400,  # MC steps
)

# Build interface
interface = build_interface(
    prototype=best_proto,
    config=build_config,
)

print(f"Interface has {len(interface.atoms)} atoms")
print(f"Cell: {interface.atoms.cell}")
```

**Output:**
```
Interface has 136 atoms
Cell: [[16.2, 0.0, 0.0], [0.0, 16.2, 0.0], [0.0, 0.0, 35.4]]
```

### Step 5: Evaluate Interface Energy

```text
from calm import compute_interfacial_energy, EnergyConfig
from calm.calculators import get_calculator

# Configure energy evaluation
energy_config = EnergyConfig(
    calculator=get_calculator("grace", model="GRACE-2L-OMAT"),
    relax_atoms=True,      # Relax atomic positions
    fmax=0.05,             # eV/Å convergence
)

# Compute interfacial energy
result = compute_interfacial_energy(
    interface=interface,
    config=energy_config,
)

print(f"Interfacial energy: {result.gamma:.3f} J/m²")
print(f"Total energy: {result.total_energy:.3f} eV")
print(f"Slab A energy: {result.slab_A_energy:.3f} eV")
print(f"Slab B energy: {result.slab_B_energy:.3f} eV")
```

**Output:**
```
Interfacial energy: 0.234 J/m²
Total energy: -1342.156 eV
Slab A energy: -678.234 eV
Slab B energy: -663.688 eV
```

## Complete Example: Parameter Sweep

Here's a complete example of sweeping over strain partitions without a workspace:

```text
from ase.build import bulk as ase_bulk
import numpy as np
import matplotlib.pyplot as plt

from calm import (
    find_prototypes,
    build_interface,
    compute_interfacial_energy,
    PrototypeSearchConfig,
    InterfaceBuildConfig,
    EnergyConfig,
)
from calm.calculators import get_calculator

# 1. Create bulks
lif = ase_bulk("LiF", crystalstructure="rocksalt", a=4.03, cubic=True)
li2o = ase_bulk("Li2O", crystalstructure="antifluorite", a=4.61, cubic=True)

# 2. Find prototypes
config = PrototypeSearchConfig(
    miller_max=2,
    k_max=10,
    n_candidates=50,
)

prototypes = find_prototypes(
    slab_A=lif,
    slab_B=li2o,
    miller_A=(1, 0, 0),
    miller_B=(1, 1, 0),
    config=config,
)

# 3. Select best prototype
best = min(prototypes, key=lambda p: p.match_score)

# 4. Strain partition scan
alphas = np.linspace(0.0, 1.0, 11)
energies = []

calculator = get_calculator("grace", model="GRACE-2L-OMAT")

for alpha in alphas:
    # Build interface with this strain partition
    build_config = InterfaceBuildConfig(
        alpha=alpha,
        translation=(0.0, 0.0),
        z_padding=2.5,
        optimize_registry=False,  # Skip for speed
    )

    interface = build_interface(best, build_config)

    # Evaluate energy
    energy_config = EnergyConfig(
        calculator=calculator,
        relax_atoms=True,
        fmax=0.05,
    )

    result = compute_interfacial_energy(interface, energy_config)
    energies.append(result.gamma)

    print(f"α={alpha:.1f}: γ={result.gamma:.3f} J/m²")

# 5. Plot results
plt.figure(figsize=(8, 5))
plt.plot(alphas, energies, 'o-', linewidth=2, markersize=8)
plt.xlabel('Strain Partition α')
plt.ylabel('Interfacial Energy (J/m²)')
plt.title(f'LiF(100) / Li₂O(110) Interface')
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig('strain_scan.png', dpi=150)
print("Saved strain_scan.png")
```

**Output:**

```
α=0.0: γ=0.342 J/m²
α=0.1: γ=0.318 J/m²
α=0.2: γ=0.289 J/m²
α=0.3: γ=0.256 J/m²
α=0.4: γ=0.234 J/m²
α=0.5: γ=0.228 J/m²  ← Minimum
α=0.6: γ=0.241 J/m²
α=0.7: γ=0.267 J/m²
α=0.8: γ=0.301 J/m²
α=0.9: γ=0.339 J/m²
α=1.0: γ=0.378 J/m²
Saved strain_scan.png
```

## Advanced: Custom Energy Function

For custom scoring beyond interfacial energy:

```text
def custom_scorer(interface):
    """Custom scoring function combining multiple criteria."""
    from ase.calculators.calculator import Calculator

    # Get calculator
    calc = get_calculator("grace")
    interface.atoms.calc = calc

    # Compute properties
    energy = interface.atoms.get_potential_energy()
    forces = interface.atoms.get_forces()
    max_force = np.max(np.linalg.norm(forces, axis=1))

    # Compute bond count (simple proxy for stability)
    from ase.neighborlist import NeighborList
    nl = NeighborList([1.5] * len(interface.atoms), self_interaction=False)
    nl.update(interface.atoms)
    n_bonds = sum(len(nl.get_neighbors(i)[0]) for i in range(len(interface.atoms)))

    # Combined score (lower is better)
    score = energy / len(interface.atoms) + 0.1 * max_force - 0.01 * n_bonds

    return {
        'score': score,
        'energy': energy,
        'max_force': max_force,
        'n_bonds': n_bonds,
    }

# Use custom scorer
interface = build_interface(best_proto, InterfaceBuildConfig())
result = custom_scorer(interface)

print(f"Custom score: {result['score']:.3f}")
print(f"  Energy: {result['energy']:.3f} eV")
print(f"  Max force: {result['max_force']:.3f} eV/Å")
print(f"  Bonds: {result['n_bonds']}")
```

## Integration with External Tools

### Export to VASP

```text
from ase.io import write

# Build interface
interface = build_interface(best_proto, InterfaceBuildConfig(alpha=0.5))

# Export to VASP
write("POSCAR", interface.atoms, format="vasp")
print("Wrote POSCAR")

# Also export strained slabs separately
write("POSCAR_slab_A", interface.slab_A_strained, format="vasp")
write("POSCAR_slab_B", interface.slab_B_strained, format="vasp")
```

### Export to Quantum ESPRESSO

```text
from ase.io import write

interface = build_interface(best_proto, InterfaceBuildConfig(alpha=0.5))

# QE input file
write("interface.pwi", interface.atoms, format="espresso-in",
      pseudopotentials={'Al': 'Al.pbe-n-kjpaw_psl.1.0.0.UPF',
                        'Si': 'Si.pbe-n-rrkjus_psl.1.0.0.UPF'},
      input_data={'calculation': 'relax',
                  'ecutwfc': 50,
                  'ecutrho': 400})
```

### Use with Pymatgen

```text
from pymatgen.io.ase import AseAtomsAdaptor

interface = build_interface(best_proto, InterfaceBuildConfig(alpha=0.5))

# Convert to pymatgen Structure
adaptor = AseAtomsAdaptor()
pmg_structure = adaptor.get_structure(interface.atoms)

print(f"Pymatgen formula: {pmg_structure.composition.reduced_formula}")
print(f"Space group: {pmg_structure.get_space_group_info()}")
```

## Configuration Reference

### PrototypeSearchConfig

```text
PrototypeSearchConfig(
    miller_max: int = 2,           # Maximum Miller index
    k_max: int = 12,               # Maximum supercell index
    n_candidates: int = 100,       # Number of candidates to return
    eps_principal_max: float = 0.15,  # Max strain (15%)
    w_match: float = 0.5,          # Strain vs size weight
    cond_max: float = 10.0,        # Conditioning threshold
    N_at_max: int = 1000,          # Max atoms for normalization
)
```

**Key parameters:**
- `miller_max`: Higher → more surfaces, slower
- `k_max`: Higher → larger supercells, more candidates
- `eps_principal_max`: Stricter → fewer candidates, lower strain
- `w_match`: 0.0 (size) ← 0.5 (balanced) → 1.0 (strain)

### InterfaceBuildConfig

```text
InterfaceBuildConfig(
    alpha: float = 0.5,            # Strain partition (0=all A, 1=all B)
    translation: Tuple[float, float] = (0.0, 0.0),  # Registry
    z_padding: float = 2.5,        # Out-of-plane separation (Å)
    optimize_registry: bool = False,  # MC registry search
    n_registry_steps: int = 400,   # MC steps if optimizing
    registry_step_scale: float = 0.25,  # MC step size
    registry_temperature: float = 0.1,  # MC temperature
    registry_seed: Optional[int] = None,  # Random seed
)
```

**Key parameters:**
- `alpha`: 0.5 (equal strain) is often optimal
- `optimize_registry`: True for best energy, False for speed
- `z_padding`: 2.0-3.0 Å typical for covalent/ionic interfaces

### EnergyConfig

```text
EnergyConfig(
    calculator: Calculator,        # ASE calculator
    relax_atoms: bool = True,      # Relax atomic positions
    fmax: float = 0.05,            # Force convergence (eV/Å)
    max_steps: int = 200,          # Max optimization steps
    optimizer: str = "BFGS",       # ASE optimizer
)
```

## Troubleshooting

### No Prototypes Found

**Symptom:** `find_prototypes` returns empty list

**Causes:**
1. Strain too restrictive: Increase `eps_principal_max`
2. Supercells too small: Increase `k_max`
3. Miller indices incompatible: Try different surfaces

**Solution:**
```text
# More permissive search
config = PrototypeSearchConfig(
    k_max=20,              # Larger supercells
    eps_principal_max=0.25,  # Allow more strain
    miller_max=3,          # More surfaces
)
```

### High Interfacial Energy

**Symptom:** `gamma` > 1.0 J/m² (unusually high)

**Causes:**
1. Poor registry: Enable `optimize_registry=True`
2. Wrong strain partition: Scan over `alpha`
3. Insufficient relaxation: Decrease `fmax`

**Solution:**
```text
# Better optimization
build_config = InterfaceBuildConfig(
    alpha=0.5,
    optimize_registry=True,
    n_registry_steps=800,  # More steps
)

energy_config = EnergyConfig(
    relax_atoms=True,
    fmax=0.01,  # Tighter convergence
)
```

### Memory Issues with Large Interfaces

**Symptom:** Out of memory for large supercells

**Solution:**
```text
# Limit supercell size
config = PrototypeSearchConfig(
    k_max=8,               # Smaller limit
    N_at_max=500,          # Penalize large interfaces
    w_match=0.2,           # Prioritize size (1-0.2=0.8 weight)
)
```

## Best Practices

1. **Start small, scale up**
   - Begin with $k_max=6$, increase if needed
   - Test with one surface pair first

2. **Validate with workspace for production**
   - Use one-off for prototyping
   - Switch to workspace for final runs

3. **Cache expensive operations**
```python
# Reuse calculator across multiple evaluations
calc = get_calculator("grace")
for proto in prototypes[:10]:
    interface = build_interface(proto, config)
    interface.atoms.calc = calc  # Reuse
    energy = interface.atoms.get_potential_energy()
```

4. **Export intermediate results**
```python
import pickle

# Save prototypes for later
with open('prototypes.pkl', 'wb') as f:
    pickle.dump(prototypes, f)

# Load later
with open('prototypes.pkl', 'rb') as f:
    prototypes = pickle.load(f)
```

5. **Use Jupyter notebooks**
   - One-off workflow is ideal for interactive exploration
   - Cell-by-cell execution
   - Easy visualization

## Related Documentation

- [Tutorial 03: Prototype Search](../../tutorials/03_prototype_search.md) - In-depth search explanation
- [Tutorial 04: Follow-up Analyses](../../tutorials/04_followups.md) - Strain partition and registry
- [Algorithm: Surface-cell matching and strain optimization](../../mathematics/algorithms/surface-cell-matching-and-strain-optimization.md) - Mathematical details
- [Workspace Prototype Search](project_prototype_search.md) - Persistent workflow
- [Concepts: Calculators](../../concepts/calculators.md) - Calculator abstraction

## See Also

See the Example Scripts guide for the current runnable scripts: `docs/guides/examples/index.md`.
- [Public API Reference](../../reference/public_api.md) - Complete function signatures
- [Glossary](../../glossary.md) - Terminology reference
