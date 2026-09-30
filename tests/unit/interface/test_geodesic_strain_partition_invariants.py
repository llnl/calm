"""Dependency-light invariants for geodesic strain partitioning."""

from __future__ import annotations

from importlib.machinery import ModuleSpec

import importlib.util
import sys
import types

import numpy as np
import pytest


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except ValueError:
        return name in sys.modules


def _module_stub(name: str) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__spec__ = ModuleSpec(name, loader=None)
    return module


_INSERTED_STUBS: list[str] = []
if not _module_available("spglib"):
    sys.modules["spglib"] = _module_stub("spglib")
    _INSERTED_STUBS.append("spglib")
if not _module_available("ase"):
    ase_stub = _module_stub("ase")

    class Atoms:  # pragma: no cover - import stub only
        pass

    ase_stub.Atoms = Atoms
    sys.modules["ase"] = ase_stub
    _INSERTED_STUBS.append("ase")

try:
    from calm.interface.refinement.strain import compute_strain_2d  # noqa: E402
    from calm.interface.refinement.partition import (  # noqa: E402
        scan_geodesic_strain_partitions,
        strain_partition_inplane,
    )
    from reference.spd_reference import airm_distance_reference  # noqa: E402
finally:
    for _module_name in _INSERTED_STUBS:
        sys.modules.pop(_module_name, None)


def _cell(basis: np.ndarray) -> np.ndarray:
    out = np.eye(3, dtype=float)
    out[:2, :2] = np.asarray(basis, dtype=float)
    return out


def _bases() -> tuple[np.ndarray, np.ndarray]:
    basis_a = np.array([[1.10, 0.30], [0.00, 0.90]])
    basis_b = np.array([[0.80, -0.10], [0.20, 1.30]])
    return basis_a, basis_b


def test_partition_is_covariant_under_common_length_scaling() -> None:
    basis_a, basis_b = _bases()
    reference = compute_strain_2d(_cell(basis_a), _cell(basis_b), alpha=0.37)

    for scale in (1e-150, 1e-75, 1.0, 1e75, 1e150):
        state = compute_strain_2d(
            _cell(scale * basis_a),
            _cell(scale * basis_b),
            alpha=0.37,
        )
        assert np.allclose(state.F_tot, reference.F_tot, atol=2e-12, rtol=2e-12)
        assert np.allclose(state.F_A, reference.F_A, atol=2e-12, rtol=2e-12)
        assert np.allclose(state.F_B, reference.F_B, atol=2e-12, rtol=2e-12)
        assert state.E_A_rms == pytest.approx(reference.E_A_rms, abs=2e-12)
        assert state.E_B_rms == pytest.approx(reference.E_B_rms, abs=2e-12)

        partition = strain_partition_inplane(
            scale * basis_a,
            scale * basis_b,
            alpha=0.37,
        )
        reference_partition = strain_partition_inplane(
            basis_a,
            basis_b,
            alpha=0.37,
        )
        assert np.allclose(
            partition.X / scale,
            reference_partition.X,
            atol=2e-12,
            rtol=2e-12,
        )
        assert np.allclose(partition.F_A, reference_partition.F_A, atol=2e-12)
        assert np.allclose(partition.F_B, reference_partition.F_B, atol=2e-12)


def test_hencky_rms_advances_at_constant_affine_invariant_speed() -> None:
    basis_a, basis_b = _bases()
    metric_a = basis_a.T @ basis_a
    metric_b = basis_b.T @ basis_b
    distance = airm_distance_reference(metric_a, metric_b)

    for alpha in (0.0, 0.2, 0.5, 0.8, 1.0):
        state = compute_strain_2d(_cell(basis_a), _cell(basis_b), alpha=alpha)
        partition = strain_partition_inplane(basis_a, basis_b, alpha=alpha)
        expected_a = alpha * distance / (2.0 * np.sqrt(2.0))
        expected_b = (1.0 - alpha) * distance / (2.0 * np.sqrt(2.0))
        assert state.E_A_rms == pytest.approx(expected_a, abs=2e-12)
        assert state.E_B_rms == pytest.approx(expected_b, abs=2e-12)
        assert partition.side_a_principal_log_strains == pytest.approx(
            np.linalg.eigvalsh(state.E_A[:2, :2]),
            abs=2e-12,
        )
        assert partition.side_b_principal_log_strains == pytest.approx(
            np.linalg.eigvalsh(state.E_B[:2, :2]),
            abs=2e-12,
        )
        assert partition.side_a_max_abs_principal_log_strain == pytest.approx(
            np.max(np.abs(np.linalg.eigvalsh(state.E_A[:2, :2]))),
            abs=2e-12,
        )
        assert partition.side_b_max_abs_principal_log_strain == pytest.approx(
            np.max(np.abs(np.linalg.eigvalsh(state.E_B[:2, :2]))),
            abs=2e-12,
        )
        assert partition.side_a_airm_distance == pytest.approx(
            alpha * distance,
            abs=2e-12,
        )
        assert partition.side_b_airm_distance == pytest.approx(
            (1.0 - alpha) * distance,
            abs=2e-12,
        )
        assert (
            partition.side_a_airm_distance + partition.side_b_airm_distance
        ) == pytest.approx(distance, abs=2e-12)
        assert np.linalg.det(state.R_A[:2, :2]) == pytest.approx(1.0, abs=2e-12)
        assert np.linalg.det(state.R_B[:2, :2]) == pytest.approx(1.0, abs=2e-12)


