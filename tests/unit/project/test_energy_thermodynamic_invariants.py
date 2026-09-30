from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from calm.interface.energy.contract import derive_thermodynamic_quantity
from calm.project.application.followups.energy import _interface_area_A2_from_atoms
from calm.project.application.followups.reference_energy import (
    _gauge_rotated_supercell_basis,
)
from calm.project.application.followups.thermodynamics import (
    _prototype_normalization_area,
    _reference_calculator_compatibility,
)


_EXCESS_CONVENTION = {
    "formula": "interface_excess_strained_bulk",
    "quantity": "interface_excess_energy",
    "n_interfaces": 1,
}
_EXCESS_REFERENCES = {
    "bulk_a_eV_per_formula_unit": -1.0,
    "bulk_b_eV_per_formula_unit": -2.0,
    "n_formula_units_a": 1,
    "n_formula_units_b": 1,
}


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("interface_total_energy_eV", float("nan")),
        ("interface_total_energy_eV", float("inf")),
        ("area_A2", float("nan")),
        ("area_A2", float("inf")),
    ],
)
def test_thermodynamic_scalar_contract_rejects_nonfinite_state(field, value):
    kwargs = {
        "interface_total_energy_eV": -4.0,
        "area_A2": 10.0,
        "convention": dict(_EXCESS_CONVENTION),
        "references": dict(_EXCESS_REFERENCES),
    }
    kwargs[field] = value
    with pytest.raises(ValueError, match="finite"):
        derive_thermodynamic_quantity(**kwargs)


@pytest.mark.parametrize("count", [True, 1.5, 0, -1])
def test_thermodynamic_scalar_contract_requires_exact_positive_counts(count):
    convention = dict(_EXCESS_CONVENTION)
    convention["n_interfaces"] = count
    with pytest.raises(ValueError, match="positive integer"):
        derive_thermodynamic_quantity(
            interface_total_energy_eV=-4.0,
            area_A2=10.0,
            convention=convention,
            references=_EXCESS_REFERENCES,
        )


@pytest.mark.parametrize("field", ["n_formula_units_a", "n_formula_units_b"])
def test_thermodynamic_scalar_contract_rejects_fractional_formula_counts(field):
    references = dict(_EXCESS_REFERENCES)
    references[field] = 1.5
    with pytest.raises(ValueError, match="positive integer"):
        derive_thermodynamic_quantity(
            interface_total_energy_eV=-4.0,
            area_A2=10.0,
            convention=_EXCESS_CONVENTION,
            references=references,
        )


def test_thermodynamic_scalar_contract_rejects_overflowed_results():
    maximum = float.fromhex("0x1.fffffffffffffp+1023")
    with pytest.raises(ValueError, match="finite"):
        derive_thermodynamic_quantity(
            interface_total_energy_eV=0.0,
            area_A2=maximum,
            convention={**_EXCESS_CONVENTION, "n_interfaces": 2},
            references=_EXCESS_REFERENCES,
        )
    with pytest.raises(ValueError, match="finite"):
        derive_thermodynamic_quantity(
            interface_total_energy_eV=-1.0,
            area_A2=1.0,
            convention=_EXCESS_CONVENTION,
            references={
                **_EXCESS_REFERENCES,
                "bulk_a_eV_per_formula_unit": maximum,
                "n_formula_units_a": 2,
            },
        )


def test_thermodynamic_scalar_contract_rejects_unrepresentable_integer_products():
    huge_count = 10**10000
    with pytest.raises(ValueError, match="finite"):
        derive_thermodynamic_quantity(
            interface_total_energy_eV=-4.0,
            area_A2=10.0,
            convention={**_EXCESS_CONVENTION, "n_interfaces": huge_count},
            references=_EXCESS_REFERENCES,
        )
    with pytest.raises(ValueError, match="finite"):
        derive_thermodynamic_quantity(
            interface_total_energy_eV=-4.0,
            area_A2=10.0,
            convention=_EXCESS_CONVENTION,
            references={
                **_EXCESS_REFERENCES,
                "n_formula_units_a": huge_count,
            },
        )


