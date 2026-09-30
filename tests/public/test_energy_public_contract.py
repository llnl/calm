from __future__ import annotations

import inspect
from dataclasses import fields

import calm
import pytest
from calm.interface.energy.contract import derive_thermodynamic_quantity
from calm.project.application.interface_prototype_payload import (
    infer_interface_area_A2,
    serialize_interface_prototype,
)
from calm.public.collections.interfaces import InterfaceCollection
from calm.public.records.search import PersistedInterfaceSearch
from calm.public.records.persistence import (
    ProjectEnergyResult,
    ProjectThermodynamicResult,
    RecordAuthority,
)
from calm.public.project import Project
from energy_result_fixtures import raw_energy_payload, thermodynamic_payload

from calm.public.inputs.settings import (
    EnergyConvention,
    EnergySettings,
    ReferenceEnergySettings,
)


def test_energy_settings_are_explicit_and_top_level() -> None:
    assert calm.EnergySettings is EnergySettings
    assert calm.EnergyConvention is EnergyConvention
    assert calm.ReferenceEnergySettings is ReferenceEnergySettings
    assert {field.name for field in fields(EnergySettings)} == {"mode"}
    assert {field.name for field in fields(EnergyConvention)} == {
        "formula",
        "n_interfaces",
        "area_source",
    }
    assert EnergyConvention(
        formula="interface_excess_strained_bulk",
        n_interfaces=1,
    ).area_source == "authoritative_interface_area"
    assert EnergySettings().to_stage_kwargs() == {
        "calculation": {"mode": "single_point"},
    }


def test_energy_settings_and_conventions_reject_ambiguous_or_unsupported_values() -> None:
    try:
        EnergySettings(mode="relax").validate()
    except ValueError:
        pass
    else:  # pragma: no cover
        raise AssertionError("unsupported energy mode was accepted")

    for convention in (
        EnergyConvention(formula="generic_interface_energy", n_interfaces=1),
        EnergyConvention(formula="interface_excess_strained_bulk", n_interfaces=0),
        EnergyConvention(
            formula="interface_excess_strained_bulk",
            n_interfaces=1,
            area_source="guessed",
        ),
    ):
        try:
            convention.validate()
        except ValueError:
            pass
        else:  # pragma: no cover
            raise AssertionError(f"invalid convention was accepted: {convention!r}")


def test_reference_settings_are_formula_specific() -> None:
    excess = EnergyConvention(
        formula="interface_excess_strained_bulk",
        n_interfaces=2,
    )
    refs = ReferenceEnergySettings(
        bulk_a_eV_per_formula_unit=-1.0,
        bulk_b_eV_per_formula_unit=-2.0,
        n_formula_units_a=2,
        n_formula_units_b=1,
    )
    refs.validate_for(excess)

    try:
        ReferenceEnergySettings(
            surface_a_total_energy_eV=-1.0,
            surface_b_total_energy_eV=-2.0,
        ).validate_for(excess)
    except ValueError:
        pass
    else:  # pragma: no cover
        raise AssertionError("surface references were accepted for bulk subtraction")


def test_explicit_thermodynamic_formulas() -> None:
    quantity, value, components = derive_thermodynamic_quantity(
        interface_total_energy_eV=-7.0,
        area_A2=10.0,
        convention={
            "formula": "interface_excess_strained_bulk",
            "n_interfaces": 2,
        },
        references={
            "bulk_a_eV_per_formula_unit": -2.0,
            "bulk_b_eV_per_formula_unit": -1.0,
            "n_formula_units_a": 2,
            "n_formula_units_b": 1,
        },
    )
    assert quantity == "interface_excess_energy"
    assert value == -0.1
    assert components["reference_total_eV"] == -5.0

    quantity, value, _ = derive_thermodynamic_quantity(
        interface_total_energy_eV=-12.0,
        area_A2=5.0,
        convention={
            "formula": "work_of_separation_unrelaxed_surfaces",
            "n_interfaces": 1,
        },
        references={
            "surface_a_total_energy_eV": -5.0,
            "surface_b_total_energy_eV": -4.0,
        },
    )
    assert quantity == "work_of_separation"
    assert value == 0.6



def test_energy_numeric_inputs_must_be_finite_and_integral() -> None:
    invalid_conventions = [
        EnergyConvention(
            formula="interface_excess_strained_bulk",
            n_interfaces=1.5,  # type: ignore[arg-type]
        ),
        EnergyConvention(
            formula="interface_excess_strained_bulk",
            n_interfaces=True,  # type: ignore[arg-type]
        ),
    ]
    for convention in invalid_conventions:
        try:
            convention.validate()
        except ValueError:
            pass
        else:  # pragma: no cover
            raise AssertionError("non-integral interface count was accepted")

    excess = EnergyConvention(
        formula="interface_excess_strained_bulk",
        n_interfaces=1,
    )
    for references in (
        ReferenceEnergySettings(
            bulk_a_eV_per_formula_unit=float("nan"),
            bulk_b_eV_per_formula_unit=-2.0,
            n_formula_units_a=1,
            n_formula_units_b=1,
        ),
        ReferenceEnergySettings(
            bulk_a_eV_per_formula_unit=-1.0,
            bulk_b_eV_per_formula_unit=-2.0,
            n_formula_units_a=1.5,  # type: ignore[arg-type]
            n_formula_units_b=1,
        ),
    ):
        try:
            references.validate_for(excess)
        except ValueError:
            pass
        else:  # pragma: no cover
            raise AssertionError("invalid reference normalization was accepted")

