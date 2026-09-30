"""Tests for the proper-orientation two-dimensional Gauss reduction."""

from __future__ import annotations

import numpy as np
import pytest

from calm.symmetry.reduction import (
    canonical_gauss_reduce_2d,
    oriented_gauss_reduce_2d,
)


def _det_exact(matrix: np.ndarray) -> int:
    return int(matrix[0, 0]) * int(matrix[1, 1]) - int(matrix[0, 1]) * int(
        matrix[1, 0]
    )


@pytest.mark.parametrize(
    "basis",
    [
        np.eye(2),
        np.array([[1.0, 4.0], [0.0, 5.0]]),
        np.array([[2.0, 1.0], [0.0, 1.0]]),
        np.array([[-3.0, -3.0], [-2.0, -3.0]]),
        np.array([[0.0, 1.0], [1.0, 0.0]]),
    ],
)
def test_oriented_reduction_returns_proper_witnesses(basis: np.ndarray) -> None:
    reduced, transform, rotation = oriented_gauss_reduce_2d(basis)

    assert _det_exact(transform) == 1
    assert np.linalg.det(rotation) == pytest.approx(1.0)
    assert rotation.T @ rotation == pytest.approx(np.eye(2), abs=1e-12)
    assert reduced == pytest.approx(rotation @ basis @ transform, abs=1e-12)
    assert np.sign(np.linalg.det(reduced)) == np.sign(np.linalg.det(basis))

    a = float(reduced[:, 0] @ reduced[:, 0])
    dot = float(reduced[:, 0] @ reduced[:, 1])
    c = float(reduced[:, 1] @ reduced[:, 1])
    assert a <= c + 1e-12 * max(1.0, a, c)
    assert 2.0 * abs(dot) <= a + 1e-12 * max(1.0, a, c)


def test_oriented_reduction_does_not_reuse_reflected_shape_gauge() -> None:
    basis = np.array([[-3.0, -3.0], [-2.0, -3.0]])
    _shape, shape_U, shape_Q = canonical_gauss_reduce_2d(
        basis,
        warn_on_handedness_repair=False,
    )
    oriented, oriented_U, oriented_Q = oriented_gauss_reduce_2d(basis)

    assert _det_exact(shape_U) == -1
    assert np.linalg.det(shape_Q) == pytest.approx(-1.0)
    assert _det_exact(oriented_U) == 1
    assert np.linalg.det(oriented_Q) == pytest.approx(1.0)
    assert oriented == pytest.approx(oriented_Q @ basis @ oriented_U)


def test_oriented_reduction_is_invariant_under_proper_integer_gauges() -> None:
    basis = np.array([[2.3, -1.7], [0.8, 3.4]])
    reference, _reference_U, _reference_Q = oriented_gauss_reduce_2d(basis)
    gauges = (
        np.array([[1, 3], [0, 1]], dtype=int),
        np.array([[1, 0], [-2, 1]], dtype=int),
        np.array([[0, -1], [1, 0]], dtype=int),
        -np.eye(2, dtype=int),
        np.array([[-2, -1], [3, 1]], dtype=int),
    )
    for gauge in gauges:
        assert _det_exact(gauge) == 1
        reduced, transform, rotation = oriented_gauss_reduce_2d(basis @ gauge)
        assert reduced == pytest.approx(reference, rel=1e-12, abs=1e-12)
        assert _det_exact(transform) == 1
        assert np.linalg.det(rotation) == pytest.approx(1.0)


def test_oriented_reduction_is_scale_covariant() -> None:
    basis = np.array([[2.0, -3.0], [1.0, 4.0]])
    reference, reference_U, reference_Q = oriented_gauss_reduce_2d(basis)
    for scale in (1e-120, 1e-9, 1.0, 1e9, 1e120):
        reduced, transform, rotation = oriented_gauss_reduce_2d(scale * basis)
        assert np.array_equal(transform, reference_U)
        assert rotation == pytest.approx(reference_Q, abs=1e-12)
        assert reduced / scale == pytest.approx(reference, rel=1e-12, abs=1e-12)


@pytest.mark.parametrize(
    "basis",
    [
        np.zeros((2, 2)),
        np.ones((3, 3)),
        np.array([[np.nan, 0.0], [0.0, 1.0]]),
    ],
)
def test_oriented_reduction_rejects_invalid_bases(basis: np.ndarray) -> None:
    with pytest.raises(ValueError):
        oriented_gauss_reduce_2d(basis)
