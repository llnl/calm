from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from calm.public.workflows.interface_build import ProjectInterfaceBuildService
from calm.public.records.buildability import BuildabilityReport
from calm.public.inputs.settings import BuildSettings


class _Candidates:
    def __init__(self, rows: list[dict[str, Any]], *, buildable: bool = True):
        self.rows = list(rows)
        self.buildable = buildable
        self.calls: list[tuple[str, Any]] = []

    def select(self, **kwargs):
        self.calls.append(("select", kwargs))
        return self

    def select_top(self, n: int, *, by: str):
        self.calls.append(("select_top", {"n": n, "by": by}))
        clone = _Candidates(self.rows[:n], buildable=self.buildable)
        clone.calls = self.calls
        return clone

    def validate_buildable(self):
        return BuildabilityReport(
            n_candidates=len(self.rows),
            n_buildable=len(self.rows) if self.buildable else 0,
            issues=[],
        )

    def __iter__(self):
        return iter(self.rows)


class _Search:
    name = "screen"

    def __init__(self, candidates: _Candidates):
        self._candidates = candidates

    def candidates(self):
        return self._candidates


class _Project:
    def search(self, search):
        return search


class _Workspace:
    def __init__(self) -> None:
        self.build_calls: list[dict[str, Any]] = []
        self.stage_calls: list[dict[str, Any]] = []

    def build_interface_from_prototype(self, prototype: str, **kwargs: Any):
        self.build_calls.append({"prototype": prototype, **kwargs})
        return SimpleNamespace(
            atoms=object(),
            prototype_uid_full=prototype,
        )

    def run_build_stage(self, prototypes: list[str], **kwargs: Any):
        self.stage_calls.append({"prototypes": list(prototypes), **kwargs})
        return [
            {"prototype_uid": prototype, "status": "completed"}
            for prototype in prototypes
        ]


class _Saver:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def record_interface_model(self, model, *, name=None, reporter=None):
        self.calls.append({"model": model, "name": name, "reporter": reporter})
        return SimpleNamespace(uid_full="iface:1", id_short="i_1")


def _service() -> tuple[ProjectInterfaceBuildService, _Workspace, _Saver]:
    workspace = _Workspace()
    saver = _Saver()
    service = ProjectInterfaceBuildService(
        project=_Project(),
        workspace=workspace,
        repository=SimpleNamespace(),
        saver=saver,
    )
    return service, workspace, saver


def test_build_service_owns_selection_construction_and_persistence() -> None:
    service, workspace, saver = _service()
    candidates = _Candidates(
        [
            {
                "candidate_id": "C0000",
                "project_prototype_uid": "proto:1",
                "score": 0.1,
                "is_pareto": True,
            }
        ]
    )
    settings = BuildSettings(
        alpha=0.25,
        gap=2.0,
        vacuum=12.0,
        translation=(0.125, 0.375),
    )

    built = service.build_interfaces(
        _Search(candidates),
        top=1,
        settings=settings,
        name_prefix="case",
    )

    assert len(built) == 1
    model = built[0]
    assert model.project_interface_uid == "iface:1"
    assert model.project_interface_id == "i_1"
    assert model.candidate["project_prototype_uid"] == "proto:1"
    assert candidates.calls == [
        ("select", {"pareto": True}),
        ("select_top", {"n": 1, "by": "score"}),
    ]
    assert workspace.build_calls == [
        {
            "prototype": "proto:1",
            "alpha": 0.25,
            "translation_frac": (0.125, 0.375),
            "z_padding": 2.0,
            "vacuum": 12.0,
        }
    ]
    assert saver.calls[0]["name"] == "case_0000"


def test_build_service_rejects_non_authoritative_candidate_before_execution() -> None:
    service, workspace, saver = _service()
    search = _Search(_Candidates([{"candidate_id": "C0000", "score": 0.1}]))

    with pytest.raises(RuntimeError, match="lack authoritative"):
        service.build_interfaces(search)

    assert workspace.build_calls == []
    assert saver.calls == []
