from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pytest

import calm.interface.matching._orchestrator as coupled
from calm.interface.matching._orchestrator import (
    enumerate_coupled_match_classes_core,
)
from calm.interface.matching._correspondence import (
    CorrespondenceEnumerationLimitError,
)
from calm.interface.matching.audit import (
    COUPLED_MATCH_AUDIT_SCHEMA,
    CoupledMatchEnumerationAudit,
)
from calm.interface.config import PrototypeSearchConfig
from calm.interface.matching.search import search_primitive_match_classes
from reference.coupled_match_reference import FULL_SQUARE_GROUP


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


def _square_slab() -> _Slab:
    return _Slab(
        atoms=_AtomsLike(cell=_Cell(np.diag([1.0, 1.0, 10.0])))
    )


def _square_group() -> tuple[np.ndarray, ...]:
    return tuple(
        np.asarray(operation, dtype=int).reshape(2, 2)
        for operation in FULL_SQUARE_GROUP
    )


def test_coupled_audit_reproduces_the_index5_square_oracle() -> None:
    slab = _square_slab()
    audit = CoupledMatchEnumerationAudit.empty(k_max=5)

    classes = enumerate_coupled_match_classes_core(
        slab,
        slab,
        k_max=5,
        cond_max=1.0e9,
        w_match=1.0,
        eps_principal_max=1.0e-10,
        N_at_max=100_000,
        surface_metric_tolerance=1.0e-10,
        pair_symmetry_policy="full",
        correspondence_orientation="proper",
        correspondence_entry_limit=100,
        point_group_A=_square_group(),
        point_group_B=_square_group(),
        audit=audit,
    )

    assert len(classes) == 2
    surface = audit.surface_A.rows(cumulative=False)[4]
    assert surface == {
        "k": 5,
        "hnf_generated": 6,
        "reduction_failed": 0,
        "condition_rejected": 0,
        "admitted_members": 6,
        "comparison_orbits": 3,
        "comparison_symmetry_reduction": 3,
    }

    pairs = audit.pairs.rows(cumulative=False)[4]
    assert pairs["orbit_pairs_considered"] == 9
    assert pairs["orbit_prefilter_rejected"] == 6
    assert pairs["orbit_prefilter_admitted"] == 3
    assert pairs["orbit_prefilter_inconclusive"] == 0
    assert pairs["member_pairs_expanded"] == 12
    assert pairs["correspondence_domains"] == 12
    assert pairs["strain_admissible_correspondences"] == 32
    assert pairs["nonprimitive_repetitions"] > 0
    assert pairs["candidates_admitted"] == 32
    assert pairs["primitive_classes_created"] == 1
    assert pairs["sources_aggregated_by_pair_key"] == 31

    assert audit.search_space is not None
    assert audit.search_space.to_dict() == {
        "raw_hnf_pairs": 441,
        "searchable_hnf_pairs": 441,
        "area_admissible_hnf_pairs": 111,
        "atom_lower_bound_admissible_hnf_pairs": 111,
        "orbit_prefilter_surviving_hnf_pairs": 39,
    }
    assert audit.identity_reduction is not None
    assert audit.identity_reduction.to_dict() == {
        "admitted_descriptions": 92,
        "unique_admitted_source_pairs": 92,
        "unique_admitted_primitive_pairs": 52,
        "unique_admitted_common_right_classes": 12,
        "unique_final_pair_classes": 2,
    }


def test_authoritative_search_returns_versioned_production_audit() -> None:
    slab = _square_slab()
    config = PrototypeSearchConfig(
        k_max=2,
        cond_max=1.0e9,
        eps_principal_max=1.0e-10,
        N_at_max=100_000,
        surface_symmetry_mode="identity_only",
        surface_metric_tolerance=1.0e-10,
    )

    result = search_primitive_match_classes(slab, slab, config)
    audit = result.enumeration_audit

    assert audit is not None
    assert audit.schema == COUPLED_MATCH_AUDIT_SCHEMA
    assert audit.implementation == result.implementation
    assert audit.surface_symmetry_A == result.surface_symmetry_a
    assert audit.surface_symmetry_B == result.surface_symmetry_b
    assert audit.pairs.totals()["primitive_classes_created"] == len(
        result.match_classes
    )

    payload = audit.to_dict(cumulative=False)
    assert payload["schema"] == COUPLED_MATCH_AUDIT_SCHEMA
    assert payload["implementation"] == "primitive_coupled_pair_v2"
    assert len(payload["pairs"]) == config.k_max
    assert payload["totals"]["pairs"]["candidates_admitted"] >= len(
        result.match_classes
    )


def test_coupled_audit_rejects_inconsistent_stage_accounting() -> None:
    audit = CoupledMatchEnumerationAudit.empty(k_max=1)
    audit.pairs.orbit_pairs_considered[0] = 1

    with pytest.raises(
        ValueError,
        match="every orbit pair must have one prefilter disposition",
    ):
        audit.validate()


def test_authoritative_limit_failure_is_recorded_before_reraising(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    slab = _square_slab()
    audit = CoupledMatchEnumerationAudit.empty(k_max=1)

    monkeypatch.setattr(
        coupled,
        "_orbit_pair_prefilter_status",
        lambda *_args, **_kwargs: "admitted",
    )

    def _raise_limit(*_args, **_kwargs):
        raise CorrespondenceEnumerationLimitError(
            required_entry_bound=4,
            entry_limit=3,
        )

    monkeypatch.setattr(
        coupled,
        "_enumerate_basis_correspondence_records_prepared_2d",
        _raise_limit,
    )

    with pytest.raises(CorrespondenceEnumerationLimitError):
        enumerate_coupled_match_classes_core(
            slab,
            slab,
            k_max=1,
            cond_max=1.0e9,
            eps_principal_max=0.0,
            N_at_max=100,
            surface_metric_tolerance=0.0,
            point_group_A=(np.eye(2, dtype=int),),
            point_group_B=(np.eye(2, dtype=int),),
            audit=audit,
        )

    assert audit.pairs.correspondence_limit_failures == [1]
