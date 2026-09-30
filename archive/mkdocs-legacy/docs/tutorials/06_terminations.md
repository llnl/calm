# Tutorial 6: Surface Terminations

Learn how to detect polar surfaces, automatically enumerate unique terminations, and understand the chemistry and stability of different surface terminations in ionic compounds.

## What You'll Learn

- Understanding polar vs non-polar surfaces
- Tasker classification of surface types
- Detecting polar surfaces automatically
- Enumerating all unique terminations
- Creating slabs for each termination
- Analyzing termination chemistry
- Physical interpretation of surface stability
- Working with ionic compounds (MgO, LiF, etc.)

## Prerequisites

- Completed [Tutorial 1: Workspace Basics](01_workspace_basics.md)
- Completed [Tutorial 2: Slab Generation](02_slab_generation.md)
- Understanding of ionic compounds and crystal structures
- Basic knowledge of electrostatics

## Background: Polar Surfaces

### What are Polar Surfaces?

A **polar surface** has a net dipole moment perpendicular to the surface due to asymmetric charge distribution. This occurs in ionic compounds when alternating charged layers are exposed.

**Key characteristics:**
- ✅ Asymmetric stacking of charged species
- ✅ Net electrostatic dipole perpendicular to surface
- ✅ Multiple possible terminations
- ✅ Termination affects surface chemistry and stability

**Examples:**
- **Polar**: MgO(100), LiF(100), NaCl(100), ZnO(0001)
- **Non-polar**: Al(111), Si(100), MgO(111), graphene(0001)

### Tasker Classification

Tasker (1979) classified ionic surfaces into three types based on charge distribution:

**Type I: Non-polar**
```
Layer sequence: ...AB AB AB| (repeated neutral layers)
Example: MgO(111)

    Mg²⁺ - O²⁻
    Mg²⁺ - O²⁻
    Mg²⁺ - O²⁻ |  ← Surface (neutral layer)
```
- Each layer is charge-neutral
- No net dipole
- Single termination
- Stable without reconstruction

**Type II: Non-polar**
```
Layer sequence: ...A B A B| (alternating charged, symmetric)
Example: NaCl(110)

    Na⁺ Cl⁻
    Cl⁻ Na⁺
    Na⁺ Cl⁻ |  ← Surface (symmetric)
```
- Layers are charged but symmetric
- No net dipole (cancels by symmetry)
- Single termination
- Stable

**Type III: Polar**
```
Layer sequence: ...A B A B| (alternating charged, asymmetric)
Example: MgO(100)

Mg-terminated:           O-terminated:
    Mg²⁺                     O²⁻
    O²⁻                      Mg²⁺
    Mg²⁺ |  ← Surface        O²⁻ |  ← Surface
```
- Alternating charged layers
- Net dipole perpendicular to surface
- Multiple terminations possible
- Unstable without reconstruction or charge compensation

### Why Terminations Matter

Different terminations have different properties:

**Chemistry:**
- **Cation-terminated**: Lewis acidic, electron-accepting
- **Anion-terminated**: Lewis basic, electron-donating
- Affects adsorption, catalysis, reactivity

**Stability:**
- Polar surfaces are intrinsically unstable (divergent electrostatic energy)
- Stabilization mechanisms:
  - Surface reconstruction
  - Charge compensation (defects, adsorbates)
  - Electronic reconstruction
  - Faceting

**Interface formation:**
- Termination affects bonding at interfaces
- Different terminations have different adhesion energies
- Critical for heterostructure design

### CALM's Approach

CALM automatically:
1. **Detects** whether a surface is polar using symmetry analysis
2. **Enumerates** all unique terminations for polar surfaces
3. **Creates** separate slab structures for each termination
4. **Labels** slabs with termination information

This ensures comprehensive coverage of all chemically distinct surface configurations.

## Step 1: Create Workspace and Ionic Bulk

```python
from pathlib import Path
from ase.build import bulk
from calm.project import open_workspace

# Create workspace
root = Path("./my_workspace")
ws = open_workspace(root=root)

# Create MgO bulk structure (rocksalt, ionic)
mgo_atoms = bulk('MgO', 'rocksalt', a=4.21, cubic=True)

# Add to workspace
mgo_bulk = ws.add_bulk(
    structure=mgo_atoms,
    label="MgO (rocksalt)",
    kind="reference",
)

print(f"Created MgO bulk: {mgo_bulk.id_short}")
print(f"Formula: {mgo_atoms.get_chemical_formula()}")
print(f"Space group: Fm-3m (rocksalt)")
```

