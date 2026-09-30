# ASE Atoms Format Specification for CALM

This document specifies the expected format and assumptions for ASE `Atoms` objects used in CALM.

## Overview

CALM uses ASE (Atomic Simulation Environment) `Atoms` objects to represent atomistic structures. To ensure correct behavior and prevent data corruption, CALM makes specific assumptions about the format of these objects.

## Required Attributes

### 1. Periodic Boundary Conditions (PBC)

**Requirement:** All bulk and slab structures must have PBC set appropriately.

```python
from ase import Atoms

# Bulk structures: PBC in all directions
bulk = Atoms(..., pbc=True)  # Equivalent to pbc=[True, True, True]

# Slab structures: PBC in xy, open in z
slab = Atoms(..., pbc=[True, True, False])
```

**Why this matters:**
- CALM uses PBC to determine periodic vs non-periodic directions
- Symmetry analysis requires proper PBC
- Interface matching assumes xy periodicity

**Validation:**
```python
from calm.util.atoms_validation import validate_atoms

# This will check PBC is set
validate_atoms(atoms, expected_pbc=[True, True, True])
```

---

### 2. Cell Format

**Requirement:** Cell must be a 3x3 array representing lattice vectors.

```python
import numpy as np

# Cell as 3x3 array of lattice vectors
cell = np.array([
    [a, 0, 0],      # a-vector
    [0, b, 0],      # b-vector
    [0, 0, c]       # c-vector
])
atoms = Atoms(..., cell=cell)
```

**Supported formats:**
- 3x3 NumPy array
- 3x3 nested list
- Length-3 array `[a, b, c]` for orthorhombic cells (converted to 3x3 diagonal)
- ASE `Cell` object

**Why this matters:**
- CALM computes cell volumes, angles, and reciprocal space vectors
- Interface matching requires well-defined cell vectors
- Zero or near-zero cell volume causes numerical issues

**Validation:**
```python
# Check cell volume is positive
validate_atoms(atoms, min_volume=1e-10)

# Cell volume
volume = atoms.cell.volume  # Must be > 0
```

---

### 3. Atomic Positions

**Requirement:** Positions must be finite, non-NaN floating-point values.

**Position formats supported:**
- **Cartesian coordinates**: Absolute positions in Ångströms (Å)
- **Scaled/fractional coordinates**: Positions relative to cell vectors [0, 1)

```python
# Cartesian positions
atoms = Atoms(symbols=['Al'], positions=[[0.0, 0.0, 0.0]], cell=[4.05, 4.05, 4.05])

# Scaled positions (preferred for periodic structures)
atoms = Atoms(symbols=['Al'], scaled_positions=[[0.0, 0.0, 0.0]], cell=[4.05, 4.05, 4.05])
```

**CALM's internal handling:**
- Bulks/slabs are typically stored as scaled positions
- Scaled positions are wrapped to [0, 1) for periodicity
- Use `atoms.get_scaled_positions(wrap=True)` for canonical positions

**Why this matters:**
- NaN or infinite positions break symmetry analysis
- Unwrapped positions can cause duplicate atom detection failures
- Positions outside cell need proper wrapping for periodic systems

**Validation:**
```python
# Check positions are finite
validate_atoms(atoms, check_finite_positions=True)

# Get wrapped scaled positions
frac_pos = atoms.get_scaled_positions(wrap=True)
```

---

### 4. Chemical Symbols

**Requirement:** All atoms must have valid chemical symbols or atomic numbers.

```python
# Using symbols
atoms = Atoms(symbols=['Al', 'Cu', 'Al'], positions=[[0,0,0], [0.5,0.5,0], [1,1,0]], cell=[4,4,4], pbc=True)

# Using atomic numbers
atoms = Atoms(numbers=[13, 29, 13], positions=[[0,0,0], [0.5,0.5,0], [1,1,0]], cell=[4,4,4], pbc=True)
```

**Why this matters:**
- Chemical formula generation
- Mass calculations for energy densities
- Calculator requirements

---

### 5. Units

**Requirement:** CALM follows ASE conventions.

