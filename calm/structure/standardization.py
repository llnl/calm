"""Dependency-light contracts for bulk standardization and structural identity.

The functions in this module own numerical validation shared by the ASE/spglib
adapter, bulk provenance, and deterministic structure fingerprints.  Keeping
these checks independent of ASE and spglib makes the mathematical boundary
executable in lightweight repository tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from numbers import Integral, Real
from typing import Any

import numpy as np


DEFAULT_SPGLIB_ANGLE_TOLERANCE = -1.0
_CELL_DETERMINANT_RELATIVE_FLOOR = 1e-12


def positive_finite_float(name: str, value: object) -> float:
    """Return one finite positive real scalar.

    Boolean values are rejected even though ``bool`` is an ``int`` subclass.
    """

    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        raise TypeError(f"{name} must be a finite positive real number.")
    number = float(value)
    if not isfinite(number) or number <= 0.0:
        raise ValueError(f"{name} must be a finite positive real number.")
    return number


def exact_bool(name: str, value: object) -> bool:
    """Return one explicit Boolean setting without truthiness coercion."""

    if not isinstance(value, (bool, np.bool_)):
        raise TypeError(f"{name} must be a Boolean value.")
    return bool(value)


def nonnegative_finite_float(name: str, value: object) -> float:
    """Return one finite nonnegative real scalar."""

    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        raise TypeError(f"{name} must be a finite nonnegative real number.")
    number = float(value)
    if not isfinite(number) or number < 0.0:
        raise ValueError(f"{name} must be a finite nonnegative real number.")
    return number


def spglib_angle_tolerance(value: object) -> float:
    """Validate spglib's angle tolerance or its ``-1`` heuristic sentinel."""

    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        raise TypeError(
            "angle_tolerance must be -1 or a finite nonnegative real number."
        )
    number = float(value)
    if not isfinite(number) or (number < 0.0 and number != -1.0):
        raise ValueError(
            "angle_tolerance must be -1 or a finite nonnegative real number."
        )
    return number


def exact_integer(name: str, value: object) -> int:
    """Return one exact integer, rejecting Boolean and nonfinite values."""

    if isinstance(value, (bool, np.bool_)):
        raise TypeError(f"{name} must be an exact integer.")
    if isinstance(value, Integral):
        return int(value)
    if isinstance(value, Real):
        number = float(value)
        if isfinite(number) and number.is_integer():
            return int(number)
        raise ValueError(f"{name} must be an exact integer.")
    raise TypeError(f"{name} must be an exact integer.")


def exact_nonnegative_integer(name: str, value: object) -> int:
    """Return one exact nonnegative integer, rejecting Boolean values."""

    result = exact_integer(name, value)
    if result < 0:
        raise ValueError(f"{name} must be a nonnegative integer.")
    return result


def fingerprint_decimals(value: object) -> int:
    """Validate the decimal precision used by representation fingerprints."""

    result = exact_nonnegative_integer("decimals", value)
    if result > 15:
        raise ValueError("decimals must be between 0 and 15 inclusive.")
    return result


def _finite_array(name: str, value: object, *, shape: tuple[int, ...]) -> np.ndarray:
    try:
        array = np.asarray(value, dtype=float)
    except (TypeError, ValueError, OverflowError) as exc:
        message = f"{name} must be a finite numeric array of shape {shape}."
        raise TypeError(message) from exc
    if array.shape != shape:
        raise ValueError(f"{name} must have shape {shape}; got {array.shape}.")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} must contain only finite values.")
    return array


def finite_cell_rows(value: object) -> np.ndarray:
    """Return a finite nonsingular 3D row-oriented cell matrix."""

    cell = _finite_array("lattice", value, shape=(3, 3))
    scale = max(float(np.linalg.norm(cell, ord=2)), np.finfo(float).tiny)
    determinant = float(np.linalg.det(cell))
    floor = _CELL_DETERMINANT_RELATIVE_FLOOR * scale**3
    if not isfinite(determinant) or abs(determinant) <= floor:
        raise ValueError(
            "lattice must be nonsingular relative to its matrix scale; "
            f"|det|={abs(determinant):.6e}, floor={floor:.6e}."
        )
    return cell


