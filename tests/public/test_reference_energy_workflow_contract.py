from __future__ import annotations

from pathlib import Path

import pytest

from energy_result_fixtures import (
    failed_reference_energy_payload,
    reference_energy_payload,
)

from calm.public.errors import (
    AmbiguousProjectQueryError,
)
from calm.public.records.followups import ReferenceEnergyWorkflowResult
from calm.public.collections.interfaces import InterfaceCollection
from calm.public.collections.persistence import ReferenceEnergyResultCollection
from calm.public.records.search import PersistedInterfaceSearch
from calm.public.records.persistence import ProjectRun
from calm.public.inputs.settings import EnergyConvention
from calm.project.application.followups.thermodynamics import (
    ThermodynamicOrchestrator,
)


def _run(uid: str, *, created_at: str = "2026-01-01T00:00:00Z") -> ProjectRun:
    return ProjectRun(
        uid_full=uid,
        id_short=uid.replace("run:", "r_"),
        run_type="reference_energy",
        status="done",
        created_at=created_at,
    )


def _reference(
    uid: str,
    *,
    run_uid: str,
    target_uid: str,
    kind: str,
    energy: float,
    per_formula_unit: float | None = None,
    interface_formula_units: int | None = None,
    formula: str = "interface_excess_strained_bulk",
):
    reference_formula_units = 2 if per_formula_unit is not None else None
    payload = reference_energy_payload(
        reference_uid_full=f"reference:{uid}",
        reference_kind=kind,
        formula_id=formula,
        energy_eV=energy,
        energy_eV_per_formula_unit=per_formula_unit,
        reference_formula_units=reference_formula_units,
        interface_formula_units=interface_formula_units,
        structure_fingerprint=f"fingerprint:{uid}",
        relaxed=formula == "work_of_adhesion_relaxed_surfaces",
    )
    return {
        "uid_full": uid,
        "id_short": uid.replace("followup:", "f_"),
        "run_uid_full": run_uid,
        "run_id_short": run_uid.replace("run:", "r_"),
        "prototype_uid_full": "proto:1",
        "target_uid_full": target_uid,
        "target_kind": "interface",
        "kind": "reference_energy",
        "status": "done",
        "best_energy": energy,
        "param1": per_formula_unit,
        "param2": (
            float(interface_formula_units)
            if interface_formula_units is not None
            else None
        ),
        "n_points": 0,
        "payload": payload,
        "authority": "authoritative",
    }


def test_reference_workflow_builds_distinct_per_interface_bulk_settings():
    run = _run("run:references")
    results = ReferenceEnergyResultCollection(
        [
            _reference(
                "followup:a1",
                run_uid=run.uid_full,
                target_uid="iface:1",
                kind="strained_bulk_a",
                energy=-20.0,
                per_formula_unit=-10.0,
                interface_formula_units=4,
            ),
            _reference(
                "followup:b1",
                run_uid=run.uid_full,
                target_uid="iface:1",
                kind="strained_bulk_b",
                energy=-30.0,
                per_formula_unit=-15.0,
                interface_formula_units=3,
            ),
            _reference(
                "followup:a2",
                run_uid=run.uid_full,
                target_uid="iface:2",
                kind="strained_bulk_a",
                energy=-18.0,
                per_formula_unit=-9.0,
                interface_formula_units=5,
            ),
            _reference(
                "followup:b2",
                run_uid=run.uid_full,
                target_uid="iface:2",
                kind="strained_bulk_b",
                energy=-28.0,
                per_formula_unit=-14.0,
                interface_formula_units=2,
            ),
        ]
    )
    convention = EnergyConvention(
        formula="interface_excess_strained_bulk",
        n_interfaces=2,
    )
    workflow = ReferenceEnergyWorkflowResult(
        run=run,
        results=results,
        convention=convention,
    )

    first = workflow.references_for("iface:1")
    second = workflow.references_for("iface:2")
    assert first.bulk_a_eV_per_formula_unit == -10.0
    assert results[0].source_interface_uid_full == "iface:1"
    assert first.bulk_b_eV_per_formula_unit == -15.0
    assert first.n_formula_units_a == 4
    assert first.n_formula_units_b == 3
    assert second.bulk_a_eV_per_formula_unit == -9.0
    assert second.n_formula_units_a == 5
    assert first.metadata["source"] == "calm.reference_energy.v3"
    assert first.metadata["compatibility_source"] == "calculated_reference_workflow"
    assert first.metadata["energy_backend"] == "deterministic"
    assert first.metadata["backend_identity"] == {"name": "deterministic"}
    assert first.metadata["energy_settings"] == {"mode": "single_point"}
    assert first.metadata["reference_area_A2"] == 10.0

    payload = workflow.to_thermodynamic_payload()
    assert payload["mode"] == "by_target_uid"
    assert payload["reference_run_uid_full"] == run.uid_full
    assert set(payload["by_target_uid"]) == {"iface:1", "iface:2"}
    assert (
        payload["by_target_uid"]["iface:2"]["bulk_b_eV_per_formula_unit"]
        == -14.0
    )


