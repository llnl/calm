"""Tests for R_align (gauge fixing rotation) tracking in oriented slab construction.

This test suite verifies that:
1. R_align is correctly captured from Niggli reduction
2. The rotation is properly tracked in OrientedSlabTransforms
3. Helper methods correctly decompose the total rotation
"""

import numpy as np
import pytest
from ase.build import bulk

from calm.bulk.bulk import Bulk
from calm.slab.oriented.builder import build_oriented_slab


def test_r_align_is_captured_when_reduce_inplane_true():
    """Test that R_align is captured when reduce_inplane=True."""
    conv = bulk("Al", "fcc", a=4.05, cubic=True)
    bulk_obj = Bulk(conv)

    res = build_oriented_slab(
        bulk_obj,
        hkl=(1, 1, 0),
        layers=3,
        reduce_inplane=True,  # Should capture R_align
        vacuum=None,
    )

    R_align = res.transforms.R_align
    assert R_align is not None
    assert R_align.shape == (3, 3)

    # Should be orthogonal
    assert np.allclose(R_align.T @ R_align, np.eye(3), atol=1e-10)
    assert np.isclose(np.linalg.det(R_align), 1.0, atol=1e-10)


def test_r_align_is_identity_when_reduce_inplane_false():
    """Test that R_align is identity when reduce_inplane=False."""
    conv = bulk("Al", "fcc", a=4.05, cubic=True)
    bulk_obj = Bulk(conv)

    res = build_oriented_slab(
        bulk_obj,
        hkl=(1, 1, 0),
        layers=3,
        reduce_inplane=False,  # Should not apply gauge fixing
        vacuum=None,
    )

    R_align = res.transforms.R_align
    # Should be identity (or None, which __post_init__ converts to identity)
    assert np.allclose(R_align, np.eye(3), atol=1e-10)


def test_r_align_is_orthogonal():
    """Test that R_align is a proper orthogonal rotation."""
    conv = bulk("Cu", "fcc", a=3.6, cubic=True)
    bulk_obj = Bulk(conv)

    res = build_oriented_slab(
        bulk_obj,
        hkl=(1, 1, 1),
        layers=3,
        reduce_inplane=True,
        vacuum=None,
    )

    R_align = res.transforms.R_align

    # Orthogonality
    assert np.allclose(R_align.T @ R_align, np.eye(3), atol=1e-10)
    assert np.allclose(R_align @ R_align.T, np.eye(3), atol=1e-10)

    # Proper rotation (det = +1)
    assert np.isclose(np.linalg.det(R_align), 1.0, atol=1e-10)


def test_rotation_decomposition():
    """Test that R_conv_to_slab can be decomposed correctly."""
    conv = bulk("Al", "fcc", a=4.05, cubic=True)
    bulk_obj = Bulk(conv)

    res = build_oriented_slab(
        bulk_obj,
        hkl=(1, 1, 0),
        layers=3,
        reduce_inplane=True,
        vacuum=None,
    )

    t = res.transforms
    R_total = t.R_conv_to_slab
    R_align = t.R_align
    R_ungauged = t.R_conv_to_ungauged()

    # Check composition: R_total ≈ R_align @ R_ungauged
    R_composed = R_align @ R_ungauged
    assert np.allclose(R_total, R_composed, atol=1e-10)


def test_helper_methods():
    """Test the helper methods for accessing different rotations."""
    conv = bulk("Al", "fcc", a=4.05, cubic=True)
    bulk_obj = Bulk(conv)

    res = build_oriented_slab(
        bulk_obj,
        hkl=(1, 1, 0),
        layers=3,
        reduce_inplane=True,
        vacuum=None,
    )

    t = res.transforms

    # Test R_conv_to_ungauged
    R_ungauged = t.R_conv_to_ungauged()
    assert R_ungauged.shape == (3, 3)
    assert np.allclose(R_ungauged.T @ R_ungauged, np.eye(3), atol=1e-10)


def test_r_align_acts_in_plane():
    """Test that R_align only rotates in the surface plane (keeps normal fixed)."""
    conv = bulk("Al", "fcc", a=4.05, cubic=True)
    bulk_obj = Bulk(conv)

    res = build_oriented_slab(
        bulk_obj,
        hkl=(1, 1, 0),
        layers=3,
        reduce_inplane=True,
        vacuum=None,
    )

    R_align = res.transforms.R_align

    # Surface normal in slab frame is [0, 0, 1]
    n_slab = np.array([0.0, 0.0, 1.0])

    # R_align should keep the normal fixed (in-plane rotation only)
    n_rotated = R_align @ n_slab
    assert np.allclose(n_rotated, n_slab, atol=1e-10)


def test_multiple_surfaces():
    """Test R_align capture for multiple surface orientations."""
    conv = bulk("Al", "fcc", a=4.05, cubic=True)
    bulk_obj = Bulk(conv)

    surfaces = [(1, 0, 0), (1, 1, 0), (1, 1, 1), (2, 1, 0)]

    for hkl in surfaces:
        res = build_oriented_slab(
            bulk_obj,
            hkl=hkl,
            layers=3,
            reduce_inplane=True,
            vacuum=None,
        )

        R_align = res.transforms.R_align

        # Should be orthogonal
        assert np.allclose(
            R_align.T @ R_align, np.eye(3), atol=1e-10
        ), f"R_align not orthogonal for {hkl}"

        # Should be proper rotation
        assert np.isclose(
            np.linalg.det(R_align), 1.0, atol=1e-10
        ), f"det(R_align) != 1 for {hkl}"


def test_serialization_with_r_align():
    """Test that R_align is correctly serialized and deserialized."""
    from calm.slab.oriented.builder import OrientedSlabTransforms

    conv = bulk("Al", "fcc", a=4.05, cubic=True)
    bulk_obj = Bulk(conv)

    res = build_oriented_slab(
        bulk_obj,
        hkl=(1, 1, 0),
        layers=3,
        reduce_inplane=True,
        vacuum=None,
    )

    t = res.transforms

    # Serialize to JSON
    json_str = t.to_json(sort_keys=True)

    # Deserialize
    t2 = OrientedSlabTransforms.from_json(json_str)

    # R_align should match
    assert np.allclose(t.R_align, t2.R_align, atol=1e-12)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
