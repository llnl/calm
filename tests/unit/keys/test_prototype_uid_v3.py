from __future__ import annotations

import pytest

from calm.keys.uid import prototype_uid_v3


PAIR_KEY = (1, 0, 0, 1, 1, 0, 0, 1)
OTHER_KEY = (1, 0, 0, 1, 1, 1, 0, 1)


def _uid(**overrides) -> str:
    kwargs = {
        "slab_uid_a": "slab:a",
        "slab_uid_b": "slab:b",
        "primitive_pair_key": PAIR_KEY,
        "pair_key_version": 1,
        "pair_symmetry_policy": "full",
        "correspondence_orientation": "proper",
        "material_exchange_identified": False,
    }
    kwargs.update(overrides)
    return prototype_uid_v3(**kwargs)


def test_prototype_uid_v3_is_exact_and_policy_sensitive() -> None:
    uid = _uid()

    assert uid.startswith("proto:v3:")
    assert uid == _uid()
    assert uid != _uid(primitive_pair_key=OTHER_KEY)
    assert uid != _uid(pair_symmetry_policy="proper")
    assert uid != _uid(correspondence_orientation="all")


def test_material_exchange_controls_slab_order_equivalence() -> None:
    ordered = _uid()
    ordered_swapped = _uid(slab_uid_a="slab:b", slab_uid_b="slab:a")
    exchange = _uid(material_exchange_identified=True)
    exchange_swapped = _uid(
        slab_uid_a="slab:b",
        slab_uid_b="slab:a",
        material_exchange_identified=True,
    )

    assert ordered != ordered_swapped
    assert exchange == exchange_swapped


@pytest.mark.parametrize(
    ("overrides", "error"),
    [
        ({"primitive_pair_key": PAIR_KEY[:-1]}, ValueError),
        ({"primitive_pair_key": (*PAIR_KEY[:-1], 1.0)}, TypeError),
        ({"pair_key_version": True}, TypeError),
        ({"pair_symmetry_policy": "invalid"}, ValueError),
        ({"correspondence_orientation": "invalid"}, ValueError),
        ({"material_exchange_identified": 1}, TypeError),
    ],
)
def test_prototype_uid_v3_rejects_ambiguous_identity(overrides, error) -> None:
    with pytest.raises(error):
        _uid(**overrides)
