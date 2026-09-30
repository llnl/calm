"""Deterministic two-dimensional lattice reduction helpers.

The authoritative identity-producing algorithm is
:func:`canonical_gauss_reduce_2d`.  It selects a verified canonical Gauss
representative of a two-dimensional lattice and returns the exact integer
right action together with the orthogonal embedding map.

"""

from __future__ import annotations

import math
import warnings

import numpy as np

from calm.exceptions import (
    CanonicalGaussReductionCycleError,
    CanonicalGaussReductionInvariantError,
    CanonicalGaussReductionIterationError,
    SurfaceCellHandednessError,
    SurfaceCellHandednessWarning,
)

# Fixed GL(2,Z) right action used internally to repair left-handed bases.
# It flips the second lattice vector without changing the underlying lattice.
_IntMatrix2D = tuple[tuple[int, int], tuple[int, int]]
_IDENTITY_2D: _IntMatrix2D = ((1, 0), (0, 1))
_SWAP_COLUMNS_2D: _IntMatrix2D = ((0, 1), (1, 0))
_FLIP_FIRST_COLUMN_2D: _IntMatrix2D = ((-1, 0), (0, 1))
_HANDEDNESS_REPAIR_TUPLE_2D: _IntMatrix2D = ((1, 0), (0, -1))
_INT64_MAX = int(np.iinfo(np.int64).max)


def _positive_finite_float(name: str, value: object) -> float:
    """Return ``value`` as a finite positive float."""

    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{name} must be a finite positive real number") from exc
    if not math.isfinite(result) or result <= 0.0:
        raise ValueError(f"{name} must be finite and > 0, got {value!r}")
    return result


def _positive_int(name: str, value: object) -> int:
    """Return ``value`` as a strictly positive integer."""

    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
        raise TypeError(f"{name} must be a positive integer")
    result = int(value)
    if result <= 0:
        raise ValueError(f"{name} must be > 0, got {value!r}")
    return result


def _right_multiply_2x2_int(
    left: _IntMatrix2D,
    right: _IntMatrix2D,
) -> _IntMatrix2D:
    """Return the exact integer product ``left @ right``.

    Python integers are used during reduction so intermediate basis changes do
    not silently overflow.  The public NumPy result is restricted to ``int64``
    because downstream CALM arrays use fixed-width integer matrices.
    """

    result = (
        (
            left[0][0] * right[0][0] + left[0][1] * right[1][0],
            left[0][0] * right[0][1] + left[0][1] * right[1][1],
        ),
        (
            left[1][0] * right[0][0] + left[1][1] * right[1][0],
            left[1][0] * right[0][1] + left[1][1] * right[1][1],
        ),
    )
    if max(abs(entry) for row in result for entry in row) > _INT64_MAX:
        raise CanonicalGaussReductionIterationError(
            "canonical_gauss_reduce_2d: unimodular transform exceeds int64 "
            "range before convergence"
        )
    return result


def _nearest_integer_ties_to_zero(value: float) -> int:
    """Return the nearest integer, resolving exact half ties toward zero."""

    magnitude = abs(value)
    lower = math.floor(magnitude)
    fraction = magnitude - lower
    rounded = lower + 1 if fraction > 0.5 else lower
    return rounded if value >= 0.0 else -rounded


def _basis_from_transform(
    basis: np.ndarray,
    transform: _IntMatrix2D,
) -> np.ndarray:
    """Apply an exact integer transform and require a finite floating result."""

    transformed = basis @ np.asarray(transform, dtype=float)
    if not np.all(np.isfinite(transformed)):
        raise CanonicalGaussReductionIterationError(
            "canonical_gauss_reduce_2d: nonfinite basis encountered during "
            "integer reduction"
        )
    return transformed


def _quadratic_parameters(basis: np.ndarray) -> tuple[float, float, float]:
    """Return ``(||a1||^2, a1·a2, ||a2||^2)`` for a column basis."""

    vector_1 = basis[:, 0]
    vector_2 = basis[:, 1]
    return (
        float(vector_1 @ vector_1),
        float(vector_1 @ vector_2),
        float(vector_2 @ vector_2),
    )


def _decision_tolerance(tol: float, a: float, c: float) -> float:
    """Return the scale-aware metric tolerance used by domain decisions."""

    return tol * max(1.0, abs(a), abs(c))


