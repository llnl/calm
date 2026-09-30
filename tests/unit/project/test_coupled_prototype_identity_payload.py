from __future__ import annotations

import pytest

from calm.project.domain.identity_v2 import (
    persisted_entity_uid_v2,
    prototype_identity_payload,
)


PAIR_IDENTITY = {
    "key_version": 1,
    "primitive_pair_key": [1, 0, 0, 1, 1, 0, 0, 1],
    "pair_symmetry_policy": "full",
    "correspondence_orientation": "proper",
    "material_exchange_identified": False,
}


def _payload(*, source_count: int = 1) -> dict:
    return {
        "schema": "calm.interface_prototype_build_payload/v2",
        "identity_algorithm": "primitive_coupled_pair_v2",
        "pair_identity": dict(PAIR_IDENTITY),
        "source_provenance": {"source_count": source_count},
        "metrics": {"match_score": float(source_count)},
    }


def test_coupled_persisted_identity_excludes_run_metrics_and_source_repeats() -> None:
    first = prototype_identity_payload(
        run_uid_full="run:first",
        slab_a_uid_full="slab:a",
        slab_b_uid_full="slab:b",
        payload=_payload(source_count=1),
        match_score=0.1,
        hencky_norm=0.01,
        interface_area=5.0,
        n_atoms=10,
    )
    repeated = prototype_identity_payload(
        run_uid_full="run:second",
        slab_a_uid_full="slab:a",
        slab_b_uid_full="slab:b",
        payload=_payload(source_count=20),
        match_score=99.0,
        hencky_norm=8.0,
        interface_area=500.0,
        n_atoms=1000,
    )

    assert first == repeated
    assert first["identity_algorithm"] == "primitive_coupled_pair_v2"
    assert "run_uid_full" not in first
    assert "match_score" not in first


def test_non_coupled_persisted_identity_is_rejected() -> None:
    with pytest.raises(ValueError, match="primitive_coupled_pair_v2"):
        prototype_identity_payload(
            run_uid_full="run:first",
            slab_a_uid_full="slab:a",
            slab_b_uid_full="slab:b",
            payload={"schema": "calm.interface_prototype_build_payload/v1"},
            match_score=0.1,
            hencky_norm=0.01,
            interface_area=5.0,
            n_atoms=10,
        )


def test_coupled_persisted_uid_is_pair_key_sensitive() -> None:
    identity = prototype_identity_payload(
        run_uid_full="run:first",
        slab_a_uid_full="slab:a",
        slab_b_uid_full="slab:b",
        payload=_payload(),
        match_score=0.1,
        hencky_norm=0.01,
        interface_area=5.0,
        n_atoms=10,
    )
    changed = _payload()
    changed["pair_identity"]["primitive_pair_key"] = [
        1, 0, 0, 1, 1, 1, 0, 1
    ]
    changed_identity = prototype_identity_payload(
        run_uid_full="run:first",
        slab_a_uid_full="slab:a",
        slab_b_uid_full="slab:b",
        payload=changed,
        match_score=0.1,
        hencky_norm=0.01,
        interface_area=5.0,
        n_atoms=10,
    )

    first_uid = persisted_entity_uid_v2("prototype", identity)
    changed_uid = persisted_entity_uid_v2("prototype", changed_identity)

    assert first_uid.startswith("proto:v2:")
    assert first_uid != changed_uid
