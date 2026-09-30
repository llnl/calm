"""Validation utilities for ASE ``Atoms`` objects used by CALM I/O."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any


class ValidationError(ValueError):
    """Raised when an ASE ``Atoms`` validation check fails."""


def validate_atoms(
    atoms: Any,
    *,
    expected_pbc: Sequence[bool] | None = None,
    min_volume: float = 1e-10,
    check_finite_positions: bool = True,
    allow_empty: bool = False,
    context: str = "",
) -> None:
    """Validate the structural conditions required by CALM file I/O.

    Parameters
    ----------
    atoms
        ASE ``Atoms`` object to validate.
    expected_pbc
        Optional exact three-axis periodic-boundary condition.
    min_volume
        Minimum allowed cell volume in cubic angstroms.
    check_finite_positions
        Whether Cartesian positions must all be finite.
    allow_empty
        Whether a zero-atom structure is accepted.
    context
        Optional description included in failure messages.
    """

    try:
        from ase import Atoms
    except ImportError as exc:  # pragma: no cover - ASE is an optional dependency
        raise RuntimeError(
            "ASE is required for atoms validation. Install with `pip install ase`."
        ) from exc

    ctx = f" for {context}" if context else ""
    if not isinstance(atoms, Atoms):
        raise ValidationError(
            f"Expected ase.Atoms object{ctx}, got {type(atoms).__name__}"
        )

    if len(atoms) == 0 and not allow_empty:
        raise ValidationError(
            "Atoms object is empty (no atoms)" + (ctx if ctx else ".")
        )

    if len(atoms) > 0:
        try:
            volume = float(atoms.cell.volume)
        except Exception as exc:
            raise ValidationError(f"Failed to compute cell volume{ctx}: {exc}") from exc
        if volume < min_volume:
            raise ValidationError(
                f"Cell volume {volume:.2e} A^3 is too small" + (ctx if ctx else ".")
            )

    if expected_pbc is not None:
        if len(expected_pbc) != 3:
            raise ValidationError(
                f"expected_pbc must have length 3{ctx}, got {len(expected_pbc)}"
            )
        actual_pbc = [bool(value) for value in atoms.pbc]
        required_pbc = [bool(value) for value in expected_pbc]
        if actual_pbc != required_pbc:
            raise ValidationError(
                f"PBC mismatch{ctx}: expected {required_pbc}, got {actual_pbc}."
            )

    if check_finite_positions and len(atoms) > 0:
        import numpy as np

        if not np.all(np.isfinite(atoms.get_positions())):
            raise ValidationError(
                "Positions contain NaN or infinite values" + (ctx if ctx else ".")
            )
