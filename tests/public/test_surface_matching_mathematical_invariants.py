"""Mathematical guardrails for bounded surface-cell matching."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

pytest.importorskip("spglib")

from calm.interface.matching._surface_orbits import (
    enumerate_surface_cell_orbits_for_index,
)
from calm.interface.config import PrototypeSearchConfig
from calm.interface.matching.search import (
    compute_valid_hnf_index_pairs,
    enumerate_primitive_match_classes,
)


class _Cell:
    def __init__(self, array: np.ndarray) -> None:
        self.array = np.asarray(array, dtype=float)


class _Atoms:
    def __init__(self, cell: np.ndarray) -> None:
        self.cell = _Cell(cell)


def _orthogonal_slab(a: float, b: float, *, n_atoms: int = 1) -> SimpleNamespace:
    # ASE-compatible row-major cell.  The matching implementation reads the
    # transpose and then uses the xy block as a column-basis representation.
    return SimpleNamespace(
        atoms=_Atoms(np.array([[a, 0.0, 0.0], [0.0, b, 0.0], [0.0, 0.0, 10.0]])),
        n_atoms=int(n_atoms),
    )


def test_area_band_is_necessary_but_not_sufficient_for_shape_match() -> None:
    """Equal areas pass the determinant prefilter but can fail shape strain."""
    # Unit square and high-aspect-ratio rectangle have the same area, so the
    # determinant-pair area filter admits (1, 1) for any nonnegative bound.
    pairs = compute_valid_hnf_index_pairs(1.0, 1.0, 1, 1, eps_principal_max_f=0.5)
    assert pairs.tolist() == [[1, 1]]

    matches = enumerate_primitive_match_classes(
        _orthogonal_slab(1.0, 1.0),
        _orthogonal_slab(4.0, 0.25),
        PrototypeSearchConfig(
            k_max=1,
            eps_principal_max=0.5,
            cond_max=1.0e9,
            w_match=1.0,
            N_at_max=100,
            surface_symmetry_mode="identity_only",
        ),
    )

    assert matches == []


def test_surface_orbit_members_preserve_index_area_and_metric() -> None:
    """The current orbit builder preserves each enumerated sublattice exactly."""
    primitive = np.array([[1.2, 0.3], [0.1, 0.9]], dtype=float)
    primitive_area = abs(float(np.linalg.det(primitive)))
    index = 3

    orbits = enumerate_surface_cell_orbits_for_index(
        prim_basis=primitive,
        k=index,
        PG_ops=[np.eye(2, dtype=int)],
        cond_max=1.0e12,
    )

    members = [member for orbit in orbits for member in orbit.members]
    assert members
    for member in members:
        assert abs(round(np.linalg.det(member.oriented_N))) == index
        assert abs(np.linalg.det(member.shape_basis)) == pytest.approx(
            index * primitive_area
        )
        assert member.shape_gram == pytest.approx(
            member.shape_basis.T @ member.shape_basis
        )
        assert member.oriented_gram == pytest.approx(
            member.oriented_basis.T @ member.oriented_basis
        )


def test_zero_cell_distance_does_not_require_zero_composite_score() -> None:
    """The mathematical zero-strain invariant is d_cell, not match_score."""
    matches = enumerate_primitive_match_classes(
        _orthogonal_slab(1.0, 1.0),
        _orthogonal_slab(2.0, 1.0),
        PrototypeSearchConfig(
            k_max=2,
            eps_principal_max=1.0e-12,
            cond_max=1.0e9,
            w_match=1.0,
            N_at_max=100,
            surface_symmetry_mode="identity_only",
        ),
    )

    exact = [
        match_class
        for match_class in matches
        if (2, 1) in match_class.source_index_pairs
        and match_class.representative.ai_strain.d_cell < 1.0e-12
    ]

    assert exact
    representative = exact[0].representative
    assert representative.ai_strain.d_cell == pytest.approx(0.0, abs=1.0e-12)
    assert representative.match_score >= 0.0
