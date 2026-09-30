from __future__ import annotations

from types import SimpleNamespace

import pytest

from calm.public.records.interfaces import InterfaceSearchResult


PAIR_A = {
    "key_version": 1,
    "primitive_pair_key": [1, 0, 0, 1, 1, 0, 0, 1],
    "pair_symmetry_policy": "full",
    "correspondence_orientation": "proper",
    "material_exchange_identified": False,
}
PAIR_B = {
    **PAIR_A,
    "primitive_pair_key": [1, 0, 0, 1, 1, 1, 0, 1],
}


def _prototype(uid: str, pair_identity=PAIR_A) -> dict[str, object]:
    return {
        "prototype_uid": uid,
        "pair_identity": pair_identity,
        "d_cell": 0.01,
        "d_area": 0.02,
        "d_shape": 0.03,
        "d_size": 0.04,
        "n_atoms_estimate": 20,
        "k_a": 5,
        "k_b": 5,
    }


def _project(*prototypes: dict[str, object]) -> InterfaceSearchResult:
    return InterfaceSearchResult.from_internal(
        SimpleNamespace(prototypes=list(prototypes))
    )


def test_distinct_exact_pair_keys_survive_equal_display_metrics() -> None:
    result = _project(
        _prototype("proto:a", PAIR_A),
        _prototype("proto:b", PAIR_B),
    )

    assert [item.candidate_uid for item in result] == ["proto:a", "proto:b"]
    assert [item.candidate_id for item in result] == ["C0000", "C0001"]


def test_duplicate_exact_pair_keys_fail_closed() -> None:
    with pytest.raises(ValueError, match="duplicate exact primitive pair"):
        _project(
            _prototype("proto:first", PAIR_A),
            _prototype("proto:repeat", PAIR_A),
        )


def test_missing_exact_pair_identity_fails_closed() -> None:
    with pytest.raises(ValueError, match="complete exact pair_identity"):
        _project(_prototype("proto:missing", None))


def test_malformed_exact_pair_identity_fails_closed() -> None:
    malformed = {**PAIR_A, "key_version": 0}

    with pytest.raises(ValueError, match="complete exact pair_identity"):
        _project(_prototype("proto:malformed", malformed))


def test_empty_authoritative_projection_remains_valid() -> None:
    result = _project()

    assert len(result) == 0
