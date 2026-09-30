"""Exact witness tests for one-sided HNF orbit canonicalization."""

from __future__ import annotations

import numpy as np

from calm.keys.hnf import canonical_hnf_under_pg_with_witness
from calm.math2d.normal_forms import enumerate_hnf_2d_by_index
from reference.coupled_match_reference import FULL_SQUARE_GROUP


def _operations() -> list[np.ndarray]:
    return [
        np.asarray(operation, dtype=int).reshape(2, 2)
        for operation in FULL_SQUARE_GROUP
    ]


def test_hnf_orbit_witness_reconstructs_the_canonical_member() -> None:
    matrix = np.array([[5, 3], [0, 1]], dtype=int)
    result = canonical_hnf_under_pg_with_witness(matrix, _operations())

    assert np.array_equal(
        result.point_operation @ matrix @ result.right_transform,
        result.canonical_hnf,
    )
    assert tuple(int(value) for value in result.canonical_hnf.ravel()) == result.key
    assert abs(round(np.linalg.det(result.point_operation))) == 1
    assert abs(round(np.linalg.det(result.right_transform))) == 1


def test_hnf_orbit_witness_is_operation_order_independent() -> None:
    matrix = np.array([[5, 2], [0, 1]], dtype=int)
    operations = _operations()
    forward = canonical_hnf_under_pg_with_witness(matrix, operations)
    reverse = canonical_hnf_under_pg_with_witness(matrix, list(reversed(operations)))

    assert forward.key == reverse.key
    assert np.array_equal(forward.canonical_hnf, reverse.canonical_hnf)
    assert np.array_equal(forward.point_operation, reverse.point_operation)
    assert np.array_equal(forward.right_transform, reverse.right_transform)


def test_hnf_orbit_witness_reconstructs_small_hnf_domain() -> None:
    operations = _operations()
    for index in range(1, 13):
        for matrix in enumerate_hnf_2d_by_index(index):
            result = canonical_hnf_under_pg_with_witness(matrix, operations)
            assert result.key == tuple(
                int(value) for value in result.canonical_hnf.ravel()
            )
            assert np.array_equal(
                result.point_operation @ matrix @ result.right_transform,
                result.canonical_hnf,
            )
