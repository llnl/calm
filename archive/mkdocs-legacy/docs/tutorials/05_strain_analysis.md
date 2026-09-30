# Tutorial 5: Comprehensive Strain Analysis

Learn how to decompose strain tensors into physical components, analyze principal strains, and map strain directions to crystallographic coordinates.

## What You'll Learn

- Understanding Hencky (logarithmic) strain tensors
- Extracting principal strains (eigenvalues ε₁, ε₂)
- Decomposing strain into area and shape components
- Computing Frobenius norms and verifying orthogonality
- Analyzing strain variation across α values
- Mapping principal directions to crystallographic coordinates
- Physical interpretation of strain metrics

## Prerequisites

- Completed [Tutorial 1: Workspace Basics](01_workspace_basics.md)
- Completed [Tutorial 3: Prototype Search](03_prototype_search.md)
- Workspace with Pareto-optimal prototypes
- Understanding of linear algebra (eigenvalues, norms)
- Basic crystallography (Miller indices, unit cells)

## Background: Strain Theory

### What is Strain?

**Strain** measures the deformation of a material relative to its initial state. For interfaces, strain quantifies how much each material must deform to achieve lattice commensurability.

**Key concepts:**
- **Reference state**: Undeformed crystal (primitive surface cell)
- **Deformed state**: Crystal after strain partition
- **Deformation gradient**: Matrix F mapping reference → deformed
- **Strain tensor**: E = (1/2) log(F^T @ F)

### Hencky (Logarithmic) Strain

CALM uses **Hencky strain** (also called **true strain** or **logarithmic strain**):

$$
E = (1/2) log(M)
$$

where M = G_ref^{-1} @ G_def is the relative metric.

**Advantages of Hencky strain:**
- ✅ Exact for large deformations
- ✅ Additive under sequential deformations
- ✅ Natural for geodesic interpolation on SPD(2)
- ✅ Principal values are natural logarithms

**Factor of 1/2 convention:**
- Some references use E = log(M) (no factor)
- CALM uses E = (1/2) log(M) (factor 1/2)
- Principal strains: ε_i = (1/2) ln(λ_i) where λ_i are eigenvalues of M

### Strain Decomposition

Any 2D strain tensor can be decomposed **orthogonally** into:

$$
E = E_area + E_shape
$$

**E_area (Isotropic/Areal component):**

$$
E_area = (Tr(E)/2) I
$$

- Changes area, preserves shape
- Diagonal matrix: uniform scaling in all directions
- Physical meaning: Volume expansion or compression
- Trace: Tr(E_area) = Tr(E)

**E_shape (Deviatoric/Shape component):**

$$
E_shape = E - E_area
$$

- Changes shape, preserves area
- Traceless: Tr(E_shape) = 0
- Physical meaning: Shear, elongation, anisotropic deformation
- Det(E_shape) ≈ 0 for small strains

**Orthogonality:**

$$
\|E\|²_{F} = \|E_area\|²_{F} + \|E_shape\|²_{F}
$$

This is analogous to Pythagorean theorem: total strain squared equals sum of component strains squared.

### Principal Strains

The **principal strains** (ε₁, ε₂) are eigenvalues of the strain tensor:

$$
E \cdot v_{i} = ε_{i} \cdot v_{i}
$$

where v_i are the eigenvectors (principal directions).

**Physical interpretation:**
- ε₁, ε₂ > 0: Biaxial tension (stretching in both directions)
- ε₁, ε₂ < 0: Biaxial compression (squeezing in both directions)
- ε₁ > 0, ε₂ < 0: Mixed (stretch in one direction, compress in other)

**Frobenius norm in terms of principal strains:**

```
\|E\|_{F} = sqrt(ε₁² + ε₂²)
\|E_area\|_{F} = (sqrt(2)/2) |ε₁ + ε₂|
\|E_shape\|_{F} = (sqrt(2)/2) |ε₁ - ε₂|
```

**Trace and area change:**

```
Tr(E) = ε₁ + ε₂ = ln(A_final / A_initial)
```text

