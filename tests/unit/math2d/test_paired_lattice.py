"""Production tests for exact coupled-pair lattice arithmetic."""

from __future__ import annotations

from math import gcd

import numpy as np
import pytest

from calm.math2d._core import det2
from calm.math2d.normal_forms import hnf2_col_with_transform
from calm.math2d.paired_lattice import (
    canonicalize_common_right_rank2,
    determinantal_divisor_rank2,
    enumerate_row_hnf_2d_by_index,
    exact_right_divide_rank2,
    maximal_minors_rank2,
    primitiveize_pair_matrix_2d,
)

IDENTITY_2D = np.eye(2, dtype=int)
SIGMA5_CELL_C4 = np.array([[2, -1], [1, 2]], dtype=int)
SIGMA5_CELL_C5 = np.array([[2, 1], [-1, 2]], dtype=int)


def _stack(block_a: np.ndarray, block_b: np.ndarray) -> np.ndarray:
    return np.vstack([block_a, block_b])


def _right_multiply_exact(matrix: np.ndarray, right: np.ndarray) -> np.ndarray:
    return np.asarray(matrix, dtype=object) @ np.asarray(right, dtype=object)


def _random_primitive_pair(rng: np.random.Generator) -> np.ndarray:
    while True:
        candidate = rng.integers(-5, 6, size=(4, 2), dtype=np.int64)
        try:
            if determinantal_divisor_rank2(candidate) == 1:
                return candidate
        except ValueError:
            continue


def _random_full_rank_factor(rng: np.random.Generator) -> np.ndarray:
    while True:
        candidate = rng.integers(-4, 5, size=(2, 2), dtype=np.int64)
        if det2(candidate, mode="exact") != 0:
            return candidate


@pytest.mark.parametrize(
    "matrix",
    [
        np.array([[2, 3], [5, 7]], dtype=int),
        np.array([[-3, 2], [5, 1]], dtype=int),
        np.array([[1, -7], [0, -3]], dtype=int),
        np.array([[0, 5], [-2, 3]], dtype=int),
    ],
)
def test_column_hnf_returns_exact_unimodular_witness(matrix: np.ndarray) -> None:
    hnf, transform = hnf2_col_with_transform(matrix)

    np.testing.assert_array_equal(_right_multiply_exact(matrix, transform), hnf)
    assert det2(transform, mode="exact") in (-1, 1)
    assert hnf[1, 0] == 0
    assert hnf[0, 0] > 0
    assert hnf[1, 1] > 0
    assert 0 <= hnf[0, 1] < hnf[0, 0]
    assert det2(hnf, mode="exact") == abs(det2(matrix, mode="exact"))


def test_row_hnf_enumeration_is_complete_and_deterministic() -> None:
    representatives = list(enumerate_row_hnf_2d_by_index(6))
    keys = [tuple(int(value) for value in matrix.ravel()) for matrix in representatives]

    assert len(representatives) == 12
    assert keys == sorted(keys, key=lambda key: (key[0], key[2]))
    assert len(set(keys)) == len(keys)
    for matrix in representatives:
        assert det2(matrix, mode="exact") == 6
        assert matrix[0, 1] == 0
        assert matrix[0, 0] > 0
        assert matrix[1, 1] > 0
        assert 0 <= matrix[1, 0] < matrix[0, 0]


def test_sigma5_maximal_minors_and_determinantal_divisor_are_exact() -> None:
    source = _stack(SIGMA5_CELL_C4, SIGMA5_CELL_C5)

    assert maximal_minors_rank2(source) == (5, 4, 3, -3, 4, 5)
    assert determinantal_divisor_rank2(source) == 1


def test_exact_right_division_distinguishes_integral_quotients() -> None:
    primitive = _stack(SIGMA5_CELL_C4, SIGMA5_CELL_C5)
    factor = np.array([[1, 0], [0, 5]], dtype=int)
    source = _right_multiply_exact(primitive, factor)

    quotient = exact_right_divide_rank2(source, factor)

    assert quotient is not None
    np.testing.assert_array_equal(quotient, primitive)
    assert exact_right_divide_rank2(source + np.array([[0, 1]] * 4), factor) is None


