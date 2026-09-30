"""Normal-form helpers for 2D integer matrices.

This module provides Hermite and Smith normal form utilities specialized for
2×2 integer matrices. It is used by the slab reduction and lattice-matching
algorithms.
"""

from __future__ import annotations

from collections.abc import Iterator
from math import gcd

import numpy as np

from ._core import _as_2x2, det2
from ._exact_rank2 import (
    exact_matrix2_tuple,
    hnf2_col_with_transform_tuple,
    tuple_to_int_array,
)


def _gcd_many(*values: int) -> int:
    """Return the nonnegative greatest common divisor of integer values."""
    common = 0
    for value in values:
        common = gcd(common, abs(int(value)))
    return common


def hnf2_col_with_transform(
    A: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Compute canonical column HNF and an exact right witness.

    Returns
    -------
    tuple[np.ndarray, np.ndarray]
        ``(H, U)`` with ``H = A @ U``, ``det(U)`` equal to ``+/-1``,
        and ``H`` in canonical right/column Hermite normal form.
    """
    source = exact_matrix2_tuple(A, name="hnf2_col_with_transform(A)")
    reduced, transform = hnf2_col_with_transform_tuple(source)
    return (
        tuple_to_int_array(
            reduced,
            shape=(2, 2),
            name="hnf2_col_with_transform(H)",
        ),
        tuple_to_int_array(
            transform,
            shape=(2, 2),
            name="hnf2_col_with_transform(U)",
        ),
    )


def hnf2_col(A: np.ndarray) -> np.ndarray:
    """Compute the canonical 2 x 2 right/column Hermite normal form."""
    H, _transform = hnf2_col_with_transform(A)
    return H


def snf_diag_2x2_full_rank(A: np.ndarray) -> tuple[int, int]:
    """
    Return the Smith Normal Form (SNF) invariant factors for a full-rank 2×2 integer matrix.

    For rank-2 (det != 0) 2×2 matrices:
      d1 = gcd(all entries)
      d2 = |det(A)| / d1
      and d1 | d2.

    Returns only (d1, d2); not unimodular transforms.
    """
    A = _as_2x2(A, dtype=object, name="snf_diag_2x2_full_rank(A)")
    detA = det2(A, mode="exact")
    if detA == 0:
        raise ValueError("snf_diag_2x2_full_rank requires det != 0")

    d1 = _gcd_many(A[0, 0], A[0, 1], A[1, 0], A[1, 1])
    if d1 == 0:
        # Defensive: should not happen if det != 0.
        d1 = 1

    det_abs = abs(int(detA))
    d2 = det_abs // int(d1)

    if int(d1) * int(d2) != det_abs:
        raise ValueError("SNF invariant computation failed (internal inconsistency)")

    return int(d1), int(d2)


def enumerate_hnf_2d_by_index(k: int) -> Iterator[np.ndarray]:
    """Enumerate all canonical 2×2 right/column HNFs of index ``k``.

    The canonical right/column HNF representatives of index ``k`` are exactly the
    upper-triangular integer matrices:

        H = [[h11, h12],
             [  0, h22]]

    such that:
      - h11 > 0, h22 > 0,
      - h11 * h22 == k,
      - 0 <= h12 < h11.

    Enumeration order
    -----------------
    Deterministic (and stable across Python versions): increasing ``h11`` (i.e.
    increasing divisors of ``k``), then increasing ``h12``.

    Parameters
    ----------
    k
        Positive integer index / determinant.

    Yields
    ------
    np.ndarray
        (2,2) integer matrix in canonical HNF form.
    """
    k = int(k)
    if k <= 0:
        raise ValueError("enumerate_hnf_2d_by_index: k must be a positive integer")

    # Enumerate divisors h11 of k in increasing order.
    # We build the full divisor list for determinism.
    divs = []
    rmax = int(np.sqrt(k))
    for d in range(1, rmax + 1):
        if k % d == 0:
            divs.append(d)
            if d != k // d:
                divs.append(k // d)
    divs.sort()

    for h11 in divs:
        h22 = k // h11
        for h12 in range(h11):
            yield np.array([[h11, h12], [0, h22]], dtype=int)


__all__ = [
    "hnf2_col",
    "hnf2_col_with_transform",
    "enumerate_hnf_2d_by_index",
    "snf_diag_2x2_full_rank",
]
