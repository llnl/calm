"""Guardrails for oriented slab operation transform JSON projection."""

from __future__ import annotations

import inspect
from pathlib import Path

import numpy as np
import pytest

from calm.slab.oriented import builder as oriented_slab
from calm.slab.oriented.builder import OrientedSlabTransforms
from calm.serialization.scientific import scientific_json_native as _json_native
from oriented_slab_fixtures import current_construction_controls


def test_oriented_slab_ops_to_dict_uses_shared_json_native_helper() -> None:
    source = inspect.getsource(OrientedSlabTransforms.to_dict)

    assert "_json_native(self.shear_info)" in source
    assert "_json_native(self.vacuum_info)" in source
    assert "def _jsonify" not in source
    assert oriented_slab._json_native is _json_native


def test_oriented_slab_ops_to_dict_preserves_json_native_projection() -> None:
    transforms = OrientedSlabTransforms(
        hkl_reduced=(1, 1, 0),
        layers=np.int64(4),
        S_conv_to_surface_col=None,
        U_inplane_col=None,
        P_supercell_row=None,
        R_conv_to_slab=None,
        R_slab_to_conv=None,
        R_align=None,
        L_c_tilt_row=None,
        c_tilt_mn=None,
        shear_info={
            "matrix": np.array([[1, 2], [3, 4]], dtype=np.int64),
            "scalar": np.float64(1.25),
        },
        vacuum_info={"offsets": (np.int64(1), np.int64(2))},
        construction_controls=current_construction_controls(),
    )

    payload = transforms.to_dict()

    assert payload["shear_info"] == {"matrix": [[1, 2], [3, 4]], "scalar": 1.25}
    assert payload["vacuum_info"] == {"offsets": [1, 2]}


def test_public_projection_persists_explicit_cartesian_frame_maps() -> None:
    path = Path(__file__).resolve().parents[3] / "calm/slab/oriented/model.py"
    source = path.read_text(encoding="utf-8")

    assert "M_conv_to_slab_cart" in source
    assert "M_slab_to_conv_cart" in source
    assert "R_conv_to_slab" in source
    assert "R_slab_to_conv" in source


def test_oriented_slab_ops_round_trip_preserves_construction_controls() -> None:
    controls = current_construction_controls()
    controls["policy_version"] = np.int64(1)
    controls["primitive_max_denominator"] = np.int64(12)
    controls["primitive_reduction_max_iter"] = np.int64(100)
    controls["stacking_search_radius"] = np.int64(2)
    controls["c_tilt_search"] = np.int64(6)
    controls["c_tilt_singular_tolerance"] = np.float64(1e-12)
    transforms = OrientedSlabTransforms(
        hkl_reduced=(1, 1, 1),
        layers=4,
        S_conv_to_surface_col=None,
        U_inplane_col=None,
        P_supercell_row=None,
        R_conv_to_slab=None,
        R_slab_to_conv=None,
        R_align=None,
        L_c_tilt_row=None,
        c_tilt_mn=None,
        shear_info=None,
        vacuum_info=None,
        construction_controls=controls,
    )

    payload = transforms.to_dict()
    restored = OrientedSlabTransforms.from_dict(payload)

    assert payload["construction_controls"] == current_construction_controls()
    assert restored.construction_controls == payload["construction_controls"]


def test_oriented_slab_ops_rejects_missing_current_construction_controls() -> None:
    transforms = OrientedSlabTransforms(
        hkl_reduced=(1, 0, 0),
        layers=2,
        S_conv_to_surface_col=None,
        U_inplane_col=None,
        P_supercell_row=None,
        R_conv_to_slab=None,
        R_slab_to_conv=None,
        R_align=None,
        L_c_tilt_row=None,
        c_tilt_mn=None,
        shear_info=None,
        vacuum_info=None,
        construction_controls=current_construction_controls(),
    )
    incomplete_payload = transforms.to_dict()
    incomplete_payload.pop("construction_controls")

    with pytest.raises(KeyError, match="construction_controls"):
        OrientedSlabTransforms.from_dict(incomplete_payload)


def test_oriented_slab_ops_rejects_malformed_current_controls() -> None:
    controls = current_construction_controls()
    controls["stacking_search_radius"] = 0

    with pytest.raises(ValueError, match="stacking_search_radius"):
        OrientedSlabTransforms(
            hkl_reduced=(1, 0, 0),
            layers=2,
            S_conv_to_surface_col=None,
            U_inplane_col=None,
            P_supercell_row=None,
            R_conv_to_slab=None,
            R_slab_to_conv=None,
            R_align=None,
            L_c_tilt_row=None,
            c_tilt_mn=None,
            shear_info=None,
            vacuum_info=None,
            construction_controls=controls,
        )