**MgO structure:**
- **Rocksalt (NaCl-type)**: Two interpenetrating FCC lattices
- **Composition**: 1:1 ratio of Mg²⁺ and O²⁻
- **Lattice constant**: a ≈ 4.21 Å
- **Coordination**: Each ion has 6 nearest neighbors of opposite charge

**Other ionic compounds to try:**
- `bulk('LiF', 'rocksalt', a=4.03)` - Lithium fluoride
- `bulk('NaCl', 'rocksalt', a=5.64)` - Sodium chloride
- `bulk('TiO2', 'rutile', a=4.59, c=2.96)` - Titanium dioxide

## Step 2: Build Slabs Without Termination Enumeration

First, see what happens with default behavior (enumerate_terminations=False):

```python
# Build slabs WITHOUT automatic enumeration
default_slabs = ws.build_slabs(
    mgo_bulk.id_short,
    millers=[(1, 0, 0), (1, 1, 0)],
    params={"vacuum": 15.0, "layers": 4},
    enumerate_terminations=False,  # Default behavior
)

print(f"\nWithout enumeration: {len(default_slabs)} slabs")
for slab in default_slabs:
    print(f"  {slab.id_short}: Miller {slab.miller}, {slab.payload.get('natoms', 'N/A')} atoms")
```

**Expected output:**

```
Without enumeration: 2 slabs
  s_abc123: Miller (1, 0, 0), 8 atoms
  s_def456: Miller (1, 1, 0), 12 atoms
```

**What happened:**
- One slab per Miller index
- Default termination used (first termination found)
- **Missing information**: Don't know if other terminations exist

**Problem:**
- For polar surfaces, only one of multiple possible terminations is created
- No systematic exploration of termination space
- May miss chemically important configurations

## Step 3: Build Slabs With Automatic Enumeration

Now enable automatic termination enumeration:

```python
# Build slabs WITH automatic enumeration
enumerated_slabs = ws.build_slabs(
    mgo_bulk.id_short,
    millers=[(1, 0, 0), (1, 1, 0)],
    params={"vacuum": 15.0, "layers": 4},
    enumerate_terminations=True,  # Enable auto-enumeration
)

print(f"\nWith enumeration: {len(enumerated_slabs)} slabs")
for slab in enumerated_slabs:
    term = slab.payload.get("termination", "default")
    print(f"  {slab.id_short}: Miller {slab.miller}, termination: {term}")
```

**Expected output:**

```
With enumeration: 3 slabs
  s_ghi789: Miller (1, 0, 0), termination: Mg
  s_jkl012: Miller (1, 0, 0), termination: O
  s_mno345: Miller (1, 1, 0), termination: default
```

**What happened:**
- **MgO(100)**: Polar surface → 2 terminations (Mg, O)
- **MgO(110)**: Non-polar surface → 1 termination (default)
- Total: 3 slabs (comprehensive coverage)

**Key insight:**
- CALM automatically detected that (100) is polar
- Enumerated both Mg-terminated and O-terminated slabs
- (110) is non-polar, so only one termination

## Step 4: Display and Analyze Terminations

```python
# Query all slabs and display enriched table
enriched_slabs = ws.enrichment.list_slabs_enriched(limit=100)

from calm.project import display_table
print("\nAll slabs in workspace:")
display_table(enriched_slabs, table="slabs")
```

**Expected output:**

```
id_short   | bulk    | miller  | termination | layers | area    | natoms
-----------|---------|---------|-------------|--------|---------|--------
s_ghi789   | MgO     | (1,0,0) | Mg          | 4      | 17.7 Ų | 8
s_jkl012   | MgO     | (1,0,0) | O           | 4      | 17.7 Ų | 8
s_mno345   | MgO     | (1,1,0) | default     | 4      | 25.0 Ų | 12
```

### Group by Miller Index

```python
# Group slabs by Miller index using helper
by_miller = ws.enrichment.group_slabs_by_miller(enumerated_slabs)

print("\nTerminations by Miller index:")
for miller, slabs in sorted(by_miller.items()):
    print(f"  {miller}: {len(slabs)} termination(s)")
    for slab in slabs:
        term = slab.payload.get("termination", "default")
        natoms = slab.payload.get("natoms", "N/A")
        print(f"    - {term} ({natoms} atoms)")
```

