import numpy as np
import pytest

from calm.math2d._core import det2
from calm.math2d.normal_forms import hnf2_col, snf_diag_2x2_full_rank


def test_hnf2_col_properties():
    A = np.array([[2, 3],
                  [5, 7]], dtype=int)
    H = hnf2_col(A)

    # Upper-triangular with positive diagonal and 0 <= h12 < h11
    assert H[1, 0] == 0
    assert H[0, 0] > 0
    assert H[1, 1] > 0
    assert 0 <= H[0, 1] < H[0, 0]

    # determinant matches abs(det(A))
    assert det2(H, mode="exact") == abs(int(det2(A, mode="exact")))


def test_snf_diag_2x2_full_rank_basic():
    A = np.array([[2, 4],
                  [6, 8]], dtype=int)  # det = -8
    d1, d2 = snf_diag_2x2_full_rank(A)
    assert d1 == 2  # gcd of entries
    assert d2 == 4  # |det|/d1 = 8/2


def test_snf_requires_full_rank():
    A = np.array([[1, 2], [2, 4]], dtype=int)  # det=0
    with pytest.raises(ValueError):
        _ = snf_diag_2x2_full_rank(A)
