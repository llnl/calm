# Oriented slab transforms

CALM attaches **oriented-slab transform provenance** to slabs that undergo primitive surface-cell reduction.

The provenance is exposed as a first-class object (`calm.slab.OrientedSlabTransforms`) and can be serialized as a deterministic JSON payload for persistence and interchange.

## Accessing transforms from a Slab

In normal usage, prefer the `calm.slab.Slab` accessors.

```python
from ase.build import bulk as ase_bulk

from calm import Bulk
from calm.slab import Slab, SlabSpec

al = Bulk(ase_bulk("Al", "fcc", a=4.05))

spec = SlabSpec(miller=(1, 1, 1), n_layers=8, vacuum=12.0)
slab = Slab(al, spec)

# First-class object
ts = slab.oriented_slab_transforms

# Canonical JSON representation
js = ts.json

# JSON-native dict payload (safe to mutate; each access returns a fresh dict)
payload = ts.payload
```

Convenience accessors are also available if you only need the serialized forms:

```python
js = slab.oriented_slab_transforms_json
payload = slab.oriented_slab_transforms_payload
```

## Controlling `Atoms.info` stamping

By default, CALM stamps the JSON payload into `slab.atoms.info` under the key:

- `calm_oriented_slab_transforms_json`

This makes provenance available in workflows that only persist or transport the underlying `ase.Atoms`.

If you want to avoid injecting CALM-specific metadata into `Atoms.info`, you can disable stamping at construction time:

```python
from calm.slab import ORIENTED_SLAB_TRANSFORMS_INFO_KEY

spec = SlabSpec(miller=(1, 1, 1), n_layers=8, vacuum=12.0, stamp_transforms_json=False)
slab = Slab(al, spec)

assert ORIENTED_SLAB_TRANSFORMS_INFO_KEY not in slab.atoms.info
assert slab.oriented_slab_transforms_json  # still available on the Slab

# Export an ase.Atoms copy with the payload stamped (does not mutate slab.atoms)
atoms_for_export = slab.to_atoms(stamp_transforms_json=True)
assert ORIENTED_SLAB_TRANSFORMS_INFO_KEY in atoms_for_export.info
```

## Exporting transforms as a sidecar JSON file

When `stamp_transforms_json=False`, you can still persist the same provenance payload separately (e.g. alongside a structure file) without modifying `Atoms.info`:

```python
from pathlib import Path

spec = SlabSpec(miller=(1, 1, 1), n_layers=8, vacuum=12.0, stamp_transforms_json=False)
slab = Slab(al, spec)

out = Path("al_111_oriented_slab_transforms.json")
slab.oriented_slab_transforms.write_json(out, overwrite=True)
```

## Accessing transforms from `ase.Atoms`

If you only have an `ase.Atoms` instance, you can retrieve the JSON/payload via helpers **if** the slab was stamped (or if the `Atoms.info` key is already present, e.g. from a persisted record):

```python
from calm.slab import (
    ORIENTED_SLAB_TRANSFORMS_INFO_KEY,
    get_oriented_slab_transforms,
    get_oriented_slab_transforms_json,
    get_oriented_slab_transforms_payload,
)

js = get_oriented_slab_transforms_json(slab.atoms)
payload = get_oriented_slab_transforms_payload(slab.atoms)

ts = get_oriented_slab_transforms(slab.atoms)
```

If stamping is disabled, these `Atoms`-based helpers will return `None` (or raise if called with `strict=True`). In that case, prefer the `Slab` accessors, or export a stamped `ase.Atoms` copy via `slab.to_atoms(stamp_transforms_json=True)`.

## Payload schema

The payload is a JSON object with the following top-level keys:

- `schema_version` (int): schema version for forwards/backwards compatibility
- `backend` (str): producer backend name (currently `primitive_slab`)
- `transforms` (object | null): backend-specific transform/diagnostic data

The `transforms` subtree is JSON-native (lists, dicts, numbers, booleans, null) and is suitable for storage in text or document formats.

In the current implementation, `transforms` always includes `U` and `hkl` and may include additional keys that capture surface-primitive reduction diagnostics (for example: `fallback`, `error`, and intermediate matrix quantities). CALM treats unknown keys as opaque and preserves them when re-serializing.
