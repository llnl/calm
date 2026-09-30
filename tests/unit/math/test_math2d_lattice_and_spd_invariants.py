"""Audit guardrails for two-dimensional lattice algebra and SPD geometry."""

from __future__ import annotations

from math import prod

import numpy as np
import pytest

from calm.math2d._core import det2
from calm.math2d.normal_forms import (
    enumerate_hnf_2d_by_index,
    hnf2_col,
    hnf2_col_with_transform,
    snf_diag_2x2_full_rank,
)
from calm.math2d.polar2x2 import polar2
from calm.math2d.spd2x2 import invsqrt_spd, log_spd, power_spd, sqrt_spd
from calm.math2d.sym2x2 import eigh2_sym
from calm.math2d.spd2x2 import (
    chol_upper,
    geodesic_spd,
    gram_2d,
)
from reference.spd_reference import airm_distance_reference


def _rotation(theta: float) -> np.ndarray:
    cosine = np.cos(theta)
    sine = np.sin(theta)
    return np.array([[cosine, -sine], [sine, cosine]])


def _sigma_one(index: int) -> int:
    return sum(divisor for divisor in range(1, index + 1) if index % divisor == 0)


@pytest.mark.parametrize(
    "matrix",
    [
        np.array([[2, 3], [5, 7]], dtype=int),
        np.array([[1, 2], [3, 4]], dtype=int),
        np.array([[2, 0], [1, 3]], dtype=int),
        np.array([[-3, 2], [5, 1]], dtype=int),
    ],
)
def test_column_hnf_is_canonical_and_right_equivalent(matrix: np.ndarray) -> None:
    hnf, transform = hnf2_col_with_transform(matrix)

    assert det2(transform, mode="exact") in (-1, 1)
    np.testing.assert_array_equal(matrix.astype(object) @ transform, hnf)
    assert hnf[1, 0] == 0
    assert hnf[0, 0] > 0
    assert hnf[1, 1] > 0
    assert 0 <= hnf[0, 1] < hnf[0, 0]
    assert det2(hnf, mode="exact") == abs(det2(matrix, mode="exact"))


def test_column_hnf_is_invariant_under_right_unimodular_changes() -> None:
    matrix = np.array([[7, -4], [3, 5]], dtype=int)
    unimodular_changes = (
        np.array([[1, 3], [0, 1]], dtype=int),
        np.array([[0, 1], [1, 0]], dtype=int),
        np.array([[-1, 0], [0, 1]], dtype=int),
    )

    reference = hnf2_col(matrix)
    for change in unimodular_changes:
        assert det2(change, mode="exact") in (-1, 1)
        np.testing.assert_array_equal(hnf2_col(matrix @ change), reference)


@pytest.mark.parametrize("index", [1, 2, 4, 6, 12, 25])
def test_hnf_enumeration_is_complete_for_each_fixed_index(index: int) -> None:
    representatives = list(enumerate_hnf_2d_by_index(index))
    keys = {tuple(int(value) for value in hnf.ravel()) for hnf in representatives}

    assert len(representatives) == _sigma_one(index)
    assert len(keys) == len(representatives)
    for hnf in representatives:
        assert det2(hnf, mode="exact") == index
        assert hnf[1, 0] == 0
        assert 0 <= hnf[0, 1] < hnf[0, 0]


def test_snf_invariants_survive_left_and_right_unimodular_changes() -> None:
    matrix = np.array([[12, 18], [8, 14]], dtype=int)
    left = np.array([[1, 2], [0, 1]], dtype=int)
    right = np.array([[0, 1], [-1, 0]], dtype=int)

    reference = snf_diag_2x2_full_rank(matrix)
    transformed = snf_diag_2x2_full_rank(left @ matrix @ right)

    assert transformed == reference
    assert reference[1] % reference[0] == 0
    assert prod(reference) == abs(det2(matrix, mode="exact"))