If Tr(E) = +0.10, the area increases by a factor exp(0.10) ≈ 1.105 (10.5% expansion).

## Step 1: Open Workspace and Select Prototype

```python
from pathlib import Path
from calm.project import open_workspace
import numpy as np

# Open workspace from Tutorial 03
root = Path("./my_workspace")
ws = open_workspace(root=root)

# Get first Pareto-optimal prototype for detailed analysis
pareto_prototypes = ws.list_prototypes(pareto=True, limit=1000)

if not pareto_prototypes:
    print("No Pareto-optimal prototypes found. Run Tutorial 03 first.")
    exit(1)

prototype = pareto_prototypes[0]
prototype_id = prototype.id_short

print(f"Analyzing strain for prototype: {prototype_id}")
print(f"  Strain: {prototype.hencky_norm:.4f}")
print(f"  Atoms: {prototype.natoms}")
```

**Selection criteria:**
- Use Pareto-optimal prototype (good geometry)
- Prefer moderate strain (0.03-0.10) for clear analysis
- Avoid very low strain (<0.01) - numerical precision issues
- Avoid very high strain (>0.20) - may be beyond elastic regime

## Step 2: Analyze Strain at Multiple α Values

Scan across strain partition parameter to see how strain is redistributed:

```python
# Define alpha values to analyze
alphas = [0.0, 0.25, 0.5, 0.75, 1.0]

print("\n" + "="*80)
print("STRAIN ANALYSIS AT MULTIPLE ALPHA VALUES")
print("="*80)
print("\nAlpha parameter controls strain distribution:")
print("  α = 0.0: All strain on slab B (slab A unstrained)")
print("  α = 0.5: Equal strain distribution")
print("  α = 1.0: All strain on slab A (slab B unstrained)")

for alpha in alphas:
    print(f"\n{'─'*80}")
    print(f"α = {alpha:.2f}")
    print(f"{'─'*80}")

    # Get detailed strain analysis
    strain_info = ws.analysis.analyze_prototype_strain(prototype_id, alpha=alpha)

    # Display results for both slabs
    for slab_name in ['slab_A', 'slab_B']:
        slab_data = strain_info[slab_name]

        print(f"\n{slab_name}:")
        print(f"  Principal strains: ε₁ = {slab_data['principal_strains'][0]:+.6f}, "
              f"ε₂ = {slab_data['principal_strains'][1]:+.6f}")
        print(f"  Max |ε_i|: {slab_data['max_principal_strain']:.6f}")
        print(f"\n  Frobenius norms:")
        print(f"    ||E||_F       = {slab_data['norm_E']:.6f}  (total strain)")
        print(f"    ||E_area||_F  = {slab_data['norm_E_area']:.6f}  (area component)")
        print(f"    ||E_shape||_F = {slab_data['norm_E_shape']:.6f}  (shape component)")
        print(f"\n  Area change:")
        print(f"    Tr(E) = {slab_data['trace_E']:+.6f}  (ln(A_final/A_initial))")
        print(f"    Area ratio = {slab_data['area_ratio']:.6f}  (A_final/A_initial)")
```

