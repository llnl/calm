"""Exact arithmetic for coupled two-dimensional lattice pairs.

A coupled lattice pair is represented by a rank-two ``4 x 2`` integer matrix
whose upper and lower ``2 x 2`` blocks use the same abstract interface-cell
coordinates. This module provides the exact arithmetic needed to saturate that
paired column lattice and to canonicalize it under one common right
``GL(2, Z)`` basis change.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from functools import lru_cache
from itertools import combinations
from math import gcd, isqrt

import numpy as np

from ._exact_rank2 import (
    Matrix2Tuple,
    Matrix4x2Tuple,
    det2_tuple,
    ensure_np_int_tuple,
    exact_matrix2_tuple,
    exact_matrix4x2_tuple,
    hnf2_col_with_transform_tuple,
    right_multiply_rows_tuple,
    tuple_to_int_array,
)
from .normal_forms import hnf2_col_with_transform

_IDENTITY_2D = np.eye(2, dtype=np.int_)
# Small bounded working set: common-right candidates have strong local reuse.
_COMMON_RIGHT_CACHE_SIZE = 512


@dataclass(frozen=True)
class PrimitivePairFactorization2D:
    """Exact source-to-primitive factorization of a coupled lattice pair."""

    primitive_matrix: np.ndarray
    source_right_factor: np.ndarray
    repeat_index: int
    maximal_minors: tuple[int, ...]


@dataclass(frozen=True)
class CommonRightCanonicalization2D:
    """Canonical representative under one common right unimodular action."""

    canonical_matrix: np.ndarray
    right_transform: np.ndarray
    pivot_rows: tuple[int, int]
    key: tuple[int, ...]


@dataclass(frozen=True)
class _CommonRightCanonicalizationTuple:
    """Immutable scalar result retained by the bounded internal cache."""

    canonical_matrix: Matrix4x2Tuple
    right_transform: Matrix2Tuple
    pivot_rows: tuple[int, int]
    key: Matrix4x2Tuple


def _maximal_minors_tuple(matrix: Matrix4x2Tuple) -> tuple[int, ...]:
    minors: list[int] = []
    for first, second in combinations(range(4), 2):
        first_offset = 2 * first
        second_offset = 2 * second
        minor = (
            matrix[first_offset] * matrix[second_offset + 1]
            - matrix[first_offset + 1] * matrix[second_offset]
        )
        minors.append(minor)
    return tuple(minors)


def _determinantal_divisor_tuple(matrix: Matrix4x2Tuple) -> int:
    divisor = 0
    for minor in _maximal_minors_tuple(matrix):
        divisor = gcd(divisor, abs(minor))
    if divisor == 0:
        raise ValueError("matrix must have rank two")
    return divisor


def _exact_right_divide_tuple(
    matrix: Matrix4x2Tuple,
    right_factor: Matrix2Tuple,
) -> Matrix4x2Tuple | None:
    determinant = det2_tuple(right_factor)
    if determinant == 0:
        raise ValueError("right_factor must have full rank")

    a, b, c, d = right_factor
    adjugate: Matrix2Tuple = (d, -b, -c, a)
    numerators = right_multiply_rows_tuple(matrix, adjugate)
    if any(value % determinant != 0 for value in numerators):
        return None

    quotient = tuple(value // determinant for value in numerators)
    ensure_np_int_tuple(quotient, name="exact_right_divide_rank2(result)")
    if right_multiply_rows_tuple(quotient, right_factor) != matrix:
        raise RuntimeError("exact_right_divide_rank2: reconstruction failed")
    return quotient  # type: ignore[return-value]


@lru_cache(maxsize=_COMMON_RIGHT_CACHE_SIZE)
def _canonicalize_common_right_rank2_tuple(
    source: Matrix4x2Tuple,
) -> _CommonRightCanonicalizationTuple:
    ensure_np_int_tuple(
        source,
        name="canonicalize_common_right_rank2(matrix)",
    )
    best_key: Matrix4x2Tuple | None = None
    best_transform: Matrix2Tuple | None = None
    best_pivot: tuple[int, int] | None = None

    for first, second in combinations(range(4), 2):
        first_offset = 2 * first
        second_offset = 2 * second
        pivot: Matrix2Tuple = (
            source[first_offset],
            source[first_offset + 1],
            source[second_offset],
            source[second_offset + 1],
        )
        if det2_tuple(pivot) == 0:
            continue
        _pivot_hnf, right_transform = hnf2_col_with_transform_tuple(pivot)
        transformed = right_multiply_rows_tuple(source, right_transform)
        if best_key is None or transformed < best_key:
            best_key = transformed
            best_transform = right_transform
            best_pivot = (first, second)

    if best_key is None or best_transform is None or best_pivot is None:
        raise ValueError("matrix must have rank two")

    if det2_tuple(best_transform) not in (-1, 1):
        raise RuntimeError("common-right witness is not unimodular")
    if right_multiply_rows_tuple(source, best_transform) != best_key:
        raise RuntimeError("common-right witness reconstruction failed")
    ensure_np_int_tuple(
        best_key,
        name="canonicalize_common_right_rank2(canonical_matrix)",
    )
    ensure_np_int_tuple(
        best_transform,
        name="canonicalize_common_right_rank2(right_transform)",
    )

    return _CommonRightCanonicalizationTuple(
        canonical_matrix=best_key,
        right_transform=best_transform,
        pivot_rows=best_pivot,
        key=best_key,
    )


def enumerate_row_hnf_2d_by_index(index: int) -> Iterator[np.ndarray]:
    """Enumerate canonical row-HNF matrices of one positive determinant."""
    if isinstance(index, (bool, np.bool_)) or not isinstance(index, (int, np.integer)):
        raise TypeError("index must be a positive integer")
    index_int = int(index)
    if index_int <= 0:
        raise ValueError("index must be a positive integer")
    if index_int > np.iinfo(np.int_).max:
        raise OverflowError("index is outside the supported np.int_ range")

    divisors: list[int] = []
    for divisor in range(1, isqrt(index_int) + 1):
        if index_int % divisor != 0:
            continue
        divisors.append(divisor)
        paired = index_int // divisor
        if paired != divisor:
            divisors.append(paired)

    for h11 in sorted(divisors):
        h22 = index_int // h11
        for h21 in range(h11):
            yield np.array([[h11, 0], [h21, h22]], dtype=np.int_)


def maximal_minors_rank2(matrix: np.ndarray) -> tuple[int, ...]:
    """Return the six exact ``2 x 2`` row minors of a ``4 x 2`` matrix."""
    source = exact_matrix4x2_tuple(matrix, name="maximal_minors_rank2(matrix)")
    return _maximal_minors_tuple(source)


def determinantal_divisor_rank2(matrix: np.ndarray) -> int:
    """Return the second determinantal divisor of a rank-two pair matrix."""
    source = exact_matrix4x2_tuple(
        matrix,
        name="determinantal_divisor_rank2(matrix)",
    )
    return _determinantal_divisor_tuple(source)


def exact_right_divide_rank2(
    matrix: np.ndarray,
    right_factor: np.ndarray,
) -> np.ndarray | None:
    """Return integral ``C`` satisfying ``matrix = C @ right_factor``.

    ``None`` is returned when the exact rational quotient is not integral.
    """
    source = exact_matrix4x2_tuple(
        matrix,
        name="exact_right_divide_rank2(matrix)",
    )
    factor = exact_matrix2_tuple(
        right_factor,
        name="exact_right_divide_rank2(right_factor)",
    )
    quotient = _exact_right_divide_tuple(source, factor)
    if quotient is None:
        return None
    return tuple_to_int_array(
        quotient,
        shape=(4, 2),
        name="exact_right_divide_rank2(result)",
    )


def canonicalize_common_right_rank2(
    matrix: np.ndarray,
) -> CommonRightCanonicalization2D:
    """Canonicalize a pair matrix under one common right ``GL(2, Z)`` action."""
    source = exact_matrix4x2_tuple(
        matrix,
        name="canonicalize_common_right_rank2(matrix)",
    )
    result = _canonicalize_common_right_rank2_tuple(source)
    return CommonRightCanonicalization2D(
        canonical_matrix=tuple_to_int_array(
            result.canonical_matrix,
            shape=(4, 2),
            name="canonicalize_common_right_rank2(canonical_matrix)",
        ),
        right_transform=tuple_to_int_array(
            result.right_transform,
            shape=(2, 2),
            name="canonicalize_common_right_rank2(right_transform)",
        ),
        pivot_rows=result.pivot_rows,
        key=result.key,
    )


def primitiveize_pair_matrix_2d(
    matrix: np.ndarray,
) -> PrimitivePairFactorization2D:
    """Saturate the rank-two column lattice of a coupled pair matrix."""
    source = exact_matrix4x2_tuple(
        matrix,
        name="primitiveize_pair_matrix_2d(matrix)",
    )
    source_minors = _maximal_minors_tuple(source)
    repeat_index = _determinantal_divisor_tuple(source)

    if repeat_index == 1:
        return PrimitivePairFactorization2D(
            primitive_matrix=tuple_to_int_array(
                source,
                shape=(4, 2),
                name="primitiveize_pair_matrix_2d(primitive_matrix)",
            ),
            source_right_factor=_IDENTITY_2D.copy(),
            repeat_index=1,
            maximal_minors=source_minors,
        )

    for factor_array in enumerate_row_hnf_2d_by_index(repeat_index):
        factor = exact_matrix2_tuple(
            factor_array,
            name="primitiveize_pair_matrix_2d(source_right_factor)",
        )
        primitive = _exact_right_divide_tuple(source, factor)
        if primitive is None:
            continue
        if _determinantal_divisor_tuple(primitive) != 1:
            continue
        if right_multiply_rows_tuple(primitive, factor) != source:
            raise RuntimeError("primitive factorization reconstruction failed")
        if abs(det2_tuple(factor)) != repeat_index:
            raise RuntimeError("primitive right-factor determinant mismatch")

        return PrimitivePairFactorization2D(
            primitive_matrix=tuple_to_int_array(
                primitive,
                shape=(4, 2),
                name="primitiveize_pair_matrix_2d(primitive_matrix)",
            ),
            source_right_factor=np.asarray(factor, dtype=np.int_).reshape(2, 2),
            repeat_index=repeat_index,
            maximal_minors=source_minors,
        )

    raise RuntimeError("no exact primitive factorization was found")


def _clear_paired_lattice_caches() -> None:
    """Clear bounded internal caches for deterministic measurements and tests."""
    _canonicalize_common_right_rank2_tuple.cache_clear()


__all__ = [
    "CommonRightCanonicalization2D",
    "PrimitivePairFactorization2D",
    "canonicalize_common_right_rank2",
    "determinantal_divisor_rank2",
    "enumerate_row_hnf_2d_by_index",
    "exact_right_divide_rank2",
    "hnf2_col_with_transform",
    "maximal_minors_rank2",
    "primitiveize_pair_matrix_2d",
]
