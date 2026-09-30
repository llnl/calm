"""Import-light slab target-width contract.

The public ``target_width`` control is a minimum Cartesian atom-span request for
the final finite slab, evaluated before vacuum is added.  A reciprocal-lattice
estimate supplies the initial layer count; the atomistic builder then increases
the count until the measured span satisfies the request or the declared hard
cap is reached.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil, gcd, isfinite
from numbers import Integral
from typing import Iterable

import numpy as np

SLAB_TARGET_WIDTH_POLICY = "minimum_cartesian_atom_span"
SLAB_TARGET_WIDTH_POLICY_VERSION = 1


class SlabThicknessLimitError(ValueError):
    """Raised when ``max_n_layers`` prevents satisfying ``target_width``."""


def _positive_integer(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise TypeError(f"{name} must be an integer.")
    result = int(value)
    if result < 1:
        raise ValueError(f"{name} must be at least 1.")
    return result


def _finite_positive(name: str, value: object) -> float:
    result = float(value)
    if not isfinite(result) or result <= 0.0:
        raise ValueError(f"{name} must be finite and positive.")
    return result


def _finite_nonnegative(name: str, value: object) -> float:
    result = float(value)
    if not isfinite(result) or result < 0.0:
        raise ValueError(f"{name} must be finite and nonnegative.")
    return result


def reduce_miller_index(hkl: Iterable[object]) -> tuple[int, int, int]:
    values = tuple(hkl)
    if len(values) != 3:
        raise ValueError("hkl must contain exactly three Miller indices.")
    if any(
        isinstance(value, bool) or not isinstance(value, Integral) for value in values
    ):
        raise TypeError("hkl must contain exact integers.")
    h, k, miller_l = (int(value) for value in values)
    if (h, k, miller_l) == (0, 0, 0):
        raise ValueError("hkl=(0, 0, 0) is invalid.")
    divisor = gcd(gcd(abs(h), abs(k)), abs(miller_l)) or 1
    reduced = (h // divisor, k // divisor, miller_l // divisor)
    for value in reduced:
        if value:
            if value < 0:
                reduced = tuple(-item for item in reduced)
            break
    return reduced


def interplanar_spacing_A(
    cell_rows_A: object,
    hkl: Iterable[object],
) -> float:
    """Return crystallographic ``d_hkl`` for an ASE-style row lattice."""

    cell = np.asarray(cell_rows_A, dtype=float)
    if cell.shape != (3, 3):
        raise ValueError(f"cell_rows_A must have shape (3, 3); got {cell.shape}.")
    if not np.all(np.isfinite(cell)):
        raise ValueError("cell_rows_A must contain only finite values.")
    hkl_reduced = np.asarray(reduce_miller_index(hkl), dtype=float)
    try:
        # ASE stores direct lattice vectors as rows.  The reciprocal normal
        # column therefore solves A g = h, so g = A^{-1} h.
        normal = np.linalg.solve(cell, hkl_reduced)
    except np.linalg.LinAlgError as exc:
        raise ValueError("cell_rows_A must be nonsingular.") from exc
    normal_norm = float(np.linalg.norm(normal))
    if not isfinite(normal_norm) or normal_norm <= 0.0:
        raise ValueError("The reciprocal surface normal must be finite and nonzero.")
    spacing = 1.0 / normal_norm
    if not isfinite(spacing) or spacing <= 0.0:
        raise ValueError("The interplanar spacing must be finite and positive.")
    return spacing


@dataclass(frozen=True)
class TargetWidthLayerPlan:
    """Deterministic reciprocal-lattice estimate for target-width construction."""

    policy: str
    policy_version: int
    hkl_reduced: tuple[int, int, int]
    interplanar_spacing_A: float
    target_width_A: float
    width_tolerance_A: float
    required_layers: int
    max_n_layers: int
    nominal_plane_span_A: float


def target_width_policy_metadata() -> dict[str, object]:
    """Return identity/provenance metadata for the target-width rule."""

    return {
        "target_width_policy": SLAB_TARGET_WIDTH_POLICY,
        "target_width_policy_version": SLAB_TARGET_WIDTH_POLICY_VERSION,
    }


def plan_target_width_layers(
    cell_rows_A: object,
    hkl: Iterable[object],
    *,
    target_width_A: object,
    width_tolerance_A: object,
    max_n_layers: object,
) -> TargetWidthLayerPlan:
    """Return the minimal initial layer estimate under the declared tolerance.

    The reciprocal-lattice estimate treats ``n`` stacking planes as having a
    nominal endpoint-to-endpoint span ``(n - 1) d_hkl``.  The tolerance permits
    an undershoot no larger than ``width_tolerance_A``.  The final atomistic
    span is checked independently after construction.
    """

    target = _finite_positive("target_width_A", target_width_A)
    tolerance = _finite_nonnegative("width_tolerance_A", width_tolerance_A)
    cap = _positive_integer("max_n_layers", max_n_layers)
    hkl_reduced = reduce_miller_index(hkl)
    spacing = interplanar_spacing_A(cell_rows_A, hkl_reduced)
    effective_target = max(target - tolerance, 0.0)
    required = max(1, int(ceil(effective_target / spacing)) + 1)
    if required > cap:
        raise SlabThicknessLimitError(
            "target_width requires at least "
            f"{required} layers from d_hkl={spacing:.12g} angstrom, but "
            f"max_n_layers={cap}."
        )
    return TargetWidthLayerPlan(
        policy=SLAB_TARGET_WIDTH_POLICY,
        policy_version=SLAB_TARGET_WIDTH_POLICY_VERSION,
        hkl_reduced=hkl_reduced,
        interplanar_spacing_A=spacing,
        target_width_A=target,
        width_tolerance_A=tolerance,
        required_layers=required,
        max_n_layers=cap,
        nominal_plane_span_A=float((required - 1) * spacing),
    )


def target_width_is_satisfied(
    actual_atom_span_A: object,
    *,
    target_width_A: object,
    width_tolerance_A: object,
) -> bool:
    """Return whether the measured Cartesian atom span meets the request."""

    actual = _finite_nonnegative("actual_atom_span_A", actual_atom_span_A)
    target = _finite_positive("target_width_A", target_width_A)
    tolerance = _finite_nonnegative("width_tolerance_A", width_tolerance_A)
    return actual + tolerance >= target


__all__ = [
    "SLAB_TARGET_WIDTH_POLICY",
    "SLAB_TARGET_WIDTH_POLICY_VERSION",
    "SlabThicknessLimitError",
    "TargetWidthLayerPlan",
    "interplanar_spacing_A",
    "plan_target_width_layers",
    "reduce_miller_index",
    "target_width_is_satisfied",
    "target_width_policy_metadata",
]
