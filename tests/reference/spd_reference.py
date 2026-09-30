"""Independent NumPy references for two-dimensional SPD geometry tests."""

from __future__ import annotations

import numpy as np


def is_spd_reference(matrix: np.ndarray, *, tol: float = 0.0) -> bool:
    """Return whether a finite symmetric matrix is positive definite."""
    array = np.asarray(matrix, dtype=float)
    if array.shape != (2, 2) or not np.all(np.isfinite(array)):
        return False
    if not np.allclose(array, array.T, atol=1.0e-12, rtol=0.0):
        return False
    return bool(np.min(np.linalg.eigvalsh(array)) > float(tol))


def airm_distance_reference(metric_a: np.ndarray, metric_b: np.ndarray) -> float:
    """Evaluate the affine-invariant SPD distance with NumPy eigensolvers."""
    a = np.asarray(metric_a, dtype=float)
    b = np.asarray(metric_b, dtype=float)
    if not is_spd_reference(a) or not is_spd_reference(b):
        raise ValueError("airm_distance_reference requires SPD 2 x 2 matrices")

    eigenvalues, eigenvectors = np.linalg.eigh(0.5 * (a + a.T))
    inverse_square_root = (
        eigenvectors * np.power(eigenvalues, -0.5)
    ) @ eigenvectors.T
    relative = inverse_square_root @ b @ inverse_square_root
    relative = 0.5 * (relative + relative.T)
    relative_eigenvalues = np.linalg.eigvalsh(relative)
    if np.any(relative_eigenvalues <= 0.0):
        raise ValueError("relative metric is not positive definite")
    return float(np.linalg.norm(np.log(relative_eigenvalues)))
