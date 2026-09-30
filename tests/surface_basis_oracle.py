"""Validation utilities for primitive surface-basis certificates."""

from __future__ import annotations

import numpy as np

def is_near_zero(
    x: float,
    scale: float = 1.0,
    *,
    atol: float = 1e-10,
    rtol: float = 1e-10,
) -> bool:
    """Independent tolerance predicate for the surface-basis test oracle."""
    return abs(float(x)) <= float(atol) + float(rtol) * float(scale)



def _integer_vector(name: str, value: np.ndarray) -> np.ndarray:
    raw = np.asarray(value)
    if raw.shape != (3,):
        raise ValueError(f"{name} must have shape (3,), got {raw.shape}")
    if not np.issubdtype(raw.dtype, np.integer):
        raise ValueError(f"{name} must contain integers")
    return raw.astype(int, copy=False)


def _positive_integer_layers(layers: int) -> int:
    if isinstance(layers, (bool, np.bool_)) or not isinstance(
        layers,
        (int, np.integer),
    ):
        raise ValueError("layers must be a positive integer")
    value = int(layers)
    if value <= 0:
        raise ValueError("layers must be a positive integer")
    return value


def _finite_lattice(A_prim: np.ndarray) -> np.ndarray:
    lattice = np.asarray(A_prim, dtype=float)
    if lattice.shape != (3, 3):
        raise ValueError(f"A_prim must have shape (3, 3), got {lattice.shape}")
    if not np.all(np.isfinite(lattice)):
        raise ValueError("A_prim must contain only finite values")
    return lattice


def _validate_exact_invariants(
    miller: np.ndarray,
    u_vector: np.ndarray,
    v_vector: np.ndarray,
    w_vector: np.ndarray,
    layers: int,
    info: dict[str, object],
) -> bool:
    ok = True

    gcd_m = int(np.gcd.reduce(np.abs(miller)))
    info["gcd_m"] = gcd_m
    if gcd_m != 1:
        info["error_gcd_m"] = True
        ok = False

    m_dot_u = int(np.dot(miller, u_vector))
    m_dot_v = int(np.dot(miller, v_vector))
    m_dot_w = int(np.dot(miller, w_vector))
    info.update(
        {
            "m_dot_u": m_dot_u,
            "m_dot_v": m_dot_v,
            "m_dot_w": m_dot_w,
        }
    )
    if m_dot_u != 0 or m_dot_v != 0:
        info["error_kernel"] = True
        ok = False
    if m_dot_w != 1:
        info["error_bezout"] = True
        ok = False

    cross_uv = np.cross(u_vector, v_vector)
    info["cross_uv"] = cross_uv.tolist()
    if np.array_equal(cross_uv, miller):
        orientation = 1
    elif np.array_equal(cross_uv, -miller):
        orientation = -1
        info["error_handedness"] = True
        ok = False
    else:
        orientation = None
        info["error_primitivity"] = True
        ok = False
    info["cross_coeff_q"] = orientation

    determinant_signed = int(np.dot(cross_uv, layers * w_vector))
    info["det_T_signed"] = determinant_signed
    info["det_T"] = abs(determinant_signed)
    info["expected_det"] = layers
    info["expected_det_signed"] = layers
    if determinant_signed != layers:
        info["error_det_mismatch"] = True
        ok = False

    return ok


def _normalized_lattice(
    lattice: np.ndarray,
    info: dict[str, object],
) -> np.ndarray:
    lattice_scale = float(np.max(np.abs(lattice)))
    if lattice_scale <= 0.0:
        raise ValueError("A_prim must have a nonzero scale")
    info["lattice_scale"] = lattice_scale
    return lattice / lattice_scale


def _reciprocal_covector(
    lattice: np.ndarray,
    miller: np.ndarray,
) -> np.ndarray:
    try:
        return 2.0 * np.pi * np.linalg.solve(
            lattice.T,
            miller.astype(float),
        )
    except np.linalg.LinAlgError as exc:
        raise ValueError("A_prim must be nonsingular") from exc


def _validate_geometric_invariants(
    lattice: np.ndarray,
    miller: np.ndarray,
    u_vector: np.ndarray,
    v_vector: np.ndarray,
    *,
    atol: float,
    rtol: float,
    info: dict[str, object],
) -> bool:
    normalized_lattice = _normalized_lattice(lattice, info)
    reciprocal_covector = _reciprocal_covector(
        normalized_lattice,
        miller,
    )

    a_surface = normalized_lattice @ u_vector
    b_surface = normalized_lattice @ v_vector
    dot_a = float(np.dot(reciprocal_covector, a_surface))
    dot_b = float(np.dot(reciprocal_covector, b_surface))
    info["dot_g_as"] = dot_a
    info["dot_g_bs"] = dot_b

    tiny = np.finfo(float).tiny
    scale_a = max(
        float(np.linalg.norm(reciprocal_covector) * np.linalg.norm(a_surface)),
        tiny,
    )
    scale_b = max(
        float(np.linalg.norm(reciprocal_covector) * np.linalg.norm(b_surface)),
        tiny,
    )
    orthogonal = is_near_zero(
        dot_a,
        scale=scale_a,
        atol=atol,
        rtol=rtol,
    ) and is_near_zero(
        dot_b,
        scale=scale_b,
        atol=atol,
        rtol=rtol,
    )

    ok = True
    if not orthogonal:
        info["error_geometric_orthogonality"] = True
        ok = False

    area_actual = float(np.linalg.norm(np.cross(a_surface, b_surface)))
    primitive_normal = np.linalg.solve(
        normalized_lattice.T,
        miller.astype(float),
    )
    area_expected = float(
        abs(np.linalg.det(normalized_lattice))
        * np.linalg.norm(primitive_normal)
    )
    info["area_lhs"] = area_actual
    info["area_rhs"] = area_expected
    area_scale = max(area_actual, area_expected, tiny)
    if not is_near_zero(
        area_actual - area_expected,
        scale=area_scale,
        atol=atol,
        rtol=rtol,
    ):
        info["error_area_mismatch"] = True
        ok = False

    return ok


def validate_surface_basis(
    A_prim: np.ndarray,
    m: np.ndarray,
    u: np.ndarray,
    v: np.ndarray,
    w: np.ndarray,
    layers: int = 1,
    atol: float = 1e-8,
    rtol: float = 1e-10,
) -> tuple[bool, dict[str, object]]:
    """Validate exact and geometric primitive surface-basis invariants.

    Exact integer checks are authoritative. Floating-point checks independently
    verify that the Cartesian in-plane vectors are reciprocal-normal orthogonal
    and have the area implied by the primitive reciprocal covector.
    """
    layer_count = _positive_integer_layers(layers)
    if atol < 0.0 or rtol < 0.0:
        raise ValueError("atol and rtol must be nonnegative")

    lattice = _finite_lattice(A_prim)
    miller = _integer_vector("m", m)
    u_vector = _integer_vector("u", u)
    v_vector = _integer_vector("v", v)
    w_vector = _integer_vector("w", w)

    info: dict[str, object] = {"m": miller.tolist()}
    exact_ok = _validate_exact_invariants(
        miller,
        u_vector,
        v_vector,
        w_vector,
        layer_count,
        info,
    )
    geometric_ok = _validate_geometric_invariants(
        lattice,
        miller,
        u_vector,
        v_vector,
        atol=atol,
        rtol=rtol,
        info=info,
    )
    return exact_ok and geometric_ok, info
