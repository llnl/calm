"""Tests for coupled-v2 surface orbit bundles."""

from __future__ import annotations

import numpy as np
import pytest

import calm.interface.matching._surface_orbits as surface_orbits
from calm.interface.matching.conditioning import scale_normalized_condition_number_2d
from calm.interface.matching._surface_orbits import build_surface_cell_orbit_index
from calm.math2d.normal_forms import enumerate_hnf_2d_by_index
from reference.coupled_match_reference import FULL_SQUARE_GROUP


def _operations() -> list[np.ndarray]:
    return [
        np.asarray(operation, dtype=int).reshape(2, 2)
        for operation in FULL_SQUARE_GROUP
    ]


def _orbit_inventory(orbits: tuple[object, ...]) -> tuple[object, ...]:
    return tuple(
        (
            orbit.key,
            tuple(tuple(int(value) for value in member.H.ravel()) for member in orbit.members),
        )
        for orbit in orbits
    )


def test_square_index_five_retains_all_members_in_three_orbits() -> None:
    stats: dict[str, int] = {}
    orbits = surface_orbits.enumerate_surface_cell_orbits_for_index(
        prim_basis=np.eye(2),
        k=5,
        PG_ops=_operations(),
        cond_max=1e6,
        stats=stats,
    )

    assert len(orbits) == 3
    assert [len(orbit.members) for orbit in orbits] == [2, 2, 2]
    assert sum(len(orbit.members) for orbit in orbits) == 6
    assert stats == {
        "hnf_total": 6,
        "reduction_failed": 0,
        "condition_rejected": 0,
        "generated_members": 6,
        "orbit_count": 3,
        "symmetry_removed_from_comparison": 3,
    }
    for orbit in orbits:
        for member in orbit.members:
            assert round(np.linalg.det(member.oriented_U)) == 1
            assert np.linalg.det(member.oriented_embedding) == pytest.approx(1.0)
            assert np.array_equal(member.oriented_N, member.H @ member.oriented_U)
            assert abs(round(np.linalg.det(member.oriented_N))) == 5
            assert abs(np.linalg.det(member.shape_basis)) == pytest.approx(5.0)
            assert member.shape_gram == pytest.approx(
                orbit.representative.shape_gram,
                abs=1e-10,
            )
            assert member.condition_number == pytest.approx(
                orbit.representative.condition_number
            )


def test_orbit_membership_is_hnf_enumeration_order_independent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = surface_orbits.enumerate_surface_cell_orbits_for_index(
        prim_basis=np.eye(2),
        k=5,
        PG_ops=_operations(),
        cond_max=1e6,
    )
    original = tuple(enumerate_hnf_2d_by_index(5))
    monkeypatch.setattr(
        surface_orbits,
        "enumerate_hnf_2d_by_index",
        lambda _index: iter(reversed(original)),
    )
    reversed_result = surface_orbits.enumerate_surface_cell_orbits_for_index(
        prim_basis=np.eye(2),
        k=5,
        PG_ops=list(reversed(_operations())),
        cond_max=1e6,
    )

    assert _orbit_inventory(reversed_result) == _orbit_inventory(expected)


def test_condition_gate_uses_canonical_shape_not_raw_hnf_basis() -> None:
    orbits = surface_orbits.enumerate_surface_cell_orbits_for_index(
        prim_basis=np.eye(2),
        k=5,
        PG_ops=_operations(),
        cond_max=1.01,
    )

    assert len(orbits) == 1
    assert len(orbits[0].members) == 2
    for member in orbits[0].members:
        assert member.condition_number == pytest.approx(1.0)
        assert scale_normalized_condition_number_2d(member.H) > 5.0


def test_index_builder_returns_surface_orbit_bundles() -> None:
    stats: dict[int, dict[str, int]] = {}
    index = build_surface_cell_orbit_index(
        prim_basis=np.eye(2),
        k_max=5,
        PG_ops=_operations(),
        cond_max=1e6,
        stats=stats,
    )

    assert tuple(index) == (1, 2, 3, 4, 5)
    assert len(index[5]) == 3
    assert stats[5]["generated_members"] == 6
    assert stats[5]["orbit_count"] == 3


@pytest.mark.parametrize(
    ("options", "error_type", "message"),
    [
        ({"tol": 0.0}, ValueError, "surface orbit reduction tol"),
        ({"max_iter": 0}, ValueError, "surface orbit reduction max_iter"),
        (
            {"validate": False},
            TypeError,
            "unsupported surface orbit reduction options",
        ),
    ],
)
def test_surface_orbit_builder_rejects_invalid_reduction_controls(
    options: dict[str, object],
    error_type: type[Exception],
    message: str,
) -> None:
    with pytest.raises(error_type, match=message):
        surface_orbits.enumerate_surface_cell_orbits_for_index(
            prim_basis=np.eye(2),
            k=1,
            PG_ops=[np.eye(2, dtype=int)],
            cond_max=1.0e6,
            reduction_kwargs=options,
        )


def test_prepared_surface_context_normalizes_reuse_key_and_matches_public_builder(
) -> None:
    forward = _operations()
    reordered_with_duplicate = list(reversed(forward)) + [forward[0].copy()]
    context_a = surface_orbits._prepare_surface_orbit_build_context_2d(
        prim_basis=np.eye(2),
        PG_ops=forward,
        cond_max=1.0e6,
        reduction_kwargs={"tol": 1.0e-12, "max_iter": 128},
    )
    context_b = surface_orbits._prepare_surface_orbit_build_context_2d(
        prim_basis=np.eye(2),
        PG_ops=reordered_with_duplicate,
        cond_max=1.0e6,
        reduction_kwargs={"max_iter": 128, "tol": 1.0e-12},
    )

    assert context_a.key == context_b.key

    prepared_stats: dict[int, dict[str, int]] = {}
    prepared = surface_orbits._build_surface_cell_orbit_index_prepared(
        context=context_a,
        k_max=5,
        stats=prepared_stats,
    )
    public_stats: dict[int, dict[str, int]] = {}
    public = build_surface_cell_orbit_index(
        prim_basis=np.eye(2),
        k_max=5,
        PG_ops=forward,
        cond_max=1.0e6,
        reduction_kwargs={"tol": 1.0e-12, "max_iter": 128},
        stats=public_stats,
    )

    assert {
        index: _orbit_inventory(orbits) for index, orbits in prepared.items()
    } == {
        index: _orbit_inventory(orbits) for index, orbits in public.items()
    }
    assert prepared_stats == public_stats


def test_surface_context_reuse_key_includes_geometry_and_reduction_policy() -> None:
    base = surface_orbits._prepare_surface_orbit_build_context_2d(
        prim_basis=np.eye(2),
        PG_ops=_operations(),
        cond_max=1.0e6,
        reduction_kwargs=None,
    )
    changed_basis = surface_orbits._prepare_surface_orbit_build_context_2d(
        prim_basis=np.diag([1.0, 1.1]),
        PG_ops=_operations(),
        cond_max=1.0e6,
        reduction_kwargs=None,
    )
    changed_condition = surface_orbits._prepare_surface_orbit_build_context_2d(
        prim_basis=np.eye(2),
        PG_ops=_operations(),
        cond_max=1.0e5,
        reduction_kwargs=None,
    )
    changed_reduction = surface_orbits._prepare_surface_orbit_build_context_2d(
        prim_basis=np.eye(2),
        PG_ops=_operations(),
        cond_max=1.0e6,
        reduction_kwargs={"tol": 1.0e-10},
    )

    assert base.key != changed_basis.key
    assert base.key != changed_condition.key
    assert base.key != changed_reduction.key