def finite_fractional_positions(value: object) -> np.ndarray:
    """Return one finite ``(N, 3)`` fractional-coordinate array."""

    try:
        positions = np.asarray(value, dtype=float)
    except (TypeError, ValueError, OverflowError) as exc:
        message = "scaled_positions must be a finite numeric (N, 3) array."
        raise TypeError(message) from exc
    if positions.ndim != 2 or positions.shape[1:] != (3,):
        raise ValueError(
            f"scaled_positions must have shape (N, 3); got {positions.shape}."
        )
    if not np.isfinite(positions).all():
        raise ValueError("scaled_positions must contain only finite values.")
    return positions


def exact_type_numbers(
    value: object,
    *,
    n_atoms: int,
    require_positive: bool,
) -> np.ndarray:
    """Return exact integer type labels matching the number of positions."""

    try:
        raw = np.asarray(value, dtype=object)
    except Exception as exc:
        raise TypeError("numbers must be a one-dimensional integer sequence.") from exc
    if raw.ndim != 1 or raw.shape[0] != int(n_atoms):
        raise ValueError(
            "numbers must be one-dimensional with one entry per position; "
            f"got shape {raw.shape} for {n_atoms} positions."
        )

    numbers = [
        _exact_integer_item(
            item,
            name=f"numbers[{index}]",
            require_positive=require_positive,
        )
        for index, item in enumerate(raw.tolist())
    ]
    try:
        return np.asarray(numbers, dtype=np.int64)
    except OverflowError as exc:
        message = "numbers contain an integer outside the supported range."
        raise ValueError(message) from exc


def _exact_integer_item(
    value: object,
    *,
    name: str,
    require_positive: bool,
) -> int:
    if isinstance(value, (bool, np.bool_)):
        raise TypeError(f"{name} must be an exact integer.")
    if isinstance(value, Integral):
        number = int(value)
    elif isinstance(value, Real):
        scalar = float(value)
        if not isfinite(scalar) or not scalar.is_integer():
            raise ValueError(f"{name} must be an exact integer.")
        number = int(scalar)
    else:
        raise TypeError(f"{name} must be an exact integer.")
    if require_positive and number <= 0:
        raise ValueError(f"{name} must be positive.")
    if not require_positive and number < 0:
        raise ValueError(f"{name} must be nonnegative.")
    return number


def exact_pbc3(value: object, *, require_all: bool) -> np.ndarray:
    """Return an explicit three-component periodic-boundary mask."""

    raw = np.asarray(value, dtype=object)
    if raw.shape != (3,):
        raise ValueError(f"pbc must have shape (3,); got {raw.shape}.")
    values: list[bool] = []
    for index, item in enumerate(raw.tolist()):
        if not isinstance(item, (bool, np.bool_)):
            raise TypeError(f"pbc[{index}] must be a Boolean value.")
        values.append(bool(item))
    result = np.asarray(values, dtype=bool)
    if require_all and not bool(np.all(result)):
        raise ValueError(f"spglib cell expects 3D periodicity; pbc={result.tolist()}.")
    return result


