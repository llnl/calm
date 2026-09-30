from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from test_helpers import CaptureReporter

from calm.public.queries.health import ProjectHealthService
from calm.public.records.buildability import BuildabilityReport


class _Repository:
    def __init__(self, *, reporting_only: bool = False) -> None:
        self._reporting_only = reporting_only
        self.search = SimpleNamespace(
            name="db_search",
            status="done",
            search_identity="interface_search:db",
            run_uid_full="run:db",
            run_id_short="r_db",
            failure=None,
        )

    def list_bulks(self):
        return [object(), object()]

    def list_slabs(self):
        return [object(), object(), object()]

    def list_searches(self, *, limit=None):
        assert limit is None
        return [self.search]

    def list_candidates(self, *, search_name=None):
        if search_name is None:
            return [{"project_prototype_uid": f"proto:{index}"} for index in range(5)]
        assert search_name == "db_search"
        if self._reporting_only:
            return [{"candidate_id": "C0000"}]
        return [{"project_prototype_uid": "proto:1"}]

    def list_interfaces(self, *, search_name=None):
        if search_name is None:
            return [object()] * 7
        assert search_name == "db_search"
        return []

    def list_datasets(self, *, limit=None):
        assert limit is None
        return [object()] * 11

    def list_followup_results(self, *, kind=None, limit=None):
        assert kind == "energy_stage"
        assert limit == 100000
        return [object()] * 13

    def get_search(self, name):
        assert name == "db_search"
        return self.search


class _CandidateCollection:
    def __init__(self, buildable: int) -> None:
        self._buildable = buildable

    def search(self, name):
        assert name == "db_search"
        return self

    def validate_buildable(self):
        return BuildabilityReport(
            n_candidates=1,
            n_buildable=self._buildable,
            issues=[],
        )


class _Queries:
    def __init__(self, *, buildable: int) -> None:
        self._buildable = buildable

    def candidates(self):
        return _CandidateCollection(self._buildable)


class _Workspace:
    def get_calculator(self, uid):
        assert uid == "calculator:1"
        return SimpleNamespace(family="mace", model="small")

    def check_prototype_buildability(self, prototype):
        return SimpleNamespace(prototype_uid_full=prototype, buildable=True)

    def check_prototypes_buildability(self, prototypes):
        return {
            prototype: self.check_prototype_buildability(prototype)
            for prototype in prototypes
        }


class _Project:
    path = Path("study.calm")
    _configuration = {
        "default_mlip": "mace",
        "default_calculator_uid_full": "calculator:1",
        "workflow_defaults": {"build": {}},
    }


def _service(*, reporting_only: bool = False, buildable: int = 1):
    return ProjectHealthService(
        project=_Project(),
        workspace=_Workspace(),
        repository=_Repository(reporting_only=reporting_only),
        queries=_Queries(buildable=buildable),
    )


def test_project_health_counts_use_authoritative_repositories() -> None:
    assert _service().project_counts() == {
        "materials": 2,
        "surfaces": 3,
        "searches": 1,
        "candidates": 5,
        "interfaces": 7,
        "datasets": 11,
        "energies": 13,
    }


def test_project_health_owns_buildability_and_search_readiness() -> None:
    service = _service(buildable=1)
    assert service.check_prototype_buildability("proto:1").buildable
    assert set(service.check_prototypes_buildability(["proto:1"])) == {"proto:1"}
    status = service.search_status("db_search")
    assert status["n_candidates"] == 1
    assert status["n_authoritative_prototypes"] == 1
    assert status["n_buildable"] == 1
    assert service.search_summary("db_search").ok


def test_project_health_reports_malformed_and_unbuildable_searches() -> None:
    reporting_only = _service(reporting_only=True, buildable=0).workflow_warnings()
    assert any("reporting-only" in message for message in reporting_only)

    unbuildable = _service(buildable=0).workflow_warnings()
    assert any("no buildable candidates" in message for message in unbuildable)


def test_project_open_report_uses_health_service() -> None:
    reporter = CaptureReporter()
    _service().report_open_project(reporter)

    project_mapping = next(
        event
        for event in reporter.events
        if event.kind == "mapping" and event.meta.get("title") == "Project"
    )
    assert "calculator: mace:small" in project_mapping.message
    assert "workflow defaults: present" in project_mapping.message

    stored = next(
        event
        for event in reporter.events
        if event.kind == "mapping" and event.meta.get("title") == "Stored objects"
    )
    assert "surfaces: 3" in stored.message
    assert "materials: 2" in stored.message
    summary = next(event for event in reporter.events if event.kind == "summary")
    assert summary.message == "Project ready for scientific workflows"