def test_reference_workflow_rejects_incompatible_calculator_pair():
    run = _run("run:incompatible-references")
    row_a = _reference(
        "followup:a",
        run_uid=run.uid_full,
        target_uid="iface:1",
        kind="strained_bulk_a",
        energy=-20.0,
        per_formula_unit=-10.0,
        interface_formula_units=2,
    )
    row_b = _reference(
        "followup:b",
        run_uid=run.uid_full,
        target_uid="iface:1",
        kind="strained_bulk_b",
        energy=-30.0,
        per_formula_unit=-15.0,
        interface_formula_units=2,
    )
    row_b["payload"]["backend"]["identity"] = {"name": "different"}
    workflow = ReferenceEnergyWorkflowResult(
        run=run,
        results=ReferenceEnergyResultCollection([row_a, row_b]),
        convention=EnergyConvention(
            formula="interface_excess_strained_bulk",
            n_interfaces=1,
        ),
    )
    with pytest.raises(RuntimeError, match="calculator identity"):
        workflow.references_for("iface:1")



def test_reference_workflow_rejects_incompatible_area_pair():
    run = _run("run:incompatible-reference-areas")
    row_a = _reference(
        "followup:area-a",
        run_uid=run.uid_full,
        target_uid="iface:1",
        kind="strained_bulk_a",
        energy=-20.0,
        per_formula_unit=-10.0,
        interface_formula_units=2,
    )
    row_b = _reference(
        "followup:area-b",
        run_uid=run.uid_full,
        target_uid="iface:1",
        kind="strained_bulk_b",
        energy=-30.0,
        per_formula_unit=-15.0,
        interface_formula_units=2,
    )
    row_b["payload"]["reference"]["metadata"]["reference_area_A2"] = 11.0
    workflow = ReferenceEnergyWorkflowResult(
        run=run,
        results=ReferenceEnergyResultCollection([row_a, row_b]),
        convention=EnergyConvention(
            formula="interface_excess_strained_bulk",
            n_interfaces=1,
        ),
    )
    with pytest.raises(RuntimeError, match="interface areas"):
        workflow.references_for("iface:1")

def test_reference_workflow_builds_unrelaxed_surface_settings_and_rejects_missing_pair(
):
    run = _run("run:surface-references")
    convention = EnergyConvention(
        formula="work_of_separation_unrelaxed_surfaces",
        n_interfaces=2,
    )
    complete = ReferenceEnergyWorkflowResult(
        run=run,
        results=ReferenceEnergyResultCollection(
            [
                _reference(
                    "followup:sa",
                    run_uid=run.uid_full,
                    target_uid="iface:1",
                    kind="isolated_surface_a",
                    energy=-11.0,
                    formula=convention.formula,
                ),
                _reference(
                    "followup:sb",
                    run_uid=run.uid_full,
                    target_uid="iface:1",
                    kind="isolated_surface_b",
                    energy=-12.0,
                    formula=convention.formula,
                ),
            ]
        ),
        convention=convention,
    )
    values = complete.references_for("iface:1")
    assert values.surface_a_total_energy_eV == -11.0
    assert values.surface_b_total_energy_eV == -12.0

    incomplete = ReferenceEnergyWorkflowResult(
        run=run,
        results=ReferenceEnergyResultCollection(
            [
                _reference(
                    "followup:sa",
                    run_uid=run.uid_full,
                    target_uid="iface:1",
                    kind="isolated_surface_a",
                    energy=-11.0,
                    formula=convention.formula,
                )
            ]
        ),
        convention=convention,
    )
    with pytest.raises(RuntimeError, match="missing reference results"):
        incomplete.references_for("iface:1")


