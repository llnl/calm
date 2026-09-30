# UID Hashing Specification

This document specifies the content-addressed UID algorithms used throughout CALM for deterministic object identification.

## Overview

CALM uses **content-addressed identifiers** (UIDs) as stable, platform-independent keys for all workspace objects. UIDs are generated using **canonical JSON serialization + SHA256 hashing**.

### Design Goals

1. **Stability**: Same input always produces same UID across platforms
2. **No filesystem paths**: UIDs depend only on scientific content, not file locations
3. **No object identity**: Python object identity (`id()`) is never used
4. **Float stability**: Explicit rounding rules prevent floating-point noise from breaking UIDs

### UID Format

All UIDs follow the format: `<prefix>:<hash>`

Where:
- `<prefix>` identifies the object type (`mat`, `bulk`, `slab`, `proto`, etc.)
- `<hash>` is a deterministic hex digest derived from canonical content

---

## Canonical JSON Algorithm

All UIDs use the same canonicalization process defined in `calm/keys/uid.py`:

### Canonicalization Rules

```python
def _canonicalize(obj, *, float_decimals=12):
    """Convert obj into JSON-serializable canonical representation."""
```

#### Primitives
- **None, bool, int, str**: Pass through unchanged
- **float**: Round to `float_decimals` (default 12), treat `|x| < 10^-12` as exactly 0.0
- **numpy scalars**: Convert to Python primitives, then apply above rules

#### Collections
- **dict/Mapping**: Sort keys alphabetically, recursively canonicalize values
- **list/tuple**: Recursively canonicalize each element (preserves order)
- **set/frozenset**: Convert to sorted list after canonicalization
- **numpy.ndarray**:
  - Integer arrays → `list[int]`
  - Float arrays → round to `float_decimals`, then `list[float]`

#### Dataclasses
- Convert to dict via `asdict()`, then apply dict rules

### JSON Serialization

```python
def canonical_json(obj, *, float_decimals=12):
    canon = _canonicalize(obj, float_decimals=float_decimals)
    return json.dumps(canon, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
```

**Parameters:**
- `sort_keys=True`: Ensures stable key ordering in nested dicts
- `separators=(",", ":")`: Removes whitespace for compact, stable format
- `ensure_ascii=True`: Avoids unicode encoding variations

### SHA256 Hashing

```python
def sha256_hex(text: str):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def hash_obj(obj, *, float_decimals=12):
    return sha256_hex(canonical_json(obj, float_decimals=float_decimals))
```

---

## UID Types

### 1. Material UID

**Format**: `mat:<hash>`

**Input**: Conventional cell (standardized via spglib)

**Algorithm**:
```python
def material_uid_from_conv_atoms(conv_atoms, *, symprec=1e-5, no_idealize=False, float_decimals=12):
    # Extract structure
    cell = conv_atoms.cell.array  # 3x3 lattice vectors
    frac = conv_atoms.get_scaled_positions(wrap=True)  # Fractional coordinates
    syms = conv_atoms.get_chemical_symbols()  # Element symbols

    # Sort atoms: (symbol, frac_x, frac_y, frac_z)
    atoms = list(zip(syms, frac.tolist()))
    atoms.sort(key=lambda t: (t[0],) + tuple(round(x, float_decimals) for x in t[1]))

    # Build canonical payload
    payload = {
        "cell": round(cell, float_decimals).tolist(),
        "atoms": [{"symbol": s, "frac": round(f, float_decimals)} for s, f in atoms],
        "pbc": [bool(x) for x in conv_atoms.pbc],
        "symprec": float(symprec),
        "no_idealize": bool(no_idealize)
    }

    return "mat:" + hash_obj(payload, float_decimals=float_decimals)
```

**Key Fields**:
- `cell`: Lattice vectors (Å), rounded to 12 decimals
- `atoms`: Sorted list of `{symbol, frac}` (fractional coordinates)
- `pbc`: Periodic boundary conditions (typically `[True, True, True]`)
- `symprec`: Symmetry precision used for standardization
- `no_idealize`: Whether idealization was skipped

**Stability Note**: Atoms are sorted deterministically, making UID order-independent.

