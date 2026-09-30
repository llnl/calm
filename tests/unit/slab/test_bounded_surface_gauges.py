"""Executable contracts for bounded primitive-surface gauge controls."""

from __future__ import annotations

import numpy as np
import pytest

from calm.exceptions import BoundedGaugeSearchError
from calm.slab.oriented._lattice import _c_tilt_reduction_matrix
from calm.slab.oriented._primitive import (
    _reduce_2d_basis,
    minimize_shear,
    primitive_miller_from_conventional,
)


def _boundary_case_lattice_columns() -> np.ndarray:
    return np.array(
        [
            [1.0, 1.0038911365688594, 1.2969663843896453],
            [0.0, 0.056543274203071335, -1.144948146499618],
            [0.0, 0.0, 1.5346406940224773],
        ],
        dtype=float,
    )


def test_primitive_rationalization_succeeds_at_declared_denominator() -> None:
    primitive = np.eye(3)
    conventional = primitive @ np.diag([1.0 / 12.0, 1.0, 1.0])

    result = primitive_miller_from_conventional(
        conventional,
        primitive,
        (1, 1, 0),
        max_denominator=12,
    )

    assert np.array_equal(result, np.array([12, 1, 0], dtype=int))
    with pytest.raises(ValueError, match="increase max_denominator"):
        primitive_miller_from_conventional(
            conventional,
            primitive,
            (1, 1, 0),
            max_denominator=11,
        )


@pytest.mark.parametrize("value", [0, -1])
def test_primitive_denominator_rejects_nonpositive_bounds(value: int) -> None:
    with pytest.raises(ValueError, match="max_denominator"):
        primitive_miller_from_conventional(
            np.eye(3),
            np.eye(3),
            (1, 0, 0),
            max_denominator=value,
        )


@pytest.mark.parametrize("value", [True, 2.5])
def test_primitive_denominator_requires_an_exact_integer(value: object) -> None:
    with pytest.raises(TypeError, match="max_denominator"):
        primitive_miller_from_conventional(
            np.eye(3),
            np.eye(3),
            (1, 0, 0),
            max_denominator=value,  # type: ignore[arg-type]
        )


def test_stacking_gauge_fails_on_boundary_then_succeeds_inside() -> None:
    lattice = _boundary_case_lattice_columns()
    u = np.array([1, 0, 0], dtype=int)
    v = np.array([0, 1, 0], dtype=int)
    w = np.array([0, 0, 1], dtype=int)

    with pytest.raises(BoundedGaugeSearchError, match="search boundary"):
        minimize_shear(w, u, v, lattice, search_radius=1)

    result = minimize_shear(w, u, v, lattice, search_radius=2)
    assert np.array_equal(result, np.array([-21, 20, 1], dtype=int))
    assert np.array_equal(
        minimize_shear(w, u, v, lattice, search_radius=3),
        result,
    )
    assert int(np.dot(np.cross(u, v), result)) == 1


def test_c_tilt_gauge_fails_on_boundary_then_succeeds_inside() -> None:
    cell_rows = _boundary_case_lattice_columns().T

    with pytest.raises(BoundedGaugeSearchError, match="search boundary"):
        _c_tilt_reduction_matrix(cell_rows, search=1)

    pair, transform = _c_tilt_reduction_matrix(cell_rows, search=2)
    assert pair == (-21, 20)
    assert _c_tilt_reduction_matrix(cell_rows, search=3)[0] == pair
    assert np.array_equal(
        transform,
        np.array([[1, 0, 0], [0, 1, 0], [-21, 20, 1]], dtype=int),
    )
    assert round(np.linalg.det(transform)) == 1


def test_primitive_gauss_iteration_bound_fails_closed() -> None:
    u = np.array([34, 0, 0], dtype=int)
    v = np.array([55, 1, 0], dtype=int)

    with pytest.raises(BoundedGaugeSearchError, match="exhausted"):
        _reduce_2d_basis(u, v, np.eye(3), max_iter=2)

    reduced_u, reduced_v = _reduce_2d_basis(
        u,
        v,
        np.eye(3),
        max_iter=3,
    )
    assert np.array_equal(
        np.cross(reduced_u, reduced_v),
        np.cross(u, v),
    )


