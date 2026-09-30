from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from typing import Any

import pytest

from calm.interface.matching.audit import CoupledMatchEnumerationAudit
from calm.project.application.interface_searches import (
    InterfaceSearchConflictError,
    InterfaceSearchPreparation,
)
from calm.project.domain.models import InterfaceSearch
from calm.public.workflows.interface_search import (
    ProjectInterfaceSearchWorkflowService,
)
from calm.public.errors import SearchIdentityConflictError
from calm.public.records.search import PersistedInterfaceSearch
from calm.public.records.persistence import ProjectSearch, RecordAuthority
from calm.public.records.interfaces import InterfaceCandidate, InterfaceSearchResult
from calm.public.inputs.settings import SearchSettings
from calm.public.records.surfaces import Surface


def _surface(uid: str) -> Surface:
    return Surface(
        object(),
        miller=(1, 0, 0),
        layers=1,
        material="M",
        label=uid,
        termination="A",
        termination_shift=0,
        project_slab_uid_full=uid,
        project_slab_id_short="s_" + uid.rsplit(":", 1)[-1],
    )


def _result(
    *,
    enumeration_audit: CoupledMatchEnumerationAudit | None = None,
) -> InterfaceSearchResult:
    return InterfaceSearchResult(
        request=None,
        candidates=[
            InterfaceCandidate(
                None,
                rank=0,
                candidate_id="C0000",
                candidate_uid="candidate:0",
                score=0.1,
                d_cell=0.01,
                n_atoms_estimate=8,
            )
        ],
        internal_result=(
            None
            if enumeration_audit is None
            else SimpleNamespace(enumeration_audit=enumeration_audit)
        ),
    )


def _search(
    *,
    name: str = "screen",
    identity: str = "interface_search:one",
    status: str = "running",
) -> InterfaceSearch:
    return InterfaceSearch(
        name=name,
        search_identity=identity,
        run_uid_full="run:search",
        run_id_short="r_search",
        status=status,
        spec={"search_identity": identity},
        error=None,
        progress={"phase": status},
    )


class _Repository:
    def __init__(self, search: InterfaceSearch) -> None:
        self.search = search
        self.calls: list[str] = []

    def get_search(self, identifier: str) -> InterfaceSearch:
        self.calls.append(str(identifier))
        if str(identifier) not in {
            self.search.name,
            self.search.search_identity,
            self.search.run_uid_full,
            self.search.run_id_short,
        }:
            raise KeyError(identifier)
        return self.search


class _Workspace:
    def __init__(self, search: InterfaceSearch, *, action: str = "execute") -> None:
        self.search = search
        self.action = action
        self.prepare_calls: list[dict[str, Any]] = []
        self.complete_calls: list[dict[str, Any]] = []
        self.fail_calls: list[dict[str, Any]] = []
        self.conflict: str | None = None
        self.repository: _Repository | None = None

    def prepare_interface_search(self, **kwargs: Any) -> InterfaceSearchPreparation:
        self.prepare_calls.append(dict(kwargs))
        if self.conflict is not None:
            raise InterfaceSearchConflictError(self.conflict)
        return InterfaceSearchPreparation(action=self.action, search=self.search)

    def complete_interface_search(
        self,
        run_uid_full: str,
        *,
        n_candidates: int,
        enumeration_audit=None,
    ) -> InterfaceSearch:
        self.complete_calls.append(
            {
                "run_uid_full": run_uid_full,
                "n_candidates": n_candidates,
                "enumeration_audit": enumeration_audit,
            }
        )
        progress = {"phase": "complete", "n_candidates": n_candidates}
        if enumeration_audit is not None:
            progress["enumeration_audit"] = dict(enumeration_audit)
        self.search = replace(
            self.search,
            status="done",
            progress=progress,
        )
        if self.repository is not None:
            self.repository.search = self.search
        return self.search

    def fail_interface_search(self, run_uid_full: str, *, error):
        self.fail_calls.append(
            {"run_uid_full": run_uid_full, "error": dict(error)}
        )
        self.search = replace(
            self.search,
            status="failed",
            error=dict(error),
            progress={"phase": "failed"},
        )
        if self.repository is not None:
            self.repository.search = self.search
        return self.search


class _Saver:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def record_search_result(self, result, *, name=None, reporter=None) -> None:
        self.calls.append(
            {"result": result, "name": name, "reporter": reporter}
        )


def _service(
    *,
    action: str = "execute",
    status: str = "running",
) -> tuple[
    ProjectInterfaceSearchWorkflowService,
    _Workspace,
    _Repository,
    _Saver,
    object,
]:
    project = object()
    search = _search(status=status)
    workspace = _Workspace(search, action=action)
    repository = _Repository(search)
    workspace.repository = repository
    saver = _Saver()
    return (
        ProjectInterfaceSearchWorkflowService(
            project=project,
            workspace=workspace,
            repository=repository,
            saver=saver,
        ),
        workspace,
        repository,
        saver,
        project,
    )


