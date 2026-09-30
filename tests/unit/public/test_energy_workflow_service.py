from __future__ import annotations

from typing import Any

import pytest

from energy_result_fixtures import (
    raw_energy_payload,
    reference_energy_payload,
    thermodynamic_payload,
)

from calm.public.workflows.energy import ProjectEnergyWorkflowService
from calm.public.inputs.settings import (
    EnergyConvention,
    EnergySettings,
    ReferenceEnergySettings,
)


def _interface(
    uid: str,
    *,
    stage: str = "relaxed",
    search_name: str = "search-a",
) -> dict[str, Any]:
    return {
        "uid_full": uid,
        "id_short": uid.replace("iface:", "i_"),
        "label": uid,
        "prototype_uid_full": "proto:1",
        "stage": stage,
        "search_name": search_name,
        "authority": "authoritative",
    }


def _run(uid: str, run_type: str) -> dict[str, Any]:
    return {
        "uid_full": uid,
        "id_short": uid.replace("run:", "r_"),
        "run_type": run_type,
        "status": "done",
        "spec": {},
        "authority": "authoritative",
    }


def _energy_result() -> dict[str, Any]:
    return {
        "uid_full": "followup:energy",
        "id_short": "f_energy",
        "run_uid_full": "run:energy",
        "run_id_short": "r_energy",
        "prototype_uid_full": "proto:1",
        "target_uid_full": "iface:1",
        "target_kind": "interface",
        "kind": "energy_stage",
        "status": "done",
        "best_energy": -5.0,
        "payload": raw_energy_payload(-5.0),
        "authority": "authoritative",
    }


def _thermodynamic_result() -> dict[str, Any]:
    return {
        "uid_full": "followup:thermo",
        "id_short": "f_thermo",
        "run_uid_full": "run:thermo",
        "run_id_short": "r_thermo",
        "prototype_uid_full": "proto:1",
        "target_uid_full": "iface:1",
        "target_kind": "interface",
        "kind": "thermodynamic_quantity",
        "status": "done",
        "payload": thermodynamic_payload(
            raw_energy_followup_uid="followup:energy",
            value_eV_per_A2=0.1,
            n_interfaces=1,
        ),
        "authority": "authoritative",
    }


def _reference_result(uid: str, kind: str, side: str) -> dict[str, Any]:
    return {
        "uid_full": uid,
        "id_short": uid.replace("followup:", "f_"),
        "run_uid_full": "run:reference",
        "run_id_short": "r_reference",
        "prototype_uid_full": "proto:1",
        "target_uid_full": "iface:1",
        "target_kind": "interface",
        "kind": "reference_energy",
        "status": "done",
        "best_energy": -2.0,
        "payload": reference_energy_payload(
            reference_uid_full=f"reference:{side}",
            reference_kind=kind,
            formula_id="interface_excess_strained_bulk",
            energy_eV=-2.0,
            energy_eV_per_formula_unit=-1.0,
            reference_formula_units=2,
            interface_formula_units=2,
        ),
        "authority": "authoritative",
    }


class _Repository:
    def __init__(self) -> None:
        self.interfaces = {
            "iface:1": _interface("iface:1"),
            "iface:2": _interface("iface:2", stage="registry_refined"),
        }
        self.runs = {
            "run:energy": _run("run:energy", "energy_stage"),
            "run:thermo": _run("run:thermo", "thermodynamic_derivation"),
            "run:reference": _run("run:reference", "reference_energy"),
        }
        self.followups = {
            "energy_stage": [_energy_result()],
            "thermodynamic_quantity": [_thermodynamic_result()],
            "reference_energy": [
                _reference_result(
                    "followup:bulk-a",
                    "strained_bulk_a",
                    "a",
                ),
                _reference_result(
                    "followup:bulk-b",
                    "strained_bulk_b",
                    "b",
                ),
            ],
        }
        self.list_interface_calls: list[str | None] = []

    def list_interfaces(self, *, search_name=None, limit=None):
        del limit
        self.list_interface_calls.append(search_name)
        return [
            row
            for row in self.interfaces.values()
            if search_name is None or row["search_name"] == search_name
        ]

    def get_interface(self, identifier: str):
        return self.interfaces[str(identifier)]

    def get_run(self, identifier: str):
        return self.runs[str(identifier)]

    def list_followup_results(
        self,
        *,
        run=None,
        prototype=None,
        kind=None,
        status=None,
        limit=None,
    ):
        del prototype, status, limit
        return [
            row
            for row in self.followups.get(str(kind), [])
            if run is None or row["run_uid_full"] == run
        ]


