"""Regression tests for current oriented-slab transform provenance.

The current writer stores one JSON-native mapping under
``Atoms.info['calm_oriented_slab_transforms']``. These tests require that
mapping to be serializable and deterministic.
"""

from __future__ import annotations

import json
from typing import Any

from ase.build import bulk as ase_bulk

from calm.bulk.bulk import Bulk
from calm.slab.oriented.transforms import ORIENTED_SLAB_TRANSFORMS_INFO_KEY
from calm.slab.slab import Slab, SlabSpec


def _is_json_native(x: Any) -> bool:
    if x is None:
        return True
    if isinstance(x, (bool, int, float, str)):
        return True
    if isinstance(x, list):
        return all(_is_json_native(v) for v in x)
    if isinstance(x, dict):
        return all(isinstance(k, str) and _is_json_native(v) for k, v in x.items())
    return False


def _slab() -> Slab:
    return Slab(
        Bulk(ase_bulk("Al", a=4.05, cubic=True), label="Al"),
        SlabSpec(
            miller=(1, 1, 1),
            n_layers=3,
            vacuum=8.0,
            pbc=(True, True, True),
            verbose=False,
        ),
    )


def test_oriented_slab_transforms_payload_is_valid_and_native() -> None:
    payload = _slab().atoms.info.get(ORIENTED_SLAB_TRANSFORMS_INFO_KEY)

    assert isinstance(payload, dict) and payload
    assert _is_json_native(payload)
    json.dumps(payload)


def test_oriented_slab_transforms_payload_is_deterministic() -> None:
    payload_1 = _slab().atoms.info.get(ORIENTED_SLAB_TRANSFORMS_INFO_KEY)
    payload_2 = _slab().atoms.info.get(ORIENTED_SLAB_TRANSFORMS_INFO_KEY)

    assert isinstance(payload_1, dict) and isinstance(payload_2, dict)
    assert payload_1 == payload_2
