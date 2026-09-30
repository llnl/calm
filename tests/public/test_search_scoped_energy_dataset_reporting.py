from __future__ import annotations

from pathlib import Path

import pytest

from energy_result_fixtures import (
    failed_raw_energy_payload,
    raw_energy_payload,
    thermodynamic_payload,
)

from calm.public.records.datasets import (
    DatasetExportResult,
    DatasetValidationError,
    DatasetValidationIssue,
    DatasetValidationReport,
)
from calm.public.errors import AmbiguousProjectQueryError
from calm.public.collections.interfaces import InterfaceCollection
from calm.public.records.search import PersistedInterfaceSearch
from calm.public.records.persistence import ProjectRun


class _Repo:
    def __init__(self, *, edges, followups):
        self._edges = list(edges)
        self._followups = {
            str(row["uid_full"]): dict(row)
            for row in followups
        }

    def list_edges(self, *, src=None, dst=None, kind=None, limit=None):
        rows = [
            row
            for row in self._edges
            if (src is None or row["src_uid_full"] == src)
            and (dst is None or row["dst_uid_full"] == dst)
            and (kind is None or row["kind"] == kind)
        ]
        return rows if limit is None else rows[:limit]

    def get_followup_result(self, identifier):
        try:
            return self._followups[str(identifier)]
        except KeyError as exc:
            raise KeyError(f"Follow-up result not found: {identifier}") from exc


class _Project:
    def __init__(self, *, interfaces, edges, followups, runs):
        self._interfaces = list(interfaces)
        self._repo = _Repo(edges=edges, followups=followups)
        self._runs = {
            record.uid_full: record
            for record in runs
        }

    def interfaces(self):
        return InterfaceCollection(interfaces=self._interfaces)

    def run(self, identifier):
        needle = str(identifier)
        for record in self._runs.values():
            if needle in {record.uid_full, record.id_short}:
                return record
        raise KeyError(f"Run not found: {identifier}")


def _run(uid: str, *, run_type: str, created_at: str, status: str = "done"):
    return ProjectRun(
        uid_full=uid,
        id_short=uid.replace("run:", "r_"),
        run_type=run_type,
        status=status,
        created_at=created_at,
    )


def _followup(
    uid: str,
    *,
    kind: str,
    run_uid: str,
    target_uid: str,
    status: str = "done",
):
    if kind == "energy_stage":
        payload = (
            failed_raw_energy_payload()
            if status == "failed"
            else raw_energy_payload(-1.0)
        )
        best_energy = None if status == "failed" else -1.0
        param1 = None
        param2 = None
        n_points = None if status == "failed" else 1
    else:
        payload = thermodynamic_payload(
            raw_energy_followup_uid="followup:energy:new",
            value_eV_per_A2=0.1,
            n_interfaces=1,
        )
        best_energy = 0.1
        param1 = 10.0
        param2 = 1.0
        n_points = 1
    return {
        "uid_full": uid,
        "id_short": uid.replace("followup:", "f_"),
        "run_uid_full": run_uid,
        "run_id_short": run_uid.replace("run:", "r_"),
        "prototype_uid_full": "proto:1",
        "target_uid_full": target_uid,
        "target_kind": "interface",
        "kind": kind,
        "status": status,
        "best_energy": best_energy,
        "param1": param1,
        "param2": param2,
        "n_points": n_points,
        "payload": payload,
        "created_at": uid,
        "authority": "authoritative",
    }


def _edge(source: str, destination: str):
    return {
        "uid_full": f"edge:{source}:{destination}",
        "src_uid_full": source,
        "dst_uid_full": destination,
        "kind": "interface_to_followup",
        "payload": {},
        "authority": "authoritative",
    }


def _project() -> _Project:
    interfaces = [
        {
            "uid_full": "interface:search-a",
            "id_short": "i_a",
            "stage": "relaxed",
            "search_name": "search-A",
            "authority": "authoritative",
        },
        {
            "uid_full": "interface:search-b",
            "id_short": "i_b",
            "stage": "relaxed",
            "search_name": "search-B",
            "authority": "authoritative",
        },
    ]
    followups = [
        _followup(
            "followup:energy:old",
            kind="energy_stage",
            run_uid="run:energy:old",
            target_uid="interface:search-a",
        ),
        _followup(
            "followup:energy:new",
            kind="energy_stage",
            run_uid="run:energy:new",
            target_uid="interface:search-a",
        ),
        _followup(
            "followup:energy:failed",
            kind="energy_stage",
            run_uid="run:energy:failed",
            target_uid="interface:search-a",
            status="failed",
        ),
        _followup(
            "followup:energy:other-search",
            kind="energy_stage",
            run_uid="run:energy:other-search",
            target_uid="interface:search-b",
        ),
        _followup(
            "followup:thermo:new",
            kind="thermodynamic_quantity",
            run_uid="run:thermo:new",
            target_uid="interface:search-a",
        ),
    ]
    edges = [
        _edge(str(row["target_uid_full"]), str(row["uid_full"]))
        for row in followups
    ]
    runs = [
        _run(
            "run:energy:old",
            run_type="energy_stage",
            created_at="2026-01-01T00:00:00Z",
        ),
        _run(
            "run:energy:new",
            run_type="energy_stage",
            created_at="2026-02-01T00:00:00Z",
        ),
        _run(
            "run:energy:failed",
            run_type="energy_stage",
            created_at="2026-03-01T00:00:00Z",
            status="failed",
        ),
        _run(
            "run:energy:other-search",
            run_type="energy_stage",
            created_at="2026-04-01T00:00:00Z",
        ),
        _run(
            "run:thermo:new",
            run_type="thermodynamic_derivation",
            created_at="2026-02-02T00:00:00Z",
        ),
    ]
    return _Project(
        interfaces=interfaces,
        edges=edges,
        followups=followups,
        runs=runs,
    )