class _Workspace:
    def __init__(self) -> None:
        self.energy_calls: list[dict[str, Any]] = []
        self.reference_calls: list[dict[str, Any]] = []
        self.thermodynamic_calls: list[dict[str, Any]] = []

    def run_energy_stage(self, prototypes, **kwargs):
        self.energy_calls.append({"prototypes": list(prototypes), **kwargs})
        return [
            {
                "run_uid": "run:energy",
                "status": "done",
                "target_uid": prototypes[0],
            }
        ]

    def run_reference_energy_stage(self, interfaces, **kwargs):
        self.reference_calls.append({"interfaces": list(interfaces), **kwargs})
        return [
            {
                "run_uid": "run:reference",
                "status": "done",
                "source_interface_uid": interfaces[0],
            }
        ]

    def run_thermodynamic_stage(self, raw_energy_results, **kwargs):
        self.thermodynamic_calls.append(
            {"raw_energy_results": list(raw_energy_results), **kwargs}
        )
        return [
            {
                "run_uid": "run:thermo",
                "status": "done",
                "target_uid": "iface:1",
            }
        ]


def _service() -> tuple[ProjectEnergyWorkflowService, _Workspace, _Repository]:
    workspace = _Workspace()
    repository = _Repository()
    return (
        ProjectEnergyWorkflowService(
            workspace=workspace,
            repository=repository,
        ),
        workspace,
        repository,
    )


def test_raw_and_thermodynamic_workflow_is_composed_by_service() -> None:
    service, workspace, _repository = _service()
    convention = EnergyConvention(
        formula="interface_excess_strained_bulk",
        n_interfaces=1,
    )
    references = ReferenceEnergySettings(
        bulk_a_eV_per_formula_unit=-1.0,
        bulk_b_eV_per_formula_unit=-1.0,
        n_formula_units_a=1,
        n_formula_units_b=1,
    )

    workflow = service.evaluate_energies(
        ["iface:1", "iface:1"],
        settings=EnergySettings(),
        backend="deterministic",
        convention=convention,
        references=references,
        search_name="display-only",
    )

    assert workflow.energy_run.uid_full == "run:energy"
    assert workflow.thermodynamic_run.uid_full == "run:thermo"
    assert [row.uid_full for row in workflow.energy_results] == [
        "followup:energy"
    ]
    assert [row.uid_full for row in workflow.thermodynamic_results] == [
        "followup:thermo"
    ]
    assert workspace.energy_calls[0]["prototypes"] == ["iface:1"]
    assert workspace.energy_calls[0]["payload"]["public_api"] == (
        "Project.evaluate_energies"
    )
    assert workspace.energy_calls[0]["payload"]["search_name"] == (
        "display-only"
    )
    assert workspace.thermodynamic_calls[0]["raw_energy_results"] == [
        "followup:energy"
    ]


def test_default_target_selection_uses_relaxed_authoritative_interfaces() -> None:
    service, workspace, repository = _service()

    workflow = service.evaluate_energies(
        None,
        backend="deterministic",
        search_name="search-a",
    )

    assert workflow.energy_run.uid_full == "run:energy"
    assert repository.list_interface_calls == ["search-a"]
    assert workspace.energy_calls[0]["prototypes"] == ["iface:1"]