**Expected output:**
```
α = 0.00
────────────────────────────────────────────────────────────────────────────────

slab_{A}:
  Principal strains: ε₁ = +0.000000, ε₂ = +0.000000
  Max |ε_{i}|: 0.000000

  Frobenius norms:
    \|E\|_{F}       = 0.000000  (total strain)
    \|E_area\|_{F}  = 0.000000  (area component)
    \|E_shape\|_{F} = 0.000000  (shape component)

  Area change:
    Tr(E) = +0.000000  (ln(A_final/A_initial))
    Area ratio = 1.000000  (A_final/A_initial)

slab_{B}:
  Principal strains: ε₁ = -0.064023, ε₂ = -0.064023
  Max |ε_{i}|: 0.064023

  Frobenius norms:
    \|E\|_{F}       = 0.090526  (total strain)
    \|E_area\|_{F}  = 0.090526  (area component)
    \|E_shape\|_{F} = 0.000000  (shape component)

  Area change:
    Tr(E) = -0.128046  (ln(A_final/A_initial))
    Area ratio = 0.879823  (A_final/A_initial)

────────────────────────────────────────────────────────────────────────────────
α = 0.50
────────────────────────────────────────────────────────────────────────────────

slab_{A}:
  Principal strains: ε₁ = +0.032012, ε₂ = +0.032012
  Max |ε_{i}|: 0.032012

  Frobenius norms:
    \|E\|_{F}       = 0.045263  (total strain)
    \|E_area\|_{F}  = 0.045263  (area component)
    \|E_shape\|_{F} = 0.000000  (shape component)

  Area change:
    Tr(E) = +0.064023  (ln(A_final/A_initial))
    Area ratio = 1.066145  (A_final/A_initial)

slab_{B}:
  Principal strains: ε₁ = -0.032012, ε₂ = -0.032012
  Max |ε_{i}|: 0.032012

  Frobenius norms:
    \|E\|_{F}       = 0.045263  (total strain)
    \|E_area\|_{F}  = 0.045263  (area component)
    \|E_shape\|_{F} = 0.000000  (shape component)

  Area change:
    Tr(E) = -0.064023  (ln(A_final/A_initial))
    Area ratio = 0.938042  (A_final/A_initial)
```

**Key observations:**
- **α = 0**: Slab A unstrained (all zeros), Slab B fully strained
- **α = 0.5**: Symmetric strain distribution (equal magnitudes, opposite signs)
- **α = 1**: Slab B unstrained, Slab A fully strained
- **Area component dominates** for this example (shape component ≈ 0)
- **Strain is reversible**: Values at α=0.25 and α=0.75 mirror each other

## Step 3: Detailed Analysis at α = 0.5

Examine the full strain tensors at symmetric partitioning:

```python
print("\n" + "="*80)
print("DETAILED ANALYSIS AT α = 0.5 (EQUAL STRAIN PARTITION)")
print("="*80)

strain_info_50 = ws.analysis.analyze_prototype_strain(prototype_id, alpha=0.5)

# Display full strain tensors
print("\nFULL STRAIN TENSORS:")
print("="*80)

for slab_name in ['slab_A', 'slab_B']:
    slab_data = strain_info_50[slab_name]

    print(f"\n{slab_name}:")

    # Total strain tensor E
    E = np.array(slab_data['E'])
    print(f"\n  E (Hencky strain tensor):")
    print(f"    [{E[0,0]:+.6f}  {E[0,1]:+.6f}]")
    print(f"    [{E[1,0]:+.6f}  {E[1,1]:+.6f}]")

    # Isotropic component
    E_area = np.array(slab_data['E_area'])
    print(f"\n  E_area (isotropic component, preserves shape):")
    print(f"    [{E_area[0,0]:+.6f}  {E_area[0,1]:+.6f}]")
    print(f"    [{E_area[1,0]:+.6f}  {E_area[1,1]:+.6f}]")

    # Deviatoric component
    E_shape = np.array(slab_data['E_shape'])
    print(f"\n  E_shape (deviatoric component, preserves area):")
    print(f"    [{E_shape[0,0]:+.6f}  {E_shape[0,1]:+.6f}]")
    print(f"    [{E_shape[1,0]:+.6f}  {E_shape[1,1]:+.6f}]")
    print(f"    (Note: Tr(E_shape) = {np.trace(E_shape):.2e}, traceless ✓)")
```

**Expected output:**

```
slab_{A}:

  E (Hencky strain tensor):
    [+0.032012  +0.000000]
    [+0.000000  +0.032012]

  E_area (isotropic component, preserves shape):
    [+0.032012  +0.000000]
    [+0.000000  +0.032012]

  E_shape (deviatoric component, preserves area):
    [+0.000000  +0.000000]
    [+0.000000  +0.000000]
    (Note: Tr(E_shape) = 0.00e+00, traceless ✓)

slab_{B}:

  E (Hencky strain tensor):
    [-0.032012  -0.000000]
    [-0.000000  -0.032012]

  E_area (isotropic component, preserves shape):
    [-0.032012  -0.000000]
    [-0.000000  -0.032012]

  E_shape (deviatoric component, preserves area):
    [-0.000000  -0.000000]
    [-0.000000  -0.000000]
    (Note: Tr(E_shape) = 0.00e+00, traceless ✓)
```

