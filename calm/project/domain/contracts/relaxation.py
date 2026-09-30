"""Dependency-light contracts for structural relaxation.

This module owns the numerical and representation invariants shared by public
settings, the persisted interface-relaxation backend, and lightweight tests.
It deliberately avoids importing ASE so the mathematical boundary remains
executable in minimal environments.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from numbers import Integral, Real
from typing import Any, Mapping

import numpy as np

FIXED_CELL_PROTOCOL = "ionic_positions_v1"
INTERFACE_CELL_PROTOCOL = "ionic_cell_v1"
PERSISTED_OPTIMIZER = "BFGS"
PERSISTED_CELL_FILTER = "FrechetCellFilter"
PERSISTED_CELL_FACTOR_MODE = "n_atoms"
INTERFACE_CELL_MASK = (True, True, False, False, False, True)
_RELATIVE_TOLERANCE = 1e-10
_FORCE_CERTIFICATE_RELATIVE_TOLERANCE = 1e-12


@dataclass(frozen=True)
class RelaxationControls:
    """Canonical operational controls for one persisted relaxation."""

    protocol: str
    force_tolerance_eV_per_A: float
    max_steps: int
    relax_cell: bool
    optimizer: str = PERSISTED_OPTIMIZER
    cell_filter: str | None = None
    cell_mask: tuple[bool, ...] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "protocol": self.protocol,
            "force_tolerance_eV_per_A": self.force_tolerance_eV_per_A,
            "max_steps": self.max_steps,
            "relax_cell": self.relax_cell,
            "optimizer": self.optimizer,
            "cell_filter": self.cell_filter,
            "cell_mask": list(self.cell_mask) if self.cell_mask is not None else None,
        }


def finite_positive_real(name: str, value: object) -> float:
    """Return one finite positive real scalar without Boolean coercion."""

    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        raise TypeError(f"{name} must be a finite positive real number.")
    number = float(value)
    if not isfinite(number) or number <= 0.0:
        raise ValueError(f"{name} must be a finite positive real number.")
    return number


def finite_nonnegative_real(name: str, value: object) -> float:
    """Return one finite nonnegative real scalar without Boolean coercion."""

    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        raise TypeError(f"{name} must be a finite nonnegative real number.")
    number = float(value)
    if not isfinite(number) or number < 0.0:
        raise ValueError(f"{name} must be a finite nonnegative real number.")
    return number


def exact_positive_integer(name: str, value: object) -> int:
    """Return one exact positive integer without float or Boolean coercion."""

    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral):
        raise TypeError(f"{name} must be a positive integer.")
    integer = int(value)
    if integer < 1:
        raise ValueError(f"{name} must be a positive integer.")
    return integer


def exact_nonnegative_integer(name: str, value: object) -> int:
    """Return one exact nonnegative integer without float or Boolean coercion."""

    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral):
        raise TypeError(f"{name} must be a nonnegative integer.")
    integer = int(value)
    if integer < 0:
        raise ValueError(f"{name} must be a nonnegative integer.")
    return integer


def exact_bool(name: str, value: object) -> bool:
    """Return one explicit Boolean setting without truthiness coercion."""

    if not isinstance(value, (bool, np.bool_)):
        raise TypeError(f"{name} must be a bool.")
    return bool(value)


def canonical_optimizer_name(value: object) -> str:
    """Return one supported public convenience-optimizer identifier."""

    if not isinstance(value, str) or not value.strip():
        raise TypeError("optimizer must be a non-empty string.")
    if value != value.strip():
        raise ValueError("optimizer must not contain surrounding whitespace.")
    if value not in {"BFGS", "LBFGS", "FIRE"}:
        raise ValueError("optimizer must be one of 'BFGS', 'LBFGS', or 'FIRE'.")
    return value


def canonical_relaxation_controls(
    *,
    protocol: object,
    convergence: Mapping[str, Any] | None,
    max_steps: object,
    relax_cell: object,
) -> RelaxationControls:
    """Validate and canonicalize persisted interface-relaxation controls."""

    cell = exact_bool("relax_cell", relax_cell)
    if not isinstance(protocol, str) or not protocol:
        raise TypeError("Relaxation protocol must be a non-empty string.")
    if protocol != protocol.strip():
        raise ValueError("Relaxation protocol must not contain surrounding whitespace.")
    requested = protocol
    expected = INTERFACE_CELL_PROTOCOL if cell else FIXED_CELL_PROTOCOL
    if requested != expected:
        raise ValueError(
            f"Relaxation protocol {requested!r} is incompatible with "
            f"relax_cell={cell}; expected {expected!r}."
        )

    convergence_dict = dict(convergence or {"force_tol": 0.05})
    unknown = sorted(set(convergence_dict) - {"force_tol"})
    if unknown:
        raise ValueError(
            "Unsupported relaxation convergence control(s): " + ", ".join(unknown)
        )
    fmax = finite_positive_real(
        "Relaxation force tolerance",
        convergence_dict.get("force_tol", 0.05),
    )
    steps = exact_positive_integer("Relaxation max_steps", max_steps)
    return RelaxationControls(
        protocol=expected,
        force_tolerance_eV_per_A=fmax,
        max_steps=steps,
        relax_cell=cell,
        cell_filter=PERSISTED_CELL_FILTER if cell else None,
        cell_mask=INTERFACE_CELL_MASK if cell else None,
    )


def finite_vector_array(
    name: str,
    value: object,
    *,
    rows: int | None = None,
) -> np.ndarray:
    """Return one finite ``(N, 3)`` vector array."""

    try:
        array = np.asarray(value, dtype=float)
    except (TypeError, ValueError, OverflowError) as exc:
        raise TypeError(f"{name} must be a finite numeric (N, 3) array.") from exc
    if array.ndim != 2 or array.shape[1:] != (3,):
        raise ValueError(f"{name} must have shape (N, 3); got {array.shape}.")
    if rows is not None and array.shape[0] != rows:
        raise ValueError(f"{name} must contain {rows} rows; got {array.shape[0]}.")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} must contain only finite values.")
    return array


def finite_cell_matrix(name: str, value: object) -> np.ndarray:
    """Return one finite row-oriented 3x3 cell matrix."""

    try:
        cell = np.asarray(value, dtype=float)
    except (TypeError, ValueError, OverflowError) as exc:
        raise TypeError(f"{name} must be a finite numeric 3x3 matrix.") from exc
    if cell.shape != (3, 3):
        raise ValueError(f"{name} must have shape (3, 3); got {cell.shape}.")
    if not np.isfinite(cell).all():
        raise ValueError(f"{name} must contain only finite values.")
    return cell


def finite_right_handed_cell(name: str, value: object) -> np.ndarray:
    """Return one finite nonsingular right-handed row-oriented cell."""

    cell = finite_cell_matrix(name, value)
    determinant = float(np.linalg.det(cell))
    scale = max(float(np.linalg.norm(cell, ord=2)), np.finfo(float).tiny)
    floor = np.finfo(float).eps * scale**3 * 32.0
    if not isfinite(determinant) or determinant <= floor:
        raise ValueError(
            f"{name} must be right-handed and nonsingular; "
            f"det={determinant:.6e}, floor={floor:.6e}."
        )
    return cell


def exact_atomic_numbers(name: str, value: object) -> np.ndarray:
    """Return one one-dimensional exact positive integer species array."""

    raw = np.asarray(value, dtype=object)
    if raw.ndim != 1:
        raise ValueError(f"{name} must be one-dimensional; got {raw.shape}.")
    out: list[int] = []
    for index, item in enumerate(raw.tolist()):
        if isinstance(item, (bool, np.bool_)) or not isinstance(item, Integral):
            raise TypeError(f"{name}[{index}] must be an exact positive integer.")
        integer = int(item)
        if integer < 1:
            raise ValueError(f"{name}[{index}] must be an exact positive integer.")
        out.append(integer)
    return np.asarray(out, dtype=np.int64)


def exact_pbc3(name: str, value: object) -> np.ndarray:
    """Return one explicit three-component periodicity mask."""

    raw = np.asarray(value, dtype=object)
    if raw.shape != (3,):
        raise ValueError(f"{name} must have shape (3,); got {raw.shape}.")
    out: list[bool] = []
    for index, item in enumerate(raw.tolist()):
        if not isinstance(item, (bool, np.bool_)):
            raise TypeError(f"{name}[{index}] must be a bool.")
        out.append(bool(item))
    return np.asarray(out, dtype=bool)


def max_vector_norm(name: str, value: object, *, rows: int | None = None) -> float:
    """Return the largest Euclidean row norm of one finite vector array."""

    vectors = finite_vector_array(name, value, rows=rows)
    if vectors.shape[0] == 0:
        return 0.0
    result = float(np.linalg.norm(vectors, axis=1).max())
    return finite_nonnegative_real(name, result)


def validate_relaxed_structure_transition(  # noqa: C901
    *,
    initial_positions: object,
    final_positions: object,
    initial_cell: object,
    final_cell: object,
    initial_numbers: object,
    final_numbers: object,
    initial_pbc: object,
    final_pbc: object,
    cell_mode: object,
) -> dict[str, float]:
    """Validate the representation invariants of one relaxed structure.

    ``cell_mode`` is ``"fixed"``, ``"interface_in_plane"``, or ``"full"``.
    """

    if not isinstance(cell_mode, str):
        raise TypeError("cell_mode must be a string.")
    mode = cell_mode.strip().lower()
    if mode not in {"fixed", "interface_in_plane", "full"}:
        raise ValueError("cell_mode must be 'fixed', 'interface_in_plane', or 'full'.")
    numbers_initial = exact_atomic_numbers("initial atomic numbers", initial_numbers)
    numbers_final = exact_atomic_numbers("final atomic numbers", final_numbers)
    if not np.array_equal(numbers_initial, numbers_final):
        raise ValueError(
            "Structural relaxation must preserve atom count and species order."
        )
    n_atoms = int(numbers_initial.size)
    if n_atoms < 1:
        raise ValueError("Structural relaxation requires at least one atom.")
    positions_initial = finite_vector_array(
        "initial positions",
        initial_positions,
        rows=n_atoms,
    )
    positions_final = finite_vector_array(
        "final positions",
        final_positions,
        rows=n_atoms,
    )
    pbc_initial = exact_pbc3("initial pbc", initial_pbc)
    pbc_final = exact_pbc3("final pbc", final_pbc)
    if not np.array_equal(pbc_initial, pbc_final):
        raise ValueError("Structural relaxation must preserve periodic-boundary flags.")

    cell_initial = finite_cell_matrix("initial cell", initial_cell)
    cell_final = finite_cell_matrix("final cell", final_cell)
    if mode != "fixed" or bool(np.any(pbc_initial)):
        cell_initial = finite_right_handed_cell("initial cell", cell_initial)
        cell_final = finite_right_handed_cell("final cell", cell_final)
    scale = max(
        float(np.linalg.norm(cell_initial, ord=2)),
        float(np.linalg.norm(cell_final, ord=2)),
        1.0,
    )
    tolerance = _RELATIVE_TOLERANCE * scale
    if mode == "fixed":
        if not np.allclose(cell_final, cell_initial, rtol=0.0, atol=tolerance):
            raise ValueError("Fixed-cell relaxation changed the simulation cell.")
    elif mode == "interface_in_plane":
        if not np.allclose(
            cell_final[2],
            cell_initial[2],
            rtol=0.0,
            atol=tolerance,
        ):
            raise ValueError(
                "Interface cell relaxation changed the interface-normal cell vector."
            )
        if not np.allclose(
            cell_final[:2, 2],
            cell_initial[:2, 2],
            rtol=0.0,
            atol=tolerance,
        ):
            raise ValueError(
                "Interface cell relaxation introduced out-of-plane coupling."
            )

    displacement = positions_final - positions_initial
    return {
        "initial_volume_A3": float(np.linalg.det(cell_initial)),
        "final_volume_A3": float(np.linalg.det(cell_final)),
        "cell_change_frobenius_A": float(np.linalg.norm(cell_final - cell_initial)),
        "max_cartesian_displacement_A": (
            float(np.linalg.norm(displacement, axis=1).max()) if n_atoms else 0.0
        ),
    }


def validate_relaxation_result(
    *,
    final_energy_eV: object,
    n_steps: object,
    max_steps: object,
    converged: object,
    max_atomic_force_eV_per_A: object,
    max_optimizer_residual: object,
    force_tolerance_eV_per_A: object,
) -> dict[str, Any]:
    """Validate one backend result and return its convergence certificate."""

    if isinstance(final_energy_eV, (bool, np.bool_)) or not isinstance(
        final_energy_eV,
        Real,
    ):
        raise TypeError("Relaxation final energy must be a finite real number.")
    energy = float(final_energy_eV)
    if not isfinite(energy):
        raise ValueError("Relaxation final energy must be finite.")

    steps = exact_nonnegative_integer("Relaxation n_steps", n_steps)
    limit = exact_positive_integer("Relaxation max_steps", max_steps)
    if steps > limit:
        raise ValueError("Relaxation n_steps cannot exceed max_steps.")
    converged_value = exact_bool("Relaxation converged", converged)
    max_atomic = finite_nonnegative_real(
        "Relaxation maximum atomic force",
        max_atomic_force_eV_per_A,
    )
    max_generalized = finite_nonnegative_real(
        "Relaxation maximum optimizer residual",
        max_optimizer_residual,
    )
    tolerance = finite_positive_real(
        "Relaxation force tolerance",
        force_tolerance_eV_per_A,
    )
    threshold = tolerance * (1.0 + _FORCE_CERTIFICATE_RELATIVE_TOLERANCE)
    residual_satisfied = max_generalized <= threshold
    if converged_value and not residual_satisfied:
        raise ValueError(
            "Relaxation backend reported convergence but the recomputed "
            "optimizer residual exceeds the requested force tolerance."
        )
    if residual_satisfied and converged_value:
        termination_reason = "converged"
    elif residual_satisfied:
        termination_reason = "residual_satisfied_after_optimizer_stop"
    else:
        termination_reason = "maximum_steps_or_force_tolerance_not_satisfied"
    return {
        "converged": residual_satisfied,
        "optimizer_reported_converged": converged_value,
        "residual_satisfied": residual_satisfied,
        "final_energy_eV": energy,
        "n_steps": steps,
        "max_steps": limit,
        "force_tolerance_eV_per_A": tolerance,
        "max_atomic_force_eV_per_A": max_atomic,
        "max_optimizer_residual": max_generalized,
        "termination_reason": termination_reason,
    }
