"""Backend resolution for validated two-dimensional surface symmetry.

Canonical interface identities use a finite two-dimensional point group.  A
backend failure is therefore not equivalent to an identity-only group: the
former is an unresolved scientific condition, while the latter is an explicit
user-selected equivalence policy.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from calm.structure.standardization import (
    nonnegative_finite_float,
    positive_finite_float,
)
from calm.symmetry.surface_group import (
    SURFACE_SYMMETRY_MODES,
    SurfaceSymmetryProvenance,
    SurfaceSymmetryResolution,
    metric_preservation_residual,
    surface_metric_from_cell_rows,
    validate_surface_symmetry_group_2d,
)
from calm.exceptions import SurfaceSymmetryDiscoveryError


def _validated_mode(mode: object) -> str:
    if not isinstance(mode, str) or mode not in SURFACE_SYMMETRY_MODES:
        allowed = ", ".join(sorted(SURFACE_SYMMETRY_MODES))
        raise ValueError(f"surface_symmetry_mode must be one of: {allowed}.")
    return mode


def _failed_provenance(
    *,
    mode: str,
    symprec: float,
    angle_tolerance: float,
    metric_tolerance: float,
    backend_version: str | None,
    error: BaseException,
) -> SurfaceSymmetryProvenance:
    return SurfaceSymmetryProvenance(
        mode=mode,
        status="failed",
        operation_count=0,
        symprec=symprec,
        angle_tolerance=angle_tolerance,
        metric_tolerance=metric_tolerance,
        max_metric_residual=None,
        backend="spglib",
        backend_version=backend_version,
        failure_type=type(error).__name__,
        failure_message=str(error) or "<no message>",
    )


def resolve_surface_pointgroup_2d(
    subject: Any,
    *,
    mode: str = "discover",
    symprec: float = 1e-5,
    angle_tolerance: float = 1e-8,
    metric_tolerance: float = 1e-5,
) -> SurfaceSymmetryResolution:
    """Resolve one validated 2D surface point group.

    ``mode="discover"`` invokes spglib and fails closed when discovery or group
    validation fails.  ``mode="identity_only"`` is an explicit scientific
    policy that skips backend discovery and records that choice in provenance.
    """

    selected_mode = _validated_mode(mode)
    symmetry_tolerance = positive_finite_float("symprec", symprec)
    angle_tol = nonnegative_finite_float(
        "angle_tolerance",
        angle_tolerance,
    )
    metric_tol = positive_finite_float(
        "metric_tolerance",
        metric_tolerance,
    )

    identity = np.eye(2, dtype=int)
    if selected_mode == "identity_only":
        operations = validate_surface_symmetry_group_2d(
            [identity],
            metric_tolerance=metric_tol,
        )
        return SurfaceSymmetryResolution(
            operations=operations,
            provenance=SurfaceSymmetryProvenance(
                mode=selected_mode,
                status="identity_only",
                operation_count=1,
                symprec=symmetry_tolerance,
                angle_tolerance=angle_tol,
                metric_tolerance=metric_tol,
                max_metric_residual=0.0,
                backend=None,
                backend_version=None,
            ),
        )

    backend_version: str | None = None
    try:
        from calm.symmetry import spglib_adapter

        backend_version = str(getattr(spglib_adapter.spglib, "__version__", "unknown"))
        atoms = getattr(subject, "atoms", subject)
        metric = surface_metric_from_cell_rows(atoms.cell.array)
        discovered = spglib_adapter.get_surface_pointgroup_ops(
            atoms,
            symprec=symmetry_tolerance,
            angle_tol=angle_tol,
            metric_tol=metric_tol,
        )
        operations = validate_surface_symmetry_group_2d(
            discovered,
            metric=metric,
            metric_tolerance=metric_tol,
        )
    except Exception as exc:
        provenance = _failed_provenance(
            mode=selected_mode,
            symprec=symmetry_tolerance,
            angle_tolerance=angle_tol,
            metric_tolerance=metric_tol,
            backend_version=backend_version,
            error=exc,
        )
        raise SurfaceSymmetryDiscoveryError(
            "Surface-symmetry discovery failed closed. Select "
            "surface_symmetry_mode='identity_only' explicitly to use the "
            "identity group instead; CALM never applies that fallback silently. "
            f"Cause: {type(exc).__name__}: {exc}",
            provenance=provenance,
        ) from exc

    residual = max(
        metric_preservation_residual(operation, metric) for operation in operations
    )
    return SurfaceSymmetryResolution(
        operations=operations,
        provenance=SurfaceSymmetryProvenance(
            mode=selected_mode,
            status="discovered",
            operation_count=len(operations),
            symprec=symmetry_tolerance,
            angle_tolerance=angle_tol,
            metric_tolerance=metric_tol,
            max_metric_residual=residual,
            backend="spglib",
            backend_version=backend_version,
        ),
    )


def surface_pointgroup_ops_2d(
    subject: Any,
    *,
    mode: str = "discover",
    symprec: float = 1e-5,
    angle_tolerance: float = 1e-8,
    metric_tolerance: float = 1e-5,
) -> list[np.ndarray]:
    """Return validated operations for one declared symmetry policy."""

    resolution = resolve_surface_pointgroup_2d(
        subject,
        mode=mode,
        symprec=symprec,
        angle_tolerance=angle_tolerance,
        metric_tolerance=metric_tolerance,
    )
    return [operation.copy() for operation in resolution.operations]
