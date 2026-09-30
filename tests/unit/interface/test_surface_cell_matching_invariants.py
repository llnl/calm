"""Dependency-light invariants for bounded surface-cell matching."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pytest

from calm.interface.matching._utils import compute_valid_hnf_index_pairs
from calm.interface.config import PrototypeSearchConfig
from calm.interface.matching.search import enumerate_primitive_match_classes


@dataclass(frozen=True)
class _Cell:
    array: np.ndarray


@dataclass(frozen=True)
class _Atoms:
    cell: _Cell


@dataclass(frozen=True)
class _Slab:
    atoms: _Atoms
    n_atoms: int = 1


def _orthogonal_slab(
    a: float,
    b: float,
    *,
    n_atoms: int = 1,
    scale: float = 1.0,
) -> _Slab:
    cell = scale * np.array(
        [[a, 0.0, 0.0], [0.0, b, 0.0], [0.0, 0.0, 10.0]],
        dtype=float,
    )
    return _Slab(atoms=_Atoms(cell=_Cell(array=cell)), n_atoms=n_atoms)


def _enumerate_primitive(
    slab_a: _Slab,
    slab_b: _Slab,
    **overrides: object,
):
    return enumerate_primitive_match_classes(
        slab_a,
        slab_b,
        PrototypeSearchConfig(**overrides),
    )


def test_exact_zero_tolerance_match_has_finite_zero_score() -> None:
    matches = _enumerate_primitive(
        _orthogonal_slab(1.0, 1.0),
        _orthogonal_slab(1.0, 1.0),
        k_max=1,
        eps_principal_max=0.0,
        N_at_max=2,
        w_match=1.0,
        surface_symmetry_mode="identity_only",
    )

    assert matches
    representatives = [match_class.representative for match_class in matches]
    assert all(rep.ai_strain.d_cell == pytest.approx(0.0) for rep in representatives)
    assert all(rep.match_score == pytest.approx(0.0) for rep in representatives)
    assert all(np.isfinite(rep.match_score) for rep in representatives)


def test_atom_limit_is_a_hard_admissibility_gate() -> None:
    slab_a = _orthogonal_slab(1.0, 1.0, n_atoms=2)
    slab_b = _orthogonal_slab(1.0, 1.0, n_atoms=2)

    assert _enumerate_primitive(
        slab_a,
        slab_b,
        k_max=2,
        eps_principal_max=0.1,
        N_at_max=3,
        w_match=0.5,
        surface_symmetry_mode="identity_only",
    ) == []

    matches = _enumerate_primitive(
        slab_a,
        slab_b,
        k_max=2,
        eps_principal_max=0.1,
        N_at_max=4,
        w_match=0.5,
        surface_symmetry_mode="identity_only",
    )
    assert matches
    assert all(
        match_class.representative.atom_count <= 4
        for match_class in matches
    )


def test_matching_is_equivariant_under_common_positive_length_scaling() -> None:
    reference = _enumerate_primitive(
        _orthogonal_slab(1.0, 1.4),
        _orthogonal_slab(1.0, 1.4),
        k_max=2,
        eps_principal_max=0.0,
        N_at_max=4,
        w_match=0.5,
        surface_symmetry_mode="identity_only",
    )
    reference_keys = [match_class.pair_key for match_class in reference]
    reference_scores = [
        match_class.representative.match_score for match_class in reference
    ]

    for scale in (1.0e-150, 1.0e150):
        scaled = _enumerate_primitive(
            _orthogonal_slab(1.0, 1.4, scale=scale),
            _orthogonal_slab(1.0, 1.4, scale=scale),
            k_max=2,
            eps_principal_max=0.0,
            N_at_max=4,
            w_match=0.5,
            surface_symmetry_mode="identity_only",
        )
        scaled_keys = [match_class.pair_key for match_class in scaled]
        assert scaled_keys == reference_keys
        assert [
            match_class.representative.match_score for match_class in scaled
        ] == pytest.approx(reference_scores)


def test_matching_rejects_a_tilted_unoriented_surface_cell() -> None:
    tilted = _Slab(
        atoms=_Atoms(
            cell=_Cell(
                array=np.array(
                    [[1.0, 0.0, 0.2], [0.0, 1.0, 0.0], [0.0, 0.0, 10.0]]
                )
            )
        )
    )
    with pytest.raises(ValueError, match="global Cartesian xy plane"):
        _enumerate_primitive(
            tilted,
            _orthogonal_slab(1.0, 1.0),
            k_max=1,
            eps_principal_max=0.1,
            N_at_max=2,
            surface_symmetry_mode="identity_only",
        )


def test_log_area_prefilter_handles_boundaries_and_extreme_finite_bounds() -> None:
    eps = 0.2
    boundary_area = float(np.exp(2.0 * eps))
    pairs = compute_valid_hnf_index_pairs(
        boundary_area,
        1.0,
        1,
        1,
        eps,
    )
    assert pairs.tolist() == [[1, 1]]

    outside = compute_valid_hnf_index_pairs(
        boundary_area * (1.0 + 1.0e-10),
        1.0,
        1,
        1,
        eps,
        rtol=0.0,
    )
    assert outside.size == 0

    all_pairs = compute_valid_hnf_index_pairs(
        1.0e-300,
        1.0e300,
        3,
        3,
        1.0e308,
    )
    assert all_pairs.shape == (9, 2)


def test_search_settings_reject_nonfinite_and_fractional_controls() -> None:
    from calm.public.inputs.settings import SearchSettings

    with pytest.raises(ValueError, match="finite and positive"):
        SearchSettings(max_principal_strain=float("nan")).validate()
    with pytest.raises(TypeError, match="max_supercell_index must be an integer"):
        SearchSettings(max_supercell_index=2.5).validate()
    with pytest.raises(TypeError, match="max_atoms must be an integer"):
        SearchSettings(max_atoms=4.5).validate()
    with pytest.raises(ValueError, match="finite and between 0 and 1"):
        SearchSettings(mismatch_weight=float("inf")).validate()
