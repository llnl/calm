"""Mathematical contracts for certified surface-supercell relations."""

from __future__ import annotations

import numpy as np
import pytest

from calm.slab.oriented._primitive import (
    certify_integer_surface_supercell_relation,
)


SKEW_PRIMITIVE_ROWS = np.array(
    [
        [2.0, 0.0, 0.0],
        [0.4, 1.0, 0.0],
    ]
)


def test_non_lattice_length_shortening_counterexample_is_rejected() -> None:
    invalid_rows = np.array(
        [
            [1.0, 0.0, 0.0],
            [0.4, 1.0, 0.0],
        ]
    )

    with pytest.raises(ValueError, match="not integral"):
        certify_integer_surface_supercell_relation(
            SKEW_PRIMITIVE_ROWS,
            invalid_rows,
        )


@pytest.mark.parametrize(
    "matrix",
    [
        np.array([[2, 1], [0, 3]], dtype=int),
        np.array([[2, 0], [1, 3]], dtype=int),
        np.array([[3, 2], [1, 2]], dtype=int),
        np.array([[2, 0], [0, 4]], dtype=int),
        np.array([[0, -1], [1, 0]], dtype=int),
    ],
)
def test_full_integer_surface_relation_is_recovered(matrix: np.ndarray) -> None:
    supercell_rows = matrix.T @ SKEW_PRIMITIVE_ROWS

    relation = certify_integer_surface_supercell_relation(
        SKEW_PRIMITIVE_ROWS,
        supercell_rows,
    )

    np.testing.assert_array_equal(relation.matrix, matrix)
    assert relation.index == int(round(np.linalg.det(matrix)))
    np.testing.assert_allclose(
        relation.matrix.T @ SKEW_PRIMITIVE_ROWS,
        supercell_rows,
        atol=0.0,
        rtol=0.0,
    )
    assert not relation.matrix.flags.writeable


@pytest.mark.parametrize("scale", [1.0e-9, 1.0, 1.0e9])
def test_integer_relation_is_covariant_under_uniform_rescaling(scale: float) -> None:
    matrix = np.array([[4, 1], [1, 2]], dtype=int)
    primitive_rows = scale * SKEW_PRIMITIVE_ROWS
    supercell_rows = matrix.T @ primitive_rows

    relation = certify_integer_surface_supercell_relation(
        primitive_rows,
        supercell_rows,
    )

    np.testing.assert_array_equal(relation.matrix, matrix)
    assert relation.index == 7


def test_near_integer_relation_obeys_declared_tolerance() -> None:
    matrix = np.array([[2.0, 1.0], [0.0, 3.0]])
    inside = matrix.copy()
    inside[0, 1] += 4.0e-7
    outside = matrix.copy()
    outside[0, 1] += 2.0e-6

    accepted = certify_integer_surface_supercell_relation(
        SKEW_PRIMITIVE_ROWS,
        inside.T @ SKEW_PRIMITIVE_ROWS,
        tol=1.0e-6,
    )
    np.testing.assert_array_equal(accepted.matrix, matrix.astype(int))

    with pytest.raises(ValueError, match="not integral"):
        certify_integer_surface_supercell_relation(
            SKEW_PRIMITIVE_ROWS,
            outside.T @ SKEW_PRIMITIVE_ROWS,
            tol=1.0e-6,
        )


def test_orientation_reversing_basis_is_rejected() -> None:
    swapped_rows = SKEW_PRIMITIVE_ROWS[[1, 0]]

    with pytest.raises(ValueError, match="reverses orientation"):
        certify_integer_surface_supercell_relation(
            SKEW_PRIMITIVE_ROWS,
            swapped_rows,
        )


def test_singular_or_invalid_inputs_are_rejected() -> None:
    singular = np.array([[1.0, 0.0, 0.0], [2.0, 0.0, 0.0]])

    with pytest.raises(ValueError, match="linearly independent"):
        certify_integer_surface_supercell_relation(singular, singular)
    with pytest.raises(ValueError, match="finite positive"):
        certify_integer_surface_supercell_relation(
            SKEW_PRIMITIVE_ROWS,
            SKEW_PRIMITIVE_ROWS,
            tol=-1.0,
        )
    with pytest.raises(ValueError, match="finite positive"):
        certify_integer_surface_supercell_relation(
            SKEW_PRIMITIVE_ROWS,
            SKEW_PRIMITIVE_ROWS,
            tol=0.0,
        )
