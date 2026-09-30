"""Mathematical guardrails for principal strain direction analysis."""

from __future__ import annotations

import numpy as np
import pytest

from calm.interface.refinement.analysis import (
    analyze_principal_directions_in_conventional_cell,
    StrainDecomposition,
    compute_strain_decomposition,
    slab_to_conventional_cartesian_map_from_payload,
)
from oriented_slab_fixtures import current_construction_controls


def _rotation_z(theta_deg: float) -> np.ndarray:
    theta = np.deg2rad(theta_deg)
    c = float(np.cos(theta))
    s = float(np.sin(theta))
    return np.array(
        [[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]],
        dtype=float,
    )


def test_legacy_positional_decomposition_constructor_remains_valid() -> None:
    strain = np.diag([-0.02, 0.03])
    area = 0.5 * np.trace(strain) * np.eye(2)
    shape = strain - area
    decomposition = StrainDecomposition(
        np.array([-0.02, 0.03]),
        np.eye(2),
        strain,
        area,
        shape,
        float(np.linalg.norm(strain, ord="fro")),
        float(np.linalg.norm(area, ord="fro")),
        float(np.linalg.norm(shape, ord="fro")),
        float(np.trace(strain)),
    )

    assert decomposition.direction_status == "defined"
    assert decomposition.principal_eigengap == pytest.approx(0.05)
    assert decomposition.principal_eigengap_threshold == pytest.approx(0.0)


def test_exactly_degenerate_strain_withholds_arbitrary_axes() -> None:
    decomposition = compute_strain_decomposition(0.02 * np.eye(2))

    assert decomposition.direction_status == "degenerate"
    assert decomposition.principal_directions is None
    assert decomposition.principal_eigengap == pytest.approx(0.0)
    assert decomposition.principal_eigenspace_projector == pytest.approx(
        np.eye(2)
    )


def test_near_degenerate_and_resolved_eigengaps_are_distinguished() -> None:
    near = compute_strain_decomposition(
        np.diag([0.1, 0.10005]),
        eigengap_atol=1.0e-12,
        eigengap_rtol=1.0e-3,
    )
    resolved = compute_strain_decomposition(
        np.diag([0.1, 0.1002]),
        eigengap_atol=1.0e-12,
        eigengap_rtol=1.0e-3,
    )

    assert near.direction_status == "near_degenerate"
    assert near.principal_directions is None
    assert near.principal_eigengap <= near.principal_eigengap_threshold
    assert resolved.direction_status == "defined"
    assert resolved.principal_directions is not None
    assert resolved.principal_eigengap > resolved.principal_eigengap_threshold


def test_resolved_eigenvector_signs_are_canonical_lines() -> None:
    theta = np.deg2rad(37.0)
    rotation = np.array(
        [
            [np.cos(theta), -np.sin(theta)],
            [np.sin(theta), np.cos(theta)],
        ]
    )
    strain = rotation @ np.diag([-0.02, 0.03]) @ rotation.T
    decomposition = compute_strain_decomposition(strain)

    assert decomposition.direction_status == "defined"
    assert decomposition.principal_directions is not None
    for column in decomposition.principal_directions.T:
        first_nonzero = next(value for value in column if abs(value) > 1.0e-14)
        assert first_nonzero > 0.0


def test_rotated_slab_frame_is_mapped_before_conventional_coordinates() -> None:
    directions_slab = np.eye(2)
    conventional_basis = np.eye(3)

    for theta in (30.0, 45.0, 90.0):
        slab_to_conventional = _rotation_z(theta)
        directions = analyze_principal_directions_in_conventional_cell(
            directions_slab,
            conventional_basis,
            slab_to_conventional,
        ).directions_conventional
        expected_first = slab_to_conventional[:, 0]
        expected_first /= np.linalg.norm(expected_first)
        actual_first = directions[:, 0]
        actual_first /= np.linalg.norm(actual_first)
        assert actual_first == pytest.approx(expected_first, abs=1.0e-12)


