"""Dependency-light conditioning contract for bounded surface matching."""

from __future__ import annotations

from numbers import Real

import numpy as np

DEFAULT_SUPERCELL_CONDITION_LIMIT = 1e6


def scale_normalized_condition_number_2d(basis: np.ndarray) -> float:
    """Return the dimensionless spectral condition number of a 2D basis.

    CALM divides the basis by its largest absolute entry and returns
    ``sigma_max / sigma_min`` from the singular values. Uniform positive
    length scaling therefore leaves the result unchanged. Singular,
    malformed, or nonfinite inputs return ``inf`` and are rejected by the
    matching admissibility gate.
    """
    try:
        matrix = np.asarray(basis, dtype=float)
    except (TypeError, ValueError):
        return float("inf")
    if matrix.shape != (2, 2) or not np.all(np.isfinite(matrix)):
        return float("inf")
    scale = float(np.max(np.abs(matrix)))
    if not np.isfinite(scale) or scale <= 0.0:
        return float("inf")
    try:
        singular_values = np.linalg.svd(
            matrix / scale,
            compute_uv=False,
        )
    except np.linalg.LinAlgError:
        return float("inf")
    if (
        singular_values.shape != (2,)
        or not np.all(np.isfinite(singular_values))
        or float(singular_values[-1]) <= 0.0
    ):
        return float("inf")
    return float(singular_values[0] / singular_values[-1])


def evaluate_condition_admissibility_2d(
    basis: np.ndarray,
    *,
    cond_max: float = DEFAULT_SUPERCELL_CONDITION_LIMIT,
) -> tuple[float, bool]:
    """Return ``(kappa_2, admitted)`` for the declared matching gate.

    The threshold is inclusive: finite ``kappa_2 <= cond_max`` is admitted.
    Singular or nonfinite condition numbers are rejected.
    """
    if isinstance(cond_max, (bool, np.bool_)) or not isinstance(
        cond_max,
        (Real, np.floating, np.integer),
    ):
        raise TypeError("cond_max must be a real number")
    limit = float(cond_max)
    if not np.isfinite(limit) or limit <= 0.0:
        raise ValueError("cond_max must be finite and positive")
    condition_number = scale_normalized_condition_number_2d(basis)
    admitted = bool(np.isfinite(condition_number) and condition_number <= limit)
    return condition_number, admitted
