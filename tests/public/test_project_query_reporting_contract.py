"""Search persistence never creates a reporting-sidecar candidate authority."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from calm.public.project import Project
from calm.public.records.interfaces import InterfaceCandidate, InterfaceSearchResult


class _WorkspaceStub:
    def list_prototypes(self, *, run=None, limit=None):
        del run, limit
        return []

    def list_interface_searches(self, *, limit=None):
        del limit
        return []


def _result() -> InterfaceSearchResult:
    candidates = [
        InterfaceCandidate(None, rank=0, uid="proto:test:0", score=0.10),
        InterfaceCandidate(None, rank=1, uid="proto:test:1", score=0.30),
    ]
    return InterfaceSearchResult(request=SimpleNamespace(), candidates=candidates)


def test_search_result_does_not_create_reporting_state(tmp_path) -> None:
    path = tmp_path / "example.calm"
    project = Project(_WorkspaceStub(), path=path)

    project._saver.record_search_result(_result(), name="screen")

    assert not hasattr(project, "_public_records")
    assert not (path / "calm-public-records.json").exists()
    assert project.candidates().to_rows(view="all") == []


def test_removed_candidate_projection_remains_absent_after_reopen(tmp_path) -> None:
    path = tmp_path / "example.calm"
    project = Project(_WorkspaceStub(), path=path)
    project._saver.record_search_result(_result(), name="screen")

    reopened = Project(_WorkspaceStub(), path=path)
    assert not hasattr(reopened, "_public_records")
    assert not (path / "calm-public-records.json").exists()
    assert reopened.candidates().to_rows(view="all") == []


def test_search_result_tags_require_an_explicit_annotation_owner(tmp_path) -> None:
    project = Project(_WorkspaceStub(), path=tmp_path / "example.calm")

    with pytest.raises(ValueError, match="explicit annotation owner"):
        project._saver.record_search_result(
            _result(),
            name="screen",
            tags=["review"],
        )
