"""Equivalence guards for the scalar exact-rank-two acceleration kernels."""

from __future__ import annotations

import numpy as np

from calm.math2d._exact_rank2 import (
    clear_exact_rank2_caches,
    exact_matrix2_tuple,
    exact_matrix4x2_tuple,
    hnf2_col_with_transform_tuple,
)
from calm.math2d.normal_forms import hnf2_col_with_transform
from calm.math2d.paired_lattice import (
    _canonicalize_common_right_rank2_tuple,
    _clear_paired_lattice_caches,
    canonicalize_common_right_rank2,
)
from reference.coupled_match_reference import (
    canonicalize_common_right_rank2 as reference_common_right,
)
from reference.coupled_match_reference import (
    hnf2_col_with_transform as reference_hnf,
)


def _determinant(matrix: tuple[int, int, int, int]) -> int:
    a, b, c, d = matrix
    return a * d - b * c


def test_scalar_hnf_matches_reference_for_random_full_rank_matrices() -> None:
    rng = np.random.default_rng(20260729)

    checked = 0
    while checked < 500:
        values = tuple(int(value) for value in rng.integers(-50, 51, size=4))
        if _determinant(values) == 0:
            continue
        production = hnf2_col_with_transform_tuple(values)
        reference = reference_hnf(values)
        assert production == (reference.hnf, reference.right_transform)
        checked += 1


def test_scalar_common_right_matches_reference_for_random_rank_two_pairs() -> None:
    rng = np.random.default_rng(20260730)

    checked = 0
    while checked < 200:
        values = tuple(int(value) for value in rng.integers(-12, 13, size=8))
        rows = tuple((values[offset], values[offset + 1]) for offset in range(0, 8, 2))
        if not any(
            first[0] * second[1] - first[1] * second[0]
            for index, first in enumerate(rows)
            for second in rows[index + 1 :]
        ):
            continue
        production = _canonicalize_common_right_rank2_tuple(values)
        reference = reference_common_right(values)
        assert production.canonical_matrix == reference.canonical_matrix
        assert production.right_transform == reference.right_transform
        assert production.pivot_rows == reference.pivot_rows
        assert production.key == reference.key
        checked += 1


def test_public_array_results_are_fresh_when_scalar_results_are_cached() -> None:
    matrix_2d = np.array([[2, 3], [5, 7]], dtype=int)
    expected_hnf, expected_transform = hnf2_col_with_transform(matrix_2d)
    first_hnf, first_transform = hnf2_col_with_transform(matrix_2d)
    first_hnf[0, 0] = 999
    first_transform[0, 0] = 999
    second_hnf, second_transform = hnf2_col_with_transform(matrix_2d)
    np.testing.assert_array_equal(second_hnf, expected_hnf)
    np.testing.assert_array_equal(second_transform, expected_transform)

    pair = np.array(
        [[2, -1], [1, 2], [2, 1], [-1, 2]],
        dtype=int,
    )
    expected = canonicalize_common_right_rank2(pair)
    first = canonicalize_common_right_rank2(pair)
    first.canonical_matrix[0, 0] = 999
    first.right_transform[0, 0] = 999
    second = canonicalize_common_right_rank2(pair)
    np.testing.assert_array_equal(second.canonical_matrix, expected.canonical_matrix)
    np.testing.assert_array_equal(second.right_transform, expected.right_transform)
    assert second.key == expected.key
    assert second.pivot_rows == expected.pivot_rows


def test_scalar_caches_are_bounded_and_record_exact_reuse() -> None:
    clear_exact_rank2_caches()
    _clear_paired_lattice_caches()

    matrix_2d = exact_matrix2_tuple(
        np.array([[2, 3], [5, 7]], dtype=int),
        name="matrix_2d",
    )
    hnf2_col_with_transform_tuple(matrix_2d)
    hnf2_col_with_transform_tuple(matrix_2d)
    hnf_info = hnf2_col_with_transform_tuple.cache_info()
    assert hnf_info.maxsize == 512
    assert hnf_info.currsize == 1
    assert hnf_info.misses == 1
    assert hnf_info.hits == 1

    pair = exact_matrix4x2_tuple(
        np.array([[2, -1], [1, 2], [2, 1], [-1, 2]], dtype=int),
        name="pair",
    )
    _canonicalize_common_right_rank2_tuple(pair)
    _canonicalize_common_right_rank2_tuple(pair)
    common_info = _canonicalize_common_right_rank2_tuple.cache_info()
    assert common_info.maxsize == 512
    assert common_info.currsize == 1
    assert common_info.misses == 1
    assert common_info.hits == 1