def _transform_verification_issues(transform: np.ndarray) -> list[str]:
    """Return executable-contract failures for the integer right action."""

    if transform.shape != (2, 2) or not np.issubdtype(
        transform.dtype,
        np.integer,
    ):
        return ["U is not a 2x2 integer matrix"]
    entry_00 = int(transform[0, 0])
    entry_01 = int(transform[0, 1])
    entry_10 = int(transform[1, 0])
    entry_11 = int(transform[1, 1])
    determinant = entry_00 * entry_11 - entry_01 * entry_10
    if abs(determinant) != 1:
        return [f"det(U)={determinant}, expected +/-1"]
    return []


def _domain_verification_issues(
    normalized_input: np.ndarray,
    reduced: np.ndarray,
    *,
    tol: float,
) -> list[str]:
    """Return failures of the canonical reduced-domain contract."""

    if reduced.shape != (2, 2) or not np.all(np.isfinite(reduced)):
        return ["B_red is not a finite 2x2 matrix"]

    issues: list[str] = []
    a, dot, c = _quadratic_parameters(reduced)
    metric_tol = _decision_tolerance(tol, a, c)
    determinant_reduced = float(np.linalg.det(reduced))
    determinant_input = float(np.linalg.det(normalized_input))

    if not math.isfinite(determinant_reduced) or determinant_reduced <= 0.0:
        issues.append(f"det(B_red)={determinant_reduced:.16g}, expected > 0")
    if abs(determinant_reduced - abs(determinant_input)) > 100.0 * metric_tol:
        issues.append("reduced signed area does not preserve lattice area")
    if a > c + metric_tol:
        issues.append(f"||a1||^2={a:.16g} exceeds ||a2||^2={c:.16g}")
    if dot < -metric_tol:
        issues.append(f"a1 dot a2={dot:.16g} is negative")
    if 2.0 * dot > a + metric_tol:
        issues.append(f"2(a1 dot a2)={2.0 * dot:.16g} exceeds ||a1||^2={a:.16g}")
    if reduced[0, 0] <= 0.0:
        issues.append("the first reduced vector is not on the positive x axis")
    if abs(float(reduced[1, 0])) > 100.0 * metric_tol:
        issues.append("the first reduced vector is not aligned with the x axis")
    if reduced[1, 1] <= 0.0:
        issues.append("the second reduced vector is not in the upper half-plane")
    return issues


def _mapping_verification_issues(
    normalized_input: np.ndarray,
    reduced: np.ndarray,
    transform: np.ndarray,
    embedding: np.ndarray,
    *,
    tol: float,
    det_tol: float,
) -> list[str]:
    """Return failures of the orthogonal embedding and transformation relation."""

    if embedding.shape != (2, 2) or not np.all(np.isfinite(embedding)):
        return ["R is not a finite 2x2 matrix"]

    issues: list[str] = []
    orthogonal_residual = float(np.max(np.abs(embedding.T @ embedding - np.eye(2))))
    relation_residual = float(
        np.max(
            np.abs(reduced - embedding @ (normalized_input @ transform.astype(float)))
        )
    )
    verification_tol = max(100.0 * tol, 100.0 * det_tol)
    if orthogonal_residual > verification_tol:
        issues.append(
            "R is not orthogonal: max residual "
            f"{orthogonal_residual:.3e} exceeds {verification_tol:.3e}"
        )
    if relation_residual > verification_tol:
        issues.append(
            "B_red != R @ A @ U: max residual "
            f"{relation_residual:.3e} exceeds {verification_tol:.3e}"
        )
    return issues


def _verify_canonical_gauss_result(
    *,
    normalized_input: np.ndarray,
    reduced: np.ndarray,
    transform: np.ndarray,
    embedding: np.ndarray,
    tol: float,
    det_tol: float,
) -> None:
    """Verify the complete executable canonical-reduction contract."""

    issues = _transform_verification_issues(transform)
    issues.extend(
        _domain_verification_issues(
            normalized_input,
            reduced,
            tol=tol,
        )
    )
    issues.extend(
        _mapping_verification_issues(
            normalized_input,
            reduced,
            transform,
            embedding,
            tol=tol,
            det_tol=det_tol,
        )
    )
    if issues:
        raise CanonicalGaussReductionInvariantError(
            "canonical_gauss_reduce_2d: verification failed: " + "; ".join(issues)
        )


