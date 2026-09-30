from __future__ import annotations

import numpy as np
import pytest

from calm.slab.oriented.builder import (
    _compute_R_from_ab_to_xy,
    _construct_slab_frame_rotation,
)


def _assert_proper_rotation(R: np.ndarray) -> None:
    assert R.shape == (3, 3)
    assert np.allclose(R.T @ R, np.eye(3), atol=1e-12, rtol=0)
    assert np.isclose(np.linalg.det(R), 1.0, atol=1e-12, rtol=0)


def test_ab_to_xy_rotation_preserves_metric_and_maps_plane_to_xy() -> None:
    """Surface-frame rotation is a proper rigid motion, not a lattice shear."""
    a = np.array([2.0, 0.3, 1.1])
    b = np.array([-0.4, 1.7, 0.6])

    R = _compute_R_from_ab_to_xy(a, b)
    _assert_proper_rotation(R)

    a_slab = R @ a
    b_slab = R @ b

    assert abs(a_slab[2]) < 1.0e-12
    assert abs(b_slab[2]) < 1.0e-12
    assert np.linalg.norm(a_slab) == pytest.approx(np.linalg.norm(a), abs=1.0e-12)
    assert np.linalg.norm(b_slab) == pytest.approx(np.linalg.norm(b), abs=1.0e-12)
    assert float(a_slab @ b_slab) == pytest.approx(float(a @ b), abs=1.0e-12)


def test_construct_slab_frame_rotation_uses_conv_to_slab_convention() -> None:
    """Rows of R are slab axes, so R maps conventional vectors to slab coordinates."""
    normal = np.array([1.0, 2.0, 3.0])
    inplane = np.array([3.0, -1.0, -1.0])
    inplane = inplane - np.dot(inplane, normal) / np.dot(normal, normal) * normal

    R = _construct_slab_frame_rotation(normal, inplane, normal_sign=+1)
    _assert_proper_rotation(R)

    n_slab = R @ normal
    v_slab = R @ inplane

    assert n_slab[:2] == pytest.approx([0.0, 0.0], abs=1.0e-12)
    assert n_slab[2] == pytest.approx(np.linalg.norm(normal), abs=1.0e-12)
    assert v_slab[0] == pytest.approx(np.linalg.norm(inplane), abs=1.0e-12)
    assert abs(v_slab[1]) < 1.0e-12
    assert abs(v_slab[2]) < 1.0e-12


def test_construct_slab_frame_rotation_respects_normal_sign() -> None:
    normal = np.array([0.0, 0.0, 2.0])
    inplane = np.array([1.0, 0.0, 0.0])

    R = _construct_slab_frame_rotation(normal, inplane, normal_sign=-1)
    _assert_proper_rotation(R)

    n_slab = R @ normal
    assert n_slab == pytest.approx([0.0, 0.0, -2.0], abs=1.0e-12)
