from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import numpy as np
import pytest

import calm.interface.pipeline as pipeline
from calm.interface.config import PrototypeSearchConfig
from calm.interface.matching.search import search_primitive_match_classes


@dataclass(frozen=True)
class _Cell:
    array: np.ndarray


@dataclass(frozen=True)
class _AtomsLike:
    cell: _Cell


@dataclass(frozen=True)
class _Slab:
    atoms: _AtomsLike
    hkl: tuple[int, int, int] = (0, 0, 1)
    n_atoms: int = 1


def _square_slab() -> _Slab:
    return _Slab(
        atoms=_AtomsLike(cell=_Cell(np.diag([1.0, 1.0, 10.0])))
    )


def _pair_keys(prototypes) -> list[tuple[int, ...]]:
    return [
        tuple(prototype.pair_identity.primitive_pair_key)
        for prototype in prototypes
    ]


def test_find_prototypes_projects_one_complete_authoritative_population(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    slab = _square_slab()
    config = PrototypeSearchConfig(
        k_max=5,
        cond_max=1.0e9,
        eps_principal_max=1.0e-10,
        N_at_max=100_000,
        max_results=100,
        surface_symmetry_mode="identity_only",
        surface_metric_tolerance=1.0e-10,
    )
    monkeypatch.setattr(
        pipeline,
        "_slab_uid",
        lambda subject: "slab:a" if subject is slab else "slab:b",
    )

    primitive = search_primitive_match_classes(slab, slab, config)
    result = pipeline.find_prototypes(slab, slab, config)

    assert result.enumeration_audit is not None
    assert primitive.enumeration_audit is not None
    assert result.enumeration_audit.to_dict() == (
        primitive.enumeration_audit.to_dict()
    )
    assert result.pareto_population_size == len(primitive.match_classes)
    assert _pair_keys(result.prototypes) == [
        match_class.pair_key for match_class in primitive.match_classes
    ]
    assert all(
        prototype.pair_identity is not None for prototype in result.prototypes
    )


def test_find_prototypes_classifies_full_population_before_truncation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    slab = _square_slab()
    complete_config = PrototypeSearchConfig(
        k_max=3,
        cond_max=1.0e9,
        eps_principal_max=1.0e-10,
        N_at_max=100_000,
        max_results=100,
        surface_symmetry_mode="identity_only",
        surface_metric_tolerance=1.0e-10,
    )
    limited_config = PrototypeSearchConfig(
        **{**complete_config.to_dict(), "max_results": 1}
    )
    monkeypatch.setattr(pipeline, "_slab_uid", lambda _slab: "slab:test")

    complete = pipeline.find_prototypes(slab, slab, complete_config)
    limited = pipeline.find_prototypes(slab, slab, limited_config)

    assert complete.pareto_population_size > 1
    assert limited.pareto_population_size == complete.pareto_population_size
    assert limited.pareto_front_uids == complete.pareto_front_uids
    assert len(limited.prototypes) == 1



def test_slab_identity_helpers_accept_persisted_records_without_bulk() -> None:
    persisted = SimpleNamespace(
        uid_full="slab:persisted",
        miller=(1, 1, 1),
    )

    assert pipeline._slab_uid(persisted) == "slab:persisted"
    assert pipeline._slab_miller(persisted) == (1, 1, 1)


def test_slab_identity_helpers_accept_in_memory_uid_without_bulk() -> None:
    in_memory = SimpleNamespace(
        uid="slab:in-memory",
        hkl=(1, 0, 0),
    )

    assert pipeline._slab_uid(in_memory) == "slab:in-memory"
    assert pipeline._slab_miller(in_memory) == (1, 0, 0)
