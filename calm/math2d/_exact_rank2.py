"""Private exact scalar kernels for small rank-two integer matrices.

The public CALM matrix APIs use NumPy arrays, but their hottest exact-arithmetic
paths operate on only four or eight integers at a time.  This module keeps those
inner operations as immutable tuples of Python integers so exactness is retained
without repeated ``dtype=object`` array allocation.
"""

from __future__ import annotations

from functools import lru_cache
from math import gcd
from typing import TypeAlias, cast

import numpy as np

Matrix2Tuple: TypeAlias = tuple[int, int, int, int]
Matrix4x2Tuple: TypeAlias = tuple[int, int, int, int, int, int, int, int]
Rank2RowsTuple: TypeAlias = Matrix2Tuple | Matrix4x2Tuple

_NP_INT_INFO = np.iinfo(np.int_)
# Small bounded working set: repeated pivots have strong local reuse within one search.
_HNF_CACHE_SIZE = 512


def _check_np_int_value(value: int, *, name: str) -> int:
    """Return ``value`` after enforcing CALM's supported ``np.int_`` range."""
    integer = int(value)
    if integer < _NP_INT_INFO.min or integer > _NP_INT_INFO.max:
        raise OverflowError(
            f"{name}: value {integer} out of range for np.int_ "
            f"[{_NP_INT_INFO.min}, {_NP_INT_INFO.max}]"
        )
    return integer


def ensure_np_int_tuple(
    values: tuple[int, ...],
    *,
    name: str,
) -> tuple[int, ...]:
    """Return ``values`` after checking every entry against ``np.int_``."""
    for value in values:
        _check_np_int_value(value, name=name)
    return values


def exact_integer_tuple(
    matrix: np.ndarray,
    *,
    shape: tuple[int, int],
    name: str,
) -> tuple[int, ...]:
    """Validate one exact integer matrix and return its row-major tuple."""
    array = np.asarray(matrix)
    if array.shape != shape:
        raise ValueError(f"{name}: expected shape {shape}, got {array.shape}")
    if array.dtype.kind == "b":
        raise TypeError(f"{name}: boolean entries are not valid integers")
    if array.dtype.kind not in ("i", "u", "O"):
        raise TypeError(f"{name}: entries must be exact integers")

    values: list[int] = []
    for value in array.flat:
        if isinstance(value, (bool, np.bool_)) or not isinstance(
            value, (int, np.integer)
        ):
            raise TypeError(f"{name}: entries must be exact integers")
        values.append(_check_np_int_value(int(value), name=name))
    return tuple(values)


def exact_matrix2_tuple(matrix: np.ndarray, *, name: str) -> Matrix2Tuple:
    """Validate and flatten one exact ``2 x 2`` integer matrix."""
    return cast(
        Matrix2Tuple,
        exact_integer_tuple(matrix, shape=(2, 2), name=name),
    )


def exact_matrix4x2_tuple(matrix: np.ndarray, *, name: str) -> Matrix4x2Tuple:
    """Validate and flatten one exact ``4 x 2`` integer matrix."""
    return cast(
        Matrix4x2Tuple,
        exact_integer_tuple(matrix, shape=(4, 2), name=name),
    )


def tuple_to_int_array(
    values: tuple[int, ...],
    *,
    shape: tuple[int, int],
    name: str,
) -> np.ndarray:
    """Return a fresh ``np.int_`` array after exact overflow checking."""
    checked = tuple(_check_np_int_value(value, name=name) for value in values)
    return np.asarray(checked, dtype=np.int_).reshape(shape)


def det2_tuple(matrix: Matrix2Tuple) -> int:
    """Return the exact determinant of one flattened ``2 x 2`` matrix."""
    a, b, c, d = matrix
    return a * d - b * c


def multiply2_tuple(
    left: Matrix2Tuple,
    right: Matrix2Tuple,
) -> Matrix2Tuple:
    """Return exact ``left @ right`` for flattened ``2 x 2`` matrices."""
    a, b, c, d = left
    e, f, g, h = right
    return (
        a * e + b * g,
        a * f + b * h,
        c * e + d * g,
        c * f + d * h,
    )


def left_multiply2_tuple(
    left: Matrix2Tuple,
    right: Matrix2Tuple,
) -> Matrix2Tuple:
    """Alias documenting a left action on one exact ``2 x 2`` block."""
    return multiply2_tuple(left, right)