def test_thermodynamic_formula_and_quantity_must_agree():
    convention = dict(_EXCESS_CONVENTION)
    convention["quantity"] = "work_of_adhesion"
    with pytest.raises(ValueError, match="does not match"):
        derive_thermodynamic_quantity(
            interface_total_energy_eV=-4.0,
            area_A2=10.0,
            convention=convention,
            references=_EXCESS_REFERENCES,
        )


def test_reference_basis_uses_the_full_orthogonal_supercell_gauge():
    atoms = SimpleNamespace(
        get_cell=lambda: np.array(
            [[2.0, 0.0, 0.0], [0.0, 3.0, 0.0], [0.0, 0.0, 5.0]]
        )
    )
    matrix = np.array([[2, 0], [0, 1]])
    reflection = np.array([[0.0, 1.0], [1.0, 0.0]])
    basis = _gauge_rotated_supercell_basis(atoms, matrix, reflection)
    expected = reflection @ np.diag([2.0, 3.0]) @ matrix
    assert np.allclose(basis, expected)


def test_calculated_reference_provenance_must_match_raw_energy():
    references = {
        "metadata": {
            "compatibility_source": "calculated_reference_workflow",
            "energy_backend": "real",
            "backend_identity": {"name": "real", "calculator": "emt"},
            "energy_settings": {"mode": "single_point"},
            "reference_area_A2": 10.0,
        }
    }
    raw = {
        "backend": {
            "name": "real",
            "identity": {"name": "real", "calculator": "emt"},
            "settings": {"mode": "single_point"},
        },
        "interface_area_A2": 10.0,
    }
    assert _reference_calculator_compatibility(raw, references)["status"] == "verified"

    incompatible = {**raw, "backend": dict(raw["backend"])}
    incompatible["backend"]["identity"] = {
        "name": "real",
        "calculator": "different",
    }
    with pytest.raises(ValueError, match="calculator identities"):
        _reference_calculator_compatibility(incompatible, references)

    wrong_area = dict(raw)
    wrong_area["interface_area_A2"] = 11.0
    with pytest.raises(ValueError, match="normalization areas"):
        _reference_calculator_compatibility(wrong_area, references)


def test_calculated_reference_provenance_requires_nonempty_identity_and_settings_mapping():
    references = {
        "metadata": {
            "compatibility_source": "calculated_reference_workflow",
            "energy_backend": "real",
            "backend_identity": {},
            "energy_settings": {"mode": "single_point"},
            "reference_area_A2": 10.0,
        }
    }
    raw = {
        "backend": {
            "name": "real",
            "identity": {},
            "settings": {"mode": "single_point"},
        },
        "interface_area_A2": 10.0,
    }
    with pytest.raises(ValueError, match="calculator provenance"):
        _reference_calculator_compatibility(raw, references)

    references["metadata"]["backend_identity"] = {
        "name": "real",
        "calculator": "emt",
    }
    raw["backend"]["identity"] = {"name": "real", "calculator": "emt"}
    raw["backend"]["settings"] = "single_point"
    with pytest.raises(ValueError, match="invalid calculation settings"):
        _reference_calculator_compatibility(raw, references)


def test_manual_reference_provenance_is_explicitly_unverified():
    status = _reference_calculator_compatibility(
        {"energy_backend": "real"},
        {"metadata": {"source": "user"}},
    )
    assert status == {
        "status": "manual_unverified",
        "reference_source": "user",
    }


def test_prototype_area_is_rejected_after_variable_cell_relaxation():
    prototype = SimpleNamespace(interface_area=12.0)
    raw = SimpleNamespace(
        target_kind="interface",
        target_uid_full="iface:1",
        payload={"interface_area_A2": 12.0},
    )
    interface = SimpleNamespace(
        params={"relaxation_settings": {"relax_cell": True}}
    )
    uow = SimpleNamespace(
        derived_interfaces=SimpleNamespace(get_by_uid_full=lambda _uid: interface)
    )
    with pytest.raises(ValueError, match="variable-cell"):
        _prototype_normalization_area(
            uow,
            raw=raw,
            prototype=prototype,
            area_source="prototype_interface_area",
        )


