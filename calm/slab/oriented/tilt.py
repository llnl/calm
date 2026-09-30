"""Exact slab tilt and shear provenance.

ASE row convention is used throughout: ``atoms.cell.array`` has lattice vectors
as rows, and residual c-vector tilt is ``atoms.cell.array[2, :2]``. Tilt is a
geometric quality metric and is never conflated with in-plane strain. The
``orthogonalize_c_applied`` field refers only to the optional physical shear; a
representation-only vacuum-axis canonicalization is recorded in
``vacuum_info``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any

import numpy as np

from calm.slab.oriented.transforms import OrientedSlabTransforms

if TYPE_CHECKING:
    from ase import Atoms


def _finite_float(name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, np.number)):
        raise TypeError(f"{name} must be numeric.")
    number = float(value)
    if not np.isfinite(number):
        raise ValueError(f"{name} must be finite.")
    return number


def _integer_pair(name: str, value: Any) -> list[int]:
    if (
        isinstance(value, (str, bytes))
        or not isinstance(value, Sequence)
        or len(value) != 2
    ):
        raise TypeError(f"{name} must be a two-integer sequence.")
    result: list[int] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, np.integer)):
            raise TypeError(f"{name} must contain only integers.")
        result.append(int(item))
    return result


def _matrix3(name: str, value: Any) -> np.ndarray:
    try:
        matrix = np.asarray(value, dtype=float)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{name} must be a numeric 3x3 matrix.") from exc
    if matrix.shape != (3, 3):
        raise ValueError(f"{name} must have shape (3, 3).")
    if not np.all(np.isfinite(matrix)):
        raise ValueError(f"{name} must contain only finite values.")
    return matrix


def _mapping_or_none(name: str, value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping or None.")
    return dict(value)


def compute_slab_tilt_metadata(
    atoms: Atoms,
    transforms: OrientedSlabTransforms | None = None,
    *,
    tilt_tolerance: float = 1e-6,
    cell_convention: str = "ase_row",
) -> dict[str, Any]:
    """Return exact, JSON-compatible slab tilt provenance.

    Malformed current transform metadata raises. CALM does not discard invalid
    tilt-reduction, shear, or vacuum provenance and continue with a partial
    record.
    """

    try:
        cell = np.asarray(atoms.cell.array, dtype=float)
    except (AttributeError, TypeError, ValueError) as exc:
        raise TypeError(
            "atoms must provide a valid cell matrix at atoms.cell.array"
        ) from exc
    if cell.shape != (3, 3):
        raise ValueError("atoms.cell.array must have shape (3, 3).")
    if not np.all(np.isfinite(cell)):
        raise ValueError("atoms.cell.array must contain only finite values.")

    tolerance = _finite_float("tilt_tolerance", tilt_tolerance)
    if tolerance < 0.0:
        raise ValueError("tilt_tolerance must be non-negative.")
    if cell_convention not in {"ase_row", "ase_row_major"}:
        raise ValueError("cell_convention must be 'ase_row' or 'ase_row_major'.")

    c_xy = cell[2, :2]
    tilt_x = float(c_xy[0])
    tilt_y = float(c_xy[1])
    tilt_magnitude = float(np.linalg.norm(c_xy))
    c_vec_norm = float(np.linalg.norm(cell[2]))
    threshold = tolerance + 1e-8 * max(c_vec_norm, 1.0)

    metadata: dict[str, Any] = {
        "cell_convention": "ase_row_major",
        "cell_generated_3x3": cell.tolist(),
        "tilt_xy": [tilt_x, tilt_y],
        "tilt_magnitude": tilt_magnitude,
        "tilt_tolerance": tolerance,
        "has_residual_tilt": bool(tilt_magnitude > threshold),
        "orthogonalize_c_applied": False,
        "integer_c_tilt_reduction_applied": False,
        "c_tilt_mn": None,
        "L_c_tilt_row": None,
        "shear_info": None,
        "vacuum_info": None,
    }

    if transforms is None:
        return metadata
    if not isinstance(transforms, OrientedSlabTransforms):
        raise TypeError(
            "transforms must be an OrientedSlabTransforms instance or None."
        )

    extra = transforms.payload
    applied_integer = False

    mn = extra.get("c_tilt_mn")
    if mn is not None:
        parsed_mn = _integer_pair("c_tilt_mn", mn)
        metadata["c_tilt_mn"] = parsed_mn
        applied_integer = parsed_mn != [0, 0]

    transform = extra.get("L_c_tilt_row")
    if transform is not None:
        parsed_transform = _matrix3("L_c_tilt_row", transform)
        metadata["L_c_tilt_row"] = parsed_transform.tolist()
        applied_integer = applied_integer or not np.allclose(
            parsed_transform,
            np.eye(3),
        )
    metadata["integer_c_tilt_reduction_applied"] = bool(applied_integer)

    shear = _mapping_or_none("shear_info", extra.get("shear_info"))
    if shear is not None:
        shear_matrix = shear.get("F_shear_cart")
        if shear_matrix is not None:
            _matrix3("shear_info.F_shear_cart", shear_matrix)

        before_raw = shear.get("c_xy_norm_before")
        after_raw = shear.get("c_xy_norm_after")
        before = (
            None
            if before_raw is None
            else _finite_float("shear_info.c_xy_norm_before", before_raw)
        )
        after = (
            None
            if after_raw is None
            else _finite_float("shear_info.c_xy_norm_after", after_raw)
        )
        if before is not None:
            metadata["c_xy_norm_before"] = before
        if after is not None:
            metadata["c_xy_norm_after"] = after

        metadata["shear_info"] = shear
        metadata["orthogonalize_c_applied"] = bool(
            shear_matrix is not None
            or (before is not None and after is not None and after < before)
        )

    metadata["vacuum_info"] = _mapping_or_none(
        "vacuum_info",
        extra.get("vacuum_info"),
    )
    return metadata


__all__ = ["compute_slab_tilt_metadata"]