def test_reference_workflow_reports_failed_only_interface_as_incomplete():
    run = _run("run:failed-references")
    failed = _reference(
        "followup:failed",
        run_uid=run.uid_full,
        target_uid="iface:failed",
        kind="strained_bulk_a",
        energy=0.0,
        per_formula_unit=None,
        interface_formula_units=None,
    )
    failed["status"] = "failed"
    failed["best_energy"] = None
    failed["param1"] = None
    failed["param2"] = None
    failed["n_points"] = None
    failed["payload"] = failed_reference_energy_payload(
        reference_uid_full="reference:followup:failed",
        reference_kind="strained_bulk_a",
        formula_id="interface_excess_strained_bulk",
    )
    workflow = ReferenceEnergyWorkflowResult(
        run=run,
        results=ReferenceEnergyResultCollection([failed]),
        convention=EnergyConvention(
            formula="interface_excess_strained_bulk",
            n_interfaces=2,
        ),
    )

    assert not workflow.ok
    with pytest.raises(RuntimeError, match="backend failed"):
        workflow.reference_map()


def test_interface_collection_does_not_execute_reference_energy_workflows() -> None:
    assert not hasattr(InterfaceCollection, "_evaluate_reference_energies")


def test_thermodynamic_reference_selection_supports_static_and_target_indexed_values():
    static = {"surface_a_total_energy_eV": -1.0}
    assert ThermodynamicOrchestrator._references_for_target(static, "iface:1") == static

    indexed = {
        "mode": "by_target_uid",
        "by_target_uid": {
            "iface:1": {"surface_a_total_energy_eV": -1.0},
            "iface:2": {"surface_a_total_energy_eV": -2.0},
        },
    }
    assert ThermodynamicOrchestrator._references_for_target(
        indexed, "iface:2"
    ) == {"surface_a_total_energy_eV": -2.0}
    with pytest.raises(KeyError, match="No authoritative reference values"):
        ThermodynamicOrchestrator._references_for_target(indexed, "iface:missing")


def test_reference_workflow_builds_relaxed_surface_settings():
    run = _run("run:relaxed-references")
    formula = "work_of_adhesion_relaxed_surfaces"
    results = ReferenceEnergyResultCollection(
        [
            _reference(
                "followup:relaxed-a",
                run_uid=run.uid_full,
                target_uid="iface:1",
                kind="relaxed_surface_a",
                energy=-12.0,
                formula=formula,
            ),
            _reference(
                "followup:relaxed-b",
                run_uid=run.uid_full,
                target_uid="iface:1",
                kind="relaxed_surface_b",
                energy=-13.0,
                formula=formula,
            ),
        ]
    )
    workflow = ReferenceEnergyWorkflowResult(
        run=run,
        results=results,
        convention=EnergyConvention(formula=formula, n_interfaces=1),
    )
    values = workflow.references_for("iface:1")
    assert values.surface_a_total_energy_eV == -12.0
    assert values.surface_b_total_energy_eV == -13.0
    assert values.metadata["reference_protocol"].startswith("cleaved_fixed_cell")


class _Repo:
    def __init__(self, edges, followups):
        self.edges = list(edges)
        self.followups = {row["uid_full"]: row for row in followups}

    def list_edges(self, *, src=None, dst=None, kind=None, limit=None):
        rows = [
            row
            for row in self.edges
            if (src is None or row["src_uid_full"] == src)
            and (dst is None or row["dst_uid_full"] == dst)
            and (kind is None or row["kind"] == kind)
        ]
        return rows if limit is None else rows[:limit]

    def get_followup_result(self, identifier):
        return self.followups[str(identifier)]