def validate_crystal_arrays(
    *,
    lattice: object,
    scaled_positions: object,
    numbers: object,
    pbc: object,
    require_3d_pbc: bool,
    require_positive_numbers: bool,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Validate the representation of one decorated periodic crystal."""

    lattice_array = finite_cell_rows(lattice)
    positions_array = finite_fractional_positions(scaled_positions)
    numbers_array = exact_type_numbers(
        numbers,
        n_atoms=positions_array.shape[0],
        require_positive=require_positive_numbers,
    )
    pbc_array = exact_pbc3(pbc, require_all=require_3d_pbc)
    return lattice_array, positions_array, numbers_array, pbc_array


def wrap_fractional_positions(value: object) -> np.ndarray:
    """Wrap finite fractional coordinates into the half-open unit cube."""

    positions = finite_fractional_positions(value)
    wrapped = np.mod(positions, 1.0)
    wrapped[wrapped == 1.0] = 0.0
    wrapped[wrapped == 0.0] = 0.0  # normalize negative zero
    return wrapped


def rounded_finite_array(value: object, *, decimals: object) -> np.ndarray:
    """Round a finite numeric array and normalize signed zero."""

    precision = fingerprint_decimals(decimals)
    try:
        array = np.asarray(value, dtype=float)
    except (TypeError, ValueError, OverflowError) as exc:
        message = "fingerprint arrays must contain finite numeric values."
        raise TypeError(message) from exc
    if not np.isfinite(array).all():
        raise ValueError("fingerprint arrays must contain only finite values.")
    rounded = np.round(array, decimals=precision)
    rounded[rounded == 0.0] = 0.0
    return rounded


def canonical_fractional_species_rows(
    *,
    scaled_positions: object,
    numbers: object,
    decimals: object,
) -> tuple[np.ndarray, np.ndarray]:
    """Return wrapped, rounded, species-sorted fractional coordinates.

    Coordinates that round to the upper boundary are mapped back to zero so
    periodic equivalents do not receive different fingerprints merely because
    one representation lies infinitesimally below one.
    """

    precision = fingerprint_decimals(decimals)
    wrapped = wrap_fractional_positions(scaled_positions)
    species = exact_type_numbers(
        numbers,
        n_atoms=wrapped.shape[0],
        require_positive=True,
    )
    rounded = np.round(wrapped, decimals=precision)
    rounded[rounded == 1.0] = 0.0
    rounded[rounded == 0.0] = 0.0

    if rounded.shape[0] == 0:
        return rounded, species

    order = np.lexsort(
        (
            rounded[:, 2],
            rounded[:, 1],
            rounded[:, 0],
            species,
        )
    )
    return rounded[order], species[order]


def finite_matrix3(name: str, value: object) -> np.ndarray:
    """Return one finite 3x3 matrix."""

    return _finite_array(name, value, shape=(3, 3))


def exact_integer_matrix3(name: str, value: object) -> np.ndarray:
    """Return one exact 3-by-3 integer matrix without truncation."""

    raw = np.asarray(value, dtype=object)
    if raw.shape != (3, 3):
        raise ValueError(f"{name} must have shape (3, 3); got {raw.shape}.")
    entries = [
        exact_integer(f"{name}[{index}]", item)
        for index, item in enumerate(raw.ravel().tolist())
    ]
    try:
        return np.asarray(entries, dtype=np.int64).reshape(3, 3)
    except OverflowError as exc:
        raise ValueError(
            f"{name} contains an integer outside the supported range."
        ) from exc


def finite_vector3(name: str, value: object) -> np.ndarray:
    """Return one finite three-vector."""

    return _finite_array(name, value, shape=(3,))


def canonical_fractional_vector3(name: str, value: object) -> np.ndarray:
    """Return one finite fractional three-vector in ``[0, 1)``.

    Fractional translations are torus coordinates.  Floating-point remainder
    can map a sufficiently small negative value to exactly ``1.0``; that upper
    boundary is periodic-equivalent to zero and must be normalized explicitly.
    """

    vector = finite_vector3(name, value)
    wrapped = np.mod(vector, 1.0)
    wrapped[wrapped == 1.0] = 0.0
    wrapped[wrapped == 0.0] = 0.0  # normalize negative zero
    return wrapped


def max_abs_scaled_residual(actual: object, predicted: object) -> tuple[float, float]:
    """Return absolute and scale-normalized maximum residuals."""

    actual_array = finite_matrix3("actual cell", actual)
    predicted_array = finite_matrix3("predicted cell", predicted)
    absolute = float(np.max(np.abs(actual_array - predicted_array)))
    scale = max(
        float(np.max(np.abs(actual_array))),
        float(np.max(np.abs(predicted_array))),
        np.finfo(float).tiny,
    )
    return absolute, absolute / scale


def relation_is_verified(
    actual: object,
    predicted: object,
    *,
    symprec: object,
) -> tuple[bool, float, float]:
    """Check a standardized-cell relation using an operation-owned tolerance."""

    tolerance = positive_finite_float("symprec", symprec)
    absolute, relative = max_abs_scaled_residual(actual, predicted)
    scale = max(
        float(np.max(np.abs(np.asarray(actual, dtype=float)))),
        float(np.max(np.abs(np.asarray(predicted, dtype=float)))),
        1.0,
    )
    threshold = max(64.0 * np.finfo(float).eps * scale, 4.0 * tolerance)
    return absolute <= threshold, absolute, relative


@dataclass(frozen=True)
class PrimitiveReductionCheck:
    """Independent composition and volume checks for a primitive reduction."""

    multiplicity: int
    volume_ratio: float
    composition_verified: bool
    volume_verified: bool


def primitive_reduction_check(
    *,
    cell_conventional_rows: object,
    cell_primitive_rows: object,
    numbers_conventional: object,
    numbers_primitive: object,
    symprec: object,
) -> PrimitiveReductionCheck:
    """Verify that conventional and primitive cells differ by centring only."""

    conventional = finite_cell_rows(cell_conventional_rows)
    primitive = finite_cell_rows(cell_primitive_rows)
    tolerance = positive_finite_float("symprec", symprec)

    conventional_raw = np.asarray(numbers_conventional, dtype=object)
    primitive_raw = np.asarray(numbers_primitive, dtype=object)
    if conventional_raw.ndim != 1 or primitive_raw.ndim != 1:
        raise ValueError("primitive-reduction species arrays must be one-dimensional.")
    if conventional_raw.size == 0 or primitive_raw.size == 0:
        raise ValueError("standardized cells must contain at least one atom.")
    conventional_numbers = exact_type_numbers(
        conventional_raw,
        n_atoms=int(conventional_raw.size),
        require_positive=True,
    )
    primitive_numbers = exact_type_numbers(
        primitive_raw,
        n_atoms=int(primitive_raw.size),
        require_positive=True,
    )

    n_conventional = int(conventional_numbers.size)
    n_primitive = int(primitive_numbers.size)
    if n_conventional % n_primitive != 0:
        raise ValueError(
            "conventional atom count must be an integer multiple of the "
            "primitive atom count."
        )
    multiplicity = n_conventional // n_primitive
    if multiplicity not in {1, 2, 3, 4}:
        raise ValueError(
            "standardized centring multiplicity must be one of 1, 2, 3, or 4."
        )

    species = set(conventional_numbers.tolist()) | set(primitive_numbers.tolist())
    composition_verified = all(
        int(np.count_nonzero(conventional_numbers == number))
        == multiplicity * int(np.count_nonzero(primitive_numbers == number))
        for number in species
    )
    if not composition_verified:
        raise ValueError(
            "conventional and primitive cells do not preserve composition at "
            "the centring multiplicity."
        )

    volume_conventional = abs(float(np.linalg.det(conventional)))
    volume_primitive = abs(float(np.linalg.det(primitive)))
    volume_ratio = volume_conventional / volume_primitive
    lengths = np.concatenate(
        (
            np.linalg.norm(conventional, axis=1),
            np.linalg.norm(primitive, axis=1),
        )
    )
    length_scale = max(float(np.min(lengths)), np.finfo(float).tiny)
    relative_tolerance = max(
        256.0 * np.finfo(float).eps,
        12.0 * tolerance / length_scale,
    )
    volume_verified = bool(
        np.isclose(
            volume_ratio,
            float(multiplicity),
            rtol=relative_tolerance,
            atol=relative_tolerance,
        )
    )
    if not volume_verified:
        raise ValueError(
            "conventional-to-primitive volume ratio does not match the "
            "atom-count multiplicity."
        )

    return PrimitiveReductionCheck(
        multiplicity=multiplicity,
        volume_ratio=float(volume_ratio),
        composition_verified=True,
        volume_verified=True,
    )


@dataclass(frozen=True)
class StandardizationRelation:
    """Explicit lattice relation for one spglib standardization result."""

    transformation_matrix_input_from_standardized: np.ndarray
    origin_shift_standardized: np.ndarray
    rigid_rotation_standardized: np.ndarray
    conventional_to_primitive: np.ndarray
    conventional_verified: bool
    primitive_verified: bool
    conventional_max_abs_residual: float
    primitive_max_abs_residual: float
    conventional_relative_residual: float
    primitive_relative_residual: float


def standardization_relation(
    *,
    cell_input_rows: object,
    cell_conventional_rows: object,
    cell_primitive_rows: object,
    transformation_matrix: object,
    origin_shift: object,
    rigid_rotation: object,
    no_idealize: object,
    symprec: object,
) -> StandardizationRelation:
    """Construct and verify the spglib change-of-basis relation.

    With column-basis cells, spglib reports ``P`` and ``p`` such that

    ``A_standardized = A_input @ inv(P)``.

    When idealization is enabled, the standardized cell is subsequently acted
    on by the Cartesian orthogonal matrix ``R``.  The primitive output is then
    related to the conventional output by a generally rational matrix ``P_c``.
    """

    A_input = finite_cell_rows(cell_input_rows).T
    A_conventional = finite_cell_rows(cell_conventional_rows).T
    A_primitive = finite_cell_rows(cell_primitive_rows).T
    P = finite_matrix3("transformation_matrix", transformation_matrix)
    p = finite_vector3("origin_shift", origin_shift)
    R_dataset = finite_matrix3("rigid_rotation", rigid_rotation)
    no_idealize_value = exact_bool("no_idealize", no_idealize)
    tolerance = positive_finite_float("symprec", symprec)

    determinant = float(np.linalg.det(P))
    if not isfinite(determinant) or abs(determinant) <= np.finfo(float).eps:
        raise ValueError("transformation_matrix must be nonsingular.")

    orthogonality = R_dataset.T @ R_dataset
    if not np.allclose(orthogonality, np.eye(3), rtol=1e-10, atol=1e-10):
        raise ValueError("rigid_rotation must be orthogonal.")
    rotation_det = float(np.linalg.det(R_dataset))
    if not np.isclose(rotation_det, 1.0, rtol=1e-10, atol=1e-10):
        raise ValueError("rigid_rotation must be a proper Cartesian rotation.")

    R_applied = np.eye(3) if no_idealize_value else R_dataset
    predicted_conventional = R_applied @ A_input @ np.linalg.inv(P)
    conv_ok, conv_abs, conv_rel = relation_is_verified(
        A_conventional,
        predicted_conventional,
        symprec=tolerance,
    )

    P_c = np.linalg.solve(A_conventional, A_primitive)
    predicted_primitive = A_conventional @ P_c
    prim_ok, prim_abs, prim_rel = relation_is_verified(
        A_primitive,
        predicted_primitive,
        symprec=tolerance,
    )

    return StandardizationRelation(
        transformation_matrix_input_from_standardized=P,
        origin_shift_standardized=canonical_fractional_vector3("origin_shift", p),
        rigid_rotation_standardized=R_dataset,
        conventional_to_primitive=P_c,
        conventional_verified=bool(conv_ok),
        primitive_verified=bool(prim_ok),
        conventional_max_abs_residual=float(conv_abs),
        primitive_max_abs_residual=float(prim_abs),
        conventional_relative_residual=float(conv_rel),
        primitive_relative_residual=float(prim_rel),
    )


def exact_integer_sequence(name: str, value: object, *, length: int) -> np.ndarray:
    """Return one fixed-length exact integer sequence."""

    array = exact_type_numbers(value, n_atoms=length, require_positive=False)
    return array


def optional_exact_integer_sequence(
    name: str,
    value: object | None,
    *,
    length: int,
) -> np.ndarray | None:
    """Validate an optional fixed-length integer mapping."""

    if value is None:
        return None
    return exact_integer_sequence(name, value, length=length)


def mapping_value(dataset: object, name: str, default: Any = None) -> Any:
    """Read one field from a mapping-style or attribute-style spglib dataset."""

    if dataset is None:
        return default
    if isinstance(dataset, dict):
        return dataset.get(name, default)
    return getattr(dataset, name, default)
