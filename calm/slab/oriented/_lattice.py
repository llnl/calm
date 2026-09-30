"""Dependency-light lattice and Cartesian-frame helpers for slab construction.

The helpers in this module own the exact Miller-index normalization, proper
rotation construction, bounded integer c-tilt gauge, and continuous
c-orthogonalization mathematics used by the oriented-slab builders.  They do
not import ASE or spglib, which keeps their invariants directly testable in
minimal environments.
"""

from __future__ import annotations

import math
from numbers import Integral, Real
from typing import Any, Sequence

import numpy as np

from calm.exceptions import BoundedGaugeSearchError

DEFAULT_C_TILT_SEARCH_RADIUS = 6
DEFAULT_C_TILT_SINGULAR_TOLERANCE = 1e-12


def _gcd3(a: int, b: int, c: int) -> int:
    return math.gcd(math.gcd(abs(a), abs(b)), abs(c))


def _integer_triplet(name: str, value: Sequence[int]) -> tuple[int, int, int]:
    raw = tuple(value)
    if len(raw) != 3:
        raise ValueError(f"{name} must contain exactly three integers")
    if not all(isinstance(item, (Integral, np.integer)) for item in raw):
        raise ValueError(f"{name} must contain integers")
    return tuple(int(item) for item in raw)  # type: ignore[return-value]


def _positive_integer(name: str, value: int) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(
        value,
        (Integral, np.integer),
    ):
        raise ValueError(f"{name} must be an integer")
    result = int(value)
    if result <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return result


def _nonnegative_integer(name: str, value: int) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(
        value,
        (Integral, np.integer),
    ):
        raise ValueError(f"{name} must be an integer")
    result = int(value)
    if result < 0:
        raise ValueError(f"{name} must be nonnegative")
    return result


def _nonnegative_finite_float(name: str, value: float) -> float:
    if isinstance(value, (bool, np.bool_)) or not isinstance(
        value,
        (Real, np.floating, np.integer),
    ):
        raise ValueError(f"{name} must be a real number")
    result = float(value)
    if not np.isfinite(result) or result < 0.0:
        raise ValueError(f"{name} must be finite and nonnegative")
    return result


def _positive_finite_float(name: str, value: float) -> float:
    result = _nonnegative_finite_float(name, value)
    if result <= 0.0:
        raise ValueError(f"{name} must be finite and positive")
    return result


def _normal_sign(value: int) -> int:
    if not isinstance(value, (Integral, np.integer)) or int(value) not in (-1, 1):
        raise ValueError("normal_sign must be either +1 or -1")
    return int(value)