def _validated_bool(name: str, value: object) -> bool:
    """Return a strict Python boolean from a bool-like scalar."""

    if not isinstance(value, (bool, np.bool_)):
        raise TypeError(f"{name} must be a bool")
    return bool(value)


def _normalized_basis(
    A: np.ndarray,
    *,
    det_tol: float,
) -> tuple[np.ndarray, float, float]:
    """Validate and scale-normalize one finite nonsingular 2D basis."""

    basis = np.asarray(A, dtype=float)
    if basis.shape != (2, 2):
        raise ValueError(
            f"canonical_gauss_reduce_2d expects a 2x2 matrix, got shape {basis.shape}"
        )
    if not np.all(np.isfinite(basis)):
        raise ValueError("canonical_gauss_reduce_2d: input basis must be finite")

    scale = float(np.max(np.abs(basis)))
    if not math.isfinite(scale) or scale <= 0.0:
        raise ValueError(
            "canonical_gauss_reduce_2d: input basis must have nonzero scale"
        )
    normalized = basis / scale
    determinant = float(np.linalg.det(normalized))
    if not math.isfinite(determinant):
        raise ValueError(
            "canonical_gauss_reduce_2d: normalized determinant is not finite"
        )
    if abs(determinant) <= det_tol:
        raise ValueError(
            "canonical_gauss_reduce_2d: near-singular normalized basis "
            f"(|det|={abs(determinant):.3e} <= det_tol={det_tol:.3e})"
        )
    return normalized, scale, determinant


def _initial_transform(
    determinant: float,
    *,
    strict_handedness: bool,
    warn_on_handedness_repair: bool,
) -> _IntMatrix2D:
    """Return the declared initial handedness normalization."""

    if determinant >= 0.0:
        return _IDENTITY_2D

    message = (
        "canonical_gauss_reduce_2d: input 2D basis is left-handed; "
        "applying the fixed diag(1,-1) integer right action. "
        "Set strict_handedness=True to reject it instead."
    )
    if strict_handedness:
        raise SurfaceCellHandednessError(message)
    if warn_on_handedness_repair:
        warnings.warn(
            message,
            SurfaceCellHandednessWarning,
            stacklevel=3,
        )
    return _HANDEDNESS_REPAIR_TUPLE_2D


def _reduce_integer_transform(
    normalized: np.ndarray,
    initial_transform: _IntMatrix2D,
    *,
    tol: float,
    max_iterations: int,
) -> _IntMatrix2D:
    """Return the exact integer right action reaching the reduced domain."""

    transform = initial_transform
    seen: set[_IntMatrix2D] = set()
    for _ in range(max_iterations):
        if transform in seen:
            raise CanonicalGaussReductionCycleError(
                "canonical_gauss_reduce_2d: repeated an integer basis state "
                "before reaching the canonical domain"
            )
        seen.add(transform)

        working = _basis_from_transform(normalized, transform)
        a, dot, c = _quadratic_parameters(working)
        if not all(math.isfinite(value) for value in (a, dot, c)) or a <= 0.0:
            raise CanonicalGaussReductionInvariantError(
                "canonical_gauss_reduce_2d: invalid quadratic form during reduction"
            )
        metric_tol = _decision_tolerance(tol, a, c)

        if abs(dot) > 0.5 * a + metric_tol:
            shear = _nearest_integer_ties_to_zero(dot / a)
            if shear == 0:
                raise CanonicalGaussReductionInvariantError(
                    "canonical_gauss_reduce_2d: nonzero shear was required "
                    "but the deterministic nearest integer was zero"
                )
            transform = _right_multiply_2x2_int(
                transform,
                ((1, -shear), (0, 1)),
            )
            continue

        if a > c + metric_tol:
            transform = _right_multiply_2x2_int(
                transform,
                _SWAP_COLUMNS_2D,
            )
            continue
        return transform

    raise CanonicalGaussReductionIterationError(
        "canonical_gauss_reduce_2d: iteration bound exhausted before "
        f"reaching the canonical domain (max_iter={max_iterations})"
    )


