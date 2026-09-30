from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from types import SimpleNamespace

import pytest

from calm.project.application.interface_searches import (
    InterfaceSearchConflictError,
    InterfaceSearchPreparation,
)
from calm.project.domain.models import InterfaceSearch
from calm.public.errors import SearchIdentityConflictError
from calm.public.project import Project
from calm.public.records.interfaces import InterfaceCandidate, InterfaceSearchResult
from calm.public.workflows.search import search_interfaces
from calm.public.workflows.search_identity import build_search_identity
from calm.public.inputs.settings import SearchSettings
from calm.public.records.surfaces import Surface


class _RunWorkspace:
    def __init__(self):
        self.runs: dict[str, SimpleNamespace] = {}
        self.searches: dict[str, tuple[str, str]] = {}

    @staticmethod
    def _uid(run_type: str, spec: dict) -> str:
        raw = json.dumps(
            {"run_type": run_type, "spec": spec},
            sort_keys=True,
            separators=(",", ":"),
        )
        return "run:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def create_run(self, *, run_type: str, spec: dict):
        uid = self._uid(run_type, spec)
        if uid not in self.runs:
            self.runs[uid] = SimpleNamespace(
                uid_full=uid,
                id_short="r_" + uid.split(":", 1)[1][:12],
                run_type=run_type,
                spec=dict(spec),
                status="queued",
                error=None,
                progress=None,
                created_at=None,
                updated_at=None,
            )
        return self.runs[uid]

    def get_run(self, run: str):
        for item in self.runs.values():
            if run in {item.uid_full, item.id_short}:
                return item
        raise KeyError(run)

    def list_runs(self, *, run_type=None, status=None, limit=None):
        items = list(self.runs.values())
        if run_type is not None:
            items = [item for item in items if item.run_type == run_type]
        if status is not None:
            items = [item for item in items if item.status == status]
        return items if limit is None else items[:limit]

    def mark_run_running(self, run: str, *, progress=None):
        item = self.get_run(run)
        item.status = "running"
        item.error = None
        item.progress = dict(progress or {}) or None
        return item

    def mark_run_done(self, run: str, *, progress=None):
        item = self.get_run(run)
        item.status = "done"
        item.error = None
        item.progress = dict(progress or {}) or None
        return item

    def mark_run_failed(self, run: str, *, error):
        item = self.get_run(run)
        item.status = "failed"
        item.error = dict(error)
        return item

    def _search_record(self, name: str) -> InterfaceSearch:
        search_identity, run_uid_full = self.searches[name]
        run = self.get_run(run_uid_full)
        return InterfaceSearch(
            name=name,
            search_identity=search_identity,
            run_uid_full=run.uid_full,
            run_id_short=run.id_short,
            status=run.status,
            spec=dict(run.spec),
            error=dict(run.error) if run.error is not None else None,
            progress=(
                dict(run.progress) if run.progress is not None else None
            ),
        )

    def prepare_interface_search(
        self,
        *,
        name,
        search_identity,
        run_spec,
        resume,
    ):
        existing = self.searches.get(name)
        if existing is not None and existing[0] != search_identity:
            raise InterfaceSearchConflictError("name conflict")
        for other_name, (identity, _run_uid) in self.searches.items():
            if identity == search_identity and other_name != name:
                raise InterfaceSearchConflictError("identity already persisted")

        run = self.create_run(run_type="prototype_search", spec=dict(run_spec))
        if existing is None:
            self.searches[name] = (search_identity, run.uid_full)
        if resume and run.status == "done":
            return InterfaceSearchPreparation(
                action="reuse",
                search=self._search_record(name),
            )
        self.mark_run_running(
            run.uid_full,
            progress={"name": name, "phase": "search"},
        )
        return InterfaceSearchPreparation(
            action="execute",
            search=self._search_record(name),
        )

    def complete_interface_search(
        self,
        run_uid_full,
        *,
        n_candidates,
        enumeration_audit=None,
    ):
        progress = {
            "phase": "complete",
            "n_candidates": int(n_candidates),
        }
        if enumeration_audit is not None:
            progress["enumeration_audit"] = dict(enumeration_audit)
        run = self.mark_run_done(
            run_uid_full,
            progress=progress,
        )
        name = next(
            name
            for name, (_identity, uid) in self.searches.items()
            if uid == run.uid_full
        )
        return self._search_record(name)

    def fail_interface_search(self, run_uid_full, *, error):
        run = self.mark_run_failed(run_uid_full, error=error)
        name = next(
            name
            for name, (_identity, uid) in self.searches.items()
            if uid == run.uid_full
        )
        return self._search_record(name)

    def list_interface_searches(self, *, limit=None):
        rows = [self._search_record(name) for name in self.searches]
        return rows if limit is None else rows[:limit]

    def get_interface_search(self, identifier):
        for name in self.searches:
            record = self._search_record(name)
            if identifier in {
                record.name,
                record.search_identity,
                record.run_uid_full,
                record.run_id_short,
            }:
                return record
        raise KeyError(identifier)

    def persist_interface_prototypes(
        self,
        prototypes,
        *,
        run_uid_full=None,
    ):
        return {}

    def list_prototypes(self, *, run=None, limit=None):
        del run, limit
        return []


def _surface(uid: str, *, termination: str = "A") -> Surface:
    return Surface(
        object(),
        miller=(1, 0, 0),
        layers=1,
        material="M",
        label=uid,
        termination=termination,
        termination_shift=0,
        project_slab_uid_full=uid,
        project_slab_id_short="s_" + uid.rsplit(":", 1)[-1],
    )