def _reduce_hkl(hkl: tuple[int, int, int]) -> tuple[int, int, int]:
    h, k, ell = _integer_triplet("hkl", hkl)
    divisor = _gcd3(h, k, ell)
    if divisor == 0:
        raise ValueError("Invalid Miller index (0,0,0).")
    return (h // divisor, k // divisor, ell // divisor)


def _right_reduce_row_to_hnf(h: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    raw = np.asarray(h)
    if raw.shape != (3,):
        raise ValueError("h must be shape (3,)")
    if not np.issubdtype(raw.dtype, np.integer):
        raise ValueError("h must contain integers")
    h_work = raw.astype(int, copy=True)

    transform = np.eye(3, dtype=int)

    if h_work[0] == 0:
        if h_work[1] != 0:
            h_work[[0, 1]] = h_work[[1, 0]]
            transform[:, [0, 1]] = transform[:, [1, 0]]
        elif h_work[2] != 0:
            h_work[[0, 2]] = h_work[[2, 0]]
            transform[:, [0, 2]] = transform[:, [2, 0]]
        else:
            raise ValueError("h cannot be zero vector")

    for column in (1, 2):
        leading = int(h_work[0])
        trailing = int(h_work[column])
        if trailing == 0:
            continue
        old_r, remainder = abs(leading), abs(trailing)
        old_s, coefficient_s = 1, 0
        old_t, coefficient_t = 0, 1
        while remainder != 0:
            quotient = old_r // remainder
            old_r, remainder = remainder, old_r - quotient * remainder
            old_s, coefficient_s = coefficient_s, old_s - quotient * coefficient_s
            old_t, coefficient_t = coefficient_t, old_t - quotient * coefficient_t
        divisor = old_r
        coefficient_leading = old_s if leading >= 0 else -old_s
        coefficient_trailing = old_t if trailing >= 0 else -old_t
        step = np.eye(3, dtype=int)
        step[0, 0] = coefficient_leading
        step[0, column] = -trailing // divisor
        step[column, 0] = coefficient_trailing
        step[column, column] = leading // divisor
        h_work = h_work @ step
        transform = transform @ step

    if h_work[0] < 0:
        step = np.eye(3, dtype=int)
        step[0, 0] = -1
        h_work = h_work @ step
        transform = transform @ step

    return h_work, transform


def surface_basis_S_from_hkl(hkl: tuple[int, int, int]) -> np.ndarray:
    hkl_reduced = np.array(_reduce_hkl(hkl), dtype=int)
    row_reduced, transform = _right_reduce_row_to_hnf(hkl_reduced)
    if not np.array_equal(row_reduced, np.array([1, 0, 0], dtype=int)):
        raise RuntimeError(
            "Internal reduction failed; got "
            f"h_reduced={row_reduced.tolist()} for hkl={hkl_reduced.tolist()}"
        )
    surface_basis = transform[:, [1, 2, 0]].copy()
    determinant = int(round(np.linalg.det(surface_basis)))
    if determinant == -1:
        surface_basis[:, 0] *= -1
        determinant = int(round(np.linalg.det(surface_basis)))
    if determinant != 1:
        raise RuntimeError(
            "Expected det(S)=+1; got "
            f"det(S)={determinant} for hkl={hkl_reduced.tolist()}"
        )
    if not np.array_equal(
        hkl_reduced @ surface_basis,
        np.array([0, 0, 1], dtype=int),
    ):
        raise RuntimeError("Construction error: hkl @ S != (0,0,1).")
    return surface_basis


def verify_surface_kernel_is_primitive(
    hkl: tuple[int, int, int],
    S_col: np.ndarray,
) -> dict[str, Any]:
    h = np.array(_reduce_hkl(hkl), dtype=int)
    raw = np.asarray(S_col)
    if raw.shape != (3, 3):
        raise ValueError("S_col must be (3,3) integer matrix with columns [u v w].")
    if not np.issubdtype(raw.dtype, np.integer):
        raise ValueError("S_col must contain integers")
    surface_basis = raw.astype(int, copy=False)
    u = surface_basis[:, 0]
    v = surface_basis[:, 1]
    w = surface_basis[:, 2]
    determinant = int(round(np.linalg.det(surface_basis)))
    h_dot_u = int(h @ u)
    h_dot_v = int(h @ v)
    h_dot_w = int(h @ w)
    cross = np.cross(u, v)

    multiplier = None
    is_multiple = True
    for index in range(3):
        if h[index] == 0:
            if cross[index] != 0:
                is_multiple = False
                break
            continue
        if cross[index] % h[index] != 0:
            is_multiple = False
            break
        candidate = int(cross[index] // h[index])
        if multiplier is None:
            multiplier = candidate
        elif candidate != multiplier:
            is_multiple = False
            break

    primitive = bool(
        is_multiple and multiplier is not None and abs(int(multiplier)) == 1
    )
    return {
        "hkl_reduced": h.tolist(),
        "detS": determinant,
        "h_dot_u": h_dot_u,
        "h_dot_v": h_dot_v,
        "h_dot_w": h_dot_w,
        "u_cross_v": cross.tolist(),
        "multiple_m": multiplier,
        "primitive_kernel_basis": primitive,
    }


def _finite_vector3(name: str, value: np.ndarray) -> np.ndarray:
    vector = np.asarray(value, dtype=float)
    if vector.shape != (3,):
        raise ValueError(f"{name} must have shape (3,), got {vector.shape}")
    if not np.all(np.isfinite(vector)):
        raise ValueError(f"{name} must contain only finite values")
    return vector


def _unit_vector(name: str, value: np.ndarray) -> tuple[np.ndarray, float]:
    vector = _finite_vector3(name, value)
    scale = float(np.max(np.abs(vector)))
    if scale <= 0.0:
        raise ValueError(f"{name} must be nonzero")
    scaled = vector / scale
    scaled_norm = float(np.linalg.norm(scaled))
    if not np.isfinite(scaled_norm) or scaled_norm <= 0.0:
        raise ValueError(f"{name} must have a finite, nonzero norm")
    return scaled / scaled_norm, scale * scaled_norm


def _validate_rotation(rotation: np.ndarray, *, ortho_tol: float) -> np.ndarray:
    tolerance = _nonnegative_finite_float("ortho_tol", ortho_tol)
    if not np.allclose(
        rotation.T @ rotation,
        np.eye(3),
        atol=tolerance,
        rtol=0.0,
    ):
        raise RuntimeError(
            "Rotation is not orthonormal within tolerance; construction failed."
        )
    determinant = float(np.linalg.det(rotation))
    if not np.isclose(determinant, 1.0, atol=tolerance, rtol=0.0):
        raise RuntimeError(f"Rotation is not proper (det != +1); det(R)={determinant}")
    return rotation


def _compute_R_from_normal_and_inplane(
    surface_normal: np.ndarray,
    inplane_vector: np.ndarray,
    *,
    normal_sign: int = +1,
    ortho_tol: float = 1e-10,
) -> np.ndarray:
    sign = _normal_sign(normal_sign)
    normal_hat, _ = _unit_vector("surface_normal", surface_normal)
    vector = _finite_vector3("inplane_vector", inplane_vector)
    vector_scale = float(np.max(np.abs(vector)))
    if vector_scale <= 0.0:
        raise ValueError("inplane_vector must be nonzero")

    z_hat = float(sign) * normal_hat
    projected = vector - float(np.dot(vector, z_hat)) * z_hat
    projected_norm = float(np.linalg.norm(projected / vector_scale))
    threshold = max(
        _nonnegative_finite_float("ortho_tol", ortho_tol),
        32.0 * np.finfo(float).eps,
    )
    if projected_norm <= threshold:
        raise ValueError("inplane_vector is parallel to surface_normal")
    x_hat = projected / float(np.linalg.norm(projected))
    y_hat = np.cross(z_hat, x_hat)
    y_hat /= float(np.linalg.norm(y_hat))
    rotation = np.vstack([x_hat, y_hat, z_hat])
    return _validate_rotation(rotation, ortho_tol=ortho_tol)


def _compute_R_from_ab_to_xy(
    a: np.ndarray,
    b: np.ndarray,
    *,
    normal_sign: int = +1,
    ortho_tol: float = 1e-10,
) -> np.ndarray:
    vector_a = _finite_vector3("a", a)
    vector_b = _finite_vector3("b", b)
    a_hat, _ = _unit_vector("a", vector_a)
    b_hat, _ = _unit_vector("b", vector_b)
    normal = np.cross(a_hat, b_hat)
    threshold = max(
        _nonnegative_finite_float("ortho_tol", ortho_tol),
        32.0 * np.finfo(float).eps,
    )
    if float(np.linalg.norm(normal)) <= threshold:
        raise ValueError("a and b are nearly colinear; cannot define a plane")
    return _compute_R_from_normal_and_inplane(
        normal,
        vector_a,
        normal_sign=normal_sign,
        ortho_tol=ortho_tol,
    )


def _to_int_mat(
    M: np.ndarray,
    *,
    name: str = "M",
    atol: float = 1e-6,
) -> np.ndarray:
    array = np.asarray(M, dtype=float)
    if array.ndim != 2:
        raise ValueError(f"{name} must be 2D; got shape={array.shape}")
    integer = np.rint(array).astype(int)
    if not np.allclose(array, integer, atol=atol, rtol=0.0):
        max_error = float(np.max(np.abs(array - integer)))
        raise ValueError(
            f"{name} is not close to an integer matrix "
            f"(max|delta|={max_error:.3e}, atol={atol})."
        )
    return integer


def _embed_u2_into_u3(U2: np.ndarray) -> np.ndarray:
    matrix = np.asarray(U2)
    if matrix.shape != (2, 2):
        raise ValueError("U2 must be (2,2)")
    if not np.issubdtype(matrix.dtype, np.integer):
        raise ValueError("U2 must contain integers")
    embedded = np.eye(3, dtype=int)
    embedded[:2, :2] = matrix.astype(int, copy=False)
    return embedded


def _cell_matrix_row(value: np.ndarray) -> np.ndarray:
    cell = np.asarray(value, dtype=float)
    if cell.shape != (3, 3):
        raise ValueError(f"cell must have shape (3,3), got {cell.shape}")
    if not np.all(np.isfinite(cell)):
        raise ValueError("cell must contain only finite values")
    return cell


def _relative_inplane_determinant(a_xy: np.ndarray, b_xy: np.ndarray) -> float:
    norm_product = float(np.linalg.norm(a_xy) * np.linalg.norm(b_xy))
    if norm_product <= 0.0:
        return 0.0
    determinant = float(np.linalg.det(np.column_stack([a_xy, b_xy])))
    return abs(determinant) / norm_product


def _c_tilt_reduction_matrix(
    cell_row: np.ndarray,
    *,
    search: int = DEFAULT_C_TILT_SEARCH_RADIUS,
    singular_tol: float = DEFAULT_C_TILT_SINGULAR_TOLERANCE,
) -> tuple[tuple[int, int], np.ndarray]:
    """Return a certified bounded integer c-tilt gauge.

    The search enumerates ``c <- c + m*a + n*b`` in the square neighborhood
    centered on the rounded continuous least-squares solution.  Ties use
    ``(objective, |m|+|n|, |m|, |n|, m, n)``.  A minimizer on the declared
    boundary is not certified and raises rather than implying global
    closest-vector optimality.
    """
    cell = _cell_matrix_row(cell_row)
    radius = _positive_integer("c_tilt_search", search)
    tolerance = _positive_finite_float(
        "c_tilt_singular_tolerance",
        singular_tol,
    )
    a_xy = cell[0, :2]
    b_xy = cell[1, :2]
    c_xy = cell[2, :2]
    if _relative_inplane_determinant(a_xy, b_xy) <= tolerance:
        raise ValueError("In-plane lattice is nearly singular; cannot reduce c tilt")

    scale = max(
        float(np.max(np.abs(a_xy))),
        float(np.max(np.abs(b_xy))),
        float(np.max(np.abs(c_xy))),
        np.finfo(float).tiny,
    )
    basis = np.column_stack([a_xy / scale, b_xy / scale])
    try:
        coefficients = np.linalg.solve(basis, c_xy / scale)
    except np.linalg.LinAlgError as exc:
        raise BoundedGaugeSearchError(
            "Unable to solve the continuous c-tilt gauge center."
        ) from exc
    if not np.all(np.isfinite(coefficients)):
        raise BoundedGaugeSearchError("The c-tilt gauge center is nonfinite.")
    rounded = np.rint(-coefficients)
    max_int = float(np.iinfo(np.int64).max)
    if float(np.max(np.abs(rounded))) > max_int:
        raise BoundedGaugeSearchError(
            "The c-tilt gauge center exceeds the supported integer range."
        )
    center_m, center_n = rounded.astype(np.int64)

    best_key: tuple[float, int, int, int, int, int] | None = None
    best_pair: tuple[int, int] | None = None
    best_delta: tuple[int, int] | None = None
    for delta_m in range(-radius, radius + 1):
        for delta_n in range(-radius, radius + 1):
            m = int(center_m) + delta_m
            n = int(center_n) + delta_n
            residual = c_xy / scale + m * a_xy / scale + n * b_xy / scale
            objective = float(np.dot(residual, residual))
            if not np.isfinite(objective):
                raise BoundedGaugeSearchError("The c-tilt objective became nonfinite.")
            key = (
                objective,
                abs(m) + abs(n),
                abs(m),
                abs(n),
                m,
                n,
            )
            if best_key is None or key < best_key:
                best_key = key
                best_pair = (m, n)
                best_delta = (delta_m, delta_n)

    if best_pair is None or best_delta is None:
        raise BoundedGaugeSearchError("The c-tilt gauge search produced no candidate.")
    if abs(best_delta[0]) == radius or abs(best_delta[1]) == radius:
        raise BoundedGaugeSearchError(
            "The best c-tilt representative lies on the declared search "
            "boundary; increase c_tilt_search."
        )

    m, n = best_pair
    row_transform = np.array(
        [[1, 0, 0], [0, 1, 0], [m, n, 1]],
        dtype=int,
    )
    return (int(m), int(n)), row_transform


def _c_orthogonalization_from_cell(
    cell_row: np.ndarray,
    *,
    z_axis: int = 2,
    z_tol: float = 1e-10,
    singular_tol: float = 1e-12,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, float, float]:
    cell = _cell_matrix_row(cell_row)
    if z_axis not in (0, 1, 2):
        raise ValueError("z_axis must be 0, 1, or 2")
    alignment_tolerance = _nonnegative_finite_float("z_tol", z_tol)
    singular_tolerance = _nonnegative_finite_float(
        "singular_tol",
        singular_tol,
    )

    a, b, c = cell
    for name, vector in (("a", a), ("b", b)):
        vector_norm = float(np.linalg.norm(vector))
        if vector_norm <= 0.0:
            raise ValueError(f"{name} must be nonzero")
        if abs(float(vector[z_axis])) > alignment_tolerance * vector_norm:
            raise ValueError(
                "Expected oriented slab with in-plane vectors normal to the "
                f"selected z axis; {name}[z_axis]={vector[z_axis]:.3e}"
            )

    inplane_axes = [axis for axis in range(3) if axis != z_axis]
    a_plane = a[inplane_axes]
    b_plane = b[inplane_axes]
    c_plane = c[inplane_axes]
    if _relative_inplane_determinant(a_plane, b_plane) <= singular_tolerance:
        raise ValueError("In-plane lattice is nearly singular; cannot orthogonalize c")

    scale = max(
        float(np.max(np.abs(a_plane))),
        float(np.max(np.abs(b_plane))),
        float(np.max(np.abs(c_plane))),
        np.finfo(float).tiny,
    )
    basis = np.column_stack([a_plane / scale, b_plane / scale])
    alpha, beta = np.linalg.solve(basis, c_plane / scale)
    lattice_shear = np.array(
        [
            [1.0, 0.0, -float(alpha)],
            [0.0, 1.0, -float(beta)],
            [0.0, 0.0, 1.0],
        ],
        dtype=float,
    )
    cell_new = lattice_shear.T @ cell
    deformation = cell_new.T @ np.linalg.inv(cell.T)
    return cell_new, lattice_shear, deformation, float(alpha), float(beta)