def _canonical_embedding(
    normalized: np.ndarray,
    transform: _IntMatrix2D,
) -> tuple[np.ndarray, np.ndarray, _IntMatrix2D]:
    """Apply the sign tie and construct the canonical orthogonal embedding."""

    working = _basis_from_transform(normalized, transform)
    _, dot, _ = _quadratic_parameters(working)
    if dot < 0.0:
        transform = _right_multiply_2x2_int(
            transform,
            _FLIP_FIRST_COLUMN_2D,
        )
        working = _basis_from_transform(normalized, transform)

    a, dot, _ = _quadratic_parameters(working)
    first_length = math.sqrt(a)
    reduced = np.asarray(
        [
            [first_length, dot / first_length],
            [0.0, abs(float(np.linalg.det(working))) / first_length],
        ],
        dtype=float,
    )
    try:
        embedding = reduced @ np.linalg.inv(working)
    except np.linalg.LinAlgError as exc:
        raise CanonicalGaussReductionInvariantError(
            "canonical_gauss_reduce_2d: failed to construct the orthogonal embedding"
        ) from exc
    return reduced, embedding, transform


def canonical_gauss_reduce_2d(
    A: np.ndarray,
    tol: float = 1e-12,
    max_iter: int = 1000,
    det_tol: float = 1e-15,
    *,
    strict_handedness: bool = False,
    warn_on_handedness_repair: bool = True,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return CALM's verified canonical two-dimensional Gauss representative.

    The columns of ``A`` are lattice vectors.  The returned arrays satisfy

    ``B_red = R @ (A @ U)``,

    where ``U`` is exactly integer-unimodular and ``R`` is orthogonal.  The
    reduced basis is embedded as

    ``B_red = [[x, s], [0, y]]``

    and belongs, within the declared dimensionless tolerance, to the domain

    ``0 <= 2(a1 dot a2) <= ||a1||^2 <= ||a2||^2``

    with ``x > 0`` and ``y > 0``.  Uniform input scaling is removed before all
    reduction decisions and restored only on the returned basis.

    Boundary rules are deterministic:

    * norm ordering swaps only when ``||a1||^2 > ||a2||^2 + eps``;
    * a shear coefficient is the nearest integer, with exact half ties toward
      zero;
    * the final inner-product sign is nonnegative;
    * left-handed inputs are either rejected or repaired by the fixed
      ``diag(1, -1)`` right action.

    The result is always verified.  Cycles, iteration exhaustion, nonfinite
    intermediates, and failed postconditions raise typed errors; this function
    never warns and returns an unverified canonical representative.

    Parameters
    ----------
    A
        Finite nonsingular 2x2 basis matrix with lattice vectors as columns.
    tol
        Finite positive dimensionless tolerance for normalized metric
        comparisons.
    max_iter
        Positive reduction-loop bound, including the terminal reduced-domain
        check.
    det_tol
        Finite positive lower bound for the absolute determinant after
        scale normalization.
    strict_handedness
        Reject left-handed input instead of applying the declared repair.
    warn_on_handedness_repair
        Emit ``SurfaceCellHandednessWarning`` when automatic repair is used.

    Returns
    -------
    B_red, U, R
        Canonical reduced basis, exact integer right action, and orthogonal
        embedding satisfying ``B_red = R @ (A @ U)``.
    """

    tol_value = _positive_finite_float("tol", tol)
    det_tol_value = _positive_finite_float("det_tol", det_tol)
    max_iterations = _positive_int("max_iter", max_iter)
    strict_value = _validated_bool("strict_handedness", strict_handedness)
    warn_value = _validated_bool(
        "warn_on_handedness_repair",
        warn_on_handedness_repair,
    )
    normalized, scale, determinant = _normalized_basis(
        A,
        det_tol=det_tol_value,
    )
    initial_transform = _initial_transform(
        determinant,
        strict_handedness=strict_value,
        warn_on_handedness_repair=warn_value,
    )
    transform = _reduce_integer_transform(
        normalized,
        initial_transform,
        tol=tol_value,
        max_iterations=max_iterations,
    )
    reduced_normalized, embedding, transform = _canonical_embedding(
        normalized,
        transform,
    )
    transform_array = np.asarray(transform, dtype=np.int64)
    _verify_canonical_gauss_result(
        normalized_input=normalized,
        reduced=reduced_normalized,
        transform=transform_array,
        embedding=embedding,
        tol=tol_value,
        det_tol=det_tol_value,
    )

    reduced = reduced_normalized * scale
    if not np.all(np.isfinite(reduced)):
        raise CanonicalGaussReductionInvariantError(
            "canonical_gauss_reduce_2d: restoring the input scale produced "
            "a nonfinite reduced basis"
        )
    return reduced, transform_array, embedding


_ORIENTED_QUARTER_TURN_2D: _IntMatrix2D = ((0, -1), (1, 0))


def _oriented_domain_verification_issues(
    normalized_input: np.ndarray,
    reduced: np.ndarray,
    transform: np.ndarray,
    embedding: np.ndarray,
    *,
    tol: float,
    det_tol: float,
) -> list[str]:
    """Return failures of the orientation-preserving reduction contract."""

    issues = _transform_verification_issues(transform)
    if not issues:
        determinant_transform = int(
            int(transform[0, 0]) * int(transform[1, 1])
            - int(transform[0, 1]) * int(transform[1, 0])
        )
        if determinant_transform != 1:
            issues.append(f"det(U)={determinant_transform}, expected +1")

    if reduced.shape != (2, 2) or not np.all(np.isfinite(reduced)):
        issues.append("B_red is not a finite 2x2 matrix")
        return issues
    if embedding.shape != (2, 2) or not np.all(np.isfinite(embedding)):
        issues.append("Q is not a finite 2x2 matrix")
        return issues

    a, dot, c = _quadratic_parameters(reduced)
    metric_tol = _decision_tolerance(tol, a, c)
    if a > c + metric_tol:
        issues.append(f"||a1||^2={a:.16g} exceeds ||a2||^2={c:.16g}")
    if 2.0 * abs(dot) > a + metric_tol:
        issues.append(f"2|a1 dot a2|={2.0 * abs(dot):.16g} exceeds ||a1||^2={a:.16g}")
    if reduced[0, 0] <= 0.0:
        issues.append("the first reduced vector is not on the positive x axis")
    if abs(float(reduced[1, 0])) > 100.0 * metric_tol:
        issues.append("the first reduced vector is not aligned with the x axis")

    determinant_input = float(np.linalg.det(normalized_input))
    determinant_reduced = float(np.linalg.det(reduced))
    if determinant_input * determinant_reduced <= 0.0:
        issues.append("the reduced basis does not preserve input handedness")
    if abs(abs(determinant_reduced) - abs(determinant_input)) > 100.0 * metric_tol:
        issues.append("reduced area does not preserve lattice area")

    determinant_embedding = float(np.linalg.det(embedding))
    verification_tol = max(100.0 * tol, 100.0 * det_tol)
    if abs(determinant_embedding - 1.0) > verification_tol:
        issues.append(f"det(Q)={determinant_embedding:.16g}, expected +1")
    orthogonal_residual = float(np.max(np.abs(embedding.T @ embedding - np.eye(2))))
    if orthogonal_residual > verification_tol:
        issues.append(
            "Q is not orthogonal: max residual "
            f"{orthogonal_residual:.3e} exceeds {verification_tol:.3e}"
        )
    relation_residual = float(
        np.max(
            np.abs(reduced - embedding @ (normalized_input @ transform.astype(float)))
        )
    )
    if relation_residual > verification_tol:
        issues.append(
            "B_red != Q @ A @ U: max residual "
            f"{relation_residual:.3e} exceeds {verification_tol:.3e}"
        )
    return issues


def _reduce_oriented_integer_transform(
    normalized: np.ndarray,
    *,
    tol: float,
    max_iterations: int,
) -> _IntMatrix2D:
    """Return a proper integer right action reaching the oriented Gauss domain."""

    transform = _IDENTITY_2D
    seen: set[_IntMatrix2D] = set()
    for _ in range(max_iterations):
        if transform in seen:
            raise CanonicalGaussReductionCycleError(
                "oriented_gauss_reduce_2d: repeated an integer basis state "
                "before reaching the oriented reduced domain"
            )
        seen.add(transform)

        working = _basis_from_transform(normalized, transform)
        a, dot, c = _quadratic_parameters(working)
        if not all(math.isfinite(value) for value in (a, dot, c)) or a <= 0.0:
            raise CanonicalGaussReductionInvariantError(
                "oriented_gauss_reduce_2d: invalid quadratic form during reduction"
            )
        metric_tol = _decision_tolerance(tol, a, c)

        if abs(dot) > 0.5 * a + metric_tol:
            shear = _nearest_integer_ties_to_zero(dot / a)
            if shear == 0:
                raise CanonicalGaussReductionInvariantError(
                    "oriented_gauss_reduce_2d: nonzero shear was required "
                    "but the deterministic nearest integer was zero"
                )
            transform = _right_multiply_2x2_int(
                transform,
                ((1, -shear), (0, 1)),
            )
            continue

        if a > c + metric_tol:
            transform = _right_multiply_2x2_int(
                transform,
                _ORIENTED_QUARTER_TURN_2D,
            )
            continue

        # Exact negative half-boundary states are equivalent to their positive
        # counterpart through one proper shear.  Select the positive branch.
        if dot < -metric_tol and abs(2.0 * dot + a) <= metric_tol:
            transform = _right_multiply_2x2_int(
                transform,
                ((1, 1), (0, 1)),
            )
            continue

        # Equal-length reduced bases retain a proper quarter-turn freedom.
        # Use it to choose the non-negative inner-product branch.
        if abs(a - c) <= metric_tol and dot < -metric_tol:
            transform = _right_multiply_2x2_int(
                transform,
                _ORIENTED_QUARTER_TURN_2D,
            )
            continue
        return transform

    raise CanonicalGaussReductionIterationError(
        "oriented_gauss_reduce_2d: iteration bound exhausted before "
        f"reaching the oriented reduced domain (max_iter={max_iterations})"
    )


def _proper_embedding(
    normalized: np.ndarray,
    transform: _IntMatrix2D,
) -> tuple[np.ndarray, np.ndarray]:
    """Return the proper Cartesian embedding of one oriented reduced basis."""

    working = _basis_from_transform(normalized, transform)
    first = working[:, 0]
    first_length = float(np.linalg.norm(first))
    if not math.isfinite(first_length) or first_length <= 0.0:
        raise CanonicalGaussReductionInvariantError(
            "oriented_gauss_reduce_2d: invalid first-vector length"
        )
    embedding = np.asarray(
        [
            [first[0] / first_length, first[1] / first_length],
            [-first[1] / first_length, first[0] / first_length],
        ],
        dtype=float,
    )
    reduced = embedding @ working
    reduced[1, 0] = 0.0
    return reduced, embedding


def oriented_gauss_reduce_2d(
    basis: np.ndarray,
    *,
    tol: float = 1e-12,
    det_tol: float = 1e-15,
    max_iter: int = 1000,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return an orientation-preserving two-dimensional Gauss reduction.

    The columns of ``basis`` are lattice vectors.  The returned arrays satisfy

    ``B_red = Q @ basis @ U``,

    with ``U`` in ``SL(2, Z)`` and ``Q`` in ``SO(2)``.  Consequently the
    handedness of the input basis is preserved.  The oriented reduced domain is

    ``2 |a1 dot a2| <= ||a1||^2 <= ||a2||^2``.

    Unlike :func:`canonical_gauss_reduce_2d`, this routine never introduces a
    reflection to identify the two orientation branches.  It is therefore the
    reduction used for coupled basis correspondence and build provenance, while
    the existing O(2)-canonical routine remains the shape-grouping gauge.

    Returns
    -------
    B_red, U, Q
        Reduced basis, proper integer right action, and proper Cartesian
        rotation satisfying the exact declared relation up to floating-point
        verification tolerance.
    """

    tol_value = _positive_finite_float("tol", tol)
    det_tol_value = _positive_finite_float("det_tol", det_tol)
    max_iterations = _positive_int("max_iter", max_iter)
    normalized, scale, _determinant = _normalized_basis(
        basis,
        det_tol=det_tol_value,
    )
    transform = _reduce_oriented_integer_transform(
        normalized,
        tol=tol_value,
        max_iterations=max_iterations,
    )
    reduced_normalized, embedding = _proper_embedding(normalized, transform)
    transform_array = np.asarray(transform, dtype=np.int64)
    issues = _oriented_domain_verification_issues(
        normalized,
        reduced_normalized,
        transform_array,
        embedding,
        tol=tol_value,
        det_tol=det_tol_value,
    )
    if issues:
        raise CanonicalGaussReductionInvariantError(
            "oriented_gauss_reduce_2d: verification failed: " + "; ".join(issues)
        )

    reduced = reduced_normalized * scale
    if not np.all(np.isfinite(reduced)):
        raise CanonicalGaussReductionInvariantError(
            "oriented_gauss_reduce_2d: restoring the input scale produced "
            "a nonfinite reduced basis"
        )
    return reduced, transform_array, embedding
