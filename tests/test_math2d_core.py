import numpy as np
import pytest

from calm.math2d._core import det2, inv2, sym2


def test_sym2_makes_symmetric():
    A = np.array([[1.0, 2.0], [3.0, 4.0]])
    S = sym2(A)
    assert np.allclose(S, S.T)
    assert np.allclose(S, 0.5 * (A + A.T))


def test_det2_float():
    A = np.array([[1.5, 2.0], [3.0, 4.0]])
    d = det2(A, mode="float")
    assert isinstance(d, float)
    assert np.isclose(d, 1.5 * 4.0 - 2.0 * 3.0)


def test_det2_exact_small_int():
    A = np.array([[2, 3], [5, 7]], dtype=int)
    d = det2(A, mode="exact")
    assert isinstance(d, int)
    assert d == 2 * 7 - 3 * 5


def test_det2_auto_int_is_exact():
    A = np.array([[2, 3], [5, 7]], dtype=int)
    d = det2(A, mode="auto")
    assert isinstance(d, int)
    assert d == 2 * 7 - 3 * 5


def test_det2_auto_float_is_float():
    A = np.array([[2.0, 3.0], [5.0, 7.0]], dtype=float)
    d = det2(A, mode="auto")
    assert isinstance(d, float)


def test_inv2_identity_roundtrip():
    A = np.array([[2.0, 1.0], [3.0, 4.0]])
    Ai = inv2(A)
    I = A @ Ai
    assert np.allclose(I, np.eye(2), atol=1e-12, rtol=0.0)


def test_inv2_singular_raises():
    A = np.array([[1.0, 2.0], [2.0, 4.0]])  # det=0
    with pytest.raises(ValueError):
        _ = inv2(A)
