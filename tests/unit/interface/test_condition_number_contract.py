"""Dependency-light tests for the surface matching conditioning gate."""

from __future__ import annotations

import numpy as np
import pytest

from calm.interface.matching.conditioning import (
    DEFAULT_SUPERCELL_CONDITION_LIMIT,
    evaluate_condition_admissibility_2d,
    scale_normalized_condition_number_2d,
)
from calm.public.inputs.settings import SearchSettings


def test_condition_number_is_spectral_and_scale_invariant() -> None:
    basis = np.diag([2.0, 1.0])
    assert scale_normalized_condition_number_2d(basis) == pytest.approx(2.0)
    for scale in (1e-150, 1e-12, 1.0, 1e12, 1e150):
        assert scale_normalized_condition_number_2d(scale * basis) == pytest.approx(
            2.0
        )


def test_condition_threshold_is_inclusive() -> None:
    basis = np.diag([2.0, 1.0])
    condition, admitted = evaluate_condition_admissibility_2d(
        basis,
        cond_max=2.0,
    )
    assert condition == pytest.approx(2.0)
    assert admitted is True

    _, admitted_below = evaluate_condition_admissibility_2d(
        basis,
        cond_max=np.nextafter(2.0, 0.0),
    )
    assert admitted_below is False


def test_singular_and_nonfinite_bases_are_rejected() -> None:
    for basis in (
        np.array([[1.0, 0.0], [0.0, 0.0]]),
        np.array([[np.nan, 0.0], [0.0, 1.0]]),
        np.zeros((2, 2)),
    ):
        condition, admitted = evaluate_condition_admissibility_2d(basis)
        assert np.isinf(condition)
        assert admitted is False


def test_condition_limit_default_and_validation() -> None:
    assert DEFAULT_SUPERCELL_CONDITION_LIMIT == 1e6
    with pytest.raises(ValueError, match="cond_max"):
        evaluate_condition_admissibility_2d(np.eye(2), cond_max=0.0)
    with pytest.raises(ValueError, match="cond_max"):
        evaluate_condition_admissibility_2d(np.eye(2), cond_max=np.inf)



def test_malformed_basis_is_rejected_without_conversion_failure() -> None:
    condition, admitted = evaluate_condition_admissibility_2d(
        [["not", "a"], ["basis", "matrix"]],
    )
    assert np.isinf(condition)
    assert admitted is False


@pytest.mark.parametrize("value", [True, "100", None])
def test_condition_limit_rejects_nonreal_controls(value: object) -> None:
    with pytest.raises(TypeError, match="cond_max"):
        evaluate_condition_admissibility_2d(
            np.eye(2),
            cond_max=value,  # type: ignore[arg-type]
        )



def test_public_search_settings_reject_boolean_condition_limit() -> None:
    with pytest.raises(TypeError, match="SearchSettings.cond_max"):
        SearchSettings(cond_max=True).validate()