**Interpretation:**

**Diagonal tensors** (off-diagonal ≈ 0):
- No shear strain
- Principal directions aligned with lattice vectors
- Simple isotropic expansion/compression

**E = E_area** (E_shape ≈ 0):
- Pure area change
- Shape preserved (aspect ratio unchanged)
- Both principal strains equal: ε₁ = ε₂

**Opposite signs for A and B:**
- Slab A experiences tensile strain (positive, expansion)
- Slab B experiences compressive strain (negative, contraction)
- Both deform to meet at common target cell

## Step 4: Verify Orthogonality

Check that the decomposition is truly orthogonal:

```python
# Verify orthogonality: ||E||² = ||E_area||² + ||E_shape||²
for slab_name in ['slab_A', 'slab_B']:
    slab_data = strain_info_50[slab_name]

    norm_E_sq = slab_data['norm_E']**2
    norm_sum_sq = slab_data['norm_E_area']**2 + slab_data['norm_E_shape']**2

    print(f"\n{slab_name} orthogonality check:")
    print(f"  ||E||² = {norm_E_sq:.8f}")
    print(f"  ||E_area||² + ||E_shape||² = {norm_sum_sq:.8f}")
    print(f"  Difference: {abs(norm_E_sq - norm_sum_sq):.2e}  ✓")
```

**Expected output:**

```
slab_{A} orthogonality check:
  \|E\|² = 0.00204866
  \|E_area\|² + \|E_shape\|² = 0.00204866
  Difference: 2.17e-19  ✓

slab_{B} orthogonality check:
  \|E\|² = 0.00204866
  \|E_area\|² + \|E_shape\|² = 0.00204866
  Difference: 2.17e-19  ✓
```

The difference is at machine precision (~10⁻¹⁹), confirming orthogonality.

## Step 5: Crystallographic Directions

Map principal strain directions to crystallographic coordinates:

```python
print("\n" + "="*80)
print("PRINCIPAL STRAIN DIRECTIONS IN CONVENTIONAL CELL COORDINATES")
print("="*80)

print("\nPrincipal strain directions show which crystallographic directions")
print("in the conventional unit cell experience maximum and minimum strain.")
print("\nDirections are expressed as: direction = u*a + v*b + w*c")
print("where a, b, c are the conventional cell lattice vectors.\n")

directions = ws.analysis.get_principal_strain_directions_crystallographic(
    prototype_id, alpha=0.5
)

for slab_name in ['slab_A', 'slab_B']:
    slab_dirs = directions[slab_name]

    print(f"\n{slab_name} ({slab_dirs['conventional_cell_formula']}):")
    print(f"  Direction 1 (ε₁): {slab_dirs['formatted'][0]}")
    print(f"  Direction 2 (ε₂): {slab_dirs['formatted'][1]}")

    # Show numerical values
    conv_dirs = np.array(slab_dirs['directions_conventional'])
    print(f"\n  Conventional cell fractional coordinates [u v w]:")
    print(f"    Direction 1: [{conv_dirs[0,0]:+.4f}, {conv_dirs[1,0]:+.4f}, {conv_dirs[2,0]:+.4f}]")
    print(f"    Direction 2: [{conv_dirs[0,1]:+.4f}, {conv_dirs[1,1]:+.4f}, {conv_dirs[2,1]:+.4f}]")

    # Show Cartesian values for reference
    cart_dirs = np.array(slab_dirs['directions_cart'])
    print(f"\n  Cartesian coordinates (Å, in-plane only):")
    print(f"    Direction 1: [{cart_dirs[0,0]:+.4f}, {cart_dirs[1,0]:+.4f}, 0.0000]")
    print(f"    Direction 2: [{cart_dirs[0,1]:+.4f}, {cart_dirs[1,1]:+.4f}, 0.0000]")
```

