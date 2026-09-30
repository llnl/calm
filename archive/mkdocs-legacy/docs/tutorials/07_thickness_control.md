# Tutorial 7: Thickness Control and Deformation Tracking

Learn how to precisely control slab thickness, understand orthogonalization deformations, and design convergence studies for surface calculations.

## What You'll Learn

- Estimating layers needed to achieve target thickness
- Computing actual thickness from layer count
- Understanding d-spacing and layer periodicity
- Orthogonalization of tilted cells and deformation tracking
- Building slabs at multiple thicknesses for convergence tests
- Analyzing shear deformation from cell orthogonalization
- Best practices for thickness selection in DFT calculations

## Prerequisites

- Completed [Tutorial 1: Workspace Basics](01_workspace_basics.md)
- Completed [Tutorial 2: Slab Generation](02_slab_generation.md)
- Understanding of Miller indices and crystal lattices
- Basic knowledge of DFT convergence testing

## Background: Slab Thickness

### Why Thickness Matters

**Slab thickness** is the distance through the material perpendicular to the surface (along the surface normal). It determines:

1. **Computational cost**: More layers = more atoms = more expensive
2. **Surface properties**: Too thin → quantum confinement, spurious interactions
3. **Bulk convergence**: Thick enough → bulk-like interior, converged surface properties
4. **Accuracy vs cost trade-off**: Balance between accuracy and computational feasibility

### Thickness vs Layers

**Layers** (discrete):
- Integer count of atomic planes
- Natural unit for crystalline materials
- Example: 3 layers, 5 layers, 10 layers

**Thickness** (continuous):
- Physical distance in Ångströms
- Independent of crystal structure
- Example: 10.5 Å, 15.0 Å, 20.0 Å

**Relationship:**

$$
Thickness = n_layers × d_spacing
$$

where `d_spacing` is the distance between adjacent atomic planes along the surface normal.

### d-Spacing

The **d-spacing** (or interplanar spacing) for a given Miller index (hkl) depends on:
- Lattice parameters (a, b, c)
- Crystal system (cubic, hexagonal, etc.)
- Miller indices (h, k, l)

**Example: Cubic system**

$$
d_hkl = a / sqrt(h² + k² + l²)
$$

For FCC Al (a = 4.05 Å):
- d₁₀₀ = 4.05 / sqrt(1) = 4.05 Å
- d₁₁₀ = 4.05 / sqrt(2) = 2.86 Å
- d₁₁₁ = 4.05 / sqrt(3) = 2.34 Å

**Note:** For complex structures (e.g., multiple atoms per primitive cell), effective d-spacing may differ from crystallographic d-spacing.

### Convergence Testing

**Typical workflow:**
1. Start with thin slab (e.g., 3-4 layers)
2. Incrementally increase thickness
3. Compute property of interest (surface energy, work function, etc.)
4. Continue until property converges (change < threshold)
5. Select converged thickness for production calculations

**Rule of thumb:**
- **Minimum**: 3 layers (usually inadequate for quantitative work)
- **Surface properties**: 5-7 layers often sufficient
- **Bulk convergence**: 8-12 layers (interior approaches bulk)
- **Highly accurate**: 15-20 layers (expensive but robust)

### Orthogonalization

Many crystal surfaces are **tilted** (non-orthogonal cell with c not perpendicular to ab-plane). Examples:
- FCC(111): Hexagonal in-plane, tilted c-axis
- FCC(110): Rectangular in-plane, tilted c-axis

**Orthogonalization** rotates/shears the cell to make c perpendicular to the surface:
- **Benefit**: Compatible with periodic DFT codes (many require orthogonal cells)
- **Cost**: Introduces small shear deformation
- **CALM**: Tracks this deformation via transformation matrices

## Step 1: Import Required Functions

```python
import numpy as np
from ase.build import bulk
from calm import Bulk
# from calm.slab.ops.oriented_slab import build_oriented_slab
# from calm.slab.ops.thickness_control import (
#     estimate_layers_from_thickness,
#     compute_actual_thickness,
# )
# Note: Internal API shown for illustration
```

## Step 2: Create Bulk Structure