**Expected output:**
```
Terminations by Miller index:
  (1, 0, 0): 2 termination(s)
    - Mg (8 atoms)
    - O (8 atoms)
  (1, 1, 0): 1 termination(s)
    - default (12 atoms)
```

**Interpretation:**
- **(100)**: 2 distinct terminations
  - **Mg-terminated**: Last layer is Mg²⁺ (cation)
  - **O-terminated**: Last layer is O²⁻ (anion)
- **(110)**: 1 termination
  - Non-polar, no termination choice

## Step 5: Analyze Surface Polarity

Use low-level functions to understand surface polarity:

```python
from calm import Bulk as CALMBulk
# from calm.slab.ops.termination_enumeration import (
#     is_polar_surface,
#     identify_unique_terminations
# )
# Note: Internal API shown for illustration

# Wrap bulk structure
calm_bulk = CALMBulk(mgo_atoms)

# Test various surfaces
test_surfaces = [(1, 0, 0), (1, 1, 0), (1, 1, 1)]

print("\nPolar surface analysis:")
for hkl in test_surfaces:
    # Check if polar
    is_polar = is_polar_surface(calm_bulk, hkl)

    # Enumerate terminations
    terminations = identify_unique_terminations(
        calm_bulk, hkl, layers=10
    )

    status = "✓ Polar" if is_polar else "✗ Non-polar"
    print(f"  {hkl}: {status}, {len(terminations)} termination(s)")

    for shift, label in terminations:
        print(f"    - {label} (shift={shift:.3f})")
```

**Expected output:**
```
Polar surface analysis:
  (1, 0, 0): ✓ Polar, 2 termination(s)
    - Mg (shift=0.000)
    - O (shift=0.500)
  (1, 1, 0): ✗ Non-polar, 1 termination(s)
    - default (shift=0.000)
  (1, 1, 1): ✗ Non-polar, 1 termination(s)
    - default (shift=0.000)
```

**Key results:**
- **(100)**: Polar with 2 terminations separated by half-layer (shift=0.5)
- **(110)**: Non-polar (Type II - symmetric alternating layers)
- **(111)**: Non-polar (Type I - charge-neutral layers)

### Understanding Shift Parameter

The **shift** parameter indicates the fractional layer displacement to reach next termination:

```
shift = 0.000: Mg-terminated
shift = 0.500: O-terminated (half-layer down)
```

For MgO(100) with 4 layers:
```
Layer sequence along [100]:
  0.000: Mg²⁺  ← shift=0.000 (Mg termination)
  0.250: O²⁻
  0.500: Mg²⁺
  0.750: O²⁻   ← shift=0.500 equivalent (O termination)
  1.000: Mg²⁺  ← Repeat
```

Shift of 0.5 means moving half-period down the stacking sequence.

## Step 6: Compare Termination Chemistry

Analyze the chemical differences between terminations:

```python
# Get both MgO(100) terminations
mgo_100_slabs = [s for s in enumerated_slabs
                 if tuple(s.miller) == (1, 0, 0)]

print("\nMgO(100) termination comparison:")
for slab in mgo_100_slabs:
    term = slab.payload.get("termination", "unknown")
    atoms = slab.atoms

    # Analyze top surface layer
    z_positions = atoms.positions[:, 2]
    top_layer_z = z_positions.max()
    top_atoms = atoms[z_positions > (top_layer_z - 0.5)]

    species = top_atoms.get_chemical_symbols()
    unique_species = set(species)

    print(f"\n  {term}-terminated:")
    print(f"    Top layer species: {', '.join(unique_species)}")
    print(f"    Top layer atoms: {len(top_atoms)}")
    print(f"    Charge character: {'Cationic' if term == 'Mg' else 'Anionic'}")
```

**Expected output:**
```
MgO(100) termination comparison:

  Mg-terminated:
    Top layer species: Mg
    Top layer atoms: 2
    Charge character: Cationic

  O-terminated:
    Top layer species: O
    Top layer atoms: 2
    Charge character: Anionic
```

**Chemical implications:**

