"""Tests for complete coupled-v2 basis-correspondence enumeration."""

from __future__ import annotations

from itertools import product

import numpy as np
import pytest

from calm.interface.matching._correspondence import (
    DEFAULT_CORRESPONDENCE_ENTRY_LIMIT,
    CorrespondenceEnumerationLimitError,
    enumerate_basis_correspondences_2d,
)
from calm.interface.matching._types import BasisCorrespondence2D


def _key(matrix: np.ndarray) -> tuple[int, int, int, int]:
    return tuple(int(value) for value in matrix.ravel())


def _principal_strains(
    metric_a: np.ndarray,
    metric_b: np.ndarray,
    transform: np.ndarray,
) -> np.ndarray:
    eigenvalues_a, vectors_a = np.linalg.eigh(metric_a)
    inverse_sqrt_a = (vectors_a * (1.0 / np.sqrt(eigenvalues_a))) @ vectors_a.T
    relative = inverse_sqrt_a @ (transform.T @ metric_b @ transform) @ inverse_sqrt_a
    eigenvalues = np.linalg.eigvalsh(0.5 * (relative + relative.T))
    return 0.5 * np.log(eigenvalues)


def _brute_force(
    metric_a: np.ndarray,
    metric_b: np.ndarray,
    *,
    eps: float,
    orientation: str,
    entry_bound: int,
    tolerance: float = 1e-12,
) -> tuple[tuple[int, int, int, int], ...]:
    accepted: list[tuple[int, int, int, int]] = []
    values = range(-entry_bound, entry_bound + 1)
    for a, b, c, d in product(values, repeat=4):
        determinant = a * d - b * c
        if orientation == "proper":
            if determinant != 1:
                continue
        elif abs(determinant) != 1:
            continue
        transform = np.array([[a, b], [c, d]], dtype=int)
        strains = _principal_strains(metric_a, metric_b, transform)
        if np.all(np.isfinite(strains)) and float(np.max(np.abs(strains))) <= eps + tolerance:
            accepted.append((a, b, c, d))
    return tuple(sorted(accepted))


def test_equal_square_zero_strain_recovers_proper_and_full_groups() -> None:
    proper = enumerate_basis_correspondences_2d(
        np.eye(2),
        np.eye(2),
        eps_principal_max=0.0,
        orientation="proper",
        metric_tolerance=0.0,
        entry_limit=1,
    )
    all_orientations = enumerate_basis_correspondences_2d(
        np.eye(2),
        np.eye(2),
        eps_principal_max=0.0,
        orientation="all",
        metric_tolerance=0.0,
        entry_limit=1,
    )

    assert len(proper) == 4
    assert len(all_orientations) == 8
    assert np.eye(2, dtype=int).ravel().tolist() in [item.U_B.ravel().tolist() for item in proper]
    assert all(round(np.linalg.det(item.U_B)) == 1 for item in proper)
    assert {round(np.linalg.det(item.U_B)) for item in all_orientations} == {-1, 1}
    assert all(item.principal_strains == pytest.approx([0.0, 0.0], abs=1e-14) for item in all_orientations)


def test_sigma5_pair_recovers_identity_correspondence() -> None:
    cell_c4 = np.array([[2.0, -1.0], [1.0, 2.0]])
    cell_c5 = np.array([[2.0, 1.0], [-1.0, 2.0]])
    correspondences = enumerate_basis_correspondences_2d(
        cell_c4.T @ cell_c4,
        cell_c5.T @ cell_c5,
        eps_principal_max=0.0,
        orientation="proper",
        metric_tolerance=1e-12,
        entry_limit=2,
    )

    assert len(correspondences) == 4
    assert (1, 0, 0, 1) in {_key(item.U_B) for item in correspondences}