def test_reference_workflow_is_composed_by_service() -> None:
    service, workspace, _repository = _service()
    convention = EnergyConvention(
        formula="interface_excess_strained_bulk",
        n_interfaces=1,
    )

    workflow = service.evaluate_reference_energies(
        "iface:1",
        convention=convention,
        backend="deterministic",
    )

    assert workflow.run.uid_full == "run:reference"
    assert len(workflow.results) == 2
    assert workspace.reference_calls[0]["interfaces"] == ["iface:1"]
    assert workspace.reference_calls[0]["formula"] == convention.formula
    assert workspace.reference_calls[0]["payload"]["public_api"] == (
        "Project.evaluate_reference_energies"
    )


def test_energy_workflow_rejects_non_relaxed_targets_before_execution() -> None:
    service, workspace, _repository = _service()

    with pytest.raises(ValueError, match="requires relaxed interfaces"):
        service.evaluate_energies(
            "iface:2",
            backend="deterministic",
        )

    assert workspace.energy_calls == []


def test_energy_workflow_rejects_ambiguous_thermodynamic_inputs() -> None:
    service, workspace, _repository = _service()
    convention = EnergyConvention(
        formula="interface_excess_strained_bulk",
        n_interfaces=1,
    )

    with pytest.raises(ValueError, match="both be provided or both be omitted"):
        service.evaluate_energies(
            "iface:1",
            backend="deterministic",
            convention=convention,
        )

    assert workspace.energy_calls == []


def test_custom_backend_requires_explicit_identity() -> None:
    class BackendWithoutIdentity:
        def compute(self, **kwargs):
            return kwargs

    service = ProjectEnergyWorkflowService(
        workspace=object(),
        repository=object(),
    )
    with pytest.raises(TypeError, match="must implement identity"):
        service.evaluate_energies(
            [],
            settings=EnergySettings(),
            backend=BackendWithoutIdentity(),
        )


def test_project_energy_methods_forward_the_complete_public_contract() -> None:
    from calm.public.project import Project

    class _Delegate:
        def __init__(self) -> None:
            self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

        def evaluate_reference_energies(self, *args: Any, **kwargs: Any):
            self.calls.append(("reference", args, kwargs))
            return "reference-result"

        def evaluate_energies(self, *args: Any, **kwargs: Any):
            self.calls.append(("energy", args, kwargs))
            return "energy-result"

    delegate = _Delegate()
    project = object.__new__(Project)
    project._energy_workflows = delegate
    reporter = object()
    settings = object()
    convention = object()
    references = object()
    relaxation = object()
    backend = object()

    assert project.evaluate_reference_energies(
        ["iface:1"],
        convention=convention,
        settings=settings,
        surface_relaxation=relaxation,
        backend=backend,
        resume=False,
        partial_resume=False,
        on_error="record",
        search_name="search-a",
        reporter=reporter,
    ) == "reference-result"
    assert project.evaluate_energies(
        ["iface:1"],
        settings=settings,
        backend=backend,
        convention=convention,
        references=references,
        resume=False,
        partial_resume=False,
        on_error="record",
        search_name="search-a",
        reporter=reporter,
    ) == "energy-result"

    reference_call, energy_call = delegate.calls
    assert reference_call == (
        "reference",
        (["iface:1"],),
        {
            "convention": convention,
            "settings": settings,
            "surface_relaxation": relaxation,
            "backend": backend,
            "resume": False,
            "partial_resume": False,
            "on_error": "record",
            "search_name": "search-a",
            "reporter": reporter,
        },
    )
    assert energy_call == (
        "energy",
        (["iface:1"],),
        {
            "settings": settings,
            "backend": backend,
            "convention": convention,
            "references": references,
            "resume": False,
            "partial_resume": False,
            "on_error": "record",
            "search_name": "search-a",
            "reporter": reporter,
        },
    )
