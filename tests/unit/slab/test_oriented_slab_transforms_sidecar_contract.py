from __future__ import annotations

import json

import numpy as np
import pytest

from calm.slab.oriented.transforms import OrientedSlabTransforms
from calm.slab.oriented.sidecar import (
    read_transforms_sidecar,
    transforms_sidecar_path,
    write_transforms_sidecar,
)
from oriented_slab_fixtures import current_construction_controls


def test_current_transform_sidecar_roundtrip(tmp_path) -> None:
    structure = tmp_path / "POSCAR"
    transforms = OrientedSlabTransforms(
        U=np.eye(3),
        hkl=(1, 1, 0),
        extra={
            "M_conv_to_slab_cart": np.eye(3).tolist(),
            "M_slab_to_conv_cart": np.eye(3).tolist(),
            "construction_controls": current_construction_controls(),
        },
    )

    sidecar = write_transforms_sidecar(structure, transforms)
    assert sidecar == transforms_sidecar_path(structure)

    restored = read_transforms_sidecar(structure)
    assert isinstance(restored, OrientedSlabTransforms)
    assert restored.payload == transforms.payload


def test_version_one_sidecar_preserves_omitted_construction_controls(
    tmp_path,
) -> None:
    structure = tmp_path / "historical-export.vasp"
    payload = {
        "version": 1,
        "hkl": [1, 0, 0],
        "U": np.eye(3).tolist(),
    }

    write_transforms_sidecar(structure, payload)
    restored = read_transforms_sidecar(structure)

    assert restored.payload == payload
    assert "construction_controls" not in restored.payload


def test_version_one_sidecar_preserves_historical_control_vocabulary(
    tmp_path,
) -> None:
    from calm.slab.oriented.transforms import from_transforms_payload

    from calm.slab.oriented.transforms import from_transforms_payload

    structure = tmp_path / "historical-controls.vasp"
    controls = {
        "policy": "bounded_surface_gauges",
        "policy_version": 1,
        "construction_path": "conventional_compatibility",
        "primitive_max_denominator": None,
        "primitive_reduction_max_iter": None,
        "stacking_search_radius": None,
        "stacking_boundary_policy": None,
        "motif_max_denominator": 12,
        "c_tilt_enabled": True,
        "c_tilt_search": 6,
        "c_tilt_singular_tolerance": 1e-12,
        "c_tilt_boundary_policy": "fail_if_best_candidate_is_on_boundary",
    }
    payload = {
        "version": 1,
        "hkl": [1, 0, 0],
        "U": np.eye(3).tolist(),
        "construction_controls": controls,
    }

    write_transforms_sidecar(structure, payload)
    restored = read_transforms_sidecar(structure)

    assert restored.payload["construction_controls"] == controls
    with pytest.raises(ValueError, match="unsupported current field"):
        from_transforms_payload(restored.payload)
    with pytest.raises(ValueError, match="unsupported current field"):
        from_transforms_payload(restored.payload)


@pytest.mark.parametrize(
    ("controls", "message"),
    [
        (None, "must be a mapping"),
        ({}, "must not be empty"),
        ([], "must be a mapping"),
        ({"bad": float("inf")}, "must be finite"),
    ],
)
def test_sidecar_rejects_malformed_present_construction_controls(
    tmp_path,
    controls,
    message,
) -> None:
    structure = tmp_path / "malformed.vasp"
    sidecar = transforms_sidecar_path(structure)
    sidecar.write_text(
        json.dumps(
            {
                "version": 1,
                "hkl": [1, 0, 0],
                "U": np.eye(3).tolist(),
                "construction_controls": controls,
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises((TypeError, ValueError), match=message):
        read_transforms_sidecar(structure)


def test_sidecar_rejects_nonfinite_transport_metadata(tmp_path) -> None:
    structure = tmp_path / "nonfinite.vasp"
    sidecar = transforms_sidecar_path(structure)
    sidecar.write_text(
        json.dumps(
            {
                "version": 1,
                "hkl": [1, 0, 0],
                "U": np.eye(3).tolist(),
                "historical_metric": float("nan"),
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="must be finite"):
        read_transforms_sidecar(structure)


def test_transform_sidecar_rejects_historical_or_arbitrary_json(tmp_path) -> None:
    structure = tmp_path / "slab.vasp"
    sidecar = transforms_sidecar_path(structure)
    sidecar.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "backend": "legacy",
                "transforms": {"U": np.eye(3).tolist()},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Historical oriented-slab transform keys"):
        read_transforms_sidecar(structure)

    with pytest.raises(ValueError, match="Historical oriented-slab transform keys"):
        write_transforms_sidecar(
            structure,
            {
                "schema_version": 1,
                "hkl": [1, 0, 0],
                "U": np.eye(3).tolist(),
            },
        )


def test_transform_sidecar_accepts_current_detailed_kernel_provenance(tmp_path) -> None:
    from types import SimpleNamespace

    structure = tmp_path / "slab.extxyz"
    kernel = SimpleNamespace(
        hkl_reduced=(1, 0, 0),
        layers=4,
        S_conv_to_surface_col=np.eye(3, dtype=int),
        U_inplane_col=np.eye(3, dtype=int),
        P_supercell_row=np.eye(3, dtype=int),
        R_conv_to_slab=np.eye(3),
        R_slab_to_conv=np.eye(3),
        R_align=np.eye(3),
        L_c_tilt_row=None,
        c_tilt_mn=None,
        shear_info=None,
        vacuum_info=None,
        canonical_sign_fix=None,
        supercell_reference="conventional",
        miller_primitive=(1, 0, 0),
        construction_controls=current_construction_controls(),
        M_conv_to_slab_cart=lambda: np.eye(3),
        M_slab_to_conv_cart=lambda: np.eye(3),
    )

    write_transforms_sidecar(structure, kernel)
    restored = read_transforms_sidecar(structure)

    assert restored.hkl == (1, 0, 0)
    assert restored.payload["M_conv_to_slab_cart"] == np.eye(3).tolist()
    assert restored.payload["M_slab_to_conv_cart"] == np.eye(3).tolist()
