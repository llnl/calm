# Bulk canonicalization transforms

CALM canonicalizes bulk inputs using spglib via `calm.symmetry.get_standardized_cell(...)`.

As part of the provenance story, CALM records the **lattice basis transforms** implied by
that standardization in `ase.Atoms.info`.

This reference describes:
- where these transforms are stored,
- their convention (column-basis), and
- how to retrieve them.

## Storage location

The transforms are stored in `Atoms.info` under:

- `calm.bulk.provenance.CALM_BULK_CANONICALIZATION_TRANSFORMS_INFO_KEY`
  (string key: `"calm_bulk_canonicalization_transforms_json"`).

The stored value is a JSON string (for portability) encoding a dictionary.

CALM stamps this key on **both**:
- the standardized conventional bulk cell (`atoms_conventional`), and
- the standardized primitive bulk cell (`atoms_primitive`).

## Convention

The recorded matrices are **column-basis lattice transforms**, consistent with the rest
of CALM’s crystallographic and geodesic code.

Let:
- `C` be the ASE cell matrix with lattice vectors as **rows** (`atoms.cell.array`), and
- `A = C.T` be the lattice matrix with vectors as **columns**.

A lattice transform `S` is recorded such that:

```
A_out = A_in @ S
```

Equivalently in ASE’s row-basis representation:

```
C_out = S.T @ C_in
```

For standardization, `S` is typically *integer-valued* (within a numerical tolerance).
Its determinant gives the volume ratio between the input and the standardized cell.

## What is (and is not) tracked

Tracked:
- Lattice/basis transforms mapping the **input** cell to the standardized conventional and primitive cells.

Not tracked (by design):
- Atom re-ordering performed by spglib.
- Origin shifts / fractional translations performed by spglib.

The intent is to support **cell provenance** and transformation-chain auditing, without
introducing a heavyweight transformation-record table.

## Programmatic access

Use the helpers in `calm.bulk.provenance`:

```python
from calm.bulk.provenance import get_bulk_canonicalization_transforms

# atoms_conv is an ASE Atoms object for a canonical conventional bulk
rec = get_bulk_canonicalization_transforms(atoms_conv)
if rec is None:
    raise RuntimeError("No canonicalization provenance found")

print(rec.S_input_to_conventional_col)
print(rec.S_input_to_primitive_col)
```

If you need to check the integer-ness / numerical stability:

```python
print(rec.is_integer_input_to_conventional, rec.max_abs_err_input_to_conventional)
print(rec.is_integer_input_to_primitive, rec.max_abs_err_input_to_primitive)
print(rec.det_input_to_conventional, rec.det_input_to_primitive)
```