@pytest.mark.parametrize("orientation", ["proper", "all"])
def test_random_small_metrics_match_complete_brute_force(orientation: str) -> None:
    rng = np.random.default_rng(20260725)
    gauges = (
        np.array([[1, 0], [0, 1]], dtype=int),
        np.array([[1, 1], [0, 1]], dtype=int),
        np.array([[0, -1], [1, 0]], dtype=int),
        np.array([[1, 0], [1, 1]], dtype=int),
    )

    for case_index in range(16):
        gauge = gauges[case_index % len(gauges)]
        raw = rng.uniform(-0.6, 0.6, size=(2, 2))
        metric_b = raw.T @ raw + 0.75 * np.eye(2)
        target = gauge.T @ metric_b @ gauge
        stretch = float(np.exp(rng.uniform(-0.12, 0.12)))
        metric_a = stretch * target
        eps = 0.22

        expected = _brute_force(
            metric_a,
            metric_b,
            eps=eps,
            orientation=orientation,
            entry_bound=4,
        )
        actual = enumerate_basis_correspondences_2d(
            metric_a,
            metric_b,
            eps_principal_max=eps,
            orientation=orientation,
            metric_tolerance=1e-12,
            entry_limit=4,
        )

        assert tuple(_key(item.U_B) for item in actual) == expected
        assert _key(gauge) in expected
        for item in actual:
            np.testing.assert_allclose(
                item.transformed_gram_B,
                item.U_B.T @ metric_b @ item.U_B,
                rtol=1e-13,
                atol=1e-13,
            )
            np.testing.assert_allclose(
                item.principal_strains,
                _principal_strains(metric_a, metric_b, item.U_B),
                rtol=1e-11,
                atol=1e-12,
            )


def test_enumeration_is_deterministic_and_returns_fresh_records() -> None:
    metric_a = np.array([[2.0, 0.25], [0.25, 1.5]])
    metric_b = np.array([[1.8, -0.1], [-0.1, 1.4]])
    first = enumerate_basis_correspondences_2d(
        metric_a,
        metric_b,
        eps_principal_max=0.35,
        orientation="all",
        metric_tolerance=1e-12,
        entry_limit=5,
    )
    second = enumerate_basis_correspondences_2d(
        metric_a,
        metric_b,
        eps_principal_max=0.35,
        orientation="all",
        metric_tolerance=1e-12,
        entry_limit=5,
    )

    assert tuple(_key(item.U_B) for item in first) == tuple(_key(item.U_B) for item in second)
    assert all(left is not right for left, right in zip(first, second, strict=True))
    if first:
        first[0].U_B[0, 0] = 999
        assert second[0].U_B[0, 0] != 999


@pytest.mark.parametrize("common_scale", [1.0e-300, 1.0e300])
def test_common_metric_scaling_does_not_change_correspondences(
    common_scale: float,
) -> None:
    metric_a = np.array([[2.0, 0.3], [0.3, 1.2]])
    metric_b = np.array([[1.7, -0.2], [-0.2, 1.1]])

    reference = enumerate_basis_correspondences_2d(
        metric_a,
        metric_b,
        eps_principal_max=0.4,
        orientation="proper",
        metric_tolerance=1e-12,
        entry_limit=6,
    )
    scaled = enumerate_basis_correspondences_2d(
        common_scale * metric_a,
        common_scale * metric_b,
        eps_principal_max=0.4,
        orientation="proper",
        metric_tolerance=1e-12,
        entry_limit=6,
    )

    assert tuple(_key(item.U_B) for item in scaled) == tuple(
        _key(item.U_B) for item in reference
    )
    for item_scaled, item_reference in zip(scaled, reference, strict=True):
        np.testing.assert_allclose(
            item_scaled.principal_strains,
            item_reference.principal_strains,
            rtol=1e-12,
            atol=1e-12,
        )


def test_automatic_limit_covers_large_complete_correspondence_bounds() -> None:
    required_shear = np.array([[1, 140], [0, 1]], dtype=int)
    metric_a = required_shear.T @ required_shear

    assert DEFAULT_CORRESPONDENCE_ENTRY_LIMIT is None
    complete = enumerate_basis_correspondences_2d(
        metric_a,
        np.eye(2),
        eps_principal_max=0.0,
        orientation="proper",
        metric_tolerance=1e-8,
        entry_limit=DEFAULT_CORRESPONDENCE_ENTRY_LIMIT,
    )

    assert _key(required_shear) in {_key(item.U_B) for item in complete}

    with pytest.raises(CorrespondenceEnumerationLimitError) as caught:
        enumerate_basis_correspondences_2d(
            metric_a,
            np.eye(2),
            eps_principal_max=0.0,
            orientation="proper",
            metric_tolerance=1e-8,
            entry_limit=128,
        )
    assert caught.value.required_entry_bound == 140


