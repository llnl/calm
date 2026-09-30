from __future__ import annotations

import pytest

from calm.interface.matching.audit import CoupledMatchEnumerationAudit
from calm.project.application.interface_searches import (
    InterfaceSearchConflictError,
    InterfaceSearchesService,
)


def _spec(identity: str) -> dict[str, object]:
    return {
        "schema_version": 2,
        "implementation": "primitive_coupled_pair_v2",
        "search_identity": identity,
        "surface_a": {"uid_full": "slab:a"},
        "surface_b": {"uid_full": "slab:b"},
        "settings": {"max_candidates": 10},
    }


def test_named_search_lifecycle_is_database_owned(sqlite_uow_factory) -> None:
    service = InterfaceSearchesService(uow_factory=sqlite_uow_factory)
    spec = _spec("interface_search:one")

    prepared = service.prepare(
        name="screen",
        search_identity="interface_search:one",
        run_spec=spec,
        resume=True,
    )
    assert prepared.action == "execute"
    assert prepared.search.name == "screen"
    assert prepared.search.status == "running"
    assert prepared.search.spec == spec

    audit = CoupledMatchEnumerationAudit.empty(2).to_dict(cumulative=False)
    completed = service.complete(
        prepared.search.run_uid_full,
        n_candidates=7,
        enumeration_audit=audit,
    )
    assert completed.status == "done"
    assert completed.progress == {
        "name": "screen",
        "phase": "complete",
        "n_candidates": 7,
        "enumeration_audit": audit,
    }

    reused = service.prepare(
        name="screen",
        search_identity="interface_search:one",
        run_spec=spec,
        resume=True,
    )
    assert reused.action == "reuse"
    assert reused.search.run_uid_full == prepared.search.run_uid_full

    assert service.get("screen") == reused.search
    assert service.get(reused.search.search_identity) == reused.search
    assert service.get(reused.search.run_uid_full) == reused.search
    assert service.get(reused.search.run_id_short) == reused.search
    assert service.list() == [reused.search]


def test_named_search_conflicts_are_authoritative(sqlite_uow_factory) -> None:
    service = InterfaceSearchesService(uow_factory=sqlite_uow_factory)
    service.prepare(
        name="screen",
        search_identity="interface_search:one",
        run_spec=_spec("interface_search:one"),
        resume=True,
    )

    with pytest.raises(InterfaceSearchConflictError, match="different"):
        service.prepare(
            name="screen",
            search_identity="interface_search:two",
            run_spec=_spec("interface_search:two"),
            resume=True,
        )

    with pytest.raises(InterfaceSearchConflictError, match="already persisted"):
        service.prepare(
            name="alias",
            search_identity="interface_search:one",
            run_spec=_spec("interface_search:one"),
            resume=True,
        )


def test_failed_search_restarts_same_authoritative_run(sqlite_uow_factory) -> None:
    service = InterfaceSearchesService(uow_factory=sqlite_uow_factory)
    spec = _spec("interface_search:retry")
    first = service.prepare(
        name="retry",
        search_identity="interface_search:retry",
        run_spec=spec,
        resume=True,
    )

    failed = service.fail(
        first.search.run_uid_full,
        error={"type": "RuntimeError", "message": "failed"},
    )
    assert failed.status == "failed"
    assert failed.error == {"type": "RuntimeError", "message": "failed"}

    restarted = service.prepare(
        name="retry",
        search_identity="interface_search:retry",
        run_spec=spec,
        resume=True,
    )
    assert restarted.action == "execute"
    assert restarted.search.status == "running"
    assert restarted.search.error is None
    assert restarted.search.run_uid_full == first.search.run_uid_full


def test_search_name_is_not_part_of_run_identity(sqlite_uow_factory) -> None:
    service = InterfaceSearchesService(uow_factory=sqlite_uow_factory)
    with pytest.raises(ValueError, match="must not participate"):
        service.prepare(
            name="screen",
            search_identity="interface_search:one",
            run_spec={**_spec("interface_search:one"), "name": "screen"},
            resume=True,
        )