@pytest.mark.parametrize(
    ("function", "keyword"),
    [
        (minimize_shear, "stacking_search_radius"),
        (_c_tilt_reduction_matrix, "c_tilt_search"),
    ],
)
def test_bounded_gauges_reject_zero_radius(function, keyword: str) -> None:
    lattice = _boundary_case_lattice_columns()
    with pytest.raises(ValueError, match=keyword):
        if function is minimize_shear:
            function(
                np.array([0, 0, 1]),
                np.array([1, 0, 0]),
                np.array([0, 1, 0]),
                lattice,
                search_radius=0,
            )
        else:
            function(lattice.T, search=0)



@pytest.mark.parametrize("value", [0.0, -1.0, np.inf, np.nan, True])
def test_c_tilt_singular_tolerance_must_be_positive_finite(
    value: object,
) -> None:
    with pytest.raises(ValueError, match="c_tilt_singular_tolerance"):
        _c_tilt_reduction_matrix(
            _boundary_case_lattice_columns().T,
            singular_tol=value,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("value", [True, 2.5])
def test_bounded_integer_search_controls_reject_nonintegers(value: object) -> None:
    lattice = _boundary_case_lattice_columns()
    with pytest.raises((TypeError, ValueError), match="stacking_search_radius"):
        minimize_shear(
            np.array([0, 0, 1]),
            np.array([1, 0, 0]),
            np.array([0, 1, 0]),
            lattice,
            search_radius=value,  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError, match="c_tilt_search"):
        _c_tilt_reduction_matrix(
            lattice.T,
            search=value,  # type: ignore[arg-type]
        )



def test_c_tilt_singularity_boundary_is_explicit_and_open() -> None:
    cell = np.array(
        [
            [1.0, 0.0, 0.0],
            [np.sqrt(3.0) / 2.0, 0.5, 0.0],
            [0.0, 0.0, 1.0],
        ]
    )
    a_xy = cell[0, :2]
    b_xy = cell[1, :2]
    boundary = abs(float(np.linalg.det(np.column_stack([a_xy, b_xy])))) / (
        float(np.linalg.norm(a_xy)) * float(np.linalg.norm(b_xy))
    )
    with pytest.raises(ValueError, match="nearly singular"):
        _c_tilt_reduction_matrix(cell, singular_tol=boundary)

    pair, _ = _c_tilt_reduction_matrix(
        cell,
        singular_tol=np.nextafter(boundary, 0.0),
    )
    assert pair == (0, 0)



def test_stacking_and_c_tilt_half_ties_prefer_smaller_coefficients() -> None:
    lattice_columns = np.array(
        [
            [1.0, 0.0, 0.5],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ]
    )
    u = np.array([1, 0, 0], dtype=int)
    v = np.array([0, 1, 0], dtype=int)
    w = np.array([0, 0, 1], dtype=int)

    assert np.array_equal(
        minimize_shear(w, u, v, lattice_columns, search_radius=1),
        w,
    )

    pair, transform = _c_tilt_reduction_matrix(
        lattice_columns.T,
        search=1,
    )
    assert pair == (0, 0)
    assert np.array_equal(transform, np.eye(3, dtype=int))



@pytest.mark.parametrize("scale", [1e-150, 1e-12, 1.0, 1e12, 1e150])
def test_bounded_gauges_are_uniform_scale_covariant(scale: float) -> None:
    lattice = scale * _boundary_case_lattice_columns()
    u = np.array([1, 0, 0], dtype=int)
    v = np.array([0, 1, 0], dtype=int)
    w = np.array([0, 0, 1], dtype=int)

    assert np.array_equal(
        minimize_shear(w, u, v, lattice, search_radius=2),
        np.array([-21, 20, 1], dtype=int),
    )
    pair, _ = _c_tilt_reduction_matrix(lattice.T, search=2)
    assert pair == (-21, 20)



def test_bounded_gauge_representative_is_inplane_order_invariant() -> None:
    lattice = _boundary_case_lattice_columns()
    u = np.array([1, 0, 0], dtype=int)
    v = np.array([0, 1, 0], dtype=int)
    w = np.array([0, 0, 1], dtype=int)

    first = minimize_shear(w, u, v, lattice, search_radius=2)
    swapped = minimize_shear(w, v, u, lattice, search_radius=2)
    assert np.array_equal(swapped, first)

    cell = lattice.T
    pair, transform = _c_tilt_reduction_matrix(cell, search=2)
    swapped_cell = cell[[1, 0, 2], :]
    swapped_pair, swapped_transform = _c_tilt_reduction_matrix(
        swapped_cell,
        search=2,
    )
    assert swapped_pair == (pair[1], pair[0])
    assert np.allclose(
        (transform @ cell)[2],
        (swapped_transform @ swapped_cell)[2],
    )