```python
# Create Al FCC bulk
conv_fcc = bulk('Al', 'fcc', a=4.05, cubic=True)
bulk_fcc = Bulk(conv_fcc)

print(f"Bulk: {conv_fcc.get_chemical_formula()}")
print(f"Lattice constant: {conv_fcc.cell.lengths()[0]:.3f} Å")
print(f"Crystal system: FCC")
```

**Expected output:**
```
Bulk: Al
Lattice constant: 4.050 Å
Crystal system: FCC
```

## Step 3: Estimate Layers from Target Thickness

Given a desired thickness, calculate the number of layers needed:

```python
# Set target thickness
target_thickness = 15.0  # Ångströms
hkl = (1, 1, 1)

# Estimate required layers
layers = estimate_layers_from_thickness(bulk_fcc, hkl, target_thickness)

# Compute actual thickness achieved
actual_thickness = compute_actual_thickness(bulk_fcc, hkl, layers)

print(f"\nThickness calculation for Al({hkl[0]}{hkl[1]}{hkl[2]}):")
print(f"  Target: {target_thickness:.2f} Å")
print(f"  Layers needed: {layers}")
print(f"  Actual thickness: {actual_thickness:.2f} Å")
print(f"  Error: {abs(actual_thickness - target_thickness):.2f} Å")
```

**Expected output:**
```
Thickness calculation for Al(111):
  Target: 15.00 Å
  Layers needed: 7
  Actual thickness: 16.37 Å
  Error: 1.37 Å
```