- **Lengths**: Angstroms (Å)
- **Energies**: Electronvolts (eV)
- **Forces**: eV/Å
- **Stress**: eV/Ų
- **Angles**: Radians (in some contexts, degrees in others - check API docs)

**Why this matters:**
- Mixed units cause incorrect energy/area calculations
- Interface energy is reported in eV/Ų

---

## Common Edge Cases

### Empty Atoms

**Problem:** Empty `Atoms()` with no atoms

**CALM behavior:** Raises `ValidationError`

```python
atoms = Atoms()  # Empty, len(atoms) == 0

validate_atoms(atoms)  # Raises ValidationError
```

**Why:** Empty structures have undefined cell volume, symmetry, and properties.

---

### Zero Cell Volume

**Problem:** Cell volume = 0 or very small (< 1e-10 Ų)

**Causes:**
- Flat cell (e.g., 2D structure without vacuum)
- Parallel cell vectors

**CALM behavior:** Raises `ValidationError`

```python
# Flat cell (determinant = 0)
atoms = Atoms(symbols=['H'], cell=[[1, 0, 0], [0, 1, 0], [0, 0, 0]])

validate_atoms(atoms)  # Raises ValidationError: cell volume too small
```

**Fix:** Add appropriate dimensions or vacuum.

---

### Non-orthogonal Cells

**Problem:** CALM assumptions about orthogonal cells

**Status:** CALM **supports** non-orthogonal cells (triclinic, monoclinic, etc.)

**However:** Some operations assume:
- Slab z-direction is perpendicular to xy plane
- Vacuum padding in z-direction

**Best practice:** For slabs, use cells where:
- c-vector is approximately perpendicular to a,b vectors
- If not, CALM's slab generation will rotate the cell appropriately

---

### Duplicate Atoms

**Problem:** Two atoms at identical positions

**CALM behavior:** May pass validation but cause issues in symmetry analysis

**Detection:**
```python
from calm.util.atoms_validation import check_duplicate_atoms

# Check for atoms closer than tolerance
duplicates = check_duplicate_atoms(atoms, tolerance=0.01)
if duplicates:
    print(f"Found {len(duplicates)} duplicate atom pairs")
```

---

### Atoms Outside Cell

**Problem:** Cartesian positions outside cell bounds

**CALM behavior:** Wraps positions to [0, 1) in scaled coordinates

```python
from calm.util.atoms_validation import normalize_atoms

# Wrap positions into cell
atoms = normalize_atoms(atoms, wrap=True)
```

---

## Validation Utilities

### `validate_atoms(atoms, **options)`

Validate an ASE Atoms object meets CALM's requirements.

```python
from calm.util.atoms_validation import validate_atoms

validate_atoms(
    atoms,
    expected_pbc=None,          # Expected PBC (e.g., [True, True, True])
    min_volume=1e-10,            # Minimum cell volume (Ų)
    check_finite_positions=True, # Check positions are finite (not NaN/inf)
    allow_empty=False,           # Allow empty Atoms objects
    context="bulk structure"     # Context for error messages
)
```

**Raises:** `ValidationError` if validation fails

---

### `normalize_atoms(atoms, **options)`

Normalize an ASE Atoms object to CALM's canonical format.

```python
from calm.util.atoms_validation import normalize_atoms

normalized = normalize_atoms(
    atoms,
    wrap=True,              # Wrap positions to [0, 1)
    center=False,           # Center structure in cell
    set_pbc=None,          # Force specific PBC (e.g., [True, True, True])
    tolerance=1e-10         # Tolerance for numerical operations
)
```

**Returns:** New `Atoms` object in normalized format (does not modify input)

---

### `check_duplicate_atoms(atoms, tolerance=0.01)`

Check for duplicate atoms (atoms closer than tolerance).

```python
from calm.util.atoms_validation import check_duplicate_atoms

duplicates = check_duplicate_atoms(atoms, tolerance=0.01)

if duplicates:
    for (i, j), dist in duplicates:
        print(f"Atoms {i} and {j} are only {dist:.4f} Å apart")
```

**Returns:** List of `((i, j), distance)` tuples for duplicate pairs

---

## Best Practices

### 1. Always Validate at Entry Points

