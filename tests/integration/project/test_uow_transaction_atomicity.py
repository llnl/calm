"""Integration contracts for the re-entrant SQLite unit of work."""

from __future__ import annotations

import pytest

from calm.project.domain.identity_v2 import (
    bulk_metadata_identity_payload,
    persisted_entity_uid_v2,
)
from calm.project.domain.models import Bulk


def _bulk(short_id: str, label: str) -> Bulk:
    payload = {"label": label}
    return Bulk(
        uid_full=persisted_entity_uid_v2(
            "bulk",
            bulk_metadata_identity_payload(payload=payload),
        ),
        id_short=short_id,
        label=label,
        payload=payload,
    )


def _assert_bulk_matches(stored: Bulk | None, expected: Bulk) -> None:
    assert stored is not None
    assert stored.uid_full == expected.uid_full
    assert stored.id_short == expected.id_short
    assert stored.label == expected.label
    assert stored.payload == expected.payload


def test_exception_rolls_back_all_repository_mutations(sqlite_uow_factory):
    uow = sqlite_uow_factory()
    bulk = _bulk("b_rollback", "rollback")

    with pytest.raises(RuntimeError, match="abort transaction"):
        with uow as entered:
            entered.bulks.upsert(bulk)
            _assert_bulk_matches(
                entered.bulks.get_by_uid_full(bulk.uid_full),
                bulk,
            )
            raise RuntimeError("abort transaction")

    with sqlite_uow_factory() as reopened:
        assert reopened.bulks.get_by_uid_full(bulk.uid_full) is None
        with pytest.raises(KeyError, match="No b entity with uid"):
            reopened.ids.resolve(bulk.uid_full, expected_tag="b")


def test_caught_nested_failure_marks_outer_transaction_rollback_only(
    sqlite_uow_factory,
):
    uow = sqlite_uow_factory()
    before = _bulk("b_before", "before")
    nested = _bulk("b_nested", "nested")
    after = _bulk("b_after", "after")

    with uow as outer:
        outer.bulks.upsert(before)
        with pytest.raises(RuntimeError, match="nested failure"):
            with uow as inner:
                inner.bulks.upsert(nested)
                raise RuntimeError("nested failure")
        outer.bulks.upsert(after)

    with sqlite_uow_factory() as reopened:
        assert reopened.bulks.get_by_uid_full(before.uid_full) is None
        assert reopened.bulks.get_by_uid_full(nested.uid_full) is None
        assert reopened.bulks.get_by_uid_full(after.uid_full) is None


def test_successful_nested_uow_commits_at_outermost_exit(sqlite_uow_factory):
    uow = sqlite_uow_factory()
    first = _bulk("b_first", "first")
    second = _bulk("b_second", "second")

    with uow as outer:
        outer.bulks.upsert(first)
        with uow as inner:
            assert inner is outer
            inner.bulks.upsert(second)

    with sqlite_uow_factory() as reopened:
        _assert_bulk_matches(reopened.bulks.get_by_uid_full(first.uid_full), first)
        _assert_bulk_matches(reopened.bulks.get_by_uid_full(second.uid_full), second)


def test_uow_is_reusable_after_rollback(sqlite_uow_factory):
    uow = sqlite_uow_factory()
    rolled_back = _bulk("b_rolledback", "rolled back")
    committed = _bulk("b_committed", "committed")

    with pytest.raises(ValueError, match="reject first transaction"):
        with uow as entered:
            entered.bulks.upsert(rolled_back)
            raise ValueError("reject first transaction")

    with uow as entered:
        entered.bulks.upsert(committed)

    with sqlite_uow_factory() as reopened:
        assert reopened.bulks.get_by_uid_full(rolled_back.uid_full) is None
        _assert_bulk_matches(
            reopened.bulks.get_by_uid_full(committed.uid_full),
            committed,
        )
