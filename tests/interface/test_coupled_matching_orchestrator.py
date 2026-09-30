from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import numpy as np
import pytest

import calm.interface.matching._orchestrator as coupled
import calm.interface.matching._surface_symmetry as surface_symmetry
import calm.interface.matching.search as matching
from calm.interface.matching._correspondence import (
    CorrespondenceEnumerationLimitError,
    enumerate_basis_correspondences_2d,
)
from calm.interface.matching._pair_identity import (
    canonicalize_primitive_pair_2d,
)
from calm.interface.matching._types import (
    PairIdentityPolicy2D,
    PrimitiveMatchClass2D,
)
from calm.interface.config import PrototypeSearchConfig
from calm.interface.matching.search import enumerate_primitive_match_classes
from calm.math2d.normal_forms import enumerate_hnf_2d_by_index
from calm.math2d.paired_lattice import (
    determinantal_divisor_rank2,
    primitiveize_pair_matrix_2d,
)
from reference.coupled_match_reference import (
    FULL_D4_DISCOVERY_BY_INDEX,
    FULL_SQUARE_GROUP,
    IDENTITY_PAIR_KEY_FULL,
    SIGMA5_PAIR_KEY_FULL,
    SIGMA5_PAIR_KEYS_PROPER,
)


@dataclass(frozen=True)
class _Cell:
    array: np.ndarray


@dataclass(frozen=True)
class _AtomsLike:
    cell: _Cell


@dataclass(frozen=True)
class _Slab:
    atoms: _AtomsLike
    n_atoms: int = 1


def _square_slab(*, n_atoms: int = 1) -> _Slab:
    return _Slab(
        atoms=_AtomsLike(cell=_Cell(np.diag([1.0, 1.0, 10.0]))),
        n_atoms=n_atoms,
    )


def _slab_from_basis(basis: np.ndarray, *, n_atoms: int = 1) -> _Slab:
    cell = np.eye(3, dtype=float)
    cell[:2, :2] = np.asarray(basis, dtype=float).T
    cell[2, 2] = 10.0
    return _Slab(atoms=_AtomsLike(cell=_Cell(cell)), n_atoms=n_atoms)


def _install_group(
    monkeypatch: pytest.MonkeyPatch,
    operations: tuple[np.ndarray, ...],
) -> None:
    monkeypatch.setattr(
        surface_symmetry,
        "resolve_surface_pointgroup_2d",
        lambda *_args, **_kwargs: SimpleNamespace(operations=operations),
    )


def _slow_full_member_keys(
    basis_a: np.ndarray,
    basis_b: np.ndarray,
    *,
    k_max: int,
    strain_limit: float,
) -> set[tuple[int, ...]]:
    identity_group = (np.eye(2, dtype=int),)
    policy = PairIdentityPolicy2D(
        pair_symmetry="full",
        correspondence_orientation="proper",
        identify_material_exchange=False,
    )
    keys: set[tuple[int, ...]] = set()
    for k_a in range(1, k_max + 1):
        for k_b in range(1, k_max + 1):
            for h_a in enumerate_hnf_2d_by_index(k_a):
                n_a = np.asarray(h_a, dtype=int)
                physical_a = basis_a @ n_a
                gram_a = physical_a.T @ physical_a
                for h_b in enumerate_hnf_2d_by_index(k_b):
                    n_b = np.asarray(h_b, dtype=int)
                    physical_b = basis_b @ n_b
                    gram_b = physical_b.T @ physical_b
                    correspondences = enumerate_basis_correspondences_2d(
                        gram_a,
                        gram_b,
                        eps_principal_max=strain_limit,
                        orientation="proper",
                        metric_tolerance=1.0e-10,
                        entry_limit=100,
                    )
                    for correspondence in correspondences:
                        source = np.vstack([n_a, n_b @ correspondence.U_B])
                        primitive = primitiveize_pair_matrix_2d(
                            source
                        ).primitive_matrix
                        canonical = canonicalize_primitive_pair_2d(
                            primitive,
                            point_group_A=identity_group,
                            point_group_B=identity_group,
                            policy=policy,
                        )
                        keys.add(canonical.key)
    return keys