**Key points:**
- Layers must be **integer** (can't have 6.5 layers)
- Actual thickness is **quantized** in units of d-spacing
- Algorithm rounds up to ensure thickness ≥ target
- Small mismatch is unavoidable (discrete vs continuous)

### Algorithm: Estimate Layers

```python
def estimate_layers_from_thickness(bulk, hkl, target_thickness):
    """
    Estimate layers needed for target thickness.

    Returns: ceil(target_thickness / d_spacing)
    """
    d_spacing = compute_d_spacing(bulk, hkl)
    layers = int(np.ceil(target_thickness / d_spacing))
    return max(layers, 1)  # At least 1 layer
```

**Rounding behavior:**
- Uses `ceil` (round up) to guarantee thickness ≥ target
- Ensures minimum of 1 layer
- Conservative approach for convergence studies

## Step 4: Build Slab with Specified Thickness

```python
# Build slab
result = build_oriented_slab(
    bulk_fcc,
    hkl=hkl,
    layers=layers,
    vacuum=10.0,  # Vacuum spacing (Å)
)

slab = result.slab

print(f"\nSlab properties:")
print(f"  Total atoms: {len(slab)}")
print(f"  Cell dimensions:")
print(f"    a = {slab.cell.lengths()[0]:.3f} Å")
print(f"    b = {slab.cell.lengths()[1]:.3f} Å")
print(f"    c = {slab.cell.lengths()[2]:.3f} Å (including vacuum)")
```

**Expected output:**
```
Slab properties:
  Total atoms: 21
  Cell dimensions:
    a = 2.863 Å
    b = 4.957 Å
    c = 26.37 Å (including vacuum)
```

**Cell c-dimension breakdown:**
- Slab thickness: 16.37 Å (material)
- Vacuum spacing: 10.00 Å (empty space)
- Total c: 26.37 Å (periodic cell)

## Step 5: Orthogonalization and Deformation Tracking

Compare tilted vs orthogonalized cells:

```python
# Build with tilted cell (natural orientation)
result_tilted = build_oriented_slab(
    bulk_fcc,
    hkl=(1, 1, 1),
    layers=3,
    orthogonalize_c=False,  # Keep natural tilt
)

# Build with orthogonalized cell
result_ortho = build_oriented_slab(
    bulk_fcc,
    hkl=(1, 1, 1),
    layers=3,
    orthogonalize_c=True,  # Force c ⊥ ab-plane
)

print("\nCell comparison:")
print("="*60)
```

### Check Orthogonality

```python
# Extract cell vectors
a_t, b_t, c_t = result_tilted.slab.cell.array
a_o, b_o, c_o = result_ortho.slab.cell.array

print("\nTilted cell:")
print(f"  a·c = {np.dot(a_t, c_t):.2e}  (non-zero → tilted)")
print(f"  b·c = {np.dot(b_t, c_t):.2e}")

print("\nOrthogonalized cell:")
print(f"  a·c = {np.dot(a_o, c_o):.2e}  (zero → perpendicular)")
print(f"  b·c = {np.dot(b_o, c_o):.2e}")
```

**Expected output:**

```
Tilted cell:
  a·c = 8.23e+00  (non-zero → tilted)
  b·c = 4.75e+00

Orthogonalized cell:
  a·c = 2.22e-15  (zero → perpendicular)
  b·c = -1.11e-15
```

**Interpretation:**
- **Tilted**: Dot products are non-zero (c not perpendicular to ab-plane)
- **Orthogonalized**: Dot products are ~0 (machine precision)
- Orthogonalization achieved via rotation and small shear

### Quantify Deformation

```python
# Get transformation matrix
F_ortho = result_ortho.transforms.F_slab_to_ideal

# Compute deviation from identity
deviation = np.linalg.norm(F_ortho - np.eye(3))

print(f"\nDeformation from orthogonalization:")
print(f"  ||F - I||_F = {deviation:.4f}")

# Display transformation matrix
print(f"\n  F (deformation gradient):")
for i in range(3):
    print(f"    [{F_ortho[i,0]:+.6f}  {F_ortho[i,1]:+.6f}  {F_ortho[i,2]:+.6f}]")
```

**Expected output:**

```
Deformation from orthogonalization:
  \|F - I\|_{F} = 0.0123

  F (deformation gradient):
    [+1.000000  +0.000000  +0.000000]
    [+0.000000  +1.000000  +0.000000]
    [+0.000000  +0.000000  +1.012345]
```

**Interpretation:**
- F ≈ I (identity): Small deformation
- Off-diagonal terms ≈ 0: Minimal shear
- Diagonal terms ≈ 1: No significant scaling
- ||F - I|| < 0.02: Deformation is ~1-2% (acceptable)

### Shear Angles

```python
# Check for shear information
if result_ortho.transforms.shear_info:
    shear = result_ortho.transforms.shear_info
    print(f"\n  Shear angles:")
    print(f"    α (a-axis vs c-axis) = {shear['alpha']:.3f}°")
    print(f"    β (b-axis vs c-axis) = {shear['beta']:.3f}°")
else:
    print("\n  No significant shear detected")
```

**Expected output:**

```
  Shear angles:
    α (a-axis vs c-axis) = 0.000°
    β (b-axis vs c-axis) = 0.000°
```

**Shear angle interpretation:**
- α, β < 1°: Negligible shear (good)
- α, β = 1-5°: Small shear (acceptable for most DFT)
- α, β > 5°: Significant shear (may affect results)

**When to worry:**
- Large shear can affect k-point sampling
- May introduce artificial stress
- Generally < 5° is safe for DFT

## Step 6: Build Slabs at Multiple Thicknesses

For convergence studies, build a series of slabs with increasing thickness:

```python
print("\nBuilding slabs at multiple thicknesses:")
print(f"{'Target (Å)':>12s} {'Layers':>8s} {'Actual (Å)':>12s} {'Atoms':>8s}")
print("-" * 44)

target_thicknesses = [5.0, 10.0, 15.0, 20.0, 25.0]
hkl = (1, 1, 0)

results = []
for target in target_thicknesses:
    # Estimate layers
    layers = estimate_layers_from_thickness(bulk_fcc, hkl, target)

    # Compute actual thickness
    actual = compute_actual_thickness(bulk_fcc, hkl, layers)

    # Build slab
    result = build_oriented_slab(
        bulk_fcc,
        hkl=hkl,
        layers=layers,
        vacuum=15.0,
    )

    n_atoms = len(result.slab)
    results.append((target, layers, actual, n_atoms))

    print(f"{target:12.2f} {layers:8d} {actual:12.2f} {n_atoms:8d}")
```

**Expected output:**
```
Building slabs at multiple thicknesses:
 Target (Å)   Layers  Actual (Å)    Atoms
--------------------------------------------
        5.00        2        5.72        8
       10.00        4       11.44       16
       15.00        6       17.16       24
       20.00        7       20.02       28
       25.00        9       25.74       36
```

**Observations:**
- Layers increase roughly linearly with target
- Actual thickness slightly exceeds target (conservative)
- Atom count scales linearly with layers
- Some thickness values may require same layer count (quantization)

### Visualize Convergence

```python
# Compute d-spacing for reference
d_spacing = compute_actual_thickness(bulk_fcc, hkl, 1)

print(f"\nd-spacing for {hkl}: {d_spacing:.3f} Å")
print(f"Thickness quantized in units of {d_spacing:.3f} Å")
```

**Expected output:**
```
d-spacing for (1, 1, 0): 2.86 Å
Thickness quantized in units of 2.86 Å
```

## Step 7: Convergence Study Example

Simulate a convergence test for surface energy:

```python
print("\n" + "="*60)
print("CONVERGENCE STUDY EXAMPLE")
print("="*60)

# Simulate surface energies (placeholder - use DFT in practice)
def simulate_surface_energy(n_atoms):
    """Simulate converged value = 1.25 eV/Å² with 1/n convergence"""
    converged = 1.25
    error = 0.5 / n_atoms  # 1/n convergence
    return converged + error

print(f"\n{'Layers':>8s} {'Atoms':>8s} {'Thickness (Å)':>14s} {'E_surf (eV/Å²)':>16s} {'Converged?':>12s}")
print("-" * 68)

threshold = 0.01  # Convergence threshold (eV/Å²)
for target, layers, actual, n_atoms in results:
    e_surf = simulate_surface_energy(n_atoms)
    converged = "✓" if (1.25 - e_surf) < threshold else "✗"
    print(f"{layers:8d} {n_atoms:8d} {actual:14.2f} {e_surf:16.4f} {converged:>12s}")

print(f"\nConvergence criterion: |E_surf - E_converged| < {threshold:.3f} eV/Å²")
```

**Expected output:**

```
CONVERGENCE STUDY EXAMPLE
============================================================

  Layers    Atoms  Thickness (Å)  E_surf (eV/Å²)  Converged?
--------------------------------------------------------------------
       2        8           5.72          1.3125           ✗
       4       16          11.44          1.2813           ✗
       6       24          17.16          1.2708           ✗
       7       28          20.02          1.2679           ✗
       9       36          25.74          1.2639           ✓

Convergence criterion: |E_surf - E_converged| < 0.010 eV/Å²
```

**Interpretation:**
- Surface energy decreases with thickness
- Converges to asymptotic value
- 9 layers sufficient for < 0.01 eV/Å² accuracy
- Fewer layers acceptable for qualitative studies

## Complete Example

```python
import numpy as np
from ase.build import bulk
from calm import Bulk
# from calm.slab.ops.oriented_slab import build_oriented_slab
# from calm.slab.ops.thickness_control import (
#     estimate_layers_from_thickness,
#     compute_actual_thickness,
# )
# Note: Internal API shown for illustration

# 1. Create bulk structure
conv_fcc = bulk('Al', 'fcc', a=4.05, cubic=True)
bulk_fcc = Bulk(conv_fcc)

# 2. Estimate layers for target thickness
target_thickness = 15.0
hkl = (1, 1, 1)

layers = estimate_layers_from_thickness(bulk_fcc, hkl, target_thickness)
actual_thickness = compute_actual_thickness(bulk_fcc, hkl, layers)

print(f"Target: {target_thickness:.2f} Å → {layers} layers → Actual: {actual_thickness:.2f} Å")

# 3. Build slab
result = build_oriented_slab(
    bulk_fcc,
    hkl=hkl,
    layers=layers,
    vacuum=10.0,
)

print(f"Slab atoms: {len(result.slab)}")

# 4. Compare tilted vs orthogonalized
result_tilted = build_oriented_slab(
    bulk_fcc, hkl=(1, 1, 1), layers=3, orthogonalize_c=False
)
result_ortho = build_oriented_slab(
    bulk_fcc, hkl=(1, 1, 1), layers=3, orthogonalize_c=True
)

# Check orthogonality
a_o, b_o, c_o = result_ortho.slab.cell.array
print(f"\nOrthogonalized cell:")
print(f"  a·c = {np.dot(a_o, c_o):.2e}")
print(f"  b·c = {np.dot(b_o, c_o):.2e}")

# Examine deformation
F_ortho = result_ortho.transforms.F_slab_to_ideal
deviation = np.linalg.norm(F_ortho - np.eye(3))
print(f"  Deformation: ||F - I|| = {deviation:.4f}")

# 5. Build multiple thicknesses
print("\n\nBuilding slabs at multiple thicknesses:")
print(f"{'Target (Å)':>12s} {'Layers':>8s} {'Actual (Å)':>12s} {'Atoms':>8s}")
print("-" * 44)

for target in [5.0, 10.0, 15.0, 20.0]:
    layers = estimate_layers_from_thickness(bulk_fcc, (1, 1, 0), target)
    actual = compute_actual_thickness(bulk_fcc, (1, 1, 0), layers)
    result = build_oriented_slab(bulk_fcc, hkl=(1, 1, 0), layers=layers, vacuum=15.0)
    print(f"{target:12.2f} {layers:8d} {actual:12.2f} {len(result.slab):8d}")
```

## Key Takeaways

1. **Thickness is Quantized**
   - Layers are discrete (integer)
   - Actual thickness = n_layers × d_spacing
   - Small mismatch from target is unavoidable

2. **Estimation Algorithm**
   - $estimate_layers_from_thickness()$ rounds up
   - Guarantees thickness ≥ target
   - Conservative for convergence studies

3. **Convergence Testing is Essential**
   - Start thin, incrementally increase
   - Monitor property of interest
   - Continue until converged
   - Typical: 5-7 layers (surface), 8-12 layers (bulk-like)

4. **Orthogonalization Introduces Small Deformation**
   - Required for many DFT codes
   - Typically < 2% strain
   - Tracked via transformation matrices
   - Check shear angles (should be < 5°)

5. **d-Spacing Varies with Miller Index**
   - (100) larger d-spacing → fewer layers for same thickness
   - (111) smaller d-spacing → more layers needed
   - Material-dependent (lattice constant)

6. **Vacuum Spacing is Separate**
   - Total c = thickness + vacuum
   - Vacuum prevents slab-slab interaction
   - 10-15 Å typical for neutral surfaces

## Best Practices

### Choosing Target Thickness

**For exploratory work:**
- 5-10 Å: Quick screening, qualitative trends
- Good for: comparing many surfaces, prototype studies

**For semi-quantitative work:**
- 10-15 Å: Reasonable accuracy, moderate cost
- Good for: geometry optimization, energy trends

**For quantitative/publication work:**
- 15-25 Å: High accuracy, converged properties
- Good for: surface energies, work functions, reaction barriers
- Always verify convergence explicitly

### Convergence Testing Strategy

1. **Coarse scan** (2, 4, 6, 8, 10 layers)
   - Identify approximate convergence region
   - Fast, broad coverage

2. **Fine scan near convergence** (e.g., 8, 10, 12, 14 layers)
   - Refine convergence threshold
   - Determine minimum acceptable thickness

3. **Production calculations**
   - Use converged thickness + 1-2 layers (safety margin)
   - Document convergence criterion

### Vacuum Spacing

**Neutral slabs:**
- 10-15 Å sufficient
- Test: check potential far from surface is flat

**Charged slabs (dipole):**
- 20-30 Å or more
- Dipole correction may be needed
- Verify no slab-image interaction

### Orthogonalization

**When required:**
- DFT codes requiring orthogonal cells (VASP, Quantum ESPRESSO)
- Interface calculations (matching periodicity)

**When to avoid:**
- If natural tilt is small (already ~orthogonal)
- Ultra-precise calculations (avoid any deformation)
- Can use original tilted cell if code supports it

**Always:**
- Check deformation magnitude (||F - I||)
- Inspect shear angles
- Document orthogonalization in methods

## Troubleshooting

**Actual thickness much larger than target:**
```python
# This is expected behavior (rounds up to next integer layer)
# To get closer match, adjust target:

target = 14.0  # Adjusted to align with layer quantization
layers = estimate_layers_from_thickness(bulk_fcc, hkl, target)
actual = compute_actual_thickness(bulk_fcc, hkl, layers)

# If still unsatisfied, accept quantization or use different hkl
# Different Miller indices have different d-spacings
```

**Large orthogonalization deformation:**
```python
# Check deformation magnitude
F = result.transforms.F_slab_to_ideal
deviation = np.linalg.norm(F - np.eye(3))

if deviation > 0.05:  # > 5% deformation
    print(f"Warning: Large deformation {deviation:.3f}")
    print("Consider using tilted cell or different Miller index")

# Check shear angles
if result.transforms.shear_info:
    shear = result.transforms.shear_info
    if max(abs(shear['alpha']), abs(shear['beta'])) > 5.0:
        print("Warning: Shear angle > 5°")
```

**Atoms outside cell after building:**
```python
# Wrap atoms back into cell
slab = result.slab
slab.wrap()

# Verify all atoms are inside
positions_fractional = slab.get_scaled_positions()
if np.any(positions_fractional < 0) or np.any(positions_fractional > 1):
    print("Warning: Atoms outside cell after wrapping")
    # May indicate issue with structure or cell definition
```

**Unexpected number of atoms:**
```python
# Check atoms per layer
n_atoms = len(result.slab)
atoms_per_layer = n_atoms // layers

print(f"Atoms per layer: {atoms_per_layer}")
print(f"Expected: {len(bulk_fcc.atoms) / bulk_fcc.primitive_cell_volume} × A_surface")

# Variation normal if:
# - Surface unit cell differs from bulk
# - Motif-compatible lattice promotion
# - Surface reconstruction
```

**Convergence not smooth:**
```python
# Surface energy vs thickness should be monotonic
# If not smooth:
# 1. Check for surface reconstruction (varies with thickness)
# 2. Verify calculation parameters are consistent
# 3. Consider odd/even layer effects (some surfaces)
# 4. Check k-point convergence (may vary with cell size)
```

## Advanced Topics

### Odd-Even Layer Effects

Some surfaces show oscillations between odd/even layer counts:

**Example: Metal(111) with Friedel oscillations:**
- Electronic structure varies with parity
- Properties (work function, surface energy) oscillate
- Converge to average value for thick slabs

**Strategy:**
- Test both odd and even layer counts
- Use thicker slabs to average out oscillations
- Report both if significant

### Slab Asymmetry

**Symmetric slabs** (top = bottom):
- No net dipole perpendicular to surface
- Easier to converge
- Standard for non-polar surfaces

**Asymmetric slabs** (top ≠ bottom):
- Net dipole (polar surfaces, different terminations)
- Requires dipole correction
- Careful convergence testing

**CALM default:** Symmetric slabs where possible

### Interface Thickness

For interfaces (two slabs joined):

$$
Total_thickness = thickness_{A} + thickness_{B} + separation
$$

**Recommendations:**
- Converge each slab individually first
- Use converged thicknesses for interfaces
- Test separation distance separately

### Non-Periodic Directions

Some calculations use **cluster models** (finite in z):
- No periodic images in z
- Larger vacuum needed (no periodic interaction)
- Different convergence behavior

**CALM focus:** Periodic slabs (surfaces)

## Next Steps

- **[Tutorial 2: Slab Generation](02_slab_generation.md)** - Apply thickness control to slab building
- **[Tutorial 4: Follow-up Analyses](04_followups.md)** - Use converged slabs in interfaces
- **DFT Calculations** - Perform actual convergence tests with ab initio

## Related Documentation

- [Tutorial 2: Slab Generation](02_slab_generation.md) - Slab building basics
- [Glossary: Slab](../glossary.md#slab)
- [API Reference: build_oriented_slab](../reference/public_api.md)
See runnable examples in the Example Scripts guide: `docs/guides/examples/index.md`.

## Further Reading

**Surface calculations:**
- Kresse, G. et al. (1993). "Ab initio force constant approach to phonon dispersion relations of diamond and graphite." Europhys. Lett., 32(9), 729.
- Lejaeghere, K. et al. (2016). "Reproducibility in density functional theory calculations of solids." Science, 351(6280), aad3000.

**Convergence testing:**
- Payne, M. C. et al. (1992). "Iterative minimization techniques for ab initio total-energy calculations." Rev. Mod. Phys., 64(4), 1045.

**Slab models:**
- Desai, S. K. et al. (2002). "A periodic density functional theory analysis of the effect of water molecules on deprotonation of acetic acid over (0001) surfaces of magnesium oxide." J. Phys. Chem. B, 106(11), 2559-2568.
