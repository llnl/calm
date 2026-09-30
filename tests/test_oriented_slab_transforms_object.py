from __future__ import annotations

from ase.build import bulk as ase_bulk

from calm.bulk.bulk import Bulk
from calm.slab.oriented.transforms import (
    ORIENTED_SLAB_TRANSFORMS_INFO_KEY,
    ORIENTED_SLAB_TRANSFORMS_VERSION,
)
from calm.slab.slab import Slab, SlabSpec, get_oriented_slab_transforms


def _make_al_slab(*, stamp: bool) -> Slab:
    bulk = Bulk(ase_bulk("Al", "fcc", a=4.05))
    spec = SlabSpec(miller=(1, 1, 1), n_layers=8, vacuum=12.0, stamp_transforms=stamp)
    return Slab(bulk, spec)


def test_oriented_slab_transforms_object_matches_json_and_payload_accessors() -> None:
    slab = _make_al_slab(stamp=True)

    ts = slab.oriented_slab_transforms
    assert ts is not None

    assert isinstance(ts.json, str)
    assert ts.json
    assert ts.json == slab.oriented_slab_transforms_json

    payload1 = ts.payload
    payload2 = slab.oriented_slab_transforms_payload
    assert payload1 == payload2
    assert payload1["version"] == ORIENTED_SLAB_TRANSFORMS_VERSION

    # The payload returned from the object should be safe to mutate without
    # affecting subsequent calls.
    payload1["version"] = 999
    payload3 = ts.payload
    assert payload3["version"] == ORIENTED_SLAB_TRANSFORMS_VERSION

    # Atoms-level access should work when stamping is enabled.
    ts_from_atoms = get_oriented_slab_transforms(slab.atoms)
    assert ts_from_atoms is not None
    assert ts_from_atoms.json == ts.json


def test_oriented_slab_transforms_can_be_detached_from_atoms_info() -> None:
    slab = _make_al_slab(stamp=False)

    # No CALM-specific stamping in Atoms.info...
    assert ORIENTED_SLAB_TRANSFORMS_INFO_KEY not in slab.atoms.info

    # ...but the Slab still exposes the transforms.
    assert slab.oriented_slab_transforms is not None
    assert slab.oriented_slab_transforms_json
    assert slab.oriented_slab_transforms_payload

    # Atoms-only retrieval should return None when not stamped.
    assert get_oriented_slab_transforms(slab.atoms) is None


def test_slab_to_atoms_can_stamp_transforms_without_mutating_original() -> None:
    slab = _make_al_slab(stamp=False)
    assert ORIENTED_SLAB_TRANSFORMS_INFO_KEY not in slab.atoms.info

    atoms_stamped = slab.to_atoms(stamp_transforms=True)

    assert ORIENTED_SLAB_TRANSFORMS_INFO_KEY in atoms_stamped.info
    assert atoms_stamped.info[ORIENTED_SLAB_TRANSFORMS_INFO_KEY] == slab.oriented_slab_transforms_payload

    # Crucially: exporting must not mutate the slab's internal atoms.
    assert ORIENTED_SLAB_TRANSFORMS_INFO_KEY not in slab.atoms.info


def test_slab_to_atoms_can_strip_transforms_without_mutating_original() -> None:
    slab = _make_al_slab(stamp=True)
    assert ORIENTED_SLAB_TRANSFORMS_INFO_KEY in slab.atoms.info

    atoms_clean = slab.to_atoms(stamp_transforms=False)

    assert ORIENTED_SLAB_TRANSFORMS_INFO_KEY not in atoms_clean.info

    # And the original slab still carries the stamp (build-time default).
    assert ORIENTED_SLAB_TRANSFORMS_INFO_KEY in slab.atoms.info