def _square_group(*, reverse: bool = False) -> tuple[np.ndarray, ...]:
    operations = tuple(
        np.asarray(operation, dtype=int).reshape(2, 2)
        for operation in FULL_SQUARE_GROUP
    )
    return tuple(reversed(operations)) if reverse else operations


def _install_square_group(
    monkeypatch: pytest.MonkeyPatch,
    *,
    reverse: bool = False,
) -> None:
    operations = _square_group(reverse=reverse)
    _install_group(monkeypatch, operations)


def _run_square(
    *,
    k_max: int,
    atom_limit: int = 100_000,
    pair_symmetry: str = "full",
) -> list[PrimitiveMatchClass2D]:
    slab = _square_slab()
    return coupled.enumerate_coupled_match_classes_core(
        slab,
        slab,
        k_max=k_max,
        cond_max=1.0e9,
        w_match=1.0,
        eps_principal_max=1.0e-10,
        N_at_max=atom_limit,
        surface_metric_tolerance=1.0e-10,
        pair_symmetry_policy=pair_symmetry,
        correspondence_orientation="proper",
        correspondence_entry_limit=100,
    )


def _run_zero_tolerance_rectangular(
    *,
    scale: float,
    weight: float,
) -> list[PrimitiveMatchClass2D]:
    basis = scale * np.diag([1.0, 1.4])
    return coupled.enumerate_coupled_match_classes_core(
        _slab_from_basis(basis),
        _slab_from_basis(basis),
        k_max=2,
        cond_max=1.0e9,
        w_match=weight,
        eps_principal_max=0.0,
        N_at_max=4,
        surface_symmetry_mode="identity_only",
        surface_metric_tolerance=1.0e-10,
        pair_symmetry_policy="full",
        correspondence_orientation="proper",
        correspondence_entry_limit=None,
    )


def _representative_signature(
    match_class: PrimitiveMatchClass2D,
) -> tuple[object, ...]:
    representative = match_class.representative
    provenance = representative.source_provenance
    return (
        match_class.pair_key,
        representative.atom_count,
        provenance.repeat_index,
        tuple(int(value) for value in provenance.source_H_A.ravel()),
        tuple(int(value) for value in provenance.source_H_B.ravel()),
        tuple(int(value) for value in provenance.correspondence_U_B.ravel()),
    )


@pytest.mark.parametrize("weight", [0.0, 0.5, 1.0])
def test_zero_tolerance_exact_matches_have_finite_scale_invariant_scores(
    weight: float,
) -> None:
    reference = _run_zero_tolerance_rectangular(scale=1.0, weight=weight)

    assert reference
    assert all(
        np.isfinite(match_class.representative.match_score)
        for match_class in reference
    )
    if weight == 1.0:
        assert all(
            match_class.representative.match_score == pytest.approx(0.0)
            for match_class in reference
        )

    reference_keys = [match_class.pair_key for match_class in reference]
    reference_scores = [
        match_class.representative.match_score for match_class in reference
    ]
    for scale in (1.0e-75, 1.0e75):
        scaled = _run_zero_tolerance_rectangular(
            scale=scale,
            weight=weight,
        )
        assert [match_class.pair_key for match_class in scaled] == reference_keys
        assert [
            match_class.representative.match_score for match_class in scaled
        ] == pytest.approx(reference_scores)


def test_zero_tolerance_rejects_tolerance_only_shape_mismatch() -> None:
    sheared = np.array([[1.0, 1.0e-9], [0.0, 1.0]])

    classes = coupled.enumerate_coupled_match_classes_core(
        _slab_from_basis(np.eye(2)),
        _slab_from_basis(sheared),
        k_max=1,
        cond_max=1.0e9,
        w_match=0.5,
        eps_principal_max=0.0,
        N_at_max=2,
        surface_symmetry_mode="identity_only",
        surface_metric_tolerance=1.0e-8,
        pair_symmetry_policy="full",
        correspondence_orientation="proper",
        correspondence_entry_limit=None,
    )

    assert classes == []