def test_c_axis_orthogonalization_shear_is_inverted_in_frame_map() -> None:
    rotation = _rotation_z(27.0)
    shear = np.array(
        [[1.0, 0.0, -0.25], [0.0, 1.0, 0.4], [0.0, 0.0, 1.0]]
    )
    payload = {
        "version": 1,
        "hkl": [1, 0, 0],
        "U": rotation,
        "M_conv_to_slab_cart": shear @ rotation,
        "M_slab_to_conv_cart": rotation.T @ np.linalg.inv(shear),
        "construction_controls": current_construction_controls(),
    }

    recovered = slab_to_conventional_cartesian_map_from_payload(payload)
    expected = rotation.T @ np.linalg.inv(shear)
    assert recovered == pytest.approx(expected, abs=1.0e-12)


def test_explicit_cartesian_maps_are_validated_as_inverses() -> None:
    forward = _rotation_z(18.0)
    payload = {
        "version": 1,
        "hkl": [1, 1, 0],
        "U": forward,
        "M_conv_to_slab_cart": forward,
        "M_slab_to_conv_cart": forward.T,
        "construction_controls": current_construction_controls(),
    }
    recovered = slab_to_conventional_cartesian_map_from_payload(payload)
    assert recovered == pytest.approx(forward.T, abs=1.0e-12)

    payload["M_slab_to_conv_cart"] = np.eye(3)
    with pytest.raises(ValueError, match="not inverses"):
        slab_to_conventional_cartesian_map_from_payload(payload)


def test_historical_transform_wrapper_is_rejected() -> None:
    with pytest.raises(ValueError, match="Historical oriented-slab transform keys"):
        slab_to_conventional_cartesian_map_from_payload(
            {"transforms": {"U": np.eye(3)}}
        )


def test_current_payload_requires_explicit_cartesian_maps() -> None:
    with pytest.raises(ValueError, match="M_slab_to_conv_cart"):
        slab_to_conventional_cartesian_map_from_payload(
            {
                "version": 1,
                "hkl": [1, 0, 0],
                "U": np.eye(3),
                "construction_controls": current_construction_controls(),
            }
        )


def test_direction_sign_flip_has_identical_conventional_result() -> None:
    directions = _rotation_z(22.0)[:2, :2]
    conventional_basis = np.eye(3)
    mapping = _rotation_z(41.0)

    positive = analyze_principal_directions_in_conventional_cell(
        directions,
        conventional_basis,
        mapping,
    )
    negative = analyze_principal_directions_in_conventional_cell(
        -directions,
        conventional_basis,
        mapping,
    )

    assert negative.directions_conventional == pytest.approx(
        positive.directions_conventional,
        abs=1.0e-12,
    )
    assert [item.integer_indices for item in negative.approximations] == [
        item.integer_indices for item in positive.approximations
    ]


def test_low_index_label_is_withheld_when_angular_fit_is_poor() -> None:
    theta = np.deg2rad(20.0)
    directions = np.array(
        [
            [np.cos(theta), -np.sin(theta)],
            [np.sin(theta), np.cos(theta)],
        ]
    )
    result = analyze_principal_directions_in_conventional_cell(
        directions,
        np.eye(3),
        np.eye(3),
        max_index=1,
        max_angular_error_deg=0.1,
    )

    assert all(item.integer_indices is None for item in result.approximations)
    assert all(item.formatted is None for item in result.approximations)
    assert all(item.angular_error_deg > 0.1 for item in result.approximations)


def test_45_degree_direction_receives_verified_110_label() -> None:
    result = analyze_principal_directions_in_conventional_cell(
        np.eye(2),
        np.eye(3),
        _rotation_z(45.0),
        max_index=2,
        max_angular_error_deg=1.0e-8,
    )

    first = result.approximations[0]
    assert first.integer_indices == (1, 1, 0)
    assert first.formatted == "[1 1 0]"
    assert first.angular_error_deg == pytest.approx(0.0, abs=1.0e-8)
