"""Import-light contract for relaxed isolated-surface references."""

from __future__ import annotations

from typing import Any, Mapping

from calm.project.domain.contracts.relaxation import (
    canonical_relaxation_controls,
    exact_nonnegative_integer,
    finite_nonnegative_real,
    finite_positive_real,
)

RELAXED_SURFACE_PROTOCOL = "cleaved_fixed_cell_independent_relaxation_v1"
RELAXED_SURFACE_REFERENCE_KINDS = (
    "relaxed_surface_a",
    "relaxed_surface_b",
)


def canonical_surface_relaxation_settings(
    value: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return the fixed-cell controls for one isolated-surface relaxation."""

    settings = dict(value or {})
    fmax = settings.get("fmax", 0.05)
    steps = settings.get("steps", 500)
    relax_cell = settings.get("relax_cell", False)
    if relax_cell is not False:
        raise ValueError(
            "Relaxed isolated-surface references require fixed-cell relaxation; "
            "relax_cell must be False."
        )
    controls = canonical_relaxation_controls(
        protocol="ionic_positions_v1",
        convergence={"force_tol": fmax},
        max_steps=steps,
        relax_cell=relax_cell,
    )
    return {
        "protocol": RELAXED_SURFACE_PROTOCOL,
        "optimizer": controls.optimizer,
        "fmax": controls.force_tolerance_eV_per_A,
        "steps": controls.max_steps,
        "relax_cell": False,
    }


def canonical_surface_partition(
    *,
    n_total: Any,
    n_side_a: Any,
    n_side_b: Any,
) -> tuple[int, int]:
    """Validate the ordered A/B atom partition inherited from construction."""

    total = exact_nonnegative_integer("Total interface atom count", n_total)
    a = exact_nonnegative_integer("Side-A atom count", n_side_a)
    b = exact_nonnegative_integer("Side-B atom count", n_side_b)
    if a < 1 or b < 1:
        raise ValueError(
            "Each isolated-surface reference must contain at least one atom."
        )
    if a + b != total:
        raise ValueError(
            "The relaxed interface atom count does not match the authoritative "
            f"ordered slab partition: {a} + {b} != {total}."
        )
    return a, b


def _require_relaxed_surface_authority(summary: Mapping[str, Any]) -> None:
    """Validate the fixed scientific protocol fields in one certificate."""

    if summary.get("scientific_authority") != "calculator_backed":
        raise ValueError(
            "Relaxed surface references require calculator-backed relaxation."
        )
    if summary.get("converged") is not True:
        raise ValueError("Relaxed surface reference did not satisfy convergence.")
    if summary.get("relax_cell") is not False:
        raise ValueError("Relaxed surface references must preserve the fixed cell.")
    if summary.get("protocol") != RELAXED_SURFACE_PROTOCOL:
        raise ValueError("Relaxed surface reference uses an unsupported protocol.")
    if summary.get("optimizer") != "ASE.BFGS":
        raise ValueError("Relaxed surface reference must use ASE.BFGS.")


def _certificate_fmax(
    summary: Mapping[str, Any],
    *,
    expected: Mapping[str, Any],
) -> float:
    """Return and verify the requested force threshold in one certificate."""

    fmax = finite_positive_real(
        "Relaxed surface reference certificate fmax",
        summary.get("fmax"),
    )
    if fmax != float(expected["fmax"]):
        raise ValueError(
            "Relaxed surface reference certificate does not match requested fmax."
        )
    return fmax


def _certificate_step_counts(
    summary: Mapping[str, Any],
    *,
    expected: Mapping[str, Any],
) -> tuple[int, int]:
    """Return and verify the requested and completed step counts."""

    requested_steps = exact_nonnegative_integer(
        "Relaxed surface requested step count",
        summary.get("steps"),
    )
    if requested_steps != int(expected["steps"]):
        raise ValueError(
            "Relaxed surface reference certificate does not match requested steps."
        )
    completed_steps = exact_nonnegative_integer(
        "Relaxed surface completed step count",
        summary.get("n_steps"),
    )
    if completed_steps > requested_steps:
        raise ValueError(
            "Relaxed surface completed step count exceeds the requested budget."
        )
    return requested_steps, completed_steps


def _validate_terminal_force(
    summary: Mapping[str, Any],
    *,
    fmax: float,
) -> None:
    """Validate the recomputed terminal atomic-force certificate."""

    max_force = finite_nonnegative_real(
        "Relaxed surface reference certificate maximum force",
        summary.get("max_force_eV_per_A"),
    )
    threshold = fmax * (1.0 + 1e-10)
    if max_force > threshold:
        raise ValueError(
            "Relaxed surface reference maximum force exceeds the requested fmax."
        )
    reason = summary.get("termination_reason")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("Relaxed surface reference is missing a termination reason.")


def validate_relaxed_surface_summary(
    value: Mapping[str, Any] | None,
    *,
    settings: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate one calculator-backed fixed-cell surface-relaxation certificate."""

    if not isinstance(value, Mapping):
        raise ValueError(
            "Relaxed surface reference computation is missing a relaxation certificate."
        )
    summary = dict(value)
    expected = canonical_surface_relaxation_settings(settings)
    _require_relaxed_surface_authority(summary)
    fmax = _certificate_fmax(summary, expected=expected)
    _certificate_step_counts(summary, expected=expected)
    _validate_terminal_force(summary, fmax=fmax)
    return summary


__all__ = [
    "RELAXED_SURFACE_PROTOCOL",
    "RELAXED_SURFACE_REFERENCE_KINDS",
    "canonical_surface_partition",
    "canonical_surface_relaxation_settings",
    "validate_relaxed_surface_summary",
]