**Expected output:**

```
slab_{A} (LiF):
  Direction 1 (ε₁): [1 0 0]
  Direction 2 (ε₂): [0 1 0]

  Conventional cell fractional coordinates [u v w]:
    Direction 1: [+1.0000, +0.0000, +0.0000]
    Direction 2: [+0.0000, +1.0000, +0.0000]

  Cartesian coordinates (Å, in-plane only):
    Direction 1: [+4.0234, +0.0000, 0.0000]
    Direction 2: [+0.0000, +4.0234, 0.0000]

slab_{B} (Li2O):
  Direction 1 (ε₁): [1 0 0]
  Direction 2 (ε₂): [0 1 0]

  Conventional cell fractional coordinates [u v w]:
    Direction 1: [+1.0000, +0.0000, +0.0000]
    Direction 2: [+0.0000, +1.0000, +0.0000]

  Cartesian coordinates (Å, in-plane only):
    Direction 1: [+4.5678, +0.0000, 0.0000]
    Direction 2: [+0.0000, +4.5678, 0.0000]
```

**Interpretation:**

**Simple case** ([1 0 0], [0 1 0]):
- Principal directions align with lattice vectors
- Strain is along a-axis and b-axis
- No off-diagonal (shear) components

**Complex case** (e.g., [1 1 0], [1 -1 0]):
- Principal directions along diagonals
- Strain maximized along specific crystallographic planes
- Important for understanding anisotropic properties

**Physical meaning:**
- Direction [1 1 0] in cubic cell: along face diagonal
- Direction [1 1 1] in cubic cell: along body diagonal
- Helps predict which crystal facets are most strained

## Step 6: Comparison Table Across α Values

Create a summary table comparing strain metrics:

```python
print("\n" + "="*80)
print("STRAIN METRICS COMPARISON ACROSS ALPHA VALUES")
print("="*80)

# Collect data for table
comparison_data = []
for alpha in [0.0, 0.25, 0.5, 0.75, 1.0]:
    strain = ws.analysis.analyze_prototype_strain(prototype_id, alpha=alpha)

    comparison_data.append({
        "alpha": f"{alpha:.2f}",
        "slab": "A",
        "eps_max": f"{strain['slab_A']['max_principal_strain']:.5f}",
        "norm_E": f"{strain['slab_A']['norm_E']:.5f}",
        "norm_area": f"{strain['slab_A']['norm_E_area']:.5f}",
        "norm_shape": f"{strain['slab_A']['norm_E_shape']:.5f}",
        "Tr(E)": f"{strain['slab_A']['trace_E']:+.5f}",
    })

    comparison_data.append({
        "alpha": f"{alpha:.2f}",
        "slab": "B",
        "eps_max": f"{strain['slab_B']['max_principal_strain']:.5f}",
        "norm_E": f"{strain['slab_B']['norm_E']:.5f}",
        "norm_area": f"{strain['slab_B']['norm_E_area']:.5f}",
        "norm_shape": f"{strain['slab_B']['norm_E_shape']:.5f}",
        "Tr(E)": f"{strain['slab_B']['trace_E']:+.5f}",
    })

# Display formatted table
table_str = ws.enrichment.format_table(
    comparison_data,
    headers=["alpha", "slab", "eps_max", "norm_E", "norm_area", "norm_shape", "Tr(E)"],
    style="grid"
)
print(table_str)
```

