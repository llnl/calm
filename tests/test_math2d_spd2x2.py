import numpy as np
import pytest

from calm.math2d.spd2x2 import (
    check_spd2,
    cholesky2_spd,
    inv2_spd,
    invsqrt_spd,
    log_spd,
    power_spd,
    sqrt_spd,
)


def _spd(A):
    A = 0.5 * (A + A.T)
    # shift to ensure SPD
    return A + 5.0 * np.eye(2)


def test_check_spd2_passes():
    G = _spd(np.array([[1.0, 2.0], [3.0, 4.0]]))
    G2 = check_spd2(G)
    assert np.allclose(G2, G2.T)


def test_check_spd2_raises():
    # Not SPD: negative leading minor
    G = np.array([[-1.0, 0.0], [0.0, 2.0]])
    with pytest.raises(ValueError):
        _ = check_spd2(G)


def test_cholesky2_spd_upper_reconstructs():
    G = _spd(np.array([[1.0, 0.2], [0.2, 0.7]]))
    R = cholesky2_spd(G, upper=True)
    assert np.allclose(R, np.triu(R))
    G2 = R.T @ R
    assert np.allclose(G2, 0.5 * (G + G.T), atol=1e-12)


def test_cholesky2_spd_lower_reconstructs():
    G = _spd(np.array([[1.0, 0.2], [0.2, 0.7]]))
    L = cholesky2_spd(G, upper=False)
    assert np.allclose(L, np.tril(L))
    G2 = L @ L.T
    assert np.allclose(G2, 0.5 * (G + G.T), atol=1e-12)


def test_inv2_spd_matches_inverse():
    G = _spd(np.array([[1.0, 0.3], [0.3, 0.8]]))
    Gi = inv2_spd(G)
    I = G @ Gi
    assert np.allclose(I, np.eye(2), atol=1e-10, rtol=0.0)


def test_sqrt_spd_roundtrip():
    G = _spd(np.array([[2.0, 0.1], [0.1, 1.0]]))
    S = sqrt_spd(G)
    G2 = S @ S
    assert np.allclose(G2, 0.5 * (G + G.T), atol=1e-10)


def test_invsqrt_spd_identity():
    G = _spd(np.array([[2.0, 0.1], [0.1, 1.0]]))
    Si = invsqrt_spd(G)
    I = Si @ G @ Si
    assert np.allclose(I, np.eye(2), atol=1e-10)


def test_log_spd_exp_like_property_via_power():
    # We can at least sanity-check that log_spd is symmetric and finite.
    G = _spd(np.array([[2.0, 0.1], [0.1, 1.0]]))
    L = log_spd(G)
    assert np.allclose(L, L.T, atol=1e-12)
    assert np.all(np.isfinite(L))


def test_power_spd_half_roundtrip():
    G = _spd(np.array([[1.0, 0.2], [0.2, 2.0]]))
    H = power_spd(G, 0.5)
    G2 = H @ H
    assert np.allclose(G2, 0.5 * (G + G.T), atol=1e-10)


def test_power_spd_negative_requires_eps():
    G = _spd(np.array([[1.0, 0.2], [0.2, 2.0]]))
    with pytest.raises(ValueError):
        _ = power_spd(G, -0.5)


def test_power_spd_negative_with_eps_ok():
    G = _spd(np.array([[1.0, 0.2], [0.2, 2.0]]))
    H = power_spd(G, -0.5, eps=1e-15)
    assert np.all(np.isfinite(H))
