"""Acceleration contracts for complete basis-correspondence enumeration."""

from __future__ import annotations

import numpy as np

from calm.interface.matching import _correspondence as correspondence


def _exact_records(values: tuple[object, ...]) -> tuple[tuple[object, ...], ...]:
    return tuple(
        (
            tuple(int(value) for value in item.U_B.ravel()),
            tuple(float(value).hex() for value in item.principal_strains),
            tuple(float(value).hex() for value in item.transformed_gram_B.ravel()),
        )
        for item in values
    )


def test_vectorized_determinant_screen_matches_scalar_path_exactly(
    monkeypatch,
) -> None:
    controls = {
        "eps_principal_max": 2.0,
        "orientation": "proper",
        "metric_tolerance": 1e-12,
        "entry_limit": None,
    }

    correspondence._enumerate_cached.cache_clear()
    vector_stats: dict[str, int] = {}
    vectorized = correspondence.enumerate_basis_correspondences_2d(
        np.eye(2),
        np.eye(2),
        stats=vector_stats,
        **controls,
    )
    assert vector_stats["determinant_chunks"] > 0

    monkeypatch.setattr(
        correspondence,
        "_VECTOR_DETERMINANT_PAIR_THRESHOLD",
        10**12,
    )
    correspondence._enumerate_cached.cache_clear()
    scalar_stats: dict[str, int] = {}
    scalar = correspondence.enumerate_basis_correspondences_2d(
        np.eye(2),
        np.eye(2),
        stats=scalar_stats,
        **controls,
    )

    assert scalar_stats["determinant_chunks"] == 0
    assert vector_stats["column_pairs_tested"] == 30_976
    assert scalar_stats["column_pairs_tested"] == 30_976
    assert _exact_records(vectorized) == _exact_records(scalar)


def test_large_frozen_correspondence_oracles_use_bounded_chunks() -> None:
    workloads = (
        (
            np.eye(2),
            np.eye(2),
            3.0,
            "proper",
            1_597_696,
            2_484,
        ),
        (
            np.array([[4.0, 1.2], [1.2, 1.5]]),
            np.array([[1.5, 0.4], [0.4, 3.0]]),
            2.7,
            "all",
            667_000,
            2_598,
        ),
    )

    for metric_a, metric_b, eps, orientation, pair_count, accepted in workloads:
        correspondence._enumerate_cached.cache_clear()
        stats: dict[str, int] = {}
        results = correspondence.enumerate_basis_correspondences_2d(
            metric_a,
            metric_b,
            eps_principal_max=eps,
            orientation=orientation,
            metric_tolerance=1e-12,
            entry_limit=None,
            stats=stats,
        )
        assert stats["column_pairs_tested"] == pair_count
        assert stats["strain_admissible_states"] == accepted
        assert len(results) == accepted
        assert stats["determinant_chunks"] > 0
        assert stats["determinant_chunks"] < stats["first_column_candidates"]


def test_determinant_vectorization_falls_back_before_int64_overflow() -> None:
    safe = correspondence._INT64_DETERMINANT_SAFE_COMPONENT
    first = ((safe + 1, 0),)
    second = ((0, safe + 1),)

    assert not correspondence._use_vectorized_determinants(
        first * correspondence._VECTOR_DETERMINANT_PAIR_THRESHOLD,
        second,
    )


def test_prepared_enumeration_matches_public_records_and_reuses_validation() -> None:
    metric_a = np.array([[2.0, 0.25], [0.25, 1.5]])
    metric_b = np.array([[1.8, -0.1], [-0.1, 1.4]])
    prepared_a = correspondence._prepare_correspondence_metric_2d(
        "G_A",
        metric_a,
        tolerance=1e-12,
    )
    prepared_b = correspondence._prepare_correspondence_metric_2d(
        "G_B",
        metric_b,
        tolerance=1e-12,
    )
    correspondence._enumerate_cached.cache_clear()
    prepared = correspondence._enumerate_basis_correspondence_records_prepared_2d(
        prepared_a,
        prepared_b,
        eps_principal_max=0.35,
        orientation="all",
        metric_tolerance=1e-12,
        entry_limit=None,
    )
    public = correspondence.enumerate_basis_correspondences_2d(
        metric_a,
        metric_b,
        eps_principal_max=0.35,
        orientation="all",
        metric_tolerance=1e-12,
        entry_limit=None,
    )

    assert tuple(record[0] for record in prepared.records) == tuple(
        tuple(int(value) for value in item.U_B.ravel())
        for item in public
    )
    assert tuple(record[1] for record in prepared.records) == tuple(
        tuple(float(value) for value in item.principal_strains)
        for item in public
    )