def test_endpoint_zero_stretch_can_include_common_gauge_rotation() -> None:
    angle = np.deg2rad(31.0)
    rotation = np.array(
        [[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]]
    )
    basis_a = rotation @ np.array([[1.2, 0.25], [0.0, 0.8]])
    basis_b = np.array([[0.9, -0.15], [0.1, 1.1]])

    state = compute_strain_2d(_cell(basis_a), _cell(basis_b), alpha=0.0)

    assert state.E_A_rms == pytest.approx(0.0, abs=2e-12)
    assert np.allclose(state.U_A[:2, :2], np.eye(2), atol=2e-12)
    assert not np.allclose(state.F_A[:2, :2], np.eye(2), atol=1e-6)
    assert np.allclose(
        state.F_A[:2, :2] @ basis_a,
        state.F_B[:2, :2] @ basis_b,
        atol=2e-12,
    )


def test_endpoint_swap_reverses_alpha_and_side_roles() -> None:
    basis_a, basis_b = _bases()
    alpha = 0.31
    ab = strain_partition_inplane(basis_a, basis_b, alpha=alpha)
    ba = strain_partition_inplane(basis_b, basis_a, alpha=1.0 - alpha)

    assert np.allclose(ab.G_target, ba.G_target, atol=2e-12, rtol=2e-12)
    assert np.allclose(ab.X, ba.X, atol=2e-12, rtol=2e-12)
    assert np.allclose(ab.F_A, ba.F_B, atol=2e-12, rtol=2e-12)
    assert np.allclose(ab.F_B, ba.F_A, atol=2e-12, rtol=2e-12)


def test_partition_rejects_reflections_and_non_xy_surface_frames() -> None:
    basis_a, basis_b = _bases()
    reflected = basis_a.copy()
    reflected[:, 0] *= -1.0
    with pytest.raises(Exception, match="right-handed"):
        strain_partition_inplane(reflected, basis_b, alpha=0.5)

    tilted = _cell(basis_a)
    tilted[2, 0] = 1e-4
    with pytest.raises(ValueError, match="global xy plane"):
        compute_strain_2d(tilted, _cell(basis_b), alpha=0.5)


def test_common_right_basis_gauge_preserves_target_and_stretches() -> None:
    basis_a, basis_b = _bases()
    alpha = 0.42
    gauge = np.array([[1.0, 2.0], [0.0, 1.0]])

    reference = strain_partition_inplane(basis_a, basis_b, alpha=alpha)
    transformed = strain_partition_inplane(
        basis_a @ gauge,
        basis_b @ gauge,
        alpha=alpha,
    )

    assert np.allclose(
        transformed.G_target,
        gauge.T @ reference.G_target @ gauge,
        atol=2e-11,
        rtol=2e-11,
    )
    assert np.allclose(
        transformed.F_A.T @ transformed.F_A,
        reference.F_A.T @ reference.F_A,
        atol=2e-11,
        rtol=2e-11,
    )
    assert np.allclose(
        transformed.F_B.T @ transformed.F_B,
        reference.F_B.T @ reference.F_B,
        atol=2e-11,
        rtol=2e-11,
    )


def test_unrepresentable_physical_target_metric_is_rejected() -> None:
    basis_a, basis_b = _bases()
    with pytest.raises(ValueError, match="representation range"):
        strain_partition_inplane(
            1e-200 * basis_a,
            1e-200 * basis_b,
            alpha=0.5,
        )


def test_finite_scan_rejects_nonfinite_scores_and_keeps_first_tie() -> None:
    basis_a, basis_b = _bases()
    cell_a = _cell(basis_a)
    cell_b = _cell(basis_b)

    result = scan_geodesic_strain_partitions(
        cell_a,
        cell_b,
        alphas=[0.8, 0.2],
        score_fn=lambda _state: 1.0,
        objective_name="constant_test_objective",
    )
    assert result.best.alpha == 0.8
    assert result.metadata == {
        "alphas": [0.8, 0.2],
        "grid_source": "explicit",
        "objective_name": "constant_test_objective",
        "minimize": True,
        "selection_direction": "minimum",
        "tie_policy": "first_occurrence_in_alpha_order",
        "nonfinite_score_policy": "raise",
        "eps": 1.0e-14,
        "symprec": 1.0e-5,
        "trace_returned": False,
    }

    with pytest.raises(ValueError, match="finite scalar"):
        scan_geodesic_strain_partitions(
            cell_a,
            cell_b,
            alphas=[0.0, 0.5],
            score_fn=lambda state: np.nan if state.alpha == 0.5 else 0.0,
        )
