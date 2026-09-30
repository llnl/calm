"""Explicit 2D matrix conventions shared by claim-oriented adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


BASIS_VECTOR_STORAGE = "columns"
SUPERCELL_CONVENTION = "S = A @ N"
CARTESIAN_DIMENSION = 2


def _matrix2(value: Any, *, name: str) -> np.ndarray:
    matrix = np.asarray(value, dtype=float)
    if matrix.shape != (2, 2):
        raise ValueError(f"{name} must have shape (2, 2), got {matrix.shape}")
    if not np.isfinite(matrix).all():
        raise ValueError(f"{name} must contain only finite values")
    return matrix


def column_basis(value: Any, *, name: str = "basis") -> np.ndarray:
    """Validate a 2D basis whose vectors are stored as columns."""

    basis = _matrix2(value, name=name)
    determinant = float(np.linalg.det(basis))
    if abs(determinant) <= np.finfo(float).eps:
        raise ValueError(f"{name} must be nonsingular")
    return basis


def row_vectors_to_column_basis(value: Any) -> np.ndarray:
    """Convert an external row-vector array to CALM's column-basis convention."""

    return column_basis(_matrix2(value, name="row_vectors").T)


def column_basis_to_row_vectors(value: Any) -> np.ndarray:
    """Convert a CALM column basis to a row-vector array."""

    return column_basis(value).T.copy()


def integer_transform(value: Any, *, name: str = "transform") -> np.ndarray:
    """Validate an exact nonsingular 2x2 integer transformation."""

    array = np.asarray(value)
    if array.shape != (2, 2):
        raise ValueError(f"{name} must have shape (2, 2), got {array.shape}")
    if not np.issubdtype(array.dtype, np.integer):
        rounded = np.rint(np.asarray(array, dtype=float))
        if not np.array_equal(np.asarray(array, dtype=float), rounded):
            raise ValueError(f"{name} must contain exact integer entries")
        array = rounded.astype(np.int64)
    else:
        array = array.astype(np.int64, copy=False)
    determinant = int(round(float(np.linalg.det(array))))
    if determinant == 0:
        raise ValueError(f"{name} must be nonsingular")
    return array


def apply_integer_transform(basis: Any, transform: Any) -> np.ndarray:
    """Construct ``S = A @ N`` with basis vectors stored as columns."""

    return column_basis(basis) @ integer_transform(transform)


def gram_matrix(basis: Any) -> np.ndarray:
    """Return ``A.T @ A`` for a column-basis matrix."""

    matrix = column_basis(basis)
    return matrix.T @ matrix


def oriented_area(basis: Any) -> float:
    """Return the signed area of a column-basis matrix."""

    return float(np.linalg.det(column_basis(basis)))


@dataclass(frozen=True)
class TransformationReconstruction:
    """Verified integer source transformation reconstructed from ``A`` and ``S``."""

    success: bool
    integer_matrix: tuple[tuple[int, int], tuple[int, int]]
    determinant: int
    source_index: int
    orientation_sign: int
    maximum_absolute_residual: float
    relative_residual: float
    atol: float
    rtol: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "integer_matrix": [list(row) for row in self.integer_matrix],
            "determinant": self.determinant,
            "source_index": self.source_index,
            "orientation_sign": self.orientation_sign,
            "maximum_absolute_residual": self.maximum_absolute_residual,
            "relative_residual": self.relative_residual,
            "atol": self.atol,
            "rtol": self.rtol,
        }


def _embedded_column_basis(value: Any, *, name: str) -> np.ndarray:
    matrix = np.asarray(value, dtype=float)
    if matrix.ndim != 2 or matrix.shape[1] != 2 or matrix.shape[0] < 2:
        raise ValueError(
            f"{name} must have shape (d, 2) with d >= 2, got {matrix.shape}"
        )
    if not np.isfinite(matrix).all():
        raise ValueError(f"{name} must contain only finite values")
    if np.linalg.matrix_rank(matrix) != 2:
        raise ValueError(f"{name} must have column rank 2")
    return matrix


def _reconstruct_from_embedded_columns(
    basis: Any,
    supercell: Any,
    *,
    atol: float,
    rtol: float,
) -> TransformationReconstruction:
    if atol < 0 or rtol < 0:
        raise ValueError("atol and rtol must be nonnegative")
    A = _embedded_column_basis(basis, name="basis")
    S = _embedded_column_basis(supercell, name="supercell")
    if A.shape != S.shape:
        raise ValueError(
            "basis and supercell must have the same embedded Cartesian shape; "
            f"got {A.shape} and {S.shape}"
        )
    floating, _, rank, _ = np.linalg.lstsq(A, S, rcond=None)
    if rank != 2:
        raise ValueError("basis must have column rank 2")
    rounded = np.rint(floating).astype(np.int64)
    reconstructed = A @ rounded
    residual = reconstructed - S
    maximum_absolute_residual = float(np.max(np.abs(residual)))
    scale = max(float(np.linalg.norm(S, ord="fro")), np.finfo(float).tiny)
    relative_residual = float(np.linalg.norm(residual, ord="fro") / scale)
    success = bool(np.allclose(reconstructed, S, atol=atol, rtol=rtol))
    determinant = int(round(float(np.linalg.det(rounded))))
    orientation_sign = 0 if determinant == 0 else (1 if determinant > 0 else -1)
    return TransformationReconstruction(
        success=success,
        integer_matrix=(
            (int(rounded[0, 0]), int(rounded[0, 1])),
            (int(rounded[1, 0]), int(rounded[1, 1])),
        ),
        determinant=determinant,
        source_index=abs(determinant),
        orientation_sign=orientation_sign,
        maximum_absolute_residual=maximum_absolute_residual,
        relative_residual=relative_residual,
        atol=float(atol),
        rtol=float(rtol),
    )


def reconstruct_integer_transform(
    basis: Any,
    supercell: Any,
    *,
    atol: float = 1.0e-8,
    rtol: float = 1.0e-8,
) -> TransformationReconstruction:
    """Reconstruct and verify ``N`` from the 2D relation ``S = A @ N``."""

    A = column_basis(basis)
    S = column_basis(supercell, name="supercell")
    return _reconstruct_from_embedded_columns(
        A,
        S,
        atol=atol,
        rtol=rtol,
    )


def reconstruct_integer_transform_from_row_vectors(
    primitive_vectors: Any,
    superlattice_vectors: Any,
    *,
    atol: float = 1.0e-8,
    rtol: float = 1.0e-8,
) -> TransformationReconstruction:
    """Reconstruct CALM's column-right ``N`` from external row vectors.

    The input arrays may contain two vectors embedded in either two or three
    Cartesian dimensions. If pymatgen writes ``S_rows = T @ A_rows``, the
    returned matrix is the equivalent CALM map ``N = T.T`` satisfying
    ``S_columns = A_columns @ N``.
    """

    primitive = np.asarray(primitive_vectors, dtype=float)
    superlattice = np.asarray(superlattice_vectors, dtype=float)
    if primitive.ndim != 2 or primitive.shape[0] != 2:
        raise ValueError(
            "primitive_vectors must contain exactly two row vectors; "
            f"got {primitive.shape}"
        )
    if superlattice.shape != primitive.shape:
        raise ValueError(
            "superlattice_vectors must match primitive_vectors shape; "
            f"got {superlattice.shape} and {primitive.shape}"
        )
    return _reconstruct_from_embedded_columns(
        primitive.T,
        superlattice.T,
        atol=atol,
        rtol=rtol,
    )
