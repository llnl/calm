import numpy as np

from calm.math2d.sym2x2 import eigvals2_spd, eigh2_sym


def test_eigvals2_spd_known_case():
    A = np.array([[2.0, 1.0], [1.0, 2.0]])
    w = eigvals2_spd(A)
    assert np.allclose(w, [1.0, 3.0])


def test_eigh2_sym_reconstructs():
    A = np.array([[3.0, 2.0], [2.0, 1.0]])
    w, Q = eigh2_sym(A)
    # Orthonormality
    assert np.allclose(Q.T @ Q, np.eye(2), atol=1e-12)
    # Reconstruction
    A2 = (Q * w) @ Q.T
    assert np.allclose(A2, 0.5 * (A + A.T), atol=1e-12)


def test_eigh2_sym_near_diagonal_stable():
    A = np.array([[5.0, 1e-20], [1e-20, 2.0]])
    w, Q = eigh2_sym(A)
    assert np.allclose(w, [2.0, 5.0], atol=1e-12)
    assert np.allclose(Q.T @ Q, np.eye(2), atol=1e-12)
