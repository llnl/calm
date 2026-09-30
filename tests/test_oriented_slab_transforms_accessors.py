import pytest
from ase.build import bulk as ase_bulk

from calm.bulk.bulk import Bulk
from calm.slab.oriented.transforms import ORIENTED_SLAB_TRANSFORMS_INFO_KEY


def test_oriented_slab_transforms_accessors_roundtrip() -> None:
    from calm.slab.slab import (
        Slab,
        SlabSpec,
        get_oriented_slab_transforms_json,
        get_oriented_slab_transforms_payload,
        parse_oriented_slab_transforms_json,
    )

    slab = Slab(
        Bulk(ase_bulk("Al", a=4.05, cubic=True), label="Al"),
        SlabSpec(
            miller=(1, 1, 1),
            n_layers=3,
            vacuum=8.0,
            pbc=(True, True, True),
            verbose=False,
        ),
    )

    js = get_oriented_slab_transforms_json(slab)
    assert isinstance(js, str) and js
    assert js == slab.oriented_slab_transforms_json
    assert get_oriented_slab_transforms_json(slab.atoms) == js

    payload = get_oriented_slab_transforms_payload(slab)
    assert isinstance(payload, dict)
    assert payload == parse_oriented_slab_transforms_json(js)
    assert payload == slab.atoms.info[ORIENTED_SLAB_TRANSFORMS_INFO_KEY]

    atoms = ase_bulk("Al", a=4.05, cubic=True)
    atoms.info.pop(ORIENTED_SLAB_TRANSFORMS_INFO_KEY, None)

    assert get_oriented_slab_transforms_json(atoms) is None
    assert get_oriented_slab_transforms_payload(atoms) is None
    with pytest.raises(KeyError):
        get_oriented_slab_transforms_payload(atoms, strict=True)


def test_atoms_info_reader_rejects_historical_json_string() -> None:
    from calm.slab.slab import get_oriented_slab_transforms_payload

    atoms = ase_bulk("Al", a=4.05, cubic=True)
    atoms.info[ORIENTED_SLAB_TRANSFORMS_INFO_KEY] = '{"version": 1}'

    with pytest.raises(ValueError, match="must be a mapping"):
        get_oriented_slab_transforms_payload(atoms)
