from __future__ import annotations

import pytest

pytest.importorskip("ase")

from calm.public.project import open_project
from calm.public.records.interfaces import InterfaceCandidate, InterfaceSearchResult
from calm.public.records.surfaces import Surface


def _surface(uid: str) -> Surface:
    return Surface(
        object(),
        miller=(1, 0, 0),
        layers=1,
        material="M",
        label=uid,
        termination="M",
        termination_shift=0,
        project_slab_uid_full=uid,
        project_slab_id_short="s_" + uid.rsplit(":", 1)[-1],
    )


def _result() -> InterfaceSearchResult:
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
    )


def test_completed_search_reuses_authoritative_run_after_reopen(
    tmp_path,
    monkeypatch,
) -> None:
    project = open_project(tmp_path)
    calls = 0

    def execute(*args, **kwargs):
        nonlocal calls
        calls += 1
        return _result()

    monkeypatch.setattr("calm.public.workflows.search.search_interfaces", execute)
    first = project.search_interfaces(
        _surface("slab:a"),
        _surface("slab:b"),
        name="roundtrip",
    )
    first_uid = first.uid_full
    assert project.run(first_uid).status == "done"

    reopened = open_project(tmp_path)

    def must_not_execute(*args, **kwargs):
        raise AssertionError("completed search should have been reused")

    monkeypatch.setattr("calm.public.workflows.search.search_interfaces", must_not_execute)
    second = reopened.search_interfaces(
        _surface("slab:a"),
        _surface("slab:b"),
        name="roundtrip",
    )

    assert calls == 1
    assert second.uid_full == first_uid
    assert second.run_status == "done"
    record = reopened.searches().get("roundtrip")
    assert record.is_authoritative
    assert record.status == "done"
    assert record.run_uid_full == first_uid