```python
from calm.util.atoms_validation import validate_atoms

def prepare_bulk(atoms, **kwargs):
    """Prepare bulk structure."""
    # Validate at API boundary
    validate_atoms(atoms, expected_pbc=[True, True, True], context="bulk")

    # Continue with processing
    ...
```

### 2. Normalize Before Storage

```python
from calm.util.atoms_validation import normalize_atoms

# Normalize before persisting
atoms_normalized = normalize_atoms(atoms, wrap=True)

# Store normalized version
bulk = Bulk(uid_full='bulk:...', id_short='b_...', label='Example', payload={'atoms': atoms_dict})
```

### 3. Use Scaled Positions for Periodic Structures

```python
# Preferred: Scaled positions
atoms = Atoms(
    symbols=['Al', 'Al'],
    scaled_positions=[[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]],
    cell=[4.05, 4.05, 4.05],
    pbc=True
)

# Works but less ideal: Cartesian positions
atoms = Atoms(
    symbols=['Al', 'Al'],
    positions=[[0.0, 0.0, 0.0], [2.025, 2.025, 2.025]],
    cell=[4.05, 4.05, 4.05],
    pbc=True
)
```

### 4. Check Cell Volume Before Operations

```python
if atoms.cell.volume < 1e-10:
    raise ValueError(f"Cell volume {atoms.cell.volume} is too small")

# Or use validation
validate_atoms(atoms, min_volume=1e-10)
```

---

## Common Errors and Fixes

### Error: "Cell volume is too small"

**Cause:** Zero or near-zero cell volume

**Fix:**
```python
# Check cell
print(f"Cell: {atoms.cell.array}")
print(f"Volume: {atoms.cell.volume}")

# Fix: Ensure proper 3D cell
atoms.cell = [[a, 0, 0], [0, b, 0], [0, 0, c]]
```

---

### Error: "Atoms object is empty"

**Cause:** No atoms in structure

**Fix:**
```python
if len(atoms) == 0:
    raise ValueError("Cannot process empty structure")
```

---

### Error: "Positions contain NaN or infinite values"

**Cause:** Invalid positions from failed calculations or I/O

**Fix:**
```python
import numpy as np

# Check for NaN/inf
positions = atoms.get_positions()
if not np.all(np.isfinite(positions)):
    raise ValueError("Positions contain invalid values")

# Or use validation
validate_atoms(atoms, check_finite_positions=True)
```

---

### Warning: "Duplicate atoms detected"

**Cause:** Two atoms at same position (within tolerance)

**Fix:**
```python
from calm.util.atoms_validation import check_duplicate_atoms, remove_duplicate_atoms

# Check for duplicates
duplicates = check_duplicate_atoms(atoms, tolerance=0.01)

if duplicates:
    # Option 1: Remove duplicates automatically
    atoms = remove_duplicate_atoms(atoms, tolerance=0.01)

    # Option 2: Manually investigate
    for (i, j), dist in duplicates:
        print(f"Atoms {i} and {j} at distance {dist}")
```

---

## Numerical Tolerances

CALM uses these default tolerances:

- **Position comparison**: `1e-5` Å
- **Cell volume minimum**: `1e-10` Ų
- **Duplicate atom detection**: `0.01` Å
- **Symmetry analysis** (spglib): `1e-5` Å
- **Float equality** (general): `1e-10`

These can be configured via function parameters where appropriate.

---

## Related Documentation

- [UID Hashing Specification](uid_hashing_specification.md) - How structures are hashed for UIDs
- `calm.validation` module - Input validation for parameters and structures
- [ASE Documentation](https://wiki.fysik.dtu.dk/ase/) - Official ASE docs

---

## Version History

- **CALM 0.1.0**: Initial ASE Atoms specification
- **Schema v1.0.0**: Atoms format is stable

---

## Summary Checklist

When working with ASE Atoms in CALM:

- ✅ Check PBC is set appropriately
- ✅ Verify cell volume > 1e-10 Ų
- ✅ Ensure positions are finite (no NaN/inf)
- ✅ Use scaled positions for periodic structures
- ✅ Wrap positions to [0, 1) for consistency
- ✅ Validate at API boundaries
- ✅ Normalize before storage
- ✅ Check for duplicate atoms if structure quality is uncertain