**Expected output:**
```text
┌───────┬──────┬─────────┬─────────┬───────────┬────────────┬──────────┐
│ alpha │ slab │ eps_max │ norm_{E}  │ norm_area │ norm_shape │ Tr(E)    │
├───────┼──────┼─────────┼─────────┼───────────┼────────────┼──────────┤
│ 0.00  │ A    │ 0.00000 │ 0.00000 │ 0.00000   │ 0.00000    │ +0.00000 │
│ 0.00  │ B    │ 0.06402 │ 0.09053 │ 0.09053   │ 0.00000    │ -0.12805 │
│ 0.25  │ A    │ 0.01600 │ 0.02263 │ 0.02263   │ 0.00000    │ +0.03201 │
│ 0.25  │ B    │ 0.04801 │ 0.06789 │ 0.06789   │ 0.00000    │ -0.09603 │
│ 0.50  │ A    │ 0.03201 │ 0.04526 │ 0.04526   │ 0.00000    │ +0.06402 │
│ 0.50  │ B    │ 0.03201 │ 0.04526 │ 0.04526   │ 0.00000    │ -0.06402 │
│ 0.75  │ A    │ 0.04801 │ 0.06789 │ 0.06789   │ 0.00000    │ +0.09603 │
│ 0.75  │ B    │ 0.01600 │ 0.02263 │ 0.02263   │ 0.00000    │ -0.03201 │
│ 1.00  │ A    │ 0.06402 │ 0.09053 │ 0.09053   │ 0.00000    │ +0.12805 │
│ 1.00  │ B    │ 0.00000 │ 0.00000 │ 0.00000   │ 0.00000    │ +0.00000 │
└───────┴──────┴─────────┴─────────┴───────────┴────────────┴──────────┘
```

**Observations:**
- **Linear interpolation**: Strain scales linearly with α
- **Symmetry**: α=0.25 and α=0.75 are mirrors (A↔B)
- **Conservation**: Sum of magnitudes conserved across α
- **Shape strain**: Zero for this example (pure area change)

## Complete Example

```python
from pathlib import Path
from calm.project import open_workspace
import numpy as np

# 1. Open workspace and get prototype
root = Path("./my_workspace")
ws = open_workspace(root=root)

pareto_prototypes = ws.list_prototypes(pareto=True, limit=1000)
prototype_id = pareto_prototypes[0].id_short

# 2. Analyze at multiple alpha values
alphas = [0.0, 0.25, 0.5, 0.75, 1.0]

for alpha in alphas:
    strain_info = ws.analysis.analyze_prototype_strain(prototype_id, alpha=alpha)

    for slab_name in ['slab_A', 'slab_B']:
        slab_data = strain_info[slab_name]
        eps1, eps2 = slab_data['principal_strains']
        norm_E = slab_data['norm_E']

        print(f"α={alpha:.2f}, {slab_name}: ε₁={eps1:+.5f}, ε₂={eps2:+.5f}, ||E||={norm_E:.5f}")

# 3. Detailed analysis at α=0.5
strain_50 = ws.analysis.analyze_prototype_strain(prototype_id, alpha=0.5)

for slab_name in ['slab_A', 'slab_B']:
    slab = strain_50[slab_name]
    E = np.array(slab['E'])

    print(f"\n{slab_name} strain tensor:")
    print(f"  [{E[0,0]:+.6f}  {E[0,1]:+.6f}]")
    print(f"  [{E[1,0]:+.6f}  {E[1,1]:+.6f}]")

    # Verify orthogonality
    norm_E_sq = slab['norm_E']**2
    norm_sum_sq = slab['norm_E_area']**2 + slab['norm_E_shape']**2
    print(f"  Orthogonality check: {abs(norm_E_sq - norm_sum_sq):.2e}")

# 4. Get crystallographic directions
directions = ws.analysis.get_principal_strain_directions_crystallographic(
    prototype_id, alpha=0.5
)

for slab_name in ['slab_A', 'slab_B']:
    dirs = directions[slab_name]
    print(f"\n{slab_name} ({dirs['conventional_cell_formula']}):")
    print(f"  Direction 1: {dirs['formatted'][0]}")
    print(f"  Direction 2: {dirs['formatted'][1]}")
```

## Key Takeaways

1. **Hencky Strain is Natural for Interfaces**
   - Exact for large deformations
   - Additive under sequential deformations
   - Geodesic interpolation on SPD(2) manifold