def _result(request=None) -> InterfaceSearchResult:
    return InterfaceSearchResult(
        request=request,
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
    )


def test_search_identity_uses_surfaces_settings_and_not_public_name() -> None:
    a = _surface("slab:a")
    b = _surface("slab:b")
    settings = SearchSettings(max_candidates=7)

    identity_1, spec_1 = build_search_identity(a, b, settings)
    identity_2, spec_2 = build_search_identity(a, b, settings)
    assert identity_1 == identity_2
    assert spec_1 == spec_2
    assert "name" not in spec_1
    assert "deduplicate" not in spec_1["settings"]
    assert spec_1["schema_version"] == 2
    assert spec_1["implementation"] == "primitive_coupled_pair_v2"
    assert spec_1["surface_a"]["uid_full"] == "slab:a"
    assert spec_1["surface_b"]["uid_full"] == "slab:b"
    assert spec_1["surface_a"]["termination"] == "A"
    assert spec_1["surface_b"]["termination"] == "A"

    with pytest.raises(TypeError, match="deduplicate"):
        SearchSettings.from_dict(
            {**settings.to_dict(), "deduplicate": False}
        )

    changed_settings = replace(settings, max_candidates=8)
    identity_3, _ = build_search_identity(a, b, changed_settings)
    assert identity_3 != identity_1

    identity_4, _ = build_search_identity(a, _surface("slab:c"), settings)
    assert identity_4 != identity_1


def test_surface_conversion_failure_is_not_hidden_by_raw_structure_fallback() -> None:
    class BrokenGeneratedSurface:
        def to_surface(self):
            raise RuntimeError("invalid generated surface")

    with pytest.raises(RuntimeError, match="invalid generated surface"):
        search_interfaces(
            BrokenGeneratedSurface(),
            _surface("slab:b"),
        )


def test_completed_identical_search_is_reused_without_kernel_execution(
    tmp_path,
    monkeypatch,
) -> None:
    workspace = _RunWorkspace()
    project = Project(workspace, path=tmp_path)
    calls = 0

    def execute(surface_a, surface_b, **kwargs):
        nonlocal calls
        calls += 1
        return _result()

    monkeypatch.setattr("calm.public.workflows.search.search_interfaces", execute)
    first = project.search_interfaces(
        _surface("slab:a"),
        _surface("slab:b"),
        name="same",
    )
    second = project.search_interfaces(
        _surface("slab:a"),
        _surface("slab:b"),
        name="same",
    )

    assert calls == 1
    assert first.uid_full == second.uid_full
    assert second.run_status == "done"
    search = project.searches().get("same")
    assert search.status == "done"
    assert search.is_authoritative
    assert search.search_identity == first.record.search_identity


def test_same_name_with_different_scientific_identity_is_rejected(
    tmp_path,
    monkeypatch,
) -> None:
    project = Project(_RunWorkspace(), path=tmp_path)
    monkeypatch.setattr(
        "calm.public.workflows.search.search_interfaces",
        lambda *args, **kwargs: _result(),
    )
    project.search_interfaces(
        _surface("slab:a"),
        _surface("slab:b"),
        name="conflict",
    )

    with pytest.raises(SearchIdentityConflictError):
        project.search_interfaces(
            _surface("slab:a"),
            _surface("slab:c"),
            name="conflict",
        )


def test_failed_search_is_recorded_and_resume_restarts_same_run(
    tmp_path,
    monkeypatch,
) -> None:
    project = Project(_RunWorkspace(), path=tmp_path)

    def fail(*args, **kwargs):
        raise RuntimeError("kernel failed")

    monkeypatch.setattr("calm.public.workflows.search.search_interfaces", fail)
    failed = project.search_interfaces(
        _surface("slab:a"),
        _surface("slab:b"),
        name="retry",
        on_error="record",
    )
    assert failed.run_status == "failed"
    failed_uid = failed.uid_full
    record = project.searches().get("retry")
    assert record.status == "failed"
    assert record.failure is not None
    assert record.failure.message == "kernel failed"

    monkeypatch.setattr(
        "calm.public.workflows.search.search_interfaces",
        lambda *args, **kwargs: _result(),
    )
    completed = project.search_interfaces(
        _surface("slab:a"),
        _surface("slab:b"),
        name="retry",
        resume=True,
    )
    assert completed.run_status == "done"
    assert completed.uid_full == failed_uid
    assert project.searches().get("retry").status == "done"


def test_project_search_rejects_nonpersistent_skip_policy(tmp_path) -> None:
    project = Project(_RunWorkspace(), path=tmp_path)
    with pytest.raises(ValueError, match="raise.*record"):
        project.search_interfaces(
            _surface("slab:a"),
            _surface("slab:b"),
            name="skip",
            on_error="skip",
        )


def test_same_scientific_identity_cannot_use_two_public_names(
    tmp_path,
    monkeypatch,
) -> None:
    project = Project(_RunWorkspace(), path=tmp_path)
    monkeypatch.setattr(
        "calm.public.workflows.search.search_interfaces",
        lambda *args, **kwargs: _result(),
    )
    project.search_interfaces(
        _surface("slab:a"),
        _surface("slab:b"),
        name="first-name",
    )

    with pytest.raises(SearchIdentityConflictError, match="already persisted"):
        project.search_interfaces(
            _surface("slab:a"),
            _surface("slab:b"),
            name="second-name",
        )



def test_retired_transient_grid_search_remains_absent() -> None:
    import calm.public.workflows.search as search_module

    assert not hasattr(search_module, "search_interface_grid")
    assert not hasattr(search_module, "InterfaceCampaignResult")