---

### 2. Bulk UID

**Format**: `bulk:<hash>`

**Algorithm**:
```python
def reference_bulk_uid(material_uid: str):
    """Deterministic bulk_uid for the reference bulk state of a material."""
    if material_uid.startswith("mat:"):
        return "bulk:" + material_uid[4:]  # Remove "mat:" prefix, add "bulk:"
    return "bulk:" + material_uid
```

**Convention**:
- Reference bulk: `mat:<X>` → `bulk:<X>`
- Optimized bulks get separate UIDs based on calculator provenance

---

### 3. Slab Spec UID

**Format**: `sspec:<hash>`

**Algorithm** (reference bulk):
```python
def slab_spec_uid(spec, *, float_decimals=12):
    return "sspec:" + hash_obj(spec, float_decimals=float_decimals)
```

**Algorithm** (optimized bulk):
```python
def slab_spec_uid_for_bulk(spec, *, bulk_uid, bulk_kind="reference", float_decimals=12):
    if bulk_kind == "reference":
        return slab_spec_uid(spec, float_decimals=float_decimals)

    # For non-reference bulks, anchor to specific bulk state
    payload = {"spec": spec, "bulk_uid": bulk_uid, "bulk_kind": bulk_kind}
    return "sspec:" + hash_obj(payload, float_decimals=float_decimals)
```

**Why bulk anchoring?**: The same `SlabSpec` applied to different relaxed cells yields different slabs. Anchoring prevents UID collisions.

---

### 4. Slab UID

**Format**: `slab:<material_uid>:<h>,<k>,<l>:<slab_spec_uid>`

**Algorithm**:
```python
def slab_uid(*, material_uid, miller, slab_spec_uid):
    h, k, l = int(miller[0]), int(miller[1]), int(miller[2])
    return f"slab:{material_uid}:{h},{k},{l}:{slab_spec_uid}"
```

**Components**:
- `material_uid`: Parent material (e.g., `mat:abc123...`)
- `h,k,l`: Miller indices (integer)
- `slab_spec_uid`: Slab generation parameters (e.g., `sspec:def456...`)

**Example**: `slab:mat:abc123...:1,1,1:sspec:def456...`

---

### 5. Supercell UID

**Format**: `scell:<slab_uid>:<a>,<b>,<c>,<d>`

**Algorithm**:
```python
def supercell_uid(*, slab_uid, hnf_key_pg):
    key = tuple(int(x) for x in hnf_key_pg)
    if len(key) != 4:
        raise ValueError("hnf_key_pg must be length-4")
    return f"scell:{slab_uid}:{key[0]},{key[1]},{key[2]},{key[3]}"
```

**Components**:
- `slab_uid`: Parent slab
- `a,b,c,d`: Hermite Normal Form (HNF) key encoding the supercell transformation (4 integers)

---

### 6. Prototype UID

**Format**: `proto:A[<supercell_uid_a>]__B[<supercell_uid_b>]`

**Algorithm**:
```python
def prototype_uid(*, supercell_uid_a, supercell_uid_b):
    return f"proto:A[{supercell_uid_a}]__B[{supercell_uid_b}]"
```

**Components**:
- `supercell_uid_a`: Supercell UID for material A
- `supercell_uid_b`: Supercell UID for material B

---

### 7. Calculator UID

**Format**: `calc:<hash>`

**Algorithm**:
```python
def calculator_uid(calc_spec, *, float_decimals=12):
    return "calc:" + hash_obj(dict(calc_spec), float_decimals=float_decimals)
```

**Input**: `CalculatorSpec` dictionary containing:
- `family`: Calculator family (e.g., "mace", "grace", "ase")
- `model`: Model name (e.g., "medium-mpa-0", "GRACE-1L-OMAT")
- `device`: Device string ("cpu", "cuda")
- `options`: Dict of calculator-specific options

**Example Payload**:
```json
{
  "family": "mace",
  "model": "medium-mpa-0",
  "device": "cpu",
  "options": {"stress": true}
}
```

---

### 8. Strain Model UID

**Format**: `smodel:<hash>`