def test_equal_sigma5_cell_repetition_primitiveizes_to_identity_pair() -> None:
    source = _stack(SIGMA5_CELL_C4, SIGMA5_CELL_C4)
    result = primitiveize_pair_matrix_2d(source)

    assert result.repeat_index == 5
    assert abs(det2(result.source_right_factor, mode="exact")) == 5
    np.testing.assert_array_equal(
        _right_multiply_exact(result.primitive_matrix, result.source_right_factor),
        source,
    )
    assert determinantal_divisor_rank2(result.primitive_matrix) == 1
    assert canonicalize_common_right_rank2(result.primitive_matrix).key == (
        0,
        1,
        1,
        0,
        0,
        1,
        1,
        0,
    )


def test_cross_sigma5_pair_is_already_primitive() -> None:
    source = _stack(SIGMA5_CELL_C4, SIGMA5_CELL_C5)
    result = primitiveize_pair_matrix_2d(source)

    assert result.repeat_index == 1
    np.testing.assert_array_equal(result.source_right_factor, IDENTITY_2D)
    np.testing.assert_array_equal(result.primitive_matrix, source)
    assert result.maximal_minors == (5, 4, 3, -3, 4, 5)


@pytest.mark.parametrize(
    ("factor", "repeat_index"),
    [
        (np.array([[1, 0], [0, 5]], dtype=int), 5),
        (np.array([[2, 0], [0, 3]], dtype=int), 6),
        (np.array([[-1, 2], [0, 7]], dtype=int), 7),
    ],
)
def test_sigma5_repetitions_recover_one_primitive_common_right_class(
    factor: np.ndarray,
    repeat_index: int,
) -> None:
    primitive = _stack(SIGMA5_CELL_C4, SIGMA5_CELL_C5)
    source = _right_multiply_exact(primitive, factor)
    result = primitiveize_pair_matrix_2d(source)

    assert result.repeat_index == repeat_index
    assert determinantal_divisor_rank2(result.primitive_matrix) == 1
    np.testing.assert_array_equal(
        _right_multiply_exact(result.primitive_matrix, result.source_right_factor),
        source,
    )
    assert canonicalize_common_right_rank2(
        result.primitive_matrix
    ).key == canonicalize_common_right_rank2(primitive).key


def test_primitiveization_is_idempotent() -> None:
    primitive = _stack(SIGMA5_CELL_C4, SIGMA5_CELL_C5)
    first = primitiveize_pair_matrix_2d(primitive)
    second = primitiveize_pair_matrix_2d(first.primitive_matrix)

    assert first.repeat_index == second.repeat_index == 1
    np.testing.assert_array_equal(second.primitive_matrix, first.primitive_matrix)
    np.testing.assert_array_equal(second.source_right_factor, IDENTITY_2D)


def test_common_right_canonicalization_is_invariant_and_exact() -> None:
    matrix = _stack(SIGMA5_CELL_C4, SIGMA5_CELL_C5)
    transforms = (
        np.array([[1, 3], [0, 1]], dtype=int),
        np.array([[0, 1], [1, 0]], dtype=int),
        np.array([[-1, 2], [0, 1]], dtype=int),
    )
    reference = canonicalize_common_right_rank2(matrix)

    np.testing.assert_array_equal(
        _right_multiply_exact(matrix, reference.right_transform),
        reference.canonical_matrix,
    )
    assert det2(reference.right_transform, mode="exact") in (-1, 1)
    assert reference.key == tuple(int(value) for value in reference.canonical_matrix.ravel())

    for transform in transforms:
        assert abs(det2(transform, mode="exact")) == 1
        changed = _right_multiply_exact(matrix, transform)
        result = canonicalize_common_right_rank2(changed)
        assert result.key == reference.key
        np.testing.assert_array_equal(result.canonical_matrix, reference.canonical_matrix)

    repeated = canonicalize_common_right_rank2(reference.canonical_matrix)
    assert repeated.key == reference.key
    np.testing.assert_array_equal(repeated.canonical_matrix, reference.canonical_matrix)


