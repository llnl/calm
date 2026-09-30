from types import SimpleNamespace

import pytest

from calm.public.projections.buildability import (
    prototype_identifier_from_candidate_row,
)
from calm.public.collections.candidates import CandidateCollection


def test_candidate_collection_uses_batch_checker_once():
    rows = [
        {"candidate_id": "C1", "project_prototype_uid": "proto:a", "score": 0.1},
        {"candidate_id": "C2", "project_prototype_uid": "proto:b", "score": 0.2},
    ]
    calls = {"count": 0, "last_args": None}

    class FakeWorkspace:
        def check_prototypes_buildability(self, prototypes):
            calls["count"] += 1
            calls["last_args"] = list(prototypes)
            return {
                prototype: SimpleNamespace(buildable=True, reasons=["ok"])
                for prototype in prototypes
            }

    collection = CandidateCollection(workspace=FakeWorkspace(), items=rows)
    report = collection.validate_buildable()

    assert report.n_candidates == 2
    assert report.n_buildable == 2
    assert calls["count"] == 1
    expected = [prototype_identifier_from_candidate_row(row) for row in rows]
    assert set(calls["last_args"]) == set(expected)


def test_candidate_collection_requires_current_batch_checker():
    rows = [
        {"candidate_id": "C3", "project_prototype_uid": "proto:c", "score": 0.3}
    ]

    class LegacyWorkspace:
        def check_prototype_buildability(self, prototype):
            return SimpleNamespace(
                buildable=False,
                reasons=["prototype_not_found"],
            )

    collection = CandidateCollection(workspace=LegacyWorkspace(), items=rows)
    with pytest.raises(AttributeError, match="check_prototypes_buildability"):
        collection.validate_buildable()


def test_candidate_collection_propagates_batch_checker_failure():
    rows = [
        {"candidate_id": "C4", "project_prototype_uid": "proto:d", "score": 0.4}
    ]

    class BrokenWorkspace:
        def check_prototypes_buildability(self, prototypes):
            del prototypes
            raise RuntimeError("repository failure")

    collection = CandidateCollection(workspace=BrokenWorkspace(), items=rows)
    with pytest.raises(RuntimeError, match="repository failure"):
        collection.validate_buildable()