**Algorithm**:
```python
def strain_model_uid(model, *, float_decimals=12):
    return "smodel:" + hash_obj(model, float_decimals=float_decimals)
```

**Input**: Strain partitioning model parameters

---

### 9. Strained UID

**Format**: `strain:<prototype_uid>:<strain_model_uid>`

**Algorithm**:
```python
def strained_uid(*, prototype_uid, strain_model_uid):
    return f"strain:{prototype_uid}:{strain_model_uid}"
```

---

### 10. Build UID

**Format**: `build:<strained_uid>:t=<t1>,<t2>:zp=<z_padding>`

**Algorithm**:
```python
def build_uid(*, strained_uid, translation_frac, z_padding, round_decimals=8):
    # Wrap translations to [0, 1)
    t1 = wrap01(translation_frac[0])
    t2 = wrap01(translation_frac[1])

    # Round to specified decimals
    t1 = round(t1, round_decimals)
    t2 = round(t2, round_decimals)
    zp = round(z_padding, round_decimals)

    # Avoid -0.0
    if abs(t1) < 10**(-round_decimals): t1 = 0.0
    if abs(t2) < 10**(-round_decimals): t2 = 0.0
    if abs(zp) < 10**(-round_decimals): zp = 0.0

    return f"build:{strained_uid}:t={t1},{t2}:zp={zp}"
```

**Components**:
- `strained_uid`: Parent strained interface
- `t1, t2`: In-plane translation (fractional coordinates)
- `zp`: Vacuum padding in z-direction (Å)

---

### 11. Energy Config UID

**Format**: `econf:<hash>`

**Algorithm**:
```python
def energy_config_uid(econf, *, float_decimals=12):
    return "econf:" + hash_obj(econf, float_decimals=float_decimals)
```

---

### 12. Energy UID

**Format**: `energy:<build_uid>:<calc_uid>:<econf_uid>`

**Algorithm**:
```python
def energy_uid(*, build_uid, calc_uid, econf_uid):
    return f"energy:{build_uid}:{calc_uid}:{econf_uid}"
```

---

### 13. Interface Relaxation UID

**Format**: `ifrel:<hash>`

**Algorithm**:
```python
def interface_relax_uid(*, interface_uid, calc_uid, relax_config_uid, float_decimals=12):
    payload = {
        "interface_uid": str(interface_uid),
        "calc_uid": str(calc_uid),
        "relax_config_uid": str(relax_config_uid)
    }
    return "ifrel:" + hash_obj(payload, float_decimals=float_decimals)
```

**Input**:
- `interface_uid`: Unrelaxed interface build UID
- `calc_uid`: Calculator used for relaxation
- `relax_config_uid`: Relaxation configuration parameters

---

### 14. Run UID

**Format**: `run:<hash>`

**Algorithm** (from `calm/project/application/runs.py`):
```python
def compute_run_uid_full(run_type: str, spec: dict):
    payload = {"run_type": run_type, "spec": spec}
    h = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return f"run:{h}"
```

**Input**:
- `run_type`: Type of run ("prototype_search", "followup_scan", etc.)
- `spec`: Run-specific parameters (dict)

---

## Float Rounding Strategy

### Why Rounding?

Floating-point arithmetic is not perfectly reproducible across:
- Different CPU architectures (x86 vs ARM)
- Different compilers and optimization levels
- Different BLAS/LAPACK implementations

Rounding to 12 decimals provides:
- **Sufficient precision** for atomic structures (~0.000001 Å resolution)
- **Reproducibility** across platforms
- **Collision resistance** (extremely unlikely hash collisions)

### When to Override

The default `float_decimals=12` is appropriate for most cases. Override only if:

1. **Higher precision needed**: Materials with ultra-precise lattice parameters
   ```python
uid = material_uid_from_conv_atoms(atoms, float_decimals=15)
```

2. **Lower precision desired**: Intentionally group "nearly identical" structures
   ```python
uid = material_uid_from_conv_atoms(atoms, float_decimals=8)
```

**Warning**: Changing `float_decimals` breaks UID compatibility with existing workspaces.

---

## UID Stability Guarantees

### Guaranteed Stable

These will **never** change (breaking change would require major version bump):

