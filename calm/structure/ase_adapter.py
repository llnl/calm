"""Current ASE adapters for CALM's column-vector lattice convention.

CALM stores lattice vectors as columns while ASE stores them as rows.  This
module contains only the adapter operations used by current slab and interface
workflows:

- convert a column-basis supercell matrix for ``ase.build.make_supercell``;
- construct an ASE supercell from a column-basis matrix;
- wrap interface coordinates in-plane without wrapping through the slab normal.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:  # pragma: no cover
    from ase import Atoms  # type: ignore


def supercell_matrix_ase_from_col(P_col: np.ndarray) -> np.ndarray:
    """Return the ASE row-basis transform corresponding to ``P_col``.

    CALM applies a column-basis supercell matrix as ``A'_col = A_col @ P``.
    ASE applies its row-basis transform as ``A'_row = P_row @ A_row``.  The two
    representations therefore satisfy ``P_row = P_col.T``.
    """

    matrix = np.asarray(P_col, dtype=int)
    if matrix.shape != (3, 3):
        raise ValueError(f"P must be shape (3,3); got {matrix.shape}")
    return matrix.T


def make_supercell_col(
    atoms: "Atoms", P_col: np.ndarray, *, wrap: bool = True
) -> "Atoms":
    """Call :func:`ase.build.make_supercell` with a column-basis transform."""

    from ase.build import make_supercell as ase_make_supercell  # type: ignore

    matrix_row = supercell_matrix_ase_from_col(P_col)
    return ase_make_supercell(atoms, matrix_row, wrap=wrap)


def wrap_xy_clamp_z(atoms: "Atoms", *, eps: float = 1.0e-8) -> None:
    """Wrap fractional x/y coordinates and clamp z without periodic wrapping.

    Small negative z drift must not wrap atoms to the opposite side of a
    periodic two-interface model.  The operation therefore wraps only the
    in-plane fractional coordinates and clamps z into ``[0, 1)``.
    """

    scaled = np.asarray(atoms.get_scaled_positions(wrap=False), dtype=float)
    if scaled.ndim != 2 or scaled.shape[1] != 3:
        raise ValueError(
            f"Expected scaled positions with shape (N, 3); got {scaled.shape}"
        )

    scaled[:, :2] = np.mod(scaled[:, :2], 1.0)

    upper = 1.0 - float(eps)
    if not np.isfinite(upper) or upper <= 0.0:
        upper = 1.0
    scaled[:, 2] = np.clip(scaled[:, 2], 0.0, upper)
    atoms.set_scaled_positions(scaled)