def test_named_search_composition_executes_persists_and_completes(monkeypatch) -> None:
    service, workspace, repository, saver, project = _service()
    monkeypatch.setattr(
        "calm.public.workflows.search.search_interfaces",
        lambda *args, **kwargs: _result(),
    )

    view = service.search_interfaces(
        _surface("slab:a"),
        _surface("slab:b"),
        settings=SearchSettings(max_candidates=7),
        name="  screen  ",
    )

    assert view.project is project
    assert view.name == "screen"
    assert view.run_status == "done"
    assert workspace.prepare_calls[0]["name"] == "screen"
    assert workspace.prepare_calls[0]["resume"] is True
    assert workspace.prepare_calls[0]["run_spec"]["settings"]["max_candidates"] == 7
    assert workspace.complete_calls == [
        {
            "run_uid_full": "run:search",
            "n_candidates": 1,
            "enumeration_audit": None,
        }
    ]
    assert saver.calls[0]["name"] == "screen"
    persisted_result = saver.calls[0]["result"]
    assert persisted_result.metadata["run_uid_full"] == "run:search"
    assert persisted_result.metadata["status"] == "done"
    assert repository.calls[-1] == "screen"



def test_named_search_persists_enumeration_audit(monkeypatch) -> None:
    service, workspace, _repository, _saver, _project = _service()
    audit = CoupledMatchEnumerationAudit.empty(2)
    monkeypatch.setattr(
        "calm.public.workflows.search.search_interfaces",
        lambda *args, **kwargs: _result(enumeration_audit=audit),
    )

    view = service.search_interfaces(
        _surface("slab:a"),
        _surface("slab:b"),
        name="screen",
    )

    expected = audit.to_dict(cumulative=False)
    assert workspace.complete_calls[0]["enumeration_audit"] == expected
    assert view.enumeration_audit().to_dict() == expected

def test_completed_search_reuse_skips_kernel_and_persistence(monkeypatch) -> None:
    service, workspace, _repository, saver, _project = _service(
        action="reuse",
        status="done",
    )

    def unexpected(*args, **kwargs):
        raise AssertionError("scientific kernel must not execute on reuse")

    monkeypatch.setattr("calm.public.workflows.search.search_interfaces", unexpected)
    view = service.search_interfaces(
        _surface("slab:a"),
        _surface("slab:b"),
        name="screen",
    )

    assert view.run_status == "done"
    assert workspace.complete_calls == []
    assert saver.calls == []


def test_application_conflicts_are_translated_to_public_error() -> None:
    service, workspace, _repository, _saver, _project = _service()
    workspace.conflict = "name conflict"

    with pytest.raises(SearchIdentityConflictError, match="name conflict"):
        service.search_interfaces(
            _surface("slab:a"),
            _surface("slab:b"),
            name="screen",
        )


def test_record_failure_policy_persists_failure_and_returns_durable_view(
    monkeypatch,
) -> None:
    service, workspace, _repository, saver, _project = _service()

    def fail(*args, **kwargs):
        raise RuntimeError("kernel failed")

    monkeypatch.setattr("calm.public.workflows.search.search_interfaces", fail)
    view = service.search_interfaces(
        _surface("slab:a"),
        _surface("slab:b"),
        name="screen",
        on_error="record",
    )

    assert view.run_status == "failed"
    assert workspace.fail_calls[0]["error"]["message"] == "kernel failed"
    assert workspace.complete_calls == []
    assert saver.calls == []


def test_search_selectors_resolve_through_authoritative_repository() -> None:
    service, _workspace, repository, _saver, project = _service(status="done")

    by_name = service.search("screen")
    by_record = service.search(ProjectSearch.from_item(repository.search))
    assert by_name.name == by_record.name == "screen"
    assert by_name.project is project
    assert by_name.authority is RecordAuthority.AUTHORITATIVE

    same_view = service.search(by_name)
    assert same_view is by_name

    other_service, *_ = _service(status="done")
    with pytest.raises(ValueError, match="another Project"):
        other_service.search(by_name)


def test_search_record_must_match_authoritative_project_state() -> None:
    service, _workspace, repository, _saver, _project = _service(status="done")
    mismatched = replace(
        ProjectSearch.from_item(repository.search),
        name="other-name",
    )

    with pytest.raises(ValueError, match="authoritative name"):
        service.search(mismatched)


def test_search_input_validation_occurs_before_lifecycle_mutation() -> None:
    service, workspace, _repository, _saver, _project = _service()

    with pytest.raises(TypeError, match="SearchSettings"):
        service.search_interfaces(
            _surface("slab:a"),
            _surface("slab:b"),
            settings=object(),
            name="screen",
        )
    with pytest.raises(ValueError, match="raise.*record"):
        service.search_interfaces(
            _surface("slab:a"),
            _surface("slab:b"),
            name="screen",
            on_error="skip",
        )
    with pytest.raises(ValueError, match="non-empty name"):
        service.search_interfaces(
            _surface("slab:a"),
            _surface("slab:b"),
            name="   ",
        )

    assert workspace.prepare_calls == []