def test_symmetric_eigendecomposition_is_scale_equivariant() -> None:
    matrix = np.array(
        [
            [7.97322066e-13, -1.72793141e-16],
            [-1.72793141e-16, 5.14805633e-14],
        ]
    )
    eigenvalues, eigenvectors = eigh2_sym(matrix)

    np.testing.assert_allclose(
        eigenvectors @ np.diag(eigenvalues) @ eigenvectors.T,
        matrix,
        atol=1.0e-27,
        rtol=1.0e-12,
    )
    np.testing.assert_allclose(eigenvectors.T @ eigenvectors, np.eye(2), atol=1.0e-14)


def test_polar_decomposition_is_covariant_under_positive_scaling() -> None:
    matrix = np.array([[1.2, 0.3], [-0.7, 2.0]])
    reference_rotation, reference_stretch = polar2(matrix)

    for scale in (1.0e-12, 1.0e-6, 1.0, 1.0e6, 1.0e12):
        rotation, stretch = polar2(scale * matrix)
        np.testing.assert_allclose(rotation, reference_rotation, atol=1.0e-12)
        np.testing.assert_allclose(
            stretch,
            scale * reference_stretch,
            atol=1.0e-12 * scale,
            rtol=1.0e-12,
        )
        np.testing.assert_allclose(rotation @ stretch, scale * matrix, rtol=1.0e-12)
        np.testing.assert_allclose(rotation.T @ rotation, np.eye(2), atol=1.0e-12)


def test_rank_deficient_polar_factor_is_a_partial_isometry() -> None:
    matrix = np.diag([2.0, 0.0])
    rotation, stretch = polar2(matrix)

    np.testing.assert_allclose(rotation @ stretch, matrix)
    np.testing.assert_allclose(rotation.T @ rotation, np.diag([1.0, 0.0]))
    assert np.linalg.det(rotation) == 0.0


def test_spd_spectral_functions_satisfy_defining_identities() -> None:
    rotation = _rotation(0.37)
    metric = rotation @ np.diag([0.8, 3.2]) @ rotation.T

    square_root = sqrt_spd(metric)
    inverse_square_root = invsqrt_spd(metric)
    logarithm = log_spd(metric)

    np.testing.assert_allclose(square_root @ square_root, metric, atol=1.0e-12)
    np.testing.assert_allclose(
        inverse_square_root @ metric @ inverse_square_root,
        np.eye(2),
        atol=1.0e-12,
    )
    np.testing.assert_allclose(power_spd(metric, 0.5), square_root, atol=1.0e-12)
    np.testing.assert_allclose(
        power_spd(metric, -0.5, eps=1.0e-15),
        inverse_square_root,
        atol=1.0e-12,
    )
    np.testing.assert_allclose(logarithm, logarithm.T, atol=1.0e-14)


def test_airm_geodesic_has_constant_speed_and_determinant_interpolation() -> None:
    metric_a = np.array([[2.0, 0.3], [0.3, 1.0]])
    metric_b = np.array([[1.4, -0.2], [-0.2, 2.2]])
    distance = airm_distance_reference(metric_a, metric_b)

    for parameter in (0.0, 0.2, 0.5, 0.9, 1.0):
        metric = geodesic_spd(metric_a, metric_b, parameter)
        partial_distance = airm_distance_reference(metric_a, metric)
        determinant = np.linalg.det(metric)
        expected_determinant = (
            np.linalg.det(metric_a) ** (1.0 - parameter)
            * np.linalg.det(metric_b) ** parameter
        )

        assert np.isclose(
            partial_distance,
            parameter * distance,
            atol=1.0e-10,
            rtol=1.0e-9,
        )
        assert np.isclose(
            determinant,
            expected_determinant,
            atol=1.0e-12,
            rtol=1.0e-12,
        )


def test_cholesky_lift_recovers_the_metric_in_a_deterministic_gauge() -> None:
    basis = np.array([[2.0, 0.4], [0.2, 1.3]])
    metric = gram_2d(basis)
    lift = chol_upper(metric)

    assert np.all(np.diag(lift) > 0.0)
    np.testing.assert_allclose(lift, np.triu(lift))
    np.testing.assert_allclose(lift.T @ lift, metric, atol=1.0e-12)