2. **Orthogonal Decomposition**
   - E = E_area + E_shape
   - ||E||² = ||E_area||² + ||E_shape||²
   - Physical separation of area vs shape changes

3. **Principal Strains are Eigenvalues**
   - ε₁, ε₂ = eigenvalues of E
   - ||E||_F = sqrt(ε₁² + ε₂²)
   - Trace: Tr(E) = ε₁ + ε₂ = ln(area ratio)

4. **Strain Partition Controls Distribution**
   - α = 0: All strain on B
   - α = 0.5: Symmetric distribution
   - α = 1: All strain on A
   - Linear interpolation between extremes

5. **Crystallographic Directions Matter**
   - Principal directions map to crystal axes
   - Helps understand anisotropic response
   - Useful for experimental design

6. **Verification is Important**
   - Always check orthogonality
   - Verify trace = ln(area ratio)
   - Confirm symmetry under α → 1-α

## Physical Interpretation Guidelines

### Principal Strain Magnitudes

| |ε_max| | Interpretation | Typical Regime |
|---------|----------------|----------------|
| < 0.01 | Very small | Elastic, reversible |
| 0.01-0.05 | Small | Elastic, minor defects |
| 0.05-0.10 | Moderate | Transition, dislocations possible |
| 0.10-0.15 | Large | Plastic, significant reconstruction |
| > 0.15 | Very large | Beyond elastic limit |

### Area vs Shape Strain

**Dominated by area** (||E_area|| >> ||E_shape||):
- Isotropic expansion/compression
- ε₁ ≈ ε₂
- Maintains shape, changes size
- Common for matching similar lattices

**Dominated by shape** (||E_shape|| >> ||E_area||):
- Shear deformation
- ε₁ and ε₂ have opposite signs
- Changes shape, preserves area
- Common for dissimilar lattice symmetries

**Mixed** (||E_area|| ≈ ||E_shape||):
- Both effects significant
- Complex deformation
- Analyze components separately

### Trace Interpretation

**Tr(E) > 0**: Tensile (expansion)
- Cell area increases
- Atoms pushed apart
- May reduce bonding

**Tr(E) < 0**: Compressive (contraction)
- Cell area decreases
- Atoms pushed together
- May increase bonding or cause overlap

**Tr(E) ≈ 0**: Area-preserving
- Pure shape change
- Shear-dominated
- Deviatoric deformation

### Sign of Principal Strains

**Both positive (ε₁ > 0, ε₂ > 0)**:
- Biaxial tension
- Cell stretched in all directions
- Weakens bonds uniformly

**Both negative (ε₁ < 0, ε₂ < 0)**:
- Biaxial compression
- Cell squeezed in all directions
- Strengthens bonds or causes buckling

**Opposite signs (ε₁ > 0, ε₂ < 0)**:
- Shear-like deformation
- Stretch one direction, compress other
- Changes aspect ratio significantly

## Troubleshooting

**Strain values seem wrong:**
```python
# Check reference and deformed states
proto = ws.get_prototype(prototype_id)
print(f"Slab A area: {proto.cell_area_a:.4f} Ų")
print(f"Slab B area: {proto.cell_area_b:.4f} Ų")
print(f"Target cell area: {proto.target_cell_area:.4f} Ų")

# Verify area ratios
strain = ws.analysis.analyze_prototype_strain(prototype_id, alpha=0.5)
for slab_name in ['slab_A', 'slab_B']:
    area_ratio = strain[slab_name]['area_ratio']
    trace_E = strain[slab_name]['trace_E']
    print(f"{slab_name}: area_ratio={area_ratio:.6f}, exp(Tr(E))={np.exp(trace_E):.6f}")
    # These should match
```

**Orthogonality check fails:**
```python
# Check for numerical precision issues
norm_E_sq = slab['norm_E']**2
norm_sum_sq = slab['norm_E_area']**2 + slab['norm_E_shape']**2
rel_error = abs(norm_E_sq - norm_sum_sq) / norm_E_sq

if rel_error > 1e-6:
    print(f"Warning: Large orthogonality error: {rel_error:.2e}")
    # May indicate numerical instability or algorithm error
else:
    print(f"OK: Orthogonality verified (relative error: {rel_error:.2e})")
```

