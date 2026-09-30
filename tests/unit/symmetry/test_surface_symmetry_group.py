from __future__ import annotations

import numpy as np
import pytest

from calm.symmetry.surface_group import (
    SURFACE_SYMMETRY_POLICY,
    SURFACE_SYMMETRY_POLICY_VERSION,
    metric_preservation_residual,
    surface_metric_from_cell_rows,
    validate_surface_symmetry_group_2d,
)


def test_valid_group_is_deduplicated_and_sorted() -> None:
    identity = np.eye(2, dtype=int)
    inversion = -identity

    operations = validate_surface_symmetry_group_2d(
        [inversion, identity, inversion.copy()],
        metric=np.array([[2.0, 0.7], [0.7, 3.0]]),
    )

    assert len(operations) == 2
    assert [tuple(operation.ravel()) for operation in operations] == sorted(
        tuple(operation.ravel()) for operation in operations
    )


def test_group_must_explicitly_contain_identity() -> None:
    with pytest.raises(ValueError, match="explicitly contain identity"):
        validate_surface_symmetry_group_2d([-np.eye(2, dtype=int)])


def test_group_must_contain_inverses() -> None:
    shear = np.array([[1, 1], [0, 1]], dtype=int)
    with pytest.raises(ValueError, match="missing the inverse"):
        validate_surface_symmetry_group_2d([np.eye(2, dtype=int), shear])


def test_group_must_be_closed() -> None:
    identity = np.eye(2, dtype=int)
    rotation = np.array([[0, -1], [1, 0]], dtype=int)
    inverse = np.array([[0, 1], [-1, 0]], dtype=int)
    with pytest.raises(ValueError, match="not closed"):
        validate_surface_symmetry_group_2d([identity, rotation, inverse])


def test_group_must_be_exact_integer_and_unimodular() -> None:
    identity = np.eye(2, dtype=int)
    with pytest.raises(TypeError, match="exact integer"):
        validate_surface_symmetry_group_2d(
            [identity, np.array([[1.0, 0.0], [0.0, -1.0]])]
        )
    with pytest.raises(ValueError, match="unimodular"):
        validate_surface_symmetry_group_2d(
            [identity, np.array([[2, 0], [0, 1]], dtype=int)]
        )


def test_group_must_preserve_selected_surface_metric() -> None:
    identity = np.eye(2, dtype=int)
    swap = np.array([[0, 1], [1, 0]], dtype=int)
    metric = np.diag([1.0, 4.0])

    with pytest.raises(ValueError, match="does not preserve"):
        validate_surface_symmetry_group_2d(
            [identity, swap],
            metric=metric,
            metric_tolerance=1e-12,
        )


def test_metric_residual_is_scale_free() -> None:
    reflection = np.diag([-1, 1])
    metric = np.diag([2.0, 5.0])
    assert metric_preservation_residual(reflection, metric) == pytest.approx(0.0)
    assert metric_preservation_residual(reflection, 1e12 * metric) == pytest.approx(
        0.0
    )


def test_surface_metric_uses_first_two_ase_style_cell_rows() -> None:
    cell = np.array(
        [[2.0, 0.0, 0.0], [0.5, 3.0, 0.0], [0.0, 0.0, 8.0]]
    )
    np.testing.assert_allclose(
        surface_metric_from_cell_rows(cell),
        np.array([[4.0, 1.0], [1.0, 9.25]]),
    )


def test_policy_constants_are_versioned() -> None:
    assert SURFACE_SYMMETRY_POLICY == "validated_surface_pointgroup"
    assert SURFACE_SYMMETRY_POLICY_VERSION == 1


def test_resolution_rejects_operation_count_mismatch_and_freezes_arrays() -> None:
    from calm.symmetry.surface_group import (
        SurfaceSymmetryProvenance,
        SurfaceSymmetryResolution,
    )

    provenance = SurfaceSymmetryProvenance(
        mode="identity_only",
        status="identity_only",
        operation_count=1,
        symprec=1e-5,
        angle_tolerance=1e-8,
        metric_tolerance=1e-5,
        max_metric_residual=0.0,
        backend=None,
        backend_version=None,
    )
    resolution = SurfaceSymmetryResolution(
        operations=(np.eye(2, dtype=int),),
        provenance=provenance,
    )
    assert resolution.operations[0].flags.writeable is False

    discovered = SurfaceSymmetryProvenance(
        mode="discover",
        status="discovered",
        operation_count=2,
        symprec=1e-5,
        angle_tolerance=1e-8,
        metric_tolerance=1e-5,
        max_metric_residual=0.0,
        backend="spglib",
        backend_version="test",
    )
    with pytest.raises(ValueError, match="operation count"):
        SurfaceSymmetryResolution(
            operations=(np.eye(2, dtype=int),),
            provenance=discovered,
        )


def test_group_rejects_boolean_and_out_of_range_integer_entries() -> None:
    identity = np.eye(2, dtype=int)
    with pytest.raises(TypeError, match="exact integer"):
        validate_surface_symmetry_group_2d(
            [identity, [[True, 0], [0, 1]]]
        )
    with pytest.raises(ValueError, match="supported range"):
        validate_surface_symmetry_group_2d(
            [identity, [[2**100, 0], [0, 1]]]
        )


def test_successful_provenance_requires_residual_within_tolerance() -> None:
    from calm.symmetry.surface_group import SurfaceSymmetryProvenance

    with pytest.raises(ValueError, match="exceeds metric_tolerance"):
        SurfaceSymmetryProvenance(
            mode="discover",
            status="discovered",
            operation_count=1,
            symprec=1e-5,
            angle_tolerance=1e-8,
            metric_tolerance=1e-6,
            max_metric_residual=2e-6,
            backend="spglib",
            backend_version="test",
        )


def test_failed_provenance_cannot_claim_identity_only_mode() -> None:
    from calm.symmetry.surface_group import SurfaceSymmetryProvenance

    with pytest.raises(ValueError, match="discover mode"):
        SurfaceSymmetryProvenance(
            mode="identity_only",
            status="failed",
            operation_count=0,
            symprec=1e-5,
            angle_tolerance=1e-8,
            metric_tolerance=1e-5,
            max_metric_residual=None,
            backend="spglib",
            backend_version=None,
            failure_type="RuntimeError",
            failure_message="failed",
        )


def test_provenance_rejects_coercible_residual_and_backend_metadata() -> None:
    from calm.symmetry.surface_group import SurfaceSymmetryProvenance

    common = {
        "mode": "discover",
        "status": "discovered",
        "operation_count": 1,
        "symprec": 1e-5,
        "angle_tolerance": 1e-8,
        "metric_tolerance": 2.0,
        "backend_version": "test",
    }
    with pytest.raises(TypeError, match="max_metric_residual"):
        SurfaceSymmetryProvenance(
            **common,
            max_metric_residual=True,
            backend="spglib",
        )
    with pytest.raises(TypeError, match="backend"):
        SurfaceSymmetryProvenance(
            **common,
            max_metric_residual=0.0,
            backend=3,
        )