def test_typed_energy_and_thermodynamic_records_preserve_provenance() -> None:
    raw = ProjectEnergyResult.from_item(
        {
            "uid_full": "followup:energy",
            "id_short": "f_energy",
            "run_uid_full": "run:energy",
            "run_id_short": "r_energy",
            "prototype_uid_full": "proto:x",
            "target_uid_full": "iface:relaxed",
            "target_kind": "interface",
            "kind": "energy_stage",
            "status": "done",
            "best_energy": -12.0,
            "payload": raw_energy_payload(
                -12.0,
                backend_name="real",
                backend_identity={
                    "name": "real",
                    "calculator_specs": {"proto:x": {"family": "emt"}},
                },
                interface_area_A2=10.0,
                artifact_refs=["artifact:energy"],
            ),
            "authority": "authoritative",
        }
    )
    assert raw.authority is RecordAuthority.AUTHORITATIVE
    assert raw.succeeded
    assert raw.energy_eV == -12.0
    assert raw.backend == "real"
    assert raw.backend_identity["name"] == "real"
    assert raw.artifact_refs == ("artifact:energy",)

    derived = ProjectThermodynamicResult.from_item(
        {
            "uid_full": "followup:thermo",
            "id_short": "f_thermo",
            "run_uid_full": "run:thermo",
            "run_id_short": "r_thermo",
            "prototype_uid_full": "proto:x",
            "target_uid_full": "iface:relaxed",
            "target_kind": "interface",
            "kind": "thermodynamic_quantity",
            "status": "done",
            "payload": thermodynamic_payload(
                raw_energy_followup_uid="followup:energy",
                value_eV_per_A2=0.2,
                area_A2=10.0,
                n_interfaces=2,
            ),
            "authority": "authoritative",
        }
    )
    assert derived.succeeded
    assert derived.raw_energy_followup_uid == raw.uid_full
    assert derived.formula_id == "interface_excess_strained_bulk"
    assert derived.value_eV_per_A2 == 0.2
    assert (
        derived.normalization_area_source_status
        == "authoritative_interface_cell"
    )
    assert derived.calculator_compatibility["status"] == "verified"
    assert derived.to_dict()["calculator_compatibility"]["status"] == "verified"
    assert derived.units["secondary"] == "J/m^2"


def test_legacy_interface_energy_projection_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="requires an energy_stage follow-up result",
    ):
        ProjectEnergyResult.from_item(
            {
                "interface_id": "legacy",
                "E_int_eV": 1.25,
                "status": "completed",
                "authority": "projection",
            }
        )


def test_interface_collection_does_not_execute_energy_workflows() -> None:
    assert not hasattr(InterfaceCollection, "_evaluate_energies")


def test_persisted_search_does_not_execute_energy_workflows() -> None:
    assert not hasattr(PersistedInterfaceSearch, "evaluate_energies")
    assert not hasattr(PersistedInterfaceSearch, "evaluate_reference_energies")

def test_project_energy_surface_is_explicit() -> None:
    for name in {
        "evaluate_energies",
        "energy_runs",
        "energy_results",
        "energy_result",
        "thermodynamic_runs",
        "thermodynamic_results",
        "thermodynamic_result",
    }:
        assert hasattr(Project, name)
    parameters = inspect.signature(Project.evaluate_energies).parameters
    assert parameters["backend"].default == "real"
    assert parameters["resume"].default is True
    assert parameters["partial_resume"].default is True
    assert parameters["on_error"].default == "raise"


def test_interface_area_is_preserved_or_inferred_for_thermodynamics() -> None:
    explicit = {"interface_area": 10.0}
    assert infer_interface_area_A2(explicit) == 10.0
    with pytest.raises(TypeError, match="requires an InterfacePrototype"):
        serialize_interface_prototype(explicit)

    supercells = {
        "supercell_a": {"S_red": [[4.0, 0.0], [0.0, 3.0]]},
        "supercell_b": {"S_red": [[5.0, 0.0], [0.0, 2.0]]},
    }
    assert infer_interface_area_A2(supercells) == 11.0

    stored = {
        "interface_area": None,
        "payload": {"metrics": {"interface_area_A2": 7.5}},
    }
    assert infer_interface_area_A2(stored) == 7.5


def test_invalid_interface_area_is_not_treated_as_normalization() -> None:
    assert infer_interface_area_A2({"interface_area": None}) is None
    assert infer_interface_area_A2({"interface_area": 0.0}) is None
    assert infer_interface_area_A2({"interface_area": float("nan")}) is None
