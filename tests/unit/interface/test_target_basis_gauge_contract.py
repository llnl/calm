from __future__ import annotations

import numpy as np
import pytest

from calm.interface.refinement._math import (
    TARGET_BASIS_GAUGE,
    TARGET_BASIS_GAUGE_VERSION,
    geodesic_strain_partition_2d,
)


def test_upper_cholesky_gauge_is_verified_and_reconstructs_target() -> None:
    basis_a = np.array([[2.0, 0.4], [0.0, 1.5]])
    basis_b = np.array([[1.8, -0.2], [0.0, 2.1]])
    result = geodesic_strain_partition_2d(basis_a, basis_b, alpha=0.37)

    assert result.target_basis_gauge == TARGET_BASIS_GAUGE
    assert result.target_basis_gauge_version == TARGET_BASIS_GAUGE_VERSION
    assert np.allclose(result.target_basis, np.triu(result.target_basis))
    assert np.all(np.diag(result.target_basis) > 0.0)
    assert np.linalg.det(result.target_basis) > 0.0
    assert result.target_metric_reconstruction_relative_error <= 1e-10
    assert result.target_lower_triangle_relative_error <= 1e-10
    assert np.allclose(
        result.target_basis.T @ result.target_basis,
        result.target_metric,
        rtol=1e-10,
        atol=1e-12,
    )


def test_endpoint_swap_uses_the_same_deterministic_target_gauge() -> None:
    basis_a = np.array([[2.0, 0.3], [0.0, 1.2]])
    basis_b = np.array([[1.4, 0.1], [0.0, 2.2]])
    ab = geodesic_strain_partition_2d(basis_a, basis_b, alpha=0.2)
    ba = geodesic_strain_partition_2d(basis_b, basis_a, alpha=0.8)
    assert np.allclose(ab.target_metric, ba.target_metric, rtol=1e-11, atol=1e-12)
    assert np.allclose(ab.target_basis, ba.target_basis, rtol=1e-11, atol=1e-12)


def test_gauge_tolerance_and_near_singularity_fail_explicitly() -> None:
    with pytest.raises(ValueError, match="gauge_relative_tolerance"):
        geodesic_strain_partition_2d(
            np.eye(2),
            np.eye(2),
            alpha=0.5,
            gauge_relative_tolerance=0.0,
        )
    with pytest.raises(ValueError, match="right-handed, nonsingular"):
        geodesic_strain_partition_2d(
            np.array([[1.0, 1.0], [0.0, 1e-16]]),
            np.eye(2),
            alpha=0.5,
            eps_spd=1e-14,
        )
