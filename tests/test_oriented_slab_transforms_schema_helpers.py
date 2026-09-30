import json

import numpy as np
import pytest
from ase.build import bulk as ase_bulk

from calm.bulk.bulk import Bulk
from calm.slab.oriented.transforms import (
    ORIENTED_SLAB_TRANSFORMS_INFO_KEY,
    ORIENTED_SLAB_TRANSFORMS_VERSION,
)
from calm.slab.slab import (
    Slab,
    SlabSpec,
    parse_oriented_slab_transforms_json,
)


def _mk_al_slab():
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


def test_oriented_slab_transforms_payload_has_current_schema() -> None:
    payload = _mk_al_slab().atoms.info.get(ORIENTED_SLAB_TRANSFORMS_INFO_KEY)

    assert isinstance(payload, dict)
    assert payload["version"] == ORIENTED_SLAB_TRANSFORMS_VERSION
    assert payload["hkl"] == [1, 1, 1]
    assert np.asarray(payload["U"]).shape == (3, 3)
    assert "M_conv_to_slab_cart" in payload
    assert "M_slab_to_conv_cart" in payload
    assert payload["construction_controls"]["policy"] == (
        "bounded_surface_gauges"
    )
    assert payload["construction_controls"]["policy_version"] == 1


def test_slab_oriented_transforms_accessors_match_atoms_info() -> None:
    slab = _mk_al_slab()
    payload = slab.atoms.info[ORIENTED_SLAB_TRANSFORMS_INFO_KEY]

    assert slab.oriented_slab_transforms_payload == payload
    assert parse_oriented_slab_transforms_json(
        slab.oriented_slab_transforms_json
    ) == payload


def test_parser_rejects_historical_wrapper_payload() -> None:
    historical = {
        "schema_version": 1,
        "backend": "primitive_slab",
        "transforms": {"U": np.eye(3).tolist()},
    }

    with pytest.raises(ValueError, match="Historical oriented-slab transform keys"):
        parse_oriented_slab_transforms_json(json.dumps(historical))
