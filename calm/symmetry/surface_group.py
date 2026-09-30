"""Validated finite groups for two-dimensional surface symmetry.

The mathematical object used by CALM's canonical surface identities is a
finite subgroup of ``GL(2, Z)`` acting on fractional in-plane coordinates.
This module validates that object independently of any symmetry-discovery
backend.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from numbers import Integral, Real
from typing import Any, Iterable

import numpy as np

SURFACE_SYMMETRY_POLICY = "validated_surface_pointgroup"
SURFACE_SYMMETRY_POLICY_VERSION = 1
SURFACE_SYMMETRY_MODES = frozenset({"discover", "identity_only"})


def _positive_finite(name: str, value: object) -> float:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        raise TypeError(f"{name} must be a positive finite real number.")
    result = float(value)
    if not math.isfinite(result) or result <= 0.0:
        raise ValueError(f"{name} must be a positive finite real number.")
    return result


def _exact_nonnegative_integer(name: str, value: object) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral):
        raise TypeError(f"{name} must be a non-negative integer.")
    result = int(value)
    if result < 0:
        raise ValueError(f"{name} must be a non-negative integer.")
    return result


def _optional_nonempty_string(name: str, value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise TypeError(f"{name} must be a non-empty string or null.")
    return value


def _exact_integer_matrix_2d(name: str, value: object) -> np.ndarray:
    matrix = np.asarray(value, dtype=object)
    if matrix.shape != (2, 2):
        raise ValueError(f"{name} must have shape (2, 2).")
    entries: list[int] = []
    for index, item in enumerate(matrix.ravel().tolist()):
        if isinstance(item, (bool, np.bool_)) or not isinstance(item, Integral):
            raise TypeError(f"{name}[{index}] must contain an exact integer value.")
        entries.append(int(item))
    try:
        return np.asarray(entries, dtype=np.int64).reshape(2, 2)
    except OverflowError as exc:
        raise ValueError(
            f"{name} contains an integer outside the supported range."
        ) from exc


def _matrix_key(matrix: np.ndarray) -> tuple[int, int, int, int]:
    return tuple(int(value) for value in matrix.ravel())  # type: ignore[return-value]


def _determinant_2d(matrix: np.ndarray) -> int:
    return int(
        int(matrix[0, 0]) * int(matrix[1, 1]) - int(matrix[0, 1]) * int(matrix[1, 0])
    )


def _inverse_key_2d(matrix: np.ndarray) -> tuple[int, int, int, int]:
    determinant = _determinant_2d(matrix)
    return (
        determinant * int(matrix[1, 1]),
        -determinant * int(matrix[0, 1]),
        -determinant * int(matrix[1, 0]),
        determinant * int(matrix[0, 0]),
    )


def _product_key_2d(
    left: np.ndarray,
    right: np.ndarray,
) -> tuple[int, int, int, int]:
    a, b, c, d = (int(value) for value in left.ravel())
    e, f, g, h = (int(value) for value in right.ravel())
    return (
        a * e + b * g,
        a * f + b * h,
        c * e + d * g,
        c * f + d * h,
    )


def validate_surface_metric_2d(metric: object) -> np.ndarray:
    """Return a validated symmetric-positive-definite surface metric."""

    matrix = np.asarray(metric, dtype=float)
    if matrix.shape != (2, 2):
        raise ValueError("surface metric must have shape (2, 2).")
    if not np.all(np.isfinite(matrix)):
        raise ValueError("surface metric must contain only finite values.")
    scale = max(1.0, float(np.linalg.norm(matrix, ord="fro")))
    if float(np.linalg.norm(matrix - matrix.T, ord="fro")) > 1e-12 * scale:
        raise ValueError("surface metric must be symmetric.")
    symmetric = 0.5 * (matrix + matrix.T)
    eigenvalues = np.linalg.eigvalsh(symmetric)
    if float(eigenvalues[0]) <= 0.0:
        raise ValueError("surface metric must be positive definite.")
    return symmetric


def surface_metric_from_cell_rows(cell: object) -> np.ndarray:
    """Return the fractional in-plane metric from an ASE-style row cell."""

    rows = np.asarray(cell, dtype=float)
    if rows.shape != (3, 3):
        raise ValueError("surface cell must have shape (3, 3).")
    if not np.all(np.isfinite(rows)):
        raise ValueError("surface cell must contain only finite values.")
    inplane = rows[:2, :]
    if np.linalg.matrix_rank(inplane) != 2:
        raise ValueError("the first two surface-cell vectors must be independent.")
    return validate_surface_metric_2d(inplane @ inplane.T)


def metric_preservation_residual(operation: object, metric: object) -> float:
    """Return the scale-free Frobenius residual for ``P.T @ G @ P = G``."""

    matrix = _exact_integer_matrix_2d("surface operation", operation)
    gram = validate_surface_metric_2d(metric)
    scale = max(float(np.linalg.norm(gram, ord="fro")), np.finfo(float).tiny)
    residual = matrix.T @ gram @ matrix - gram
    return float(np.linalg.norm(residual, ord="fro") / scale)


def validate_surface_symmetry_group_2d(
    operations: Iterable[object],
    *,
    metric: object | None = None,
    metric_tolerance: float = 1e-8,
) -> tuple[np.ndarray, ...]:
    """Validate and deterministically order a finite surface point group.

    The supplied operations must explicitly contain the identity, be exact
    integer unimodular matrices, and be closed under composition and inversion.
    When ``metric`` is provided, every operation must preserve that oriented
    surface metric within the relative Frobenius tolerance
    ``metric_tolerance``.
    """

    tolerance = _positive_finite("metric_tolerance", metric_tolerance)
    candidates = list(operations)
    if not candidates:
        raise ValueError("surface symmetry group cannot be empty.")

    unique: dict[tuple[int, int, int, int], np.ndarray] = {}
    for index, operation in enumerate(candidates):
        matrix = _exact_integer_matrix_2d(
            f"surface symmetry operations[{index}]",
            operation,
        )
        determinant = _determinant_2d(matrix)
        if determinant not in {-1, 1}:
            raise ValueError(
                "Surface symmetry operations must be unimodular with determinant "
                f"+1 or -1; operation {index} has determinant {determinant}."
            )
        unique[_matrix_key(matrix)] = matrix.copy()

    identity_key = _matrix_key(np.eye(2, dtype=int))
    if identity_key not in unique:
        raise ValueError("surface symmetry group must explicitly contain identity.")

    keys = set(unique)
    for left_key, left in unique.items():
        inverse_key = _inverse_key_2d(left)
        if inverse_key not in keys:
            raise ValueError(
                "surface symmetry group is missing the inverse of operation "
                f"{left_key}."
            )
        for right_key, right in unique.items():
            product_key = _product_key_2d(left, right)
            if product_key not in keys:
                raise ValueError(
                    "surface symmetry group is not closed: product of operations "
                    f"{left_key} and {right_key} is absent."
                )

    if metric is not None:
        gram = validate_surface_metric_2d(metric)
        for key, operation in unique.items():
            residual = metric_preservation_residual(operation, gram)
            if residual > tolerance:
                raise ValueError(
                    "surface symmetry operation does not preserve the selected "
                    f"oriented-surface metric: operation={key}, "
                    f"relative_residual={residual:.6e}, "
                    f"metric_tolerance={tolerance:.6e}."
                )

    return tuple(unique[key] for key in sorted(unique))


@dataclass(frozen=True)
class SurfaceSymmetryProvenance:
    """Serializable provenance for one resolved surface-symmetry group."""

    mode: str
    status: str
    operation_count: int
    symprec: float
    angle_tolerance: float
    metric_tolerance: float
    max_metric_residual: float | None
    backend: str | None
    backend_version: str | None
    failure_type: str | None = None
    failure_message: str | None = None
    policy: str = SURFACE_SYMMETRY_POLICY
    policy_version: int = SURFACE_SYMMETRY_POLICY_VERSION

    def __post_init__(self) -> None:
        if self.policy != SURFACE_SYMMETRY_POLICY:
            raise ValueError("unsupported surface-symmetry policy.")
        policy_version = _exact_nonnegative_integer(
            "policy_version",
            self.policy_version,
        )
        if policy_version != SURFACE_SYMMETRY_POLICY_VERSION:
            raise ValueError("unsupported surface-symmetry policy version.")
        if self.mode not in SURFACE_SYMMETRY_MODES:
            raise ValueError("invalid surface-symmetry mode.")
        if self.status not in {"discovered", "identity_only", "failed"}:
            raise ValueError("invalid surface-symmetry status.")
        operation_count = _exact_nonnegative_integer(
            "operation_count",
            self.operation_count,
        )
        _positive_finite("symprec", self.symprec)
        _positive_finite("metric_tolerance", self.metric_tolerance)
        if isinstance(self.angle_tolerance, (bool, np.bool_)) or not isinstance(
            self.angle_tolerance, Real
        ):
            raise TypeError(
                "angle_tolerance must be a non-negative finite real number."
            )
        angle = float(self.angle_tolerance)
        if not math.isfinite(angle) or angle < 0.0:
            raise ValueError(
                "angle_tolerance must be a non-negative finite real number."
            )

        backend = _optional_nonempty_string("backend", self.backend)
        backend_version = _optional_nonempty_string(
            "backend_version",
            self.backend_version,
        )
        failure_type = _optional_nonempty_string(
            "failure_type",
            self.failure_type,
        )
        failure_message = _optional_nonempty_string(
            "failure_message",
            self.failure_message,
        )

        if self.status == "failed":
            if self.mode != "discover":
                raise ValueError("failed symmetry provenance requires discover mode.")
            if operation_count != 0:
                raise ValueError(
                    "failed symmetry provenance cannot contain operations."
                )
            if not backend or not failure_type or not failure_message:
                raise ValueError("failed symmetry provenance requires failure details.")
            if self.max_metric_residual is not None:
                raise ValueError("failed symmetry provenance has no metric residual.")
            return

        if operation_count <= 0:
            raise ValueError("successful symmetry provenance requires operations.")
        if self.failure_type is not None or self.failure_message is not None:
            raise ValueError(
                "successful symmetry provenance cannot contain failure details."
            )
        if self.max_metric_residual is None:
            raise ValueError(
                "successful symmetry provenance requires a metric residual."
            )
        if isinstance(self.max_metric_residual, (bool, np.bool_)) or not isinstance(
            self.max_metric_residual, Real
        ):
            raise TypeError(
                "max_metric_residual must be a non-negative finite real number."
            )
        residual = float(self.max_metric_residual)
        if not math.isfinite(residual) or residual < 0.0:
            raise ValueError("max_metric_residual must be non-negative and finite.")
        if residual > float(self.metric_tolerance):
            raise ValueError("successful symmetry provenance exceeds metric_tolerance.")
        if self.status == "identity_only":
            if self.mode != "identity_only" or operation_count != 1:
                raise ValueError(
                    "identity-only provenance must record one identity operation."
                )
            if backend is not None or backend_version is not None:
                raise ValueError("identity-only provenance must not claim a backend.")
        elif self.mode != "discover" or not backend or not backend_version:
            raise ValueError(
                "discovered symmetry provenance requires backend metadata."
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy": self.policy,
            "policy_version": int(self.policy_version),
            "mode": self.mode,
            "status": self.status,
            "operation_count": _exact_nonnegative_integer(
                "operation_count",
                self.operation_count,
            ),
            "symprec": float(self.symprec),
            "angle_tolerance": float(self.angle_tolerance),
            "metric_tolerance": float(self.metric_tolerance),
            "max_metric_residual": (
                None
                if self.max_metric_residual is None
                else float(self.max_metric_residual)
            ),
            "backend": self.backend,
            "backend_version": self.backend_version,
            "failure_type": self.failure_type,
            "failure_message": self.failure_message,
        }


@dataclass(frozen=True)
class SurfaceSymmetryResolution:
    """Validated operations together with their discovery provenance."""

    operations: tuple[np.ndarray, ...]
    provenance: SurfaceSymmetryProvenance

    def __post_init__(self) -> None:
        if self.provenance.status == "failed":
            raise ValueError("a symmetry resolution cannot contain failed provenance.")
        validated = validate_surface_symmetry_group_2d(
            self.operations,
            metric_tolerance=self.provenance.metric_tolerance,
        )
        if len(validated) != int(self.provenance.operation_count):
            raise ValueError(
                "symmetry operation count does not match recorded provenance."
            )
        frozen: list[np.ndarray] = []
        for operation in validated:
            copy = operation.copy()
            copy.flags.writeable = False
            frozen.append(copy)
        object.__setattr__(self, "operations", tuple(frozen))