**Mg-terminated (cationic):**
- Surface is Lewis acidic (electron-accepting)
- Favorable for binding Lewis bases (H₂O, CO₂, NH₃)
- Lower work function
- Positive surface dipole

**O-terminated (anionic):**
- Surface is Lewis basic (electron-donating)
- Favorable for binding Lewis acids (metal atoms)
- Higher work function
- Negative surface dipole

**Stability considerations:**
- Both terminations are unstable in vacuum (polar catastrophe)
- Stabilized by: reconstruction, hydroxylation, or charge transfer
- Relative stability depends on environment (gas phase, aqueous, etc.)

## Step 7: Visualize and Export Terminations

```python
# Export both terminations for visualization
export_dir = root / "terminations"
export_dir.mkdir(exist_ok=True)

for slab in mgo_100_slabs:
    term = slab.payload.get("termination", "unknown")
    filename = f"MgO_100_{term}_term.vasp"

    ws.export_poscar(
        atoms=slab.atoms,
        filepath=export_dir / filename
    )
    print(f"Exported: {filename}")
```

**Visualization checklist** (use VESTA, OVITO, or similar):

1. **Verify termination:**
   - Identify top and bottom layers
   - Confirm expected species at surface
   - Check layer spacing

2. **Check symmetry:**
   - Symmetric termination (top = bottom): Non-polar or reconstructed
   - Asymmetric (top ≠ bottom): Polar, may be unphysical

3. **Inspect geometry:**
   - Surface relaxation (bond length changes)
   - Rumpling (cation/anion height differences)
   - Reconstruction patterns

## Complete Example

```python
from pathlib import Path
from ase.build import bulk
from calm.project import open_workspace
from calm.project import display_table
from calm import Bulk as CALMBulk
# from calm.slab.ops.termination_enumeration import is_polar_surface
# Note: Internal API shown for illustration

# 1. Create workspace and add MgO bulk
root = Path("./my_workspace")
ws = open_workspace(root=root)

mgo_atoms = bulk('MgO', 'rocksalt', a=4.21, cubic=True)
mgo_bulk = ws.add_bulk(
    structure=mgo_atoms,
    label="MgO (rocksalt)",
    kind="reference",
)

print(f"Created MgO bulk: {mgo_bulk.id_short}")

# 2. Build slabs with automatic termination enumeration
slabs = ws.build_slabs(
    mgo_bulk.id_short,
    millers=[(1, 0, 0), (1, 1, 0), (1, 1, 1)],
    params={"vacuum": 15.0, "layers": 4},
    enumerate_terminations=True,  # KEY: Enable enumeration
)

print(f"\nCreated {len(slabs)} slabs (including all terminations)")

# 3. Display slab table
enriched = ws.enrichment.list_slabs_enriched(limit=100)
display_table(enriched, table="slabs")

# 4. Group by Miller index
by_miller = ws.enrichment.group_slabs_by_miller(slabs)

print("\nTerminations by Miller index:")
for miller, miller_slabs in sorted(by_miller.items()):
    print(f"  {miller}: {len(miller_slabs)} termination(s)")
    for slab in miller_slabs:
        term = slab.payload.get("termination", "default")
        print(f"    - {term}")

# 5. Analyze polarity
calm_bulk = CALMBulk(mgo_atoms)

print("\nSurface polarity:")
for hkl in [(1, 0, 0), (1, 1, 0), (1, 1, 1)]:
    is_polar = is_polar_surface(calm_bulk, hkl)
    status = "Polar" if is_polar else "Non-polar"
    print(f"  {hkl}: {status}")

# 6. Export for visualization
export_dir = root / "terminations"
export_dir.mkdir(exist_ok=True)

for slab in slabs:
    miller_str = "_".join(map(str, slab.miller))
    term = slab.payload.get("termination", "default")
    filename = f"MgO_{miller_str}_{term}.vasp"

    ws.export_poscar(
        atoms=slab.atoms,
        filepath=export_dir / filename
    )

print(f"\nExported {len(slabs)} POSCAR files to: {export_dir}")
```

## Key Takeaways

1. **Automatic Detection**
   - CALM automatically detects polar surfaces using symmetry analysis
   - No manual specification required
   - Works for all space groups

2. **Comprehensive Enumeration**
   - `enumerate_terminations=True` creates all unique terminations
   - Ensures no chemically distinct configurations are missed
   - Critical for polar surfaces (Type III in Tasker classification)