1. SHA256 hashing algorithm
2. Canonical JSON format (sorted keys, no whitespace)
3. UID prefixes (`mat:`, `bulk:`, `slab:`, etc.)
4. Default `float_decimals=12`
5. Atom sorting in material UIDs (by symbol, then fractional coordinates)

### May Change (Minor/Patch Versions)

These could change in backwards-compatible ways:

1. Additional fields in payload (old fields preserved)
2. New UID types (new prefixes)
3. Improved float rounding logic (if current approach has bugs)

---

## Testing UID Stability

To ensure UID stability across CALM versions:

```python
def test_material_uid_stability():
    """Test that material UIDs remain stable across versions."""
    from ase.build import bulk
    from calm.keys.uid import material_uid_from_conv_atoms

    # Create test structure
    atoms = bulk("Al", "fcc", a=4.05)

    # Known-good UID from CALM 0.1.0
    expected_uid = "mat:abc123..."  # Insert actual UID from test

    # Verify current version produces same UID
    actual_uid = material_uid_from_conv_atoms(atoms, symprec=1e-5)
    assert actual_uid == expected_uid, "UID changed - BREAKING CHANGE!"
```

See `tests/test_schema_versioning.py` for schema compatibility tests.

---

## Debugging UIDs

### Inspecting UID Components

```python
from calm.keys.uid import hash_obj, canonical_json

# See canonical representation
obj = {"family": "mace", "model": "medium-mpa-0", "device": "cpu"}
print(canonical_json(obj))
# Output: {"device":"cpu","family":"mace","model":"medium-mpa-0"}

# Compute hash manually
print(hash_obj(obj))
# Output: abc123...
```

### Common UID Mismatches

**Problem**: "Same" structure produces different UIDs

**Causes**:
1. **Atom order**: Use conventional cell, not primitive
2. **Floating-point noise**: Ensure atoms are properly wrapped (`wrap=True`)
3. **symprec mismatch**: Different `symprec` → different standardization → different UID
4. **Cell vs scaled positions**: Always use `get_scaled_positions(wrap=True)`

---

## Security Considerations

### UID Collisions

**SHA256 collision probability**: ~1 in 2^256 (~10^77)

For context:
- Total atoms in observable universe: ~10^80
- CALM workspace might have: ~10^6 objects

**Practical risk**: Negligible. More likely to encounter:
- Hardware failures
- Cosmic ray bit flips
- Bugs in code

### UID as Primary Keys

UIDs are used as database primary keys (`uid_full` columns). Benefits:

1. **Content-addressed**: Same scientific data → same UID → automatic deduplication
2. **Portable**: UIDs stable across machines, can merge workspaces
3. **Provenance**: UID encodes object's input dependencies

Drawback:
- Long strings (64 hex chars) vs integer primary keys
- Acceptable trade-off for CALM's use case (scientific reproducibility >> storage efficiency)

---

## Implementation Notes

### Location

All UID algorithms are in:
```
calm/keys/uid.py
```

### Dependencies

Minimal:
- `hashlib` (Python stdlib)
- `json` (Python stdlib)
- `numpy` (for array handling)

No ASE dependency at UID computation time (ASE types are passed in, but not imported in uid.py module scope).

### Version History

- **CALM 0.1.0**: Initial UID specification
- **Schema v1.0.0**: UIDs are stable, workspace compatibility guaranteed

---

## References

- Source code: `calm/keys/uid.py`
- Schema versioning: `docs/development/schema_version_guide.md` (if exists)
- Database tables: `calm/project/infrastructure/db/tables.py`
- Tests: `tests/test_schema_versioning.py`

---

## Future Extensions

Potential future UID types (not yet implemented):

- `relax:<build_uid>:<calc_uid>:<relax_spec_uid>` - Relaxed structures
- `phonon:<relax_uid>:<phonon_spec_uid>` - Phonon calculations
- `elastic:<relax_uid>:<elastic_spec_uid>` - Elastic tensors
- `dos:<relax_uid>:<dos_spec_uid>` - Density of states

When adding new UID types, follow the same canonical JSON + SHA256 pattern for consistency.