def test_search_energy_results_exclude_other_searches_and_do_not_mix_runs():
    search = PersistedInterfaceSearch(_project(), "search-A")

    with pytest.raises(
        AmbiguousProjectQueryError,
        match="multiple 'energy_stage' runs",
    ):
        search.energy_results(status="completed")

    latest = search.energy_results(status="completed", latest_run=True)
    assert [record.uid_full for record in latest] == ["followup:energy:new"]

    old = search.energy_results(run="run:energy:old", status="completed")
    assert [record.uid_full for record in old] == ["followup:energy:old"]

    failed_as_completed = search.energy_results(
        run="run:energy:failed",
        status="completed",
    )
    assert len(failed_as_completed) == 0


def test_search_energy_queries_are_reopen_safe_and_return_typed_empty_collections():
    first = PersistedInterfaceSearch(_project(), "search-A")
    reopened = PersistedInterfaceSearch(_project(), "search-A")

    first_ids = [
        record.uid_full
        for record in first.energy_results(status="completed", latest_run=True)
    ]
    reopened_ids = [
        record.uid_full
        for record in reopened.energy_results(status="completed", latest_run=True)
    ]
    assert reopened_ids == first_ids == ["followup:energy:new"]

    empty = PersistedInterfaceSearch(_project(), "missing-search")
    assert len(empty.energy_results(status="completed", latest_run=True)) == 0
    assert len(empty.energy_runs()) == 0


def test_search_run_queries_and_thermodynamic_results_remain_distinct():
    search = PersistedInterfaceSearch(_project(), "search-A")

    assert {run.uid_full for run in search.energy_runs()} == {
        "run:energy:old",
        "run:energy:new",
        "run:energy:failed",
    }
    assert [run.uid_full for run in search.energy_runs(status="failed")] == [
        "run:energy:failed"
    ]
    assert [record.uid_full for record in search.thermodynamic_results()] == [
        "followup:thermo:new"
    ]
    assert [run.uid_full for run in search.thermodynamic_runs()] == [
        "run:thermo:new"
    ]


def test_explicit_run_selection_rejects_the_wrong_run_type():
    search = PersistedInterfaceSearch(_project(), "search-A")

    with pytest.raises(ValueError, match="expected 'energy_stage'"):
        search.energy_results(run="run:thermo:new")
    with pytest.raises(ValueError, match="mutually exclusive"):
        search.energy_results(run="run:energy:new", latest_run=True)


def test_dataset_validation_and_export_summaries_are_user_facing(tmp_path: Path):
    valid = DatasetValidationReport(
        dataset_uid_full="dataset:1",
        schema_version="calm.raw_energy.v1",
        n_items=2,
        n_valid=2,
    )
    valid.raise_for_errors()
    assert valid.summary() == "\n".join(
        [
            "Dataset validation: valid",
            "  schema: calm.raw_energy.v1",
            "  items: 2",
            "  valid items: 2",
            "  errors: 0",
            "  warnings: 0",
        ]
    )

    invalid = DatasetValidationReport(
        dataset_uid_full="dataset:1",
        schema_version="calm.raw_energy.v1",
        n_items=2,
        n_valid=1,
        issues=(
            DatasetValidationIssue(code="missing", message="missing provenance"),
            DatasetValidationIssue(
                code="warning",
                message="optional structure unavailable",
                severity="warning",
            ),
        ),
    )
    with pytest.raises(DatasetValidationError) as exc_info:
        invalid.raise_for_errors()
    assert exc_info.value.report is invalid
    assert "Dataset validation: invalid" in invalid.summary()
    assert "  errors: 1" in invalid.summary()
    assert "  warnings: 1" in invalid.summary()

    exported = DatasetExportResult(
        dataset_uid_full="dataset:1",
        destination=tmp_path / "export",
        manifest_path=tmp_path / "export" / "manifest.json",
        n_items=2,
        files=(tmp_path / "export" / "manifest.json",),
        checksums={"manifest.json": "abc"},
    )
    summary = exported.summary()
    assert "Dataset export: complete" in summary
    assert f"  destination: {tmp_path / 'export'}" in summary
    assert "  items: 2" in summary
    assert "  files: 1" in summary
    assert "  checksums: 1" in summary


def test_example_09_uses_search_scoping_and_typed_reporting():
    source = Path("examples/09_build_interface_dataset.py").read_text(
        encoding="utf-8"
    )
    assert "project.search(SEARCH_NAME)" in source
    assert "search.thermodynamic_results(" in source
    assert 'status="completed"' in source
    assert "latest_run=True" in source
    assert "project.energy_results().completed()" not in source
    assert "validation.raise_for_errors()" in source
    assert "validation.summary()" in source
    assert "readiness.raise_for_errors()" in source
    assert "readiness.summary()" in source
    assert "exported.summary()" in source
    assert ".to_dict()" not in source