def test_fixed_cell_interface_verifies_prototype_area_normalization():
    prototype = SimpleNamespace(interface_area=12.0)
    raw = SimpleNamespace(
        target_kind="interface",
        target_uid_full="iface:1",
        payload={"interface_area_A2": 12.0},
    )
    interface = SimpleNamespace(
        params={"relaxation_settings": {"relax_cell": False}}
    )
    uow = SimpleNamespace(
        derived_interfaces=SimpleNamespace(get_by_uid_full=lambda _uid: interface)
    )
    area, status = _prototype_normalization_area(
        uow,
        raw=raw,
        prototype=prototype,
        area_source="prototype_interface_area",
    )
    assert area == 12.0
    assert status == "verified_prototype_matches_interface"


def test_authoritative_interface_area_uses_evaluated_target_cell():
    prototype = SimpleNamespace(interface_area=12.0)
    raw = SimpleNamespace(
        target_kind="interface",
        target_uid_full="iface:1",
        payload={"interface_area_A2": 13.5},
    )
    interface = SimpleNamespace(
        params={"relaxation_settings": {"relax_cell": True}}
    )
    uow = SimpleNamespace(
        derived_interfaces=SimpleNamespace(get_by_uid_full=lambda _uid: interface)
    )
    area, status = _prototype_normalization_area(
        uow,
        raw=raw,
        prototype=prototype,
    )
    assert area == 13.5
    assert status == "authoritative_interface_cell"


def test_prototype_area_source_rejects_a_different_interface_cell():
    prototype = SimpleNamespace(interface_area=12.0)
    raw = SimpleNamespace(
        target_kind="interface",
        target_uid_full="iface:1",
        payload={"interface_area_A2": 13.5},
    )
    interface = SimpleNamespace(
        params={"relaxation_settings": {"relax_cell": False}}
    )
    uow = SimpleNamespace(
        derived_interfaces=SimpleNamespace(get_by_uid_full=lambda _uid: interface)
    )
    with pytest.raises(ValueError, match="does not match"):
        _prototype_normalization_area(
            uow,
            raw=raw,
            prototype=prototype,
            area_source="prototype_interface_area",
        )


def test_raw_interface_area_uses_the_full_three_dimensional_cell_vectors():
    atoms = SimpleNamespace(
        get_cell=lambda: np.array(
            [[2.0, 0.0, 1.0], [0.0, 3.0, 1.0], [0.0, 0.0, 8.0]]
        )
    )
    expected = np.linalg.norm(np.cross(atoms.get_cell()[0], atoms.get_cell()[1]))
    assert _interface_area_A2_from_atoms(atoms) == pytest.approx(expected)


@pytest.mark.parametrize(
    "cell",
    [
        [[0.0, 0.0, 0.0], [0.0, 3.0, 0.0], [0.0, 0.0, 8.0]],
        [[float("nan"), 0.0, 0.0], [0.0, 3.0, 0.0], [0.0, 0.0, 8.0]],
    ],
)
def test_raw_interface_area_rejects_invalid_cells(cell):
    atoms = SimpleNamespace(get_cell=lambda: np.asarray(cell, dtype=float))
    with pytest.raises(ValueError, match="cell area|finite 3x3 cell"):
        _interface_area_A2_from_atoms(atoms)


def test_thermodynamic_contract_rejects_coercive_string_scalars() -> None:
    with pytest.raises(TypeError, match="finite real number"):
        derive_thermodynamic_quantity(
            interface_total_energy_eV="-4.0",  # type: ignore[arg-type]
            area_A2=2.0,
            convention=_EXCESS_CONVENTION,
            references=_EXCESS_REFERENCES,
        )
    with pytest.raises(TypeError, match="Energy formula must be a string"):
        derive_thermodynamic_quantity(
            interface_total_energy_eV=-4.0,
            area_A2=2.0,
            convention={**_EXCESS_CONVENTION, "formula": 1},
            references=_EXCESS_REFERENCES,
        )
    with pytest.raises(TypeError, match="quantity must be a string"):
        derive_thermodynamic_quantity(
            interface_total_energy_eV=-4.0,
            area_A2=2.0,
            convention={**_EXCESS_CONVENTION, "quantity": 1},
            references=_EXCESS_REFERENCES,
        )
