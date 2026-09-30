"""Dependency-light mathematics for primitive surface-plane construction.

The authoritative primitive-surface path is certificate based.  It converts a
conventional Miller covector to primitive coordinates through a verified
rational basis transform, constructs an exact integer kernel and Bezout
stacking vector, and then applies optional metric gauges that preserve the
integer certificates.

This module intentionally contains no ASE imports.  The exact oriented-slab
constructor imports these helpers directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from functools import reduce
from math import gcd
from numbers import Integral
from typing import Sequence

import numpy as np

from calm.exceptions import BoundedGaugeSearchError

ArrayF = np.ndarray

DEFAULT_PRIMITIVE_MAX_DENOMINATOR = 12
DEFAULT_PRIMITIVE_REDUCTION_MAX_ITER = 100
DEFAULT_STACKING_SEARCH_RADIUS = 2


@dataclass(frozen=True)
class IntegerSurfaceSupercellRelation:
    """Certified integer relation between two in-plane row bases.

    The relation follows CALM's column-basis convention

    ``B_super = B_primitive @ P``

    and therefore ASE's row-storage convention

    ``C_super = P.T @ C_primitive``.
    """

    matrix: np.ndarray
    index: int
    integrality_residual: float
    reconstruction_residual: float
    relative_reconstruction_residual: float

    def __post_init__(self) -> None:
        matrix = np.asarray(self.matrix, dtype=int)
        if matrix.shape != (2, 2):
            raise ValueError("matrix must have shape (2, 2)")
        matrix = matrix.copy()
        matrix.setflags(write=False)
        object.__setattr__(self, "matrix", matrix)


def _surface_basis_rows(name: str, basis: np.ndarray) -> np.ndarray:
    """Validate and return a finite full-rank ``(2, 3)`` row basis."""

    array = np.asarray(basis, dtype=float)
    if array.shape != (2, 3):
        raise ValueError(f"{name} must have shape (2, 3); got {array.shape}")
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must contain only finite values")

    singular_values = np.linalg.svd(array, compute_uv=False)
    rank_threshold = (
        np.finfo(float).eps
        * max(array.shape)
        * max(float(singular_values[0]), np.finfo(float).tiny)
    )
    if float(singular_values[-1]) <= rank_threshold:
        raise ValueError(f"{name} must contain two linearly independent vectors")
    return array


def _solve_surface_relation_coefficients(
    primitive: np.ndarray,
    supercell: np.ndarray,
) -> np.ndarray:
    """Solve ``primitive.T @ P = supercell.T`` for the real matrix ``P``."""

    try:
        coefficients, _, rank, _ = np.linalg.lstsq(
            primitive.T,
            supercell.T,
            rcond=None,
        )
    except np.linalg.LinAlgError as exc:
        raise ValueError("Unable to solve the surface supercell relation") from exc
    if int(rank) != 2 or not np.all(np.isfinite(coefficients)):
        raise ValueError("Surface supercell relation is not finite and full rank")
    return coefficients


def _round_surface_relation_matrix(
    coefficients: np.ndarray,
    tolerance: float,
) -> tuple[np.ndarray, float]:
    """Round one real relation matrix and certify coefficient integrality."""

    max_int = float(np.iinfo(np.int64).max)
    if float(np.max(np.abs(coefficients))) > max_int - 0.5:
        raise ValueError("Surface supercell coefficients exceed int64 range")

    rounded = np.rint(coefficients)
    residual = float(np.max(np.abs(coefficients - rounded)))
    if residual > tolerance:
        raise ValueError(
            "Surface supercell coefficients are not integral within tolerance: "
            f"residual={residual:.3e}, tol={tolerance:.3e}"
        )
    return rounded.astype(np.int64), residual


def _positive_surface_relation_index(matrix: np.ndarray) -> int:
    """Return the positive determinant or reject singular/reversed maps."""

    determinant = int(matrix[0, 0]) * int(matrix[1, 1]) - int(matrix[0, 1]) * int(
        matrix[1, 0]
    )
    if determinant == 0:
        raise ValueError("Surface supercell matrix must be nonsingular")
    if determinant < 0:
        raise ValueError(
            "Surface supercell relation reverses orientation; provide a "
            "right-handed in-plane basis or canonicalize it explicitly"
        )
    return determinant


def _surface_reconstruction_residuals(
    primitive: np.ndarray,
    supercell: np.ndarray,
    matrix: np.ndarray,
    tolerance: float,
) -> tuple[float, float]:
    """Return absolute/relative residuals after validating reconstruction."""

    reconstructed = matrix.T @ primitive
    residual = float(np.linalg.norm(reconstructed - supercell, ord=np.inf))
    scale = max(
        float(np.linalg.norm(reconstructed, ord=np.inf)),
        float(np.linalg.norm(supercell, ord=np.inf)),
        np.finfo(float).tiny,
    )
    relative_residual = residual / scale
    if relative_residual > tolerance:
        raise ValueError(
            "Surface supercell matrix does not reconstruct the candidate basis "
            "within tolerance: "
            f"relative_residual={relative_residual:.3e}, "
            f"tol={tolerance:.3e}"
        )
    return residual, relative_residual


def certify_integer_surface_supercell_relation(
    primitive_basis_rows: np.ndarray,
    supercell_basis_rows: np.ndarray,
    *,
    tol: float = 1e-6,
) -> IntegerSurfaceSupercellRelation:
    """Recover and certify a positive-orientation integer surface map.

    Parameters
    ----------
    primitive_basis_rows
        Two primitive in-plane Cartesian vectors stored as rows.
    supercell_basis_rows
        Two candidate supercell Cartesian vectors stored as rows.
    tol
        Positive dimensionless tolerance used for both coefficient
        integrality and scale-normalized Cartesian reconstruction.

    Returns
    -------
    IntegerSurfaceSupercellRelation
        The certified matrix ``P`` satisfying
        ``C_super = P.T @ C_primitive``, together with its positive index and
        residuals.

    Raises
    ------
    ValueError
        If either basis is invalid, the recovered coefficients are not
        integral, reconstruction fails, the matrix is singular, or the
        relation reverses orientation.
    """

    tolerance = float(tol)
    if not np.isfinite(tolerance) or tolerance <= 0.0:
        raise ValueError("tol must be a finite positive number")

    primitive = _surface_basis_rows(
        "primitive_basis_rows",
        primitive_basis_rows,
    )
    supercell = _surface_basis_rows(
        "supercell_basis_rows",
        supercell_basis_rows,
    )
    coefficients = _solve_surface_relation_coefficients(primitive, supercell)
    matrix, integrality_residual = _round_surface_relation_matrix(
        coefficients,
        tolerance,
    )
    determinant = _positive_surface_relation_index(matrix)
    (
        reconstruction_residual,
        relative_reconstruction_residual,
    ) = _surface_reconstruction_residuals(
        primitive,
        supercell,
        matrix,
        tolerance,
    )

    return IntegerSurfaceSupercellRelation(
        matrix=matrix,
        index=determinant,
        integrality_residual=integrality_residual,
        reconstruction_residual=reconstruction_residual,
        relative_reconstruction_residual=relative_reconstruction_residual,
    )


def lcm(a: int, b: int) -> int:
    """Return the nonnegative least common multiple of two integers."""
    a_i = int(a)
    b_i = int(b)
    if a_i == 0 or b_i == 0:
        return 0
    return abs(a_i * b_i) // gcd(a_i, b_i)


def lcm_multiple(integers: Sequence[int]) -> int:
    """Return the least common multiple of an integer sequence."""
    return reduce(lcm, (int(value) for value in integers), 1)


def gcd_multiple(integers: Sequence[int]) -> int:
    """Return the nonnegative greatest common divisor of an integer sequence."""
    return reduce(gcd, (abs(int(value)) for value in integers), 0)


def _integer_at_least(name: str, value: object, *, minimum: int) -> int:
    """Return an exact integer control with a declared lower bound."""
    if isinstance(value, bool) or not isinstance(value, (Integral, np.integer)):
        raise TypeError(f"{name} must be an integer")
    result = int(value)
    if result < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return result


def _fraction_matrix_from_float(
    matrix: np.ndarray,
    max_denominator: int,
) -> list[list[Fraction]]:
    denominator_bound = _integer_at_least(
        "max_denominator",
        max_denominator,
        minimum=1,
    )
    array = np.asarray(matrix, dtype=float)
    if not np.all(np.isfinite(array)):
        raise ValueError("matrix must contain only finite values")
    return [
        [
            Fraction(float(array[i, j])).limit_denominator(denominator_bound)
            for j in range(array.shape[1])
        ]
        for i in range(array.shape[0])
    ]


def _fraction_det3(matrix: list[list[Fraction]]) -> Fraction:
    return (
        matrix[0][0] * (matrix[1][1] * matrix[2][2] - matrix[1][2] * matrix[2][1])
        - matrix[0][1] * (matrix[1][0] * matrix[2][2] - matrix[1][2] * matrix[2][0])
        + matrix[0][2] * (matrix[1][0] * matrix[2][1] - matrix[1][1] * matrix[2][0])
    )


def _fraction_inverse3(
    matrix: list[list[Fraction]],
) -> list[list[Fraction]]:
    determinant = _fraction_det3(matrix)
    if determinant == 0:
        raise ValueError("Rational matrix is singular")

    cofactors = [[Fraction(0) for _ in range(3)] for _ in range(3)]
    for i in range(3):
        for j in range(3):
            rows = [row for row in range(3) if row != i]
            cols = [col for col in range(3) if col != j]
            minor = (
                matrix[rows[0]][cols[0]] * matrix[rows[1]][cols[1]]
                - matrix[rows[0]][cols[1]] * matrix[rows[1]][cols[0]]
            )
            cofactors[i][j] = ((-1) ** (i + j)) * minor
    return [[cofactors[j][i] / determinant for j in range(3)] for i in range(3)]


def _fraction_matvec(
    matrix: list[list[Fraction]],
    vector: list[Fraction],
) -> list[Fraction]:
    return [
        sum(matrix[i][j] * vector[j] for j in range(len(vector)))
        for i in range(len(matrix))
    ]


def _as_lattice_matrix(name: str, value: np.ndarray) -> np.ndarray:
    matrix = np.asarray(value, dtype=float)
    if matrix.shape != (3, 3):
        raise ValueError(f"{name} must have shape (3, 3), got {matrix.shape}")
    if not np.all(np.isfinite(matrix)):
        raise ValueError(f"{name} must contain only finite values")
    return matrix


def _integer_vector3(name: str, value: Sequence[int] | np.ndarray) -> np.ndarray:
    raw = np.asarray(value)
    if raw.shape != (3,):
        raise ValueError(f"{name} must have shape (3,), got {raw.shape}")
    if not np.issubdtype(raw.dtype, np.integer):
        raise ValueError(f"{name} must contain integers")
    return raw.astype(int, copy=False)


def _normalized_lattice_metric(matrix: np.ndarray) -> np.ndarray:
    """Return a uniformly scaled matrix for metric-only gauge operations."""
    scale = float(np.max(np.abs(matrix)))
    if not np.isfinite(scale) or scale <= 0.0:
        raise ValueError("A_prim must have a finite, nonzero scale")
    return matrix / scale


def primitive_miller_from_conventional(
    A_conv: np.ndarray,
    A_prim: np.ndarray,
    h_conv: tuple[int, int, int] | np.ndarray,
    *,
    max_denominator: int = DEFAULT_PRIMITIVE_MAX_DENOMINATOR,
    atol: float = 1e-10,
    rtol: float = 1e-10,
) -> np.ndarray:
    """Convert a conventional Miller covector to primitive integer form.

    The direct bases satisfy ``A_conv = A_prim @ P``.  Reciprocal covectors
    therefore transform as ``P^{-T}``.  CALM rationalizes and verifies ``P``,
    evaluates the inverse transpose with exact :class:`fractions.Fraction`
    arithmetic, and removes the common integer gcd from the result.

    ``max_denominator`` bounds entries of the direct basis transform ``P``.  It
    does not bound denominators that arise when the exact inverse is formed.
    """
    if atol < 0.0 or rtol < 0.0:
        raise ValueError("atol and rtol must be nonnegative")

    conventional = _as_lattice_matrix("A_conv", A_conv)
    primitive = _as_lattice_matrix("A_prim", A_prim)
    h_array = _integer_vector3("h_conv", h_conv)
    if not np.any(h_array):
        raise ValueError("Miller indices cannot all be zero")

    try:
        transform = np.linalg.solve(primitive, conventional)
        np.linalg.solve(conventional, primitive)
    except np.linalg.LinAlgError as exc:
        raise ValueError("A_conv and A_prim must both be nonsingular") from exc

    rational_transform = _fraction_matrix_from_float(
        transform,
        max_denominator,
    )
    rational_float = np.array(
        [[float(value) for value in row] for row in rational_transform],
        dtype=float,
    )
    transform_scale = max(
        float(np.linalg.norm(transform)),
        float(np.linalg.norm(rational_float)),
        np.finfo(float).tiny,
    )
    transform_error = float(np.linalg.norm(rational_float - transform))
    if transform_error > atol + rtol * transform_scale:
        raise ValueError(
            "Rationalized basis transform does not reproduce the "
            "conventional-to-primitive transform within tolerance; increase "
            "max_denominator or relax tolerances."
        )

    try:
        inverse = _fraction_inverse3(rational_transform)
    except ValueError as exc:
        raise ValueError(
            "Rationalized conventional-to-primitive transform is singular; "
            "increase max_denominator or inspect A_conv/A_prim."
        ) from exc

    inverse_transpose = [[inverse[j][i] for j in range(3)] for i in range(3)]
    h_fraction = [Fraction(int(value), 1) for value in h_array.tolist()]
    primitive_fraction = _fraction_matvec(inverse_transpose, h_fraction)
    common_denom = lcm_multiple([value.denominator for value in primitive_fraction])
    numerators = [
        int(value.numerator * (common_denom // value.denominator))
        for value in primitive_fraction
    ]

    divisor = gcd_multiple(numerators)
    if divisor == 0:
        raise ValueError(
            "Rationalized primitive Miller vector is zero; inspect the basis "
            "transform and Miller indices."
        )
    primitive_miller = np.array(
        [numerator // divisor for numerator in numerators],
        dtype=int,
    )
    if np.gcd.reduce(np.abs(primitive_miller)) != 1:
        raise ValueError("Primitive Miller vector failed gcd reduction")

    mapped = transform.T @ primitive_miller
    h_float = h_array.astype(float)
    cross_error = float(np.linalg.norm(np.cross(mapped, h_float)))
    parallel_scale = float(np.linalg.norm(mapped) * np.linalg.norm(h_float))
    if cross_error > atol + rtol * parallel_scale:
        raise ValueError(
            "Primitive Miller vector is not parallel to the conventional "
            "Miller index under P.T; increase max_denominator or inspect "
            "A_conv/A_prim."
        )
    return primitive_miller


def _extended_gcd_pair(a: int, b: int) -> tuple[int, int, int]:
    """Return ``(g, x, y)`` with ``a*x + b*y = g = gcd(a,b) >= 0``."""
    a_int = int(a)
    b_int = int(b)
    if a_int == 0 and b_int == 0:
        return 0, 0, 0

    old_r, remainder = abs(a_int), abs(b_int)
    old_s, coefficient_s = 1, 0
    old_t, coefficient_t = 0, 1
    while remainder != 0:
        quotient = old_r // remainder
        old_r, remainder = remainder, old_r - quotient * remainder
        old_s, coefficient_s = coefficient_s, old_s - quotient * coefficient_s
        old_t, coefficient_t = coefficient_t, old_t - quotient * coefficient_t

    x = old_s if a_int >= 0 else -old_s
    y = old_t if b_int >= 0 else -old_t
    return int(old_r), int(x), int(y)


def _primitive_surface_triplet_from_m(
    m: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Construct an exact primitive kernel and Bezout stacking vector."""
    miller = _integer_vector3("m", m)
    if not np.any(miller):
        raise ValueError("m cannot be zero")
    if np.gcd.reduce(np.abs(miller)) != 1:
        raise ValueError(f"m must be primitive, got {miller.tolist()}")

    a, b, c = map(int, miller.tolist())
    if a == 0 and b == 0:
        if abs(c) != 1:
            raise ValueError(
                f"Primitive m with a=b=0 must have c=+/-1, got {miller.tolist()}"
            )
        u = np.array([1, 0, 0], dtype=int)
        v = np.array([0, c, 0], dtype=int)
        w = np.array([0, 0, c], dtype=int)
    else:
        common_ab, p, q = _extended_gcd_pair(a, b)
        if common_ab <= 0:
            raise ValueError(f"Failed gcd construction for m={miller.tolist()}")
        common_all, s, t = _extended_gcd_pair(common_ab, c)
        if common_all != 1:
            raise ValueError(
                "Primitive m should satisfy gcd(gcd(a,b),c)=1, "
                f"got gcd(a,b)={common_ab}, c={c}"
            )

        u = np.array([b // common_ab, -a // common_ab, 0], dtype=int)
        v = np.array([-c * p, -c * q, common_ab], dtype=int)
        w = np.array([s * p, s * q, t], dtype=int)

    cross_uv = np.cross(u, v)
    if not (np.array_equal(cross_uv, miller) or np.array_equal(cross_uv, -miller)):
        raise ValueError(
            "Exact construction failed primitive certificate: "
            f"cross(u,v)={cross_uv.tolist()} vs m={miller.tolist()}"
        )
    if int(np.dot(miller, w)) != 1:
        raise ValueError(
            "Exact construction failed Bezout certificate: "
            f"m.w={int(np.dot(miller, w))} for m={miller.tolist()}"
        )
    return u, v, w


def minimize_shear(
    w: np.ndarray,
    u: np.ndarray,
    v: np.ndarray,
    A_prim: np.ndarray,
    *,
    search_radius: int = DEFAULT_STACKING_SEARCH_RADIUS,
) -> np.ndarray:
    """Choose a certified bounded stacking representative.

    CALM minimizes ``||A_prim @ (w + p*u + q*v)||_2`` over the square
    integer neighborhood centered on the rounded continuous least-squares
    solution, with ``|delta_p|, |delta_q| <= search_radius``.  Ties are
    resolved by ``(objective, |p|+|q|, |p|, |q|, p, q)``.

    This is a bounded gauge, not a global closest-vector proof.  A candidate
    on the declared search boundary is not certified because a better point
    may lie immediately outside the enumerated domain; in that case CALM
    raises :class:`~calm.exceptions.BoundedGaugeSearchError`.
    """
    radius = _integer_at_least(
        "stacking_search_radius",
        search_radius,
        minimum=1,
    )
    lattice = _normalized_lattice_metric(_as_lattice_matrix("A_prim", A_prim))
    w_array = _integer_vector3("w", w)
    u_array = _integer_vector3("u", u)
    v_array = _integer_vector3("v", v)

    w_cart = lattice @ w_array
    inplane = np.column_stack([lattice @ u_array, lattice @ v_array])
    try:
        coefficients, _, rank, _ = np.linalg.lstsq(
            inplane,
            -w_cart,
            rcond=None,
        )
    except np.linalg.LinAlgError as exc:
        raise BoundedGaugeSearchError(
            "Unable to solve the continuous stacking-gauge center."
        ) from exc
    if int(rank) != 2 or not np.all(np.isfinite(coefficients)):
        raise BoundedGaugeSearchError(
            "The stacking-gauge center is not finite and full rank."
        )

    rounded = np.rint(coefficients)
    max_int = float(np.iinfo(np.int64).max)
    if float(np.max(np.abs(rounded))) > max_int:
        raise BoundedGaugeSearchError(
            "The stacking-gauge center exceeds the supported integer range."
        )
    p_center, q_center = rounded.astype(np.int64)

    best_key: tuple[float, int, int, int, int, int] | None = None
    best: np.ndarray | None = None
    best_delta: tuple[int, int] | None = None
    for delta_p in range(-radius, radius + 1):
        for delta_q in range(-radius, radius + 1):
            p = int(p_center) + delta_p
            q = int(q_center) + delta_q
            candidate = w_array + p * u_array + q * v_array
            cartesian = lattice @ candidate
            objective = float(np.dot(cartesian, cartesian))
            if not np.isfinite(objective):
                raise BoundedGaugeSearchError(
                    "The stacking-gauge objective became nonfinite."
                )
            key = (
                objective,
                abs(p) + abs(q),
                abs(p),
                abs(q),
                p,
                q,
            )
            if best_key is None or key < best_key:
                best_key = key
                best = candidate
                best_delta = (delta_p, delta_q)

    if best is None or best_delta is None:
        raise BoundedGaugeSearchError(
            "The stacking-gauge search produced no candidate."
        )
    if abs(best_delta[0]) == radius or abs(best_delta[1]) == radius:
        raise BoundedGaugeSearchError(
            "The best stacking representative lies on the declared search "
            "boundary; increase stacking_search_radius."
        )

    original_triple = int(np.dot(np.cross(u_array, v_array), w_array))
    candidate_triple = int(np.dot(np.cross(u_array, v_array), best))
    if candidate_triple != original_triple:
        raise ValueError(
            "Shear minimization produced a stacking vector that violates the "
            "triple-product invariant"
        )
    return best


def _reduce_2d_basis(
    u: np.ndarray,
    v: np.ndarray,
    A_cart: np.ndarray,
    max_iter: int = DEFAULT_PRIMITIVE_REDUCTION_MAX_ITER,
) -> tuple[np.ndarray, np.ndarray]:
    """Apply a bounded metric Gauss gauge to an exact integer basis.

    ``max_iter`` is the maximum number of integer shear updates.  The routine
    verifies the reduced inequality after the final allowed update and raises
    instead of returning an unverified basis when the budget is exhausted.
    """
    iteration_limit = _integer_at_least(
        "primitive_reduction_max_iter",
        max_iter,
        minimum=1,
    )
    lattice = _normalized_lattice_metric(_as_lattice_matrix("A_cart", A_cart))
    u_current = _integer_vector3("u", u).copy()
    v_current = _integer_vector3("v", v).copy()
    seen: set[tuple[int, ...]] = set()

    def _state() -> tuple[int, ...]:
        return tuple(
            int(value) for value in np.concatenate([u_current, v_current]).tolist()
        )

    def _reduced() -> bool:
        u_cart = lattice @ u_current
        v_cart = lattice @ v_current
        u_norm_squared = float(np.dot(u_cart, u_cart))
        v_norm_squared = float(np.dot(v_cart, v_cart))
        if not np.isfinite(u_norm_squared) or u_norm_squared <= 0.0:
            raise ValueError("In-plane basis is singular in the primitive metric")
        if not np.isfinite(v_norm_squared) or v_norm_squared <= 0.0:
            raise ValueError("In-plane basis is singular in the primitive metric")
        coefficient = float(np.dot(u_cart, v_cart)) / u_norm_squared
        return u_norm_squared <= v_norm_squared and abs(coefficient) <= 0.5 + 1e-12

    updates = 0
    while True:
        state = _state()
        if state in seen:
            raise BoundedGaugeSearchError(
                "Primitive in-plane Gauss reduction entered a cycle."
            )
        seen.add(state)

        u_cart = lattice @ u_current
        v_cart = lattice @ v_current
        u_norm_squared = float(np.dot(u_cart, u_cart))
        v_norm_squared = float(np.dot(v_cart, v_cart))
        if not np.isfinite(u_norm_squared) or u_norm_squared <= 0.0:
            raise ValueError("In-plane basis is singular in the primitive metric")
        if not np.isfinite(v_norm_squared) or v_norm_squared <= 0.0:
            raise ValueError("In-plane basis is singular in the primitive metric")

        if v_norm_squared < u_norm_squared:
            u_current, v_current = v_current, u_current
            u_cart, v_cart = v_cart, u_cart
            u_norm_squared = v_norm_squared

        reduction_coefficient = float(np.dot(u_cart, v_cart)) / u_norm_squared
        if abs(reduction_coefficient) <= 0.5 + 1e-12:
            return u_current, v_current
        if updates >= iteration_limit:
            break
        v_current = v_current - int(round(reduction_coefficient)) * u_current
        updates += 1

    if _reduced():
        return u_current, v_current
    raise BoundedGaugeSearchError(
        "Primitive in-plane Gauss reduction exhausted "
        "primitive_reduction_max_iter before verification."
    )


def compute_primitive_surface_basis(
    h: int,
    k: int,
    l: int,  # noqa: E741 - (h,k,l) are canonical Miller indices
    A_conv: np.ndarray,
    A_prim: np.ndarray,
    *,
    max_denominator: int = DEFAULT_PRIMITIVE_MAX_DENOMINATOR,
    reduction_max_iter: int = DEFAULT_PRIMITIVE_REDUCTION_MAX_ITER,
    stacking_search_radius: int = DEFAULT_STACKING_SEARCH_RADIUS,
    atol: float = 1e-10,
    rtol: float = 1e-10,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Construct a primitive bulk-induced surface-plane basis.

    Returned vectors are integer fractional-coordinate columns in the
    primitive bulk basis.  The exact certificates are

    ``m @ u = m @ v = 0``, ``cross(u,v) = m``, and ``m @ w = 1``.

    The kernel construction is exact for an admissible rational basis
    transform.  Metric Gauss reduction and stacking shear selection are gauge
    choices; they preserve the certificates but do not establish decorated
    surface-motif minimality. ``reduction_max_iter`` bounds integer Gauss
    updates. ``stacking_search_radius`` bounds the certified square search
    around the continuous stacking-gauge center.
    """
    primitive = _as_lattice_matrix("A_prim", A_prim)
    primitive_miller = primitive_miller_from_conventional(
        A_conv,
        primitive,
        (h, k, l),
        max_denominator=max_denominator,
        atol=atol,
        rtol=rtol,
    )

    u, v, bezout_w = _primitive_surface_triplet_from_m(primitive_miller)

    u, v = _reduce_2d_basis(
        u,
        v,
        primitive,
        max_iter=reduction_max_iter,
    )
    cross_uv = np.cross(u, v)
    if np.array_equal(cross_uv, -primitive_miller):
        # Gauss norm ordering may reverse the two-vector basis. Fix that
        # final discrete gauge without changing vector lengths or the reduced
        # in-plane metric.
        v = -v
        cross_uv = -cross_uv
    if not np.array_equal(cross_uv, primitive_miller):
        raise ValueError(
            "In-plane basis is not an oriented primitive kernel: "
            f"cross(u,v)={cross_uv.tolist()} vs "
            f"m={primitive_miller.tolist()}"
        )

    w = minimize_shear(
        bezout_w,
        u,
        v,
        primitive,
        search_radius=stacking_search_radius,
    )
    if int(np.dot(primitive_miller, w)) != 1:
        raise ValueError(
            "Shear minimization broke the Bezout certificate: "
            f"m.w={int(np.dot(primitive_miller, w))}"
        )
    triple_product = int(np.dot(cross_uv, w))
    if triple_product != 1:
        raise ValueError(
            "Primitive surface basis must be right-handed and unimodular: "
            f"det([u v w])={triple_product}"
        )
    return u, v, w, primitive_miller
