"""Exact-current persistence contract for interface strain states.

The public strain kernel returns an in-memory value object.  Persistence uses a
separate versioned JSON representation so stored scientific state is explicit,
self-describing, and independently validated on every read.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import isfinite
from numbers import Real
from typing import Any

import numpy as np

from calm.interface.refinement.strain import INCREMENTAL_INTERFACE_MATCHING_SCOPE
from calm.slab.oriented.cell_contract import (
    DEFAULT_SLAB_CELL_RELATIVE_TOLERANCE,
    SLAB_DEFORMATION_ACCOUNTING_POLICY,
    SLAB_DEFORMATION_ACCOUNTING_VERSION,
)

STRAIN_STATE_SCHEMA = "calm.interface_strain_state"
STRAIN_STATE_VERSION = 2
STRAIN_STATE_DEFORMATION_SCOPE = INCREMENTAL_INTERFACE_MATCHING_SCOPE

_FIELDS = frozenset(
    {
        "schema",
        "version",
        "prototype_uid_full",
        "strain_model_uid",
        "strain_alpha",
        "deformation_scope",
        "deformation_accounting_policy",
        "deformation_accounting_version",
        "F_tot",
        "F_A",
        "F_B",
        "E_A_rms",
        "E_B_rms",
    }
)


def _nonempty_string(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise TypeError(f"{name} must be a non-empty, whitespace-trimmed string.")
    return value


def _finite_real(name: str, value: Any, *, nonnegative: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{name} must be a finite real number.")
    result = float(value)
    if not isfinite(result):
        raise ValueError(f"{name} must be finite.")
    if nonnegative and result < 0.0:
        raise ValueError(f"{name} must be non-negative.")
    return result


def _matrix3(name: str, value: Any) -> np.ndarray:
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError(f"{name} must be a 3x3 sequence.")
    if len(value) != 3:
        raise ValueError(f"{name} must contain exactly three rows.")
    rows: list[list[float]] = []
    for row_index, row in enumerate(value):
        if isinstance(row, (str, bytes)) or not isinstance(row, Sequence):
            raise TypeError(f"{name}[{row_index}] must be a three-value sequence.")
        if len(row) != 3:
            raise ValueError(f"{name}[{row_index}] must contain three values.")
        rows.append(
            [
                _finite_real(f"{name}[{row_index}][{column_index}]", item)
                for column_index, item in enumerate(row)
            ]
        )
    return np.asarray(rows, dtype=float)


def _matrix_close(left: Any, right: Any) -> bool:
    lhs = np.asarray(left, dtype=float)
    rhs = np.asarray(right, dtype=float)
    scale = max(
        1.0,
        float(np.linalg.norm(lhs, ord=np.inf)),
        float(np.linalg.norm(rhs, ord=np.inf)),
    )
    return bool(
        np.allclose(
            lhs,
            rhs,
            atol=DEFAULT_SLAB_CELL_RELATIVE_TOLERANCE * scale,
            rtol=0.0,
        )
    )


def _incremental_matching_matrix(name: str, value: Any) -> np.ndarray:
    matrix = _matrix3(name, value)
    determinant = float(np.linalg.det(matrix))
    if not isfinite(determinant) or determinant <= 0.0:
        raise ValueError(f"{name} must have positive finite determinant.")
    expected_z = np.array([0.0, 0.0, 1.0])
    tolerance = DEFAULT_SLAB_CELL_RELATIVE_TOLERANCE
    if not np.allclose(matrix[:, 2], expected_z, atol=tolerance, rtol=0.0):
        raise ValueError(
            f"{name} must be an in-plane deformation with an unchanged z column."
        )
    if not np.allclose(matrix[2, :], expected_z, atol=tolerance, rtol=0.0):
        raise ValueError(
            f"{name} must be an in-plane deformation with an unchanged z row."
        )
    return matrix


def _hencky_rms(matrix: np.ndarray) -> float:
    singular_values = np.linalg.svd(matrix[:2, :2], compute_uv=False)
    if np.any(~np.isfinite(singular_values)) or np.any(singular_values <= 0.0):
        raise ValueError("Incremental matching deformation must be nonsingular.")
    principal_hencky = np.log(singular_values)
    return float(np.sqrt(np.mean(principal_hencky**2)))


def _require_scalar_close(name: str, stored: float, expected: float) -> None:
    scale = max(1.0, abs(stored), abs(expected))
    tolerance = DEFAULT_SLAB_CELL_RELATIVE_TOLERANCE * scale
    if not np.isclose(stored, expected, atol=tolerance, rtol=0.0):
        raise ValueError(
            f"{name} is inconsistent with its incremental matching deformation."
        )


def canonical_strain_state(
    value: Mapping[str, Any],
    *,
    prototype_uid_full: str,
    strain_alpha: float,
) -> dict[str, Any]:
    """Validate one exact-current persisted strain-state mapping."""

    if not isinstance(value, Mapping):
        raise TypeError("Derived-interface strain_state must be a mapping.")
    stored = dict(value)
    missing = sorted(_FIELDS - stored.keys())
    if missing:
        raise ValueError(
            "Derived-interface strain_state is missing required current field(s): "
            + ", ".join(missing)
            + "."
        )
    unsupported = sorted(stored.keys() - _FIELDS)
    if unsupported:
        raise ValueError(
            "Derived-interface strain_state contains unsupported or historical "
            "field(s): " + ", ".join(unsupported) + "."
        )

    schema = _nonempty_string("strain_state schema", stored["schema"])
    if schema != STRAIN_STATE_SCHEMA:
        raise ValueError(
            f"Unsupported strain_state schema {schema!r}; "
            f"expected {STRAIN_STATE_SCHEMA!r}."
        )
    version = stored["version"]
    if isinstance(version, bool) or not isinstance(version, int):
        raise TypeError("strain_state version must be an integer.")
    if version != STRAIN_STATE_VERSION:
        raise ValueError(
            f"Unsupported strain_state version {version!r}; "
            f"expected {STRAIN_STATE_VERSION}."
        )

    expected_prototype = _nonempty_string(
        "prototype_uid_full",
        prototype_uid_full,
    )
    stored_prototype = _nonempty_string(
        "strain_state prototype_uid_full",
        stored["prototype_uid_full"],
    )
    if stored_prototype != expected_prototype:
        raise ValueError(
            "strain_state prototype_uid_full does not match the authoritative "
            "derived-interface prototype."
        )

    model_uid = _nonempty_string(
        "strain_state strain_model_uid",
        stored["strain_model_uid"],
    )
    if not model_uid.startswith("smodel:"):
        raise ValueError(
            "strain_state strain_model_uid must use the current smodel: UID."
        )

    expected_alpha = _finite_real("strain_alpha", strain_alpha)
    if not 0.0 <= expected_alpha <= 1.0:
        raise ValueError("strain_alpha must lie in [0, 1].")
    stored_alpha = _finite_real(
        "strain_state strain_alpha",
        stored["strain_alpha"],
    )
    if stored_alpha != expected_alpha:
        raise ValueError(
            "strain_state strain_alpha does not match the derived-interface "
            "strain_alpha."
        )

    scope = _nonempty_string(
        "strain_state deformation_scope", stored["deformation_scope"]
    )
    if scope != STRAIN_STATE_DEFORMATION_SCOPE:
        raise ValueError(
            "strain_state deformation_scope must identify incremental interface "
            "matching deformation."
        )
    accounting_policy = _nonempty_string(
        "strain_state deformation_accounting_policy",
        stored["deformation_accounting_policy"],
    )
    if accounting_policy != SLAB_DEFORMATION_ACCOUNTING_POLICY:
        raise ValueError(
            "strain_state deformation_accounting_policy is inconsistent with the "
            "current composed slab-deformation contract."
        )
    accounting_version = stored["deformation_accounting_version"]
    if isinstance(accounting_version, bool) or not isinstance(accounting_version, int):
        raise TypeError(
            "strain_state deformation_accounting_version must be an integer."
        )
    if accounting_version != SLAB_DEFORMATION_ACCOUNTING_VERSION:
        raise ValueError(
            "strain_state deformation_accounting_version is inconsistent with the "
            "current composed slab-deformation contract."
        )

    F_tot = _incremental_matching_matrix("strain_state F_tot", stored["F_tot"])
    F_A = _incremental_matching_matrix("strain_state F_A", stored["F_A"])
    F_B = _incremental_matching_matrix("strain_state F_B", stored["F_B"])
    try:
        expected_total = np.linalg.solve(F_B, F_A)
    except np.linalg.LinAlgError as exc:
        raise ValueError("strain_state F_B must be nonsingular.") from exc
    if not _matrix_close(F_tot, expected_total):
        raise ValueError(
            "strain_state F_tot must equal inverse(F_B) @ F_A for the "
            "incremental matching partition."
        )
    E_A_rms = _finite_real(
        "strain_state E_A_rms", stored["E_A_rms"], nonnegative=True
    )
    E_B_rms = _finite_real(
        "strain_state E_B_rms", stored["E_B_rms"], nonnegative=True
    )
    _require_scalar_close("strain_state E_A_rms", E_A_rms, _hencky_rms(F_A))
    _require_scalar_close("strain_state E_B_rms", E_B_rms, _hencky_rms(F_B))

    return {
        "schema": STRAIN_STATE_SCHEMA,
        "version": STRAIN_STATE_VERSION,
        "prototype_uid_full": expected_prototype,
        "strain_model_uid": model_uid,
        "strain_alpha": expected_alpha,
        "deformation_scope": STRAIN_STATE_DEFORMATION_SCOPE,
        "deformation_accounting_policy": SLAB_DEFORMATION_ACCOUNTING_POLICY,
        "deformation_accounting_version": SLAB_DEFORMATION_ACCOUNTING_VERSION,
        "F_tot": F_tot.tolist(),
        "F_A": F_A.tolist(),
        "F_B": F_B.tolist(),
        "E_A_rms": E_A_rms,
        "E_B_rms": E_B_rms,
    }


def strain_state_from_current_object(
    value: Any,
    *,
    prototype_uid_full: str,
    strain_alpha: float,
) -> dict[str, Any]:
    """Convert a current in-memory kernel object or validate a current mapping.

    Mapping inputs are treated as persisted representations and therefore must
    already use the exact schema.  Attribute-based conversion is reserved for
    the current in-memory :class:`calm.interface.results.StrainState` boundary.
    """

    if isinstance(value, Mapping):
        return canonical_strain_state(
            value,
            prototype_uid_full=prototype_uid_full,
            strain_alpha=strain_alpha,
        )

    required_attributes = (
        "prototype_uid",
        "strain_model_uid",
        "F_tot",
        "F_A",
        "F_B",
        "E_A_rms",
        "E_B_rms",
    )
    missing = [name for name in required_attributes if not hasattr(value, name)]
    if missing:
        raise TypeError(
            "strain_state must be an exact-current persisted mapping or the "
            "current in-memory StrainState object; missing attribute(s): "
            + ", ".join(missing)
            + "."
        )

    raw = getattr(value, "raw", None)
    raw_alpha = getattr(raw, "alpha", None)
    if raw_alpha is not None:
        current_alpha = _finite_real("in-memory strain_state raw.alpha", raw_alpha)
        expected_alpha = _finite_real("strain_alpha", strain_alpha)
        if current_alpha != expected_alpha:
            raise ValueError(
                "In-memory strain_state alpha does not match the derived-interface "
                "strain_alpha."
            )

    payload = {
        "schema": STRAIN_STATE_SCHEMA,
        "version": STRAIN_STATE_VERSION,
        "prototype_uid_full": getattr(value, "prototype_uid"),
        "strain_model_uid": getattr(value, "strain_model_uid"),
        "strain_alpha": strain_alpha,
        "deformation_scope": STRAIN_STATE_DEFORMATION_SCOPE,
        "deformation_accounting_policy": SLAB_DEFORMATION_ACCOUNTING_POLICY,
        "deformation_accounting_version": SLAB_DEFORMATION_ACCOUNTING_VERSION,
        "F_tot": getattr(value, "F_tot"),
        "F_A": getattr(value, "F_A"),
        "F_B": getattr(value, "F_B"),
        "E_A_rms": getattr(value, "E_A_rms"),
        "E_B_rms": getattr(value, "E_B_rms"),
    }
    return canonical_strain_state(
        payload,
        prototype_uid_full=prototype_uid_full,
        strain_alpha=strain_alpha,
    )


__all__ = [
    "STRAIN_STATE_DEFORMATION_SCOPE",
    "STRAIN_STATE_SCHEMA",
    "STRAIN_STATE_VERSION",
    "canonical_strain_state",
    "strain_state_from_current_object",
]
