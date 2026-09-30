"""Shared validated surface-symmetry helpers for interface construction."""

from __future__ import annotations

from typing import Any

import numpy as np

from calm.symmetry.surface_group import SurfaceSymmetryResolution
from calm.symmetry.surface_resolver import (
    resolve_surface_pointgroup_2d as _resolve_surface_pointgroup_2d,
)


def resolve_surface_pointgroup_2d(
    slab: Any,
    *,
    mode: str = "discover",
    symprec: float = 1e-5,
    angle_tolerance: float = 1e-8,
    metric_tolerance: float = 1e-5,
) -> SurfaceSymmetryResolution:
    """Resolve the validated surface group used by interface identities."""

    return _resolve_surface_pointgroup_2d(
        slab,
        mode=mode,
        symprec=symprec,
        angle_tolerance=angle_tolerance,
        metric_tolerance=metric_tolerance,
    )


def surface_pointgroup_ops_2d(
    slab: Any,
    *,
    mode: str = "discover",
    symprec: float = 1e-5,
    angle_tolerance: float = 1e-8,
    metric_tolerance: float = 1e-5,
) -> list[np.ndarray]:
    """Return validated operations for one declared symmetry policy."""

    resolution = resolve_surface_pointgroup_2d(
        slab,
        mode=mode,
        symprec=symprec,
        angle_tolerance=angle_tolerance,
        metric_tolerance=metric_tolerance,
    )
    return [operation.copy() for operation in resolution.operations]


__all__ = ["resolve_surface_pointgroup_2d", "surface_pointgroup_ops_2d"]