def test_random_factorizations_are_exact_and_common_right_invariant() -> None:
    rng = np.random.default_rng(20260724)
    gauges = (
        np.array([[1, 2], [0, 1]], dtype=int),
        np.array([[0, 1], [1, 0]], dtype=int),
    )

    for _ in range(60):
        primitive = _random_primitive_pair(rng)
        factor = _random_full_rank_factor(rng)
        source = _right_multiply_exact(primitive, factor)
        expected_repeat = abs(det2(factor, mode="exact"))
        result = primitiveize_pair_matrix_2d(source)

        assert result.repeat_index == expected_repeat
        assert gcd(*[abs(value) for value in result.maximal_minors]) == expected_repeat
        assert determinantal_divisor_rank2(result.primitive_matrix) == 1
        np.testing.assert_array_equal(
            _right_multiply_exact(result.primitive_matrix, result.source_right_factor),
            source,
        )
        expected_key = canonicalize_common_right_rank2(primitive).key
        assert canonicalize_common_right_rank2(result.primitive_matrix).key == expected_key

        for gauge in gauges:
            gauged_source = _right_multiply_exact(source, gauge)
            gauged = primitiveize_pair_matrix_2d(gauged_source)
            assert gauged.repeat_index == expected_repeat
            assert canonicalize_common_right_rank2(gauged.primitive_matrix).key == expected_key


def test_primitiveization_is_covariant_under_unimodular_row_operations() -> None:
    primitive = _stack(SIGMA5_CELL_C4, SIGMA5_CELL_C5)
    source = _right_multiply_exact(
        primitive,
        np.array([[2, 1], [0, 3]], dtype=int),
    )
    left = np.eye(4, dtype=object)
    left[[0, 2]] = left[[2, 0]]
    left[3] += 4 * left[1]

    reference = primitiveize_pair_matrix_2d(source)
    transformed = primitiveize_pair_matrix_2d(left @ source)

    assert transformed.repeat_index == reference.repeat_index
    np.testing.assert_array_equal(
        transformed.source_right_factor,
        reference.source_right_factor,
    )
    np.testing.assert_array_equal(
        transformed.primitive_matrix,
        left @ reference.primitive_matrix,
    )


@pytest.mark.parametrize(
    "function,args",
    [
        (maximal_minors_rank2, (np.ones((4, 2), dtype=float),)),
        (maximal_minors_rank2, (np.ones((4, 2), dtype=bool),)),
        (primitiveize_pair_matrix_2d, (np.ones((3, 2), dtype=int),)),
        (canonicalize_common_right_rank2, (np.ones((4, 3), dtype=int),)),
        (hnf2_col_with_transform, (np.eye(2, dtype=float),)),
        (hnf2_col_with_transform, (np.eye(2, dtype=bool),)),
    ],
)
def test_exact_apis_reject_invalid_shapes_and_noninteger_inputs(
    function: object,
    args: tuple[np.ndarray, ...],
) -> None:
    with pytest.raises((TypeError, ValueError)):
        function(*args)  # type: ignore[operator]


def test_rank_deficient_inputs_are_rejected() -> None:
    rank_one = np.array([[1, 2], [2, 4], [3, 6], [4, 8]], dtype=int)

    assert maximal_minors_rank2(rank_one) == (0, 0, 0, 0, 0, 0)
    with pytest.raises(ValueError, match="rank two"):
        determinantal_divisor_rank2(rank_one)
    with pytest.raises(ValueError, match="rank two"):
        primitiveize_pair_matrix_2d(rank_one)
    with pytest.raises(ValueError, match="rank two"):
        canonicalize_common_right_rank2(rank_one)
    with pytest.raises(ValueError, match="full rank"):
        exact_right_divide_rank2(np.ones((4, 2), dtype=int), np.ones((2, 2), dtype=int))


def test_index_validation_and_integer_overflow_fail_explicitly() -> None:
    with pytest.raises(TypeError):
        list(enumerate_row_hnf_2d_by_index(True))
    with pytest.raises(TypeError):
        list(enumerate_row_hnf_2d_by_index(2.0))
    with pytest.raises(ValueError):
        list(enumerate_row_hnf_2d_by_index(0))
    with pytest.raises(OverflowError):
        list(enumerate_row_hnf_2d_by_index(np.iinfo(np.int_).max + 1))

    too_large = np.zeros((4, 2), dtype=object)
    too_large[0, 0] = np.iinfo(np.int_).max + 1
    with pytest.raises(OverflowError):
        maximal_minors_rank2(too_large)


def test_exact_right_division_rejects_unrepresentable_integer_result() -> None:
    maximum = int(np.iinfo(np.int_).max)
    source = np.array([[maximum, maximum], [0, 0], [0, 0], [0, 0]], dtype=object)
    factor = np.array([[maximum, 1], [maximum - 1, 1]], dtype=object)

    with pytest.raises(OverflowError):
        exact_right_divide_rank2(source, factor)
