from __future__ import annotations

import pytest

from calm.project.application.buildability import (
    check_prototype_buildability,
    check_prototypes_buildability,
)
from calm.project.domain.models import Prototype, Slab
from slab_record_fixtures import current_atoms, current_slab_payload


_SUPERCELL = {
    "k": 1,
    "N_tot": [[1, 0], [0, 1]],
    "R_sup": [[1.0, 0.0], [0.0, 1.0]],
    "hnf_key_pg": [1, 0, 1],
    "cond": 1.0,
}


def _prototype(*, uid: str = "proto:1", payload=None) -> Prototype:
    return Prototype(
        uid_full=uid,
        id_short="p_1",
        run_uid_full="run:1",
        run_id_short="r_1",
        slab_a_uid_full="slab:a",
        slab_b_uid_full="slab:b",
        match_score=0.1,
        hencky_norm=0.0,
        interface_area=9.0,
        natoms=2,
        is_pareto=True,
        pareto_rank=0,
        payload=payload
        if payload is not None
        else {"supercell_a": dict(_SUPERCELL), "supercell_b": dict(_SUPERCELL)},
    )


def _slab(uid: str, id_short: str, *, atoms=True) -> Slab:
    return Slab(
        uid_full=uid,
        id_short=id_short,
        bulk_uid_full="bulk:1",
        bulk_id_short="b_1",
        miller=(1, 0, 0),
        payload=current_slab_payload(
            bulk_uid_full="bulk:1",
            atoms=current_atoms() if atoms else None,
        ),
    )


class _Ids:
    def __init__(self, mapping=None, *, error=None):
        self.mapping = mapping or {}
        self.error = error

    def resolve_prototype(self, identifier):
        if self.error is not None:
            raise self.error
        if identifier not in self.mapping:
            raise KeyError(identifier)
        return self.mapping[identifier]


class _Repository:
    def __init__(self, rows, *, error=None):
        self.rows = {row.uid_full: row for row in rows}
        self.error = error
        self.calls = []

    def get_many_by_uid_full(self, identifiers):
        self.calls.append(list(identifiers))
        if self.error is not None:
            raise self.error
        return [self.rows[value] for value in identifiers if value in self.rows]


class _Uow:
    def __init__(self, *, ids, prototypes, slabs):
        self.ids = ids
        self.prototypes = prototypes
        self.slabs = slabs


def _uow(*, prototype=None, slabs=None, ids=None):
    proto_rows = [] if prototype is None else [prototype]
    slab_rows = slabs or []
    return _Uow(
        ids=ids or _Ids({"p_short": "proto:1", "proto:1": "proto:1"}),
        prototypes=_Repository(proto_rows),
        slabs=_Repository(slab_rows),
    )


def test_batch_buildability_preserves_requested_keys_and_typed_ids() -> None:
    prototype = _prototype()
    uow = _uow(
        prototype=prototype,
        slabs=[_slab("slab:a", "s_a"), _slab("slab:b", "s_b")],
    )

    results = check_prototypes_buildability(uow, ["p_short"])

    assert set(results) == {"p_short"}
    result = results["p_short"]
    assert result.prototype_uid_full == "proto:1"
    assert result.prototype_id_short == "p_1"
    assert result.slab_a_id_short == "s_a"
    assert result.slab_b_id_short == "s_b"
    assert result.reconstructable is True
    assert result.buildable is True
    assert result.reasons == ["ok"]
    assert uow.prototypes.calls == [["proto:1"]]
    assert uow.slabs.calls == [["slab:a", "slab:b"]]


def test_missing_prototype_is_a_buildability_result() -> None:
    uow = _uow()

    result = check_prototype_buildability(uow, "proto:missing")

    assert result.prototype_uid_full == "proto:missing"
    assert result.buildable is False
    assert result.reasons == ["prototype_not_found"]


def test_missing_atoms_and_recipe_are_reported_without_shape_fallbacks() -> None:
    prototype = _prototype(payload={"supercell_a": dict(_SUPERCELL)})
    uow = _uow(
        prototype=prototype,
        slabs=[_slab("slab:a", "s_a", atoms=False), _slab("slab:b", "s_b")],
    )

    result = check_prototype_buildability(uow, "proto:1")

    assert result.reconstructable is True
    assert result.buildable is False
    assert result.reasons == ["slab_a_missing_atoms", "missing_supercell"]


def test_wrong_kind_or_ambiguous_identifier_errors_propagate() -> None:
    error = ValueError("wrong identifier kind")
    uow = _uow(ids=_Ids(error=error))

    with pytest.raises(ValueError, match="wrong identifier kind"):
        check_prototype_buildability(uow, "b_wrong")


def test_repository_failures_propagate() -> None:
    uow = _Uow(
        ids=_Ids({"proto:1": "proto:1"}),
        prototypes=_Repository([], error=RuntimeError("database failure")),
        slabs=_Repository([]),
    )

    with pytest.raises(RuntimeError, match="database failure"):
        check_prototype_buildability(uow, "proto:1")
