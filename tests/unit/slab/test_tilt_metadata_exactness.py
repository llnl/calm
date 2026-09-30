from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from calm.slab.oriented.tilt import compute_slab_tilt_metadata
from calm.slab.oriented.transforms import OrientedSlabTransforms


def _atoms(cell) -> SimpleNamespace:
    return SimpleNamespace(cell=SimpleNamespace(array=cell))


def test_tilt_metadata_requires_exact_cell_shape() -> None:
    with pytest.raises(ValueError, match=r"shape \(3, 3\)"):
        compute_slab_tilt_metadata(_atoms(np.eye(2)))


def test_tilt_metadata_rejects_nonfinite_cell() -> None:
    cell = np.eye(3)
    cell[2, 0] = np.nan
    with pytest.raises(ValueError, match="finite"):
        compute_slab_tilt_metadata(_atoms(cell))


def test_tilt_metadata_rejects_transform_like_objects() -> None:
    with pytest.raises(TypeError, match="OrientedSlabTransforms"):
        compute_slab_tilt_metadata(
            _atoms(np.eye(3)),
            transforms=SimpleNamespace(payload={}),
        )


def test_tilt_metadata_rejects_malformed_integer_reduction() -> None:
    transforms = OrientedSlabTransforms(
        extra={"c_tilt_mn": ["1", 0]},
    )
    with pytest.raises(TypeError, match="c_tilt_mn"):
        compute_slab_tilt_metadata(_atoms(np.eye(3)), transforms=transforms)


def test_tilt_metadata_rejects_malformed_shear_provenance() -> None:
    transforms = OrientedSlabTransforms(
        extra={"shear_info": {"c_xy_norm_before": "bad"}},
    )
    with pytest.raises(TypeError, match="c_xy_norm_before"):
        compute_slab_tilt_metadata(_atoms(np.eye(3)), transforms=transforms)


def test_tilt_metadata_preserves_valid_current_provenance() -> None:
    transforms = OrientedSlabTransforms(
        extra={
            "c_tilt_mn": [1, -1],
            "L_c_tilt_row": [[1, 0, 0], [0, 1, 0], [1, -1, 1]],
            "shear_info": {
                "F_shear_cart": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
                "c_xy_norm_before": 1.0,
                "c_xy_norm_after": 0.0,
            },
            "vacuum_info": {"vacuum_per_side": 8.0},
        },
    )

    result = compute_slab_tilt_metadata(
        _atoms([[2.0, 0.0, 0.0], [0.0, 2.0, 0.0], [0.2, 0.1, 8.0]]),
        transforms=transforms,
    )

    assert result["c_tilt_mn"] == [1, -1]
    assert result["integer_c_tilt_reduction_applied"] is True
    assert result["orthogonalize_c_applied"] is True
    assert result["c_xy_norm_before"] == 1.0
    assert result["c_xy_norm_after"] == 0.0
    assert result["vacuum_info"] == {"vacuum_per_side": 8.0}