class _Project:
    def __init__(self, interfaces, followups, runs):
        self._interfaces = list(interfaces)
        self._repo = _Repo(
            [
                {
                    "uid_full": f"edge:{row['uid_full']}",
                    "src_uid_full": row["target_uid_full"],
                    "dst_uid_full": row["uid_full"],
                    "kind": "interface_to_followup",
                    "payload": {},
                    "authority": "authoritative",
                }
                for row in followups
            ],
            followups,
        )
        self._runs = {run.uid_full: run for run in runs}

    def interfaces(self):
        return InterfaceCollection(interfaces=self._interfaces)

    def run(self, identifier):
        for run in self._runs.values():
            if str(identifier) in {run.uid_full, run.id_short}:
                return run
        raise KeyError(identifier)


def test_search_scoped_reference_queries_do_not_mix_runs_or_searches():
    first_run = _run("run:reference:old", created_at="2026-01-01T00:00:00Z")
    second_run = _run("run:reference:new", created_at="2026-02-01T00:00:00Z")
    other_run = _run("run:reference:other", created_at="2026-03-01T00:00:00Z")
    followups = [
        _reference(
            "followup:old:a",
            run_uid=first_run.uid_full,
            target_uid="iface:search-a",
            kind="strained_bulk_a",
            energy=-20.0,
            per_formula_unit=-10.0,
            interface_formula_units=4,
        ),
        _reference(
            "followup:new:a",
            run_uid=second_run.uid_full,
            target_uid="iface:search-a",
            kind="strained_bulk_a",
            energy=-18.0,
            per_formula_unit=-9.0,
            interface_formula_units=4,
        ),
        _reference(
            "followup:other:a",
            run_uid=other_run.uid_full,
            target_uid="iface:search-b",
            kind="strained_bulk_a",
            energy=-16.0,
            per_formula_unit=-8.0,
            interface_formula_units=4,
        ),
    ]
    project = _Project(
        interfaces=[
            {
                "uid_full": "iface:search-a",
                "id_short": "i_a",
                "stage": "relaxed",
                "search_name": "search-A",
                "authority": "authoritative",
            },
            {
                "uid_full": "iface:search-b",
                "id_short": "i_b",
                "stage": "relaxed",
                "search_name": "search-B",
                "authority": "authoritative",
            },
        ],
        followups=followups,
        runs=[first_run, second_run, other_run],
    )
    search = PersistedInterfaceSearch(project, "search-A")

    with pytest.raises(
        AmbiguousProjectQueryError,
        match="multiple 'reference_energy' runs",
    ):
        search.reference_energy_results(status="completed")
    latest = search.reference_energy_results(
        status="completed",
        latest_run=True,
    )
    assert [record.uid_full for record in latest] == ["followup:new:a"]
    assert {run.uid_full for run in search.reference_energy_runs()} == {
        first_run.uid_full,
        second_run.uid_full,
    }


def test_example_08_uses_first_class_reference_workflow():
    source = Path("examples/08_evaluate_interface_energetics.py").read_text(
        encoding="utf-8"
    )
    assert "project.evaluate_reference_energies(" in source
    assert "references = reference_workflow" in source
    assert "reference_workflow.write_table(" in source
    assert "CALM_EXAMPLE_08_REFERENCE_MODE" in source


def test_reference_workflow_public_and_lineage_contracts_are_documented():
    project_source = Path("calm/public/project.py").read_text(encoding="utf-8")
    thermo_source = Path(
        "calm/project/application/followups/thermodynamics.py"
    ).read_text(encoding="utf-8")
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "def reference_energy_result(" in project_source
    assert 'kind="reference_to_thermodynamic"' in thermo_source
    assert "automatic reference-energy generation is not implemented" not in readme
    assert "fixed-cell relaxed interfaces" in readme


def test_reference_pair_rejects_unrepresentable_area():
    from calm.public.records.followups import _positive_reference_area

    with pytest.raises(RuntimeError, match="positive interface area"):
        _positive_reference_area(10**10000)
