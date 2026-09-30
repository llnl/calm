"""Dependency-light invariants for primitive surface-plane construction."""

from __future__ import annotations

import numpy as np
import pytest

from calm.slab.oriented._primitive import (
    compute_primitive_surface_basis,
    primitive_miller_from_conventional,
)
from surface_basis_oracle import validate_surface_basis


def _skew_primitive_basis() -> np.ndarray:
    return np.array(
        [
            [2.0, 0.3, -0.2],
            [0.1, 1.7, 0.4],
            [0.2, -0.1, 2.3],
        ],
        dtype=float,
    )


def test_exact_inverse_denominator_is_not_bounded_by_direct_transform() -> None:
    primitive = np.eye(3)
    conventional = np.diag([13.0, 1.0, 1.0])

    miller = primitive_miller_from_conventional(
        conventional,
        primitive,
        (1, 1, 0),
        max_denominator=12,
    )

    assert np.array_equal(miller, np.array([1, 13, 0], dtype=int))


def test_rational_direct_transform_preserves_covector_orientation() -> None:
    primitive = _skew_primitive_basis()
    direct_transform = np.diag([0.5, 1.0, 1.0])
    conventional = primitive @ direct_transform

    miller = primitive_miller_from_conventional(
        conventional,
        primitive,
        (1, 1, 0),
        max_denominator=2,
    )

    assert np.array_equal(miller, np.array([2, 1, 0], dtype=int))


def test_complete_basis_is_uniform_scale_invariant() -> None:
    primitive_base = _skew_primitive_basis()
    direct_transform = np.diag([13.0, 1.0, 1.0])
    outputs: list[tuple[tuple[int, ...], ...]] = []

    for scale in [1e-150, 1e-12, 1.0, 1e12, 1e150]:
        primitive = scale * primitive_base
        conventional = primitive @ direct_transform
        u, v, w, miller = compute_primitive_surface_basis(
            1,
            1,
            0,
            conventional,
            primitive,
            max_denominator=12,
        )
        outputs.append(
            tuple(tuple(int(value) for value in vector) for vector in (u, v, w, miller))
        )
        ok, diagnostics = validate_surface_basis(
            primitive,
            miller,
            u,
            v,
            w,
            layers=7,
        )
        assert ok, diagnostics
        assert diagnostics["det_T"] == 7

    assert all(output == outputs[0] for output in outputs[1:])


def test_nonprimitive_hkl_has_same_primitive_plane_certificates() -> None:
    primitive = _skew_primitive_basis()
    first = compute_primitive_surface_basis(2, 2, 0, primitive, primitive)
    second = compute_primitive_surface_basis(1, 1, 0, primitive, primitive)

    for left, right in zip(first, second, strict=True):
        assert np.array_equal(left, right)


def test_validator_rejects_non_bezout_stacking_vector() -> None:
    primitive = np.eye(3)
    u, v, w, miller = compute_primitive_surface_basis(
        2,
        1,
        3,
        primitive,
        primitive,
    )

    ok, diagnostics = validate_surface_basis(
        primitive,
        miller,
        u,
        v,
        2 * w,
        layers=1,
    )

    assert not ok
    assert diagnostics["error_bezout"] is True
    assert diagnostics["error_det_mismatch"] is True


@pytest.mark.parametrize(
    ("conventional", "primitive", "match"),
    [
        (np.eye(2), np.eye(3), "A_conv must have shape"),
        (np.eye(3), np.eye(2), "A_prim must have shape"),
        (np.zeros((3, 3)), np.eye(3), "must both be nonsingular"),
    ],
)
def test_miller_transform_rejects_invalid_lattice_matrices(
    conventional: np.ndarray,
    primitive: np.ndarray,
    match: str,
) -> None:
    with pytest.raises(ValueError, match=match):
        primitive_miller_from_conventional(
            conventional,
            primitive,
            (1, 0, 0),
        )


def test_exact_integer_inputs_are_not_silently_truncated() -> None:
    identity = np.eye(3)

    with pytest.raises(ValueError, match="h_conv must contain integers"):
        primitive_miller_from_conventional(
            identity,
            identity,
            (1.5, 0.0, 0.0),
        )

    with pytest.raises(ValueError, match="u must contain integers"):
        validate_surface_basis(
            identity,
            np.array([1, 0, 0]),
            np.array([0.0, 1.5, 0.0]),
            np.array([0, 0, 1]),
            np.array([1, 0, 0]),
        )

    with pytest.raises(ValueError, match="layers must be a positive integer"):
        validate_surface_basis(
            identity,
            np.array([1, 0, 0]),
            np.array([0, 1, 0]),
            np.array([0, 0, 1]),
            np.array([1, 0, 0]),
            layers=1.5,
        )