def test_proven_bound_exceeding_entry_limit_raises_without_truncation() -> None:
    required_shear = np.array([[1, 4], [0, 1]], dtype=int)
    metric_a = required_shear.T @ required_shear

    with pytest.raises(CorrespondenceEnumerationLimitError) as caught:
        enumerate_basis_correspondences_2d(
            metric_a,
            np.eye(2),
            eps_principal_max=0.0,
            orientation="proper",
            metric_tolerance=0.0,
            entry_limit=3,
        )

    assert caught.value.required_entry_bound == 4
    assert caught.value.entry_limit == 3
    assert "exceeds entry_limit=3" in str(caught.value)

    complete = enumerate_basis_correspondences_2d(
        metric_a,
        np.eye(2),
        eps_principal_max=0.0,
        orientation="proper",
        metric_tolerance=0.0,
        entry_limit=4,
    )
    assert _key(required_shear) in {_key(item.U_B) for item in complete}


def test_basis_correspondence_validates_exact_unimodular_state() -> None:
    correspondence = BasisCorrespondence2D(
        U_B=np.eye(2, dtype=int),
        principal_strains=np.zeros(2),
        transformed_gram_B=np.eye(2),
    )
    assert _key(correspondence.U_B) == (1, 0, 0, 1)

    with pytest.raises(ValueError, match="unimodular"):
        BasisCorrespondence2D(
            U_B=np.diag([2, 1]),
            principal_strains=np.zeros(2),
            transformed_gram_B=np.eye(2),
        )
    with pytest.raises(TypeError, match="exact integers"):
        BasisCorrespondence2D(
            U_B=np.eye(2),
            principal_strains=np.zeros(2),
            transformed_gram_B=np.eye(2),
        )


@pytest.mark.parametrize(
    ("kwargs", "error", "match"),
    [
        ({"orientation": "reflected"}, ValueError, "orientation"),
        ({"entry_limit": 0}, ValueError, "entry_limit"),
        ({"eps_principal_max": -1.0}, ValueError, "eps_principal_max"),
        ({"metric_tolerance": -1.0}, ValueError, "metric_tolerance"),
    ],
)
def test_invalid_controls_fail_explicitly(
    kwargs: dict[str, object],
    error: type[Exception],
    match: str,
) -> None:
    controls: dict[str, object] = {
        "eps_principal_max": 0.1,
        "orientation": "proper",
        "metric_tolerance": 1e-12,
        "entry_limit": 4,
    }
    controls.update(kwargs)
    with pytest.raises(error, match=match):
        enumerate_basis_correspondences_2d(
            np.eye(2),
            np.eye(2),
            **controls,  # type: ignore[arg-type]
        )


def test_invalid_metrics_fail_explicitly() -> None:
    controls = {
        "eps_principal_max": 0.1,
        "orientation": "proper",
        "metric_tolerance": 1e-12,
        "entry_limit": 4,
    }
    with pytest.raises(ValueError, match="shape"):
        enumerate_basis_correspondences_2d(np.eye(3), np.eye(2), **controls)
    with pytest.raises(ValueError, match="symmetric"):
        enumerate_basis_correspondences_2d(
            np.array([[1.0, 0.5], [0.0, 1.0]]),
            np.eye(2),
            **controls,
        )
    with pytest.raises(ValueError, match="not SPD"):
        enumerate_basis_correspondences_2d(
            np.diag([1.0, -1.0]),
            np.eye(2),
            **controls,
        )


def test_correspondence_enumeration_reports_exact_search_work() -> None:
    stats: dict[str, int] = {}

    correspondences = enumerate_basis_correspondences_2d(
        np.eye(2),
        np.eye(2),
        eps_principal_max=0.0,
        orientation="proper",
        metric_tolerance=0.0,
        stats=stats,
    )

    assert len(correspondences) == 4
    assert stats == {
        "required_entry_bound": 1,
        "first_column_candidates": 4,
        "second_column_candidates": 4,
        "column_pairs_tested": 16,
        "unimodular_states_tested": 4,
        "strain_admissible_states": 4,
        "determinant_chunks": 0,
    }
