import numpy as np
import pytest

from calm.math2d.polar2x2 import polar2


def test_polar2_reconstructs():
    A = np.array([[1.2, 0.3], [-0.7, 2.0]])
    U, H = polar2(A, eps=1e-15)
    assert np.allclose(H, H.T, atol=1e-12)
    assert np.allclose(U @ H, A, atol=1e-10)


def test_polar2_U_orthogonalish():
    A = np.array([[1.2, 0.3], [-0.7, 2.0]])
    U, H = polar2(A, eps=1e-15, reorthonormalize=True)
    I = U.T @ U
    assert np.allclose(I, np.eye(2), atol=1e-10)


def test_polar2_eps_must_be_positive():
    A = np.eye(2)
    with pytest.raises(ValueError):
        _ = polar2(A, eps=0.0)