def test_orbit_prefilter_limit_is_inconclusive_not_fatal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    orbit = SimpleNamespace(
        representative=SimpleNamespace(shape_gram=np.eye(2, dtype=float))
    )

    def over_limit(*_args, **_kwargs):
        raise CorrespondenceEnumerationLimitError(
            required_entry_bound=129,
            entry_limit=128,
        )

    monkeypatch.setattr(
        coupled,
        "_enumerate_basis_correspondence_records_prepared_2d",
        over_limit,
    )

    assert coupled._orbit_pair_prefilter_status(
        orbit,
        orbit,
        strain_limit=0.15,
        metric_tolerance=1.0e-8,
        entry_limit=128,
    ) == "inconclusive"


def test_orbit_prefilter_still_rejects_completed_empty_search(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    orbit = SimpleNamespace(
        representative=SimpleNamespace(shape_gram=np.eye(2, dtype=float))
    )
    monkeypatch.setattr(
        coupled,
        "_enumerate_basis_correspondence_records_prepared_2d",
        lambda *_args, **_kwargs: SimpleNamespace(records=()),
    )

    assert coupled._orbit_pair_prefilter_status(
        orbit,
        orbit,
        strain_limit=0.15,
        metric_tolerance=1.0e-8,
        entry_limit=128,
    ) == "rejected"


def test_exact_index5_stage_counts_match_frozen_oracle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_square_group(monkeypatch)
    monkeypatch.setattr(
        coupled,
        "compute_valid_hnf_index_pairs",
        lambda *_args, **_kwargs: np.array([[5, 5]], dtype=int),
    )
    original_enumerator = (
        coupled._enumerate_basis_correspondence_records_prepared_2d
    )
    counts = {
        "orbit_pair_schedules": 0,
        "shape_compatible_orbit_pairs": 0,
        "member_pairs_expanded": 0,
        "correspondence_states": 0,
    }

    def counting_enumerator(*args, **kwargs):
        result = original_enumerator(*args, **kwargs)
        if kwargs["orientation"] == "all":
            counts["orbit_pair_schedules"] += 1
            if result.records:
                counts["shape_compatible_orbit_pairs"] += 1
        else:
            counts["member_pairs_expanded"] += 1
            counts["correspondence_states"] += len(result.records)
        return result

    monkeypatch.setattr(
        coupled,
        "_enumerate_basis_correspondence_records_prepared_2d",
        counting_enumerator,
    )
    classes = _run_square(k_max=5)

    assert counts == {
        "orbit_pair_schedules": 9,
        "shape_compatible_orbit_pairs": 3,
        "member_pairs_expanded": 12,
        "correspondence_states": 32,
    }
    assert len(classes) == 2
    assert sum(match_class.source_count for match_class in classes) == 32


def test_equal_square_k5_recovers_full_d4_identity_and_sigma5(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_square_group(monkeypatch)

    classes = _run_square(k_max=5)
    by_key = {match_class.pair_key: match_class for match_class in classes}

    assert set(by_key) == {IDENTITY_PAIR_KEY_FULL, SIGMA5_PAIR_KEY_FULL}
    sigma5 = by_key[SIGMA5_PAIR_KEY_FULL]
    assert (5, 5) in sigma5.source_index_pairs
    assert 1 in sigma5.repeat_indices
    assert sigma5.representative.atom_count == 10

    identity = by_key[IDENTITY_PAIR_KEY_FULL]
    assert (5, 5) in identity.source_index_pairs
    assert 5 in identity.repeat_indices
    assert identity.representative.atom_count == 2


def test_equal_square_k5_proper_symmetry_retains_three_ordered_classes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_square_group(monkeypatch)

    classes = _run_square(k_max=5, pair_symmetry="proper")

    assert {match_class.pair_key for match_class in classes} == {
        IDENTITY_PAIR_KEY_FULL,
        *SIGMA5_PAIR_KEYS_PROPER,
    }


def test_every_representative_is_primitive_and_reconstructs_its_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_square_group(monkeypatch)

    for match_class in _run_square(k_max=5):
        candidate = match_class.representative
        primitive = np.vstack(
            [candidate.primitive_N_A, candidate.primitive_N_B]
        )
        provenance = candidate.source_provenance

        assert determinantal_divisor_rank2(primitive) == 1
        assert np.array_equal(
            primitive @ provenance.source_right_factor,
            provenance.source_pair_matrix,
        )
        assert np.array_equal(
            primitive @ candidate.build_common_right_transform,
            np.vstack([candidate.build_N_A, candidate.build_N_B]),
        )
        assert round(np.linalg.det(candidate.build_common_right_transform)) == 1
        assert round(np.linalg.det(candidate.build_R_A)) == 1
        assert round(np.linalg.det(candidate.build_R_B)) == 1


def test_safe_atom_lower_bound_allows_repeated_sources_to_primitiveize(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_square_group(monkeypatch)

    classes = _run_square(k_max=5, atom_limit=2)

    assert [match_class.pair_key for match_class in classes] == [
        IDENTITY_PAIR_KEY_FULL
    ]
    identity = classes[0]
    assert identity.representative.atom_count == 2
    assert (5, 5) in identity.source_index_pairs
    assert 5 in identity.repeat_indices


def test_full_d4_inventory_through_k30_matches_exact_reference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_square_group(monkeypatch)

    classes = _run_square(k_max=30)
    by_key = {match_class.pair_key: match_class for match_class in classes}

    assert set(by_key) == {
        key for _first_index, key in FULL_D4_DISCOVERY_BY_INDEX
    }
    for first_index, key in FULL_D4_DISCOVERY_BY_INDEX:
        assert min(
            max(index_pair) for index_pair in by_key[key].source_index_pairs
        ) == first_index
    sigma5 = by_key[SIGMA5_PAIR_KEY_FULL]
    assert {(5, 5), (25, 25), (30, 30)} <= sigma5.source_index_pairs
    assert {1, 5, 6} <= sigma5.repeat_indices


def test_enumeration_and_group_order_do_not_change_classes_or_representatives(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_square_group(monkeypatch)
    forward = _run_square(k_max=5)

    original_index_pairs = coupled.compute_valid_hnf_index_pairs
    monkeypatch.setattr(
        coupled,
        "compute_valid_hnf_index_pairs",
        lambda *args, **kwargs: original_index_pairs(*args, **kwargs)[::-1],
    )
    _install_square_group(monkeypatch, reverse=True)
    reversed_order = _run_square(k_max=5)

    assert [match_class.pair_key for match_class in reversed_order] == [
        match_class.pair_key for match_class in forward
    ]
    assert [
        _representative_signature(match_class) for match_class in reversed_order
    ] == [_representative_signature(match_class) for match_class in forward]


@pytest.mark.parametrize(
    "basis",
    [
        np.array([[1.0, 0.0], [0.0, 1.7]]),
        np.array([[1.0, 0.35], [0.0, 1.2]]),
    ],
)
def test_orbit_bundle_path_matches_slow_full_member_reference(
    monkeypatch: pytest.MonkeyPatch,
    basis: np.ndarray,
) -> None:
    identity_group = (np.eye(2, dtype=int),)
    _install_group(monkeypatch, identity_group)
    slab = _slab_from_basis(basis)

    classes = coupled.enumerate_coupled_match_classes_core(
        slab,
        slab,
        k_max=3,
        cond_max=1.0e9,
        w_match=1.0,
        eps_principal_max=1.0e-10,
        N_at_max=100_000,
        surface_metric_tolerance=1.0e-10,
        pair_symmetry_policy="full",
        correspondence_orientation="proper",
        correspondence_entry_limit=100,
    )
    reference_keys = _slow_full_member_keys(
        basis,
        basis,
        k_max=3,
        strain_limit=1.0e-10,
    )

    assert {match_class.pair_key for match_class in classes} == reference_keys


def test_explicit_coupled_api_projects_authoritative_search_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    coupled_result = [object()]
    monkeypatch.setattr(
        matching,
        "search_primitive_match_classes",
        lambda *_a, **_k: SimpleNamespace(match_classes=tuple(coupled_result)),
    )
    slab = _square_slab()
    config = PrototypeSearchConfig(surface_symmetry_mode="identity_only")

    assert enumerate_primitive_match_classes(slab, slab, config) == coupled_result


def test_search_scoped_context_reuses_identical_surface_catalog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_square_group(monkeypatch)
    original_surface_builder = coupled._build_surface_cell_orbit_index_prepared
    original_pair_context = coupled._prepare_pair_identity_context_2d
    counts = {"surface_catalogs": 0, "pair_contexts": 0}

    def counting_surface_builder(*args, **kwargs):
        counts["surface_catalogs"] += 1
        return original_surface_builder(*args, **kwargs)

    def counting_pair_context(*args, **kwargs):
        counts["pair_contexts"] += 1
        return original_pair_context(*args, **kwargs)

    monkeypatch.setattr(
        coupled,
        "_build_surface_cell_orbit_index_prepared",
        counting_surface_builder,
    )
    monkeypatch.setattr(
        coupled,
        "_prepare_pair_identity_context_2d",
        counting_pair_context,
    )

    classes = _run_square(k_max=5)

    assert classes
    assert counts == {"surface_catalogs": 1, "pair_contexts": 1}


def test_primitive_geometry_is_reused_and_candidates_are_materialized_lazily(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_square_group(monkeypatch)
    original_geometry_builder = coupled._build_candidate_geometry
    original_candidate_builder = coupled._build_candidate
    counts = {"geometries": 0, "candidates": 0}

    def counting_geometry_builder(*args, **kwargs):
        counts["geometries"] += 1
        return original_geometry_builder(*args, **kwargs)

    def counting_candidate_builder(*args, **kwargs):
        counts["candidates"] += 1
        return original_candidate_builder(*args, **kwargs)

    monkeypatch.setattr(
        coupled,
        "_build_candidate_geometry",
        counting_geometry_builder,
    )
    monkeypatch.setattr(
        coupled,
        "_build_candidate",
        counting_candidate_builder,
    )

    classes = _run_square(k_max=5)
    source_count = sum(match_class.source_count for match_class in classes)

    assert source_count == 92
    assert counts["geometries"] == 52
    assert counts["geometries"] < source_count
    assert counts["candidates"] == len(classes) == 2


def test_core_entrypoint_composes_preparation_traversal_and_finalization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = SimpleNamespace(index_pairs=((1, 2), (3, 4)))
    state = object()
    expected = [object()]
    traversed: list[tuple[int, int]] = []

    monkeypatch.setattr(
        coupled,
        "_prepare_coupled_match_search",
        lambda *_args, **_kwargs: (plan, state),
    )

    def traverse(_plan, _state, *, k_a, k_b):
        assert _plan is plan
        assert _state is state
        traversed.append((k_a, k_b))

    monkeypatch.setattr(coupled, "_traverse_scheduled_index_pair", traverse)

    def finalize(_state):
        assert _state is state
        return expected

    monkeypatch.setattr(coupled, "_finalize_coupled_match_search", finalize)

    result = coupled.enumerate_coupled_match_classes_core(
        _square_slab(),
        _square_slab(),
    )

    assert traversed == [(1, 2), (3, 4)]
    assert result is expected


def test_coupled_search_state_owns_fresh_search_scoped_caches() -> None:
    first = coupled._CoupledMatchSearchState(audit=None)
    second = coupled._CoupledMatchSearchState(audit=None)

    cache_names = (
        "primitive_cache",
        "identity_cache",
        "geometry_cache",
        "correspondence_metric_cache",
        "classes_by_key",
        "representative_ranks",
    )
    for name in cache_names:
        first_cache = getattr(first, name)
        second_cache = getattr(second, name)
        assert first_cache == second_cache == {}
        assert first_cache is not second_cache
