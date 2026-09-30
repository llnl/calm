"""Geometry utilities for two-dimensional lattices."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int64]
IndexRange = tuple[int, int]


@dataclass(frozen=True)
class GaussReductionResult:
    """Result of two-dimensional Gauss reduction and gauge fixing.

    The original basis vectors are stored as columns. The returned arrays obey

    ``reduced_basis = original_basis @ integer_transform``

    and

    ``gauged_basis = rotation @ reduced_basis``.

    ``integer_transform`` is unimodular, so the reduced basis generates the
    same lattice as the original basis. ``rotation`` is a proper Cartesian
    rotation. The gauged basis is right handed, its first vector is a shortest
    lattice vector, and that vector lies along the positive x-axis.
    """

    original_basis: FloatArray
    reduced_basis: FloatArray
    gauged_basis: FloatArray
    integer_transform: IntArray
    rotation: FloatArray
    iterations: int

    @property
    def basis(self) -> FloatArray:
        """Alias for :attr:`gauged_basis`."""
        return self.gauged_basis

    def rotate_basis(self, basis: ArrayLike) -> FloatArray:
        """Apply the gauge rotation to another column-oriented 2D basis.

        This is the operation to use for an associated primitive basis when the
        reduced object is a supercell basis. The Gauss integer transform is not
        applied to the primitive basis.
        """
        return self.rotation @ as_basis(basis)

    def rotate_points(self, points: ArrayLike) -> FloatArray:
        """Apply the gauge rotation to Cartesian points with shape ``(n, 2)``."""
        array = np.asarray(points, dtype=float)

        if array.ndim != 2 or array.shape[1] != 2:
            raise ValueError(
                "points must have shape (number_of_points, 2); "
                f"received {array.shape}."
            )

        if not np.all(np.isfinite(array)):
            raise ValueError("points must contain only finite values.")

        return (self.rotation @ array.T).T


def as_basis(basis: ArrayLike, *, name: str = "basis") -> FloatArray:
    """Return a validated 2x2 basis with basis vectors stored as columns."""
    array = np.asarray(basis, dtype=float)

    if array.shape != (2, 2):
        raise ValueError(f"{name} must have shape (2, 2); received {array.shape}.")

    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must contain only finite values.")

    if np.isclose(np.linalg.det(array), 0.0):
        raise ValueError(f"{name} must contain linearly independent vectors.")

    return array


def as_point(point: ArrayLike, *, name: str = "point") -> FloatArray:
    """Return a validated two-component Cartesian point."""
    array = np.asarray(point, dtype=float)

    if array.shape != (2,):
        raise ValueError(f"{name} must have shape (2,); received {array.shape}.")

    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must contain only finite values.")

    return array


def as_cell_index(cell_index: Sequence[int] | ArrayLike) -> NDArray[np.int64]:
    """Return a validated two-component integer cell index."""
    raw = np.asarray(cell_index)

    if raw.shape != (2,):
        raise ValueError(
            f"cell_index must have shape (2,); received {raw.shape}."
        )

    if not np.issubdtype(raw.dtype, np.integer):
        if not np.all(np.equal(raw, np.round(raw))):
            raise ValueError("cell_index must contain integer values.")

    return raw.astype(np.int64)


def as_index_range(index_range: Sequence[int], *, name: str) -> IndexRange:
    """Return a validated inclusive integer range ``(minimum, maximum)``."""
    if len(index_range) != 2:
        raise ValueError(f"{name} must contain exactly two integers.")

    minimum, maximum = index_range

    if not isinstance(minimum, (int, np.integer)) or not isinstance(
        maximum, (int, np.integer)
    ):
        raise TypeError(f"{name} must contain integers.")

    minimum = int(minimum)
    maximum = int(maximum)

    if minimum > maximum:
        raise ValueError(f"{name} must be ordered as (minimum, maximum).")

    return minimum, maximum


def is_gauss_reduced(
    basis: ArrayLike,
    *,
    rtol: float = 1.0e-12,
    atol: float = 1.0e-14,
) -> bool:
    """Return whether a basis satisfies the 2D Gauss-reduction inequalities.

    For column vectors ``b1`` and ``b2``, the tested conditions are

    ``||b1|| <= ||b2||``

    and

    ``2 |b1 . b2| <= ||b1||^2``.
    """
    basis_array = as_basis(basis)
    _validate_tolerances(rtol=rtol, atol=atol)

    b1 = basis_array[:, 0]
    b2 = basis_array[:, 1]
    norm1_sq = float(b1 @ b1)
    norm2_sq = float(b2 @ b2)
    dot = float(b1 @ b2)
    scale = max(norm1_sq, norm2_sq, 1.0)
    tolerance = atol + rtol * scale

    return (
        norm1_sq <= norm2_sq + tolerance
        and 2.0 * abs(dot) <= norm1_sq + tolerance
    )


def gauss_reduce(
    basis: ArrayLike,
    *,
    rtol: float = 1.0e-12,
    atol: float = 1.0e-14,
    max_iterations: int = 100,
) -> GaussReductionResult:
    """Gauss-reduce a 2D basis and rotate it into a common gauge.

    The basis vectors must be stored as columns. The algorithm performs only
    unimodular integer column operations, so the reduced basis generates the
    same lattice as the input basis. It then chooses a right-handed basis and
    applies a proper Cartesian rotation such that the shortest reduced vector
    is parallel to ``x_hat = (1, 0)`` and points in the positive x direction.

    The gauged basis therefore has the form

    ``[[|b1|, b1.b2/|b1|], [0, det(B)/|b1|]]``

    with positive determinant.

    Parameters
    ----------
    basis
        A nonsingular 2x2 basis with vectors stored as columns.
    rtol, atol
        Relative and absolute tolerances used for reduction comparisons.
    max_iterations
        Safety limit for the Gauss-reduction loop.

    Returns
    -------
    GaussReductionResult
        Reduced and gauged bases together with the exact integer basis change
        and the Cartesian gauge rotation.
    """
    original = as_basis(basis).copy()
    _validate_tolerances(rtol=rtol, atol=atol)

    if not isinstance(max_iterations, (int, np.integer)):
        raise TypeError("max_iterations must be an integer.")
    if max_iterations <= 0:
        raise ValueError("max_iterations must be positive.")

    reduced = original.copy()
    transform = np.eye(2, dtype=np.int64)
    completed_iterations = 0

    for iteration in range(1, int(max_iterations) + 1):
        completed_iterations = iteration
        b1 = reduced[:, 0]
        b2 = reduced[:, 1]
        norm1_sq = float(b1 @ b1)
        norm2_sq = float(b2 @ b2)
        scale = max(norm1_sq, norm2_sq, 1.0)
        comparison_tolerance = atol + rtol * scale

        if norm2_sq < norm1_sq - comparison_tolerance:
            reduced = reduced[:, [1, 0]]
            transform = transform[:, [1, 0]]
            continue

        coefficient = float((b1 @ b2) / norm1_sq)
        rounding_tolerance = (
            16.0
            * np.finfo(float).eps
            * max(1.0, abs(coefficient))
        )
        nearest_integer = int(
            np.floor(coefficient + 0.5 + rounding_tolerance)
        )

        if nearest_integer == 0:
            break

        reduced[:, 1] = reduced[:, 1] - nearest_integer * reduced[:, 0]
        transform[:, 1] = (
            transform[:, 1] - nearest_integer * transform[:, 0]
        )
    else:
        raise RuntimeError(
            "Gauss reduction did not converge within "
            f"{max_iterations} iterations."
        )

    # The lattice is unchanged by reversing one basis vector. Use that freedom
    # to enforce a right-handed reduced cell before applying a proper rotation.
    if np.linalg.det(reduced) < 0.0:
        reduced[:, 1] *= -1.0
        transform[:, 1] *= -1

    b1 = reduced[:, 0]
    shortest_length = float(np.linalg.norm(b1))
    unit_x = b1 / shortest_length
    rotation = np.array(
        [
            [unit_x[0], unit_x[1]],
            [-unit_x[1], unit_x[0]],
        ],
        dtype=float,
    )

    gauged = rotation @ reduced

    # Remove roundoff in the defining gauge constraints without changing the
    # meaningful second-vector components.
    gauged[0, 0] = shortest_length
    gauged[1, 0] = 0.0

    if not is_gauss_reduced(reduced, rtol=rtol, atol=atol):
        raise RuntimeError("Internal error: the returned basis is not Gauss reduced.")

    if np.linalg.det(gauged) <= 0.0:
        raise RuntimeError("Internal error: the gauged basis is not right handed.")

    return GaussReductionResult(
        original_basis=original,
        reduced_basis=reduced,
        gauged_basis=gauged,
        integer_transform=transform,
        rotation=rotation,
        iterations=completed_iterations,
    )


def _validate_tolerances(*, rtol: float, atol: float) -> None:
    """Validate numerical tolerances used by reduction routines."""
    if not np.isfinite(rtol) or rtol < 0.0:
        raise ValueError("rtol must be finite and nonnegative.")
    if not np.isfinite(atol) or atol < 0.0:
        raise ValueError("atol must be finite and nonnegative.")


def cell_origin(
    basis: ArrayLike,
    *,
    origin: ArrayLike = (0.0, 0.0),
    cell_index: Sequence[int] = (0, 0),
) -> FloatArray:
    """Return the Cartesian origin of an indexed basis cell."""
    basis_array = as_basis(basis)
    origin_array = as_point(origin, name="origin")
    index_array = as_cell_index(cell_index)
    return origin_array + basis_array @ index_array


def cell_vertices(
    basis: ArrayLike,
    *,
    origin: ArrayLike = (0.0, 0.0),
    cell_index: Sequence[int] = (0, 0),
) -> FloatArray:
    """Return the four Cartesian vertices of an indexed basis cell.

    The vertices are ordered as ``o``, ``o + a1``, ``o + a1 + a2``, and
    ``o + a2``, where ``o`` is the selected cell origin.
    """
    basis_array = as_basis(basis)
    selected_origin = cell_origin(
        basis_array,
        origin=origin,
        cell_index=cell_index,
    )
    fractional_vertices = np.array(
        [
            [0.0, 1.0, 1.0, 0.0],
            [0.0, 0.0, 1.0, 1.0],
        ]
    )
    return (selected_origin[:, None] + basis_array @ fractional_vertices).T


def cell_centroid(
    basis: ArrayLike,
    *,
    origin: ArrayLike = (0.0, 0.0),
    cell_index: Sequence[int] = (0, 0),
) -> FloatArray:
    """Return the centroid of an indexed basis cell."""
    basis_array = as_basis(basis)
    selected_origin = cell_origin(
        basis_array,
        origin=origin,
        cell_index=cell_index,
    )
    return selected_origin + 0.5 * basis_array.sum(axis=1)


def lattice_sites(
    basis: ArrayLike,
    *,
    i_range: Sequence[int] = (-4, 4),
    j_range: Sequence[int] = (-4, 4),
    origin: ArrayLike = (0.0, 0.0),
) -> FloatArray:
    """Generate lattice sites over inclusive integer-coordinate ranges.

    Parameters
    ----------
    basis
        A 2x2 matrix whose columns are the lattice basis vectors.
    i_range, j_range
        Inclusive integer-coordinate ranges.
    origin
        Cartesian translation applied to every generated site.

    Returns
    -------
    numpy.ndarray
        Array with shape ``(number_of_sites, 2)``.
    """
    basis_array = as_basis(basis)
    origin_array = as_point(origin, name="origin")
    i_min, i_max = as_index_range(i_range, name="i_range")
    j_min, j_max = as_index_range(j_range, name="j_range")

    i_values = np.arange(i_min, i_max + 1)
    j_values = np.arange(j_min, j_max + 1)
    ii, jj = np.meshgrid(i_values, j_values, indexing="ij")
    integer_coordinates = np.vstack((ii.ravel(), jj.ravel()))

    return (origin_array[:, None] + basis_array @ integer_coordinates).T