def right_multiply_rows_tuple(
    matrix: Rank2RowsTuple,
    right: Matrix2Tuple,
) -> Rank2RowsTuple:
    """Return exact ``matrix @ right`` for a two-column row-major matrix."""
    a, b, c, d = right
    output: list[int] = []
    for offset in range(0, len(matrix), 2):
        x = matrix[offset]
        y = matrix[offset + 1]
        output.extend((x * a + y * c, x * b + y * d))
    return cast(Rank2RowsTuple, tuple(output))


def _extended_gcd(a: int, b: int) -> tuple[int, int, int]:
    """Return ``(g, x, y)`` with ``x*a + y*b = g = gcd(a, b)``."""
    if b == 0:
        return abs(a), 1 if a >= 0 else -1, 0
    common, x_previous, y_previous = _extended_gcd(b, a % b)
    return common, y_previous, x_previous - (a // b) * y_previous


@lru_cache(maxsize=_HNF_CACHE_SIZE)
def hnf2_col_with_transform_tuple(
    matrix: Matrix2Tuple,
) -> tuple[Matrix2Tuple, Matrix2Tuple]:
    """Return exact column HNF and right witness using scalar Python integers."""
    ensure_np_int_tuple(matrix, name="hnf2_col_with_transform(A)")
    determinant = det2_tuple(matrix)
    if determinant == 0:
        raise ValueError("hnf2_col_with_transform requires full rank (det != 0)")

    _a, _b, c, d = matrix
    common = gcd(c, d)
    if common == 0:
        raise RuntimeError("hnf2_col_with_transform: unexpected zero gcd")

    bezout_gcd, x, y = _extended_gcd(c, d)
    if bezout_gcd != common:
        raise RuntimeError("hnf2_col_with_transform: inconsistent Bezout witness")

    transform: Matrix2Tuple = (d // common, x, -c // common, y)
    reduced = multiply2_tuple(matrix, transform)

    if reduced[2] != 0:
        raise RuntimeError("hnf2_col_with_transform: elimination failed")

    if reduced[0] < 0:
        sign_flip: Matrix2Tuple = (-1, 0, 0, 1)
        transform = multiply2_tuple(transform, sign_flip)
        reduced = multiply2_tuple(reduced, sign_flip)

    h11, h12, _zero, h22 = reduced
    if h11 <= 0 or h22 <= 0:
        raise RuntimeError(
            "hnf2_col_with_transform: canonical diagonal entries are not positive"
        )

    remainder = h12 % h11
    quotient = (h12 - remainder) // h11
    shear: Matrix2Tuple = (1, -quotient, 0, 1)
    transform = multiply2_tuple(transform, shear)
    reduced = multiply2_tuple(reduced, shear)

    if det2_tuple(transform) not in (-1, 1):
        raise RuntimeError("hnf2_col_with_transform: witness is not unimodular")
    if multiply2_tuple(matrix, transform) != reduced:
        raise RuntimeError("hnf2_col_with_transform: witness reconstruction failed")
    if not (
        reduced[2] == 0
        and reduced[0] > 0
        and reduced[3] > 0
        and 0 <= reduced[1] < reduced[0]
    ):
        raise RuntimeError("hnf2_col_with_transform: noncanonical result")
    if det2_tuple(reduced) != abs(determinant):
        raise RuntimeError("hnf2_col_with_transform: determinant mismatch")

    for value in reduced:
        _check_np_int_value(value, name="hnf2_col_with_transform(H)")
    for value in transform:
        _check_np_int_value(value, name="hnf2_col_with_transform(U)")
    return reduced, transform


def clear_exact_rank2_caches() -> None:
    """Clear bounded scalar-kernel caches for deterministic measurements/tests."""
    hnf2_col_with_transform_tuple.cache_clear()


__all__ = [
    "Matrix2Tuple",
    "Matrix4x2Tuple",
    "Rank2RowsTuple",
    "clear_exact_rank2_caches",
    "det2_tuple",
    "ensure_np_int_tuple",
    "exact_matrix2_tuple",
    "exact_matrix4x2_tuple",
    "hnf2_col_with_transform_tuple",
    "left_multiply2_tuple",
    "multiply2_tuple",
    "right_multiply_rows_tuple",
    "tuple_to_int_array",
]