3. **Termination Labels**
   - Each slab labeled with termination information
   - Stored in `slab.payload["termination"]`
   - Enables filtering and analysis

4. **Chemical Significance**
   - Different terminations have different chemistry (acidic vs basic)
   - Affects catalysis, adsorption, interface formation
   - Both terminations should be considered in studies

5. **Non-Polar Surfaces**
   - Single termination (no choice)
   - Labeled as "default"
   - No enumeration needed

6. **Polar Catastrophe**
   - Bare polar surfaces are unstable (divergent electrostatic energy)
   - Require stabilization: reconstruction, compensation, or faceting
   - CALM creates both terminations for comprehensive study

## Physical Interpretation

### Why Polar Surfaces are Unstable

For an infinite polar surface with dipole moment μ per unit cell:

$$
E_electrostatic ∝ N × μ → ∞  as N → ∞
$$

This is the **polar catastrophe**: energy diverges with slab thickness.

**Stabilization mechanisms:**

1. **Electronic reconstruction:**
   - Charge transfer between surface and subsurface
   - Reduces or eliminates surface dipole
   - Observed in some oxides (e.g., LaAlO₃/SrTiO₃)

2. **Atomic reconstruction:**
   - Surface atoms rearrange to reduce charge imbalance
   - Example: Missing-row reconstruction
   - Can break or restore symmetry

3. **Charge compensation:**
   - Adsorption of charged species (OH⁻, H⁺)
   - Defects (vacancies, interstitials)
   - Example: Hydroxylation in ambient conditions

4. **Faceting:**
   - Surface breaks into non-polar facets
   - Eliminates global dipole at cost of energy

### Experimental Considerations

**In vacuum:**
- Polar terminations may reconstruct
- Charge compensation from defects
- Preparation history matters

**In solution:**
- Hydration stabilizes polar surfaces
- pH affects termination preference
- Hydroxyl groups common

**For interfaces:**
- Both terminations should be tested
- Interfacial chemistry depends on termination
- May differ from bulk-terminated expectations

## Troubleshooting

**No terminations enumerated for known polar surface:**
```python
# Check if surface is correctly identified as polar
from calm import Bulk as CALMBulk
# from calm.slab.ops.termination_enumeration import is_polar_surface
# Note: Internal API shown for illustration

calm_bulk = CALMBulk(bulk_atoms)
is_polar = is_polar_surface(calm_bulk, (1, 0, 0))
print(f"Is (100) polar? {is_polar}")

# If False but should be True, check:
# 1. Bulk structure is correct (use spglib to verify space group)
# 2. Primitive cell is being used
# 3. Atoms are on correct Wyckoff positions
```

**Too many terminations enumerated:**
```python
# Check termination details
# from calm.slab.ops.termination_enumeration import identify_unique_terminations
# Note: Internal API shown for illustration

terminations = identify_unique_terminations(calm_bulk, (1, 0, 0), layers=10)
print(f"Found {len(terminations)} terminations:")
for shift, label in terminations:
    print(f"  {label}: shift={shift:.3f}")

# If more than expected (e.g., 4 instead of 2), may indicate:
# - Supercell being used instead of primitive
# - Complex stacking with multiple unique positions
# - Algorithm detecting spurious differences (numerical precision)
```

**Termination labels are generic (e.g., "term_0", "term_1"):**
```python
# This occurs when species can't be unambiguously identified
# Common causes:
# - Mixed occupancy sites
# - Alloy or disordered structures
# - Complex stacking sequences

# Check species in top layer manually:
slab = slabs[0]
z_positions = slab.atoms.positions[:, 2]
top_z = z_positions.max()
top_atoms = slab.atoms[z_positions > (top_z - 0.5)]
print(f"Top layer species: {set(top_atoms.get_chemical_symbols())}")
```

**Different number of atoms for same Miller index:**
```python
# This is normal for polar surfaces
# Different terminations may have different atom counts due to:
# - Surface layer stoichiometry
# - Reconstruction

# Example: MgO(100)
# - Mg-terminated: 4 Mg + 4 O = 8 atoms (for 4 layers)
# - O-terminated: 4 Mg + 4 O = 8 atoms (same in this case)

# But for some compounds, terminations have different stoichiometry
```