**Crystallographic directions look strange:**
```python
# Verify directions are orthonormal (for symmetric case)
dirs = directions['slab_A']
cart_dirs = np.array(dirs['directions_cart'])
dir1, dir2 = cart_dirs[:, 0], cart_dirs[:, 1]

# Check normalization
norm1 = np.linalg.norm(dir1)
norm2 = np.linalg.norm(dir2)
print(f"Direction 1 norm: {norm1:.6f}")
print(f"Direction 2 norm: {norm2:.6f}")

# Check orthogonality
dot_product = np.dot(dir1, dir2)
print(f"Dot product: {dot_product:.2e}")
# Should be ~0 for orthogonal directions
```

**Very small strains (< 0.001):**
```python
# Use a different prototype with larger strain
pareto_sorted = sorted(pareto_prototypes,
                      key=lambda p: p.hencky_norm,
                      reverse=True)

# Try prototype with larger strain
prototype_id = pareto_sorted[0].id_short
print(f"Selected prototype with hencky_norm = {pareto_sorted[0].hencky_norm:.4f}")
```

## Advanced Topics

### Non-Diagonal Strain Tensors

When E has non-zero off-diagonal elements:

$$
E = [ε_xx   ε_xy]
    [ε_xy   ε_yy]
$$

**Physical meaning:**
- ε_xy ≠ 0: Shear strain present
- Principal directions rotated from lattice vectors
- More complex deformation pattern

**Analysis:**
- Eigendecomposition: E = Q @ Λ @ Q^T
- Λ = diag(ε₁, ε₂): principal strains
- Q columns: principal directions

### Relation to Elastic Energy

For linear elastic material with Young's modulus E and Poisson ratio ν:

$$
U_elastic ∝ E × (ε₁² + ε₂² + 2ν ε₁ ε₂)
$$

**CALM's Frobenius norm** (||E||_F² = ε₁² + ε₂²) corresponds to **isotropic elasticity** (ν = 0).

For anisotropic materials, strain decomposition helps separate:
- Volumetric energy (from E_area)
- Deviatoric energy (from E_shape)

### Multiple Interfaces

For systems with multiple interfaces in series:

$$
E_total = E₁ + E₂ + ... + E_{n}
$$

Hencky strain **adds** under sequential deformations (advantage over other strain measures).

## Next Steps

- **[Tutorial 4: Follow-up Analyses](04_followups.md)** - Use strain analysis to optimize α
- **DFT Calculations** - Export interfaces and validate with ab initio
-- **[Algorithm: Geodesic Strain Partitioning](../mathematics/algorithms/geodesic-strain-partitioning.md)** - Mathematical details

## Related Documentation

- [Glossary: Hencky Strain](../glossary.md#hencky-strain)
- [Glossary: Principal Strains](../glossary.md#principal-strains)
- [API Reference: analyze_prototype_strain](../reference/public_api.md)
See runnable examples in the Example Scripts guide: `docs/guides/examples/index.md`.

## Further Reading

**Strain theory:**
- Ogden, R. W. (1997). "Non-linear Elastic Deformations." Dover.
- Holzapfel, G. A. (2000). "Nonlinear Solid Mechanics." Wiley.

**Logarithmic strain:**
- Hencky, H. (1928). "Über die Form des Elastizitätsgesetzes bei ideal elastischen Stoffen." Z. Tech. Phys.
- Xiao, H. et al. (1997). "Elastoplasticity beyond small deformations." Acta Mech.

**SPD manifold geometry:**
- Pennec, X. et al. (2006). "A Riemannian Framework for Tensor Computing." IJCV.
-- [Algorithm Documentation: Strain Partitioning](../mathematics/algorithms/geodesic-strain-partitioning.md)

**Computational mechanics:**
- Bonet, J. & Wood, R. D. (2008). "Nonlinear Continuum Mechanics for Finite Element Analysis." Cambridge.