**Slabs look identical despite different terminations:**
```python
# Check if viewing from correct direction
# Use visualization software to:
# 1. Rotate to view along surface normal (perpendicular to slab)
# 2. Zoom in on top surface layer
# 3. Color atoms by species

# In VESTA:
# - Style → Ball & Stick
# - Color by element
# - Rotate to view [001] projection for (100) surface
```

## Advanced Topics

### Tasker Type III Reconstruction

Polar surfaces (Type III) cannot exist in ideal form. Common reconstructions:

**Example: MgO(100)**

**Ideal (unreconstructed):**
```
... Mg²⁺ - O²⁻ - Mg²⁺ - O²⁻ |
```
- Infinite dipole moment
- Unstable

**Reconstructed options:**

1. **Octopolar reconstruction:**

$$
   ... Mg²⁺ - O²⁻ - Mg_vacancy - O_vacancy |
$$

   - Creates neutral surface via defects
   - Observed experimentally

2. **Hydroxylation:**
```
   ... Mg²⁺ - O²⁻ - Mg(OH)₂ |
```
   - Adds H₂O to neutralize charge
   - Common in ambient conditions

3. **Faceting:**
   - (100) surface breaks into (111) facets
   - Eliminates dipole at cost of increased area

### Comparing Termination Energies

To compare termination stabilities, you need:

1. **DFT calculations:** Accurate surface energies
2. **Chemical potentials:** Environment-dependent (gas phase, solution)
3. **Phase diagram:** Stable termination vs μ(O₂), T, P

CALM provides the structures; energy calculations require quantum chemistry tools.

### Non-Stoichiometric Terminations

Some surfaces exhibit non-1:1 terminations:

**Example: Rutile TiO₂(110):**
- Bulk: TiO₂ (1:2 ratio)
- Possible terminations:
  - Ti-rich: More Ti exposed
  - O-rich: More O exposed
  - Stoichiometric: 1:2 ratio preserved

CALM's enumeration focuses on **stoichiometric terminations** (bulk-like stacking).

### Interfaces with Polar Slabs

When building interfaces with polar slabs:

**Strategy 1: Test both terminations**
```python
# Build interfaces for all termination combinations
for slab_a in lif_terminations:
    for slab_b in li2o_terminations:
        run = ws.start_prototype_search(
            slab_a.id_short,
            slab_b.id_short,
            ...
        )
```

**Strategy 2: Focus on chemically favorable pairings**
- Cation-Anion pairing often favorable (e.g., Mg²⁺ - O²⁻)
- Avoid like-charge interfaces (high electrostatic penalty)

**Strategy 3: Compensate polar interfaces**
- Use non-polar slab on one side
- Or include adsorbates/defects in interface region

## Next Steps

- **[Tutorial 3: Prototype Search](03_prototype_search.md)** - Use termination-enumerated slabs in searches
- **[Tutorial 4: Follow-up Analyses](04_followups.md)** - Optimize interfaces with different terminations
- **DFT Calculations** - Compute accurate termination energies

## Related Documentation

- [Tutorial 2: Slab Generation](02_slab_generation.md) - Basic slab generation
- [Glossary: Polar Surface](../glossary.md#polar-surface)
- [Glossary: Termination](../glossary.md#termination)
- [API Reference: build_slabs](../reference/public_api.md)
See runnable examples in the Example Scripts guide: `docs/guides/examples/index.md`.

## Further Reading

**Tasker analysis:**
- Tasker, P. W. (1979). "The stability of ionic crystal surfaces." J. Phys. C: Solid State Physics, 12(22), 4977.

**Polar surfaces and reconstruction:**
- Noguera, C. (1996). "Physics and Chemistry at Oxide Surfaces." Cambridge University Press.
- Noguera, C. (2000). "Polar oxide surfaces." J. Phys.: Condens. Matter, 12(31), R367.

**MgO surfaces:**
- Patel, J. R. et al. (1999). "Atomic-scale imaging of MgO(100) surfaces." Phys. Rev. B, 60(11), 8218.
- Giordano, L. et al. (2006). "Charging of metal adatoms on ultrathin oxide films." Phys. Rev. Lett., 97(2), 026104.

**Oxide interfaces:**
- Ohtomo, A. & Hwang, H. Y. (2004). "A high-mobility electron gas at the LaAlO₃/SrTiO₃ heterointerface." Nature, 427(6973), 423-426.
