from __future__ import annotations

import json
import math

import pytest

from calm.interface.energy.reference import compute_interface_energy_from_scalars
from calm.interface.results import InterfaceEnergyScalarResult, EV_PER_A2_TO_J_PER_M2


def test_compute_interface_energy_from_scalars_double_interface_case() -> None:
    result = compute_interface_energy_from_scalars(
        interface_energy_eV=100.0,
        n_formula_units_A=4,
        n_formula_units_B=6,
        mu_A_eV_per_formula_unit=5.0,
        mu_B_eV_per_formula_unit=10.0,
        interface_area_A2=5.0,
        n_interfaces=2,
    )

    assert isinstance(result, InterfaceEnergyScalarResult)
    assert EV_PER_A2_TO_J_PER_M2 == 16.02176634
    assert math.isclose(result.numerator_eV, 20.0)
    assert math.isclose(result.denominator_A2, 10.0)
    assert math.isclose(result.gamma_eV_per_A2, 2.0)
    assert math.isclose(result.gamma_J_per_m2, 2.0 * EV_PER_A2_TO_J_PER_M2)


def test_compute_interface_energy_from_scalars_single_interface_case() -> None:
    result = compute_interface_energy_from_scalars(
        interface_energy_eV=100.0,
        n_formula_units_A=4,
        n_formula_units_B=6,
        mu_A_eV_per_formula_unit=5.0,
        mu_B_eV_per_formula_unit=10.0,
        interface_area_A2=5.0,
        n_interfaces=1,
    )
    assert math.isclose(result.denominator_A2, 5.0)
    assert math.isclose(result.gamma_eV_per_A2, 4.0)


def test_compute_interface_energy_from_scalars_to_dict_roundtrip() -> None:
    result = compute_interface_energy_from_scalars(
        interface_energy_eV=-19.58,
        n_formula_units_A=2,
        n_formula_units_B=2,
        mu_A_eV_per_formula_unit=-4.88,
        mu_B_eV_per_formula_unit=-4.79,
        interface_area_A2=18.0,
        n_interfaces=2,
    )
    payload = result.to_dict()
    restored = json.loads(json.dumps(payload))
    assert restored["strained_bulk_reference_mode"] == "unrelaxed_scaled_positions"
    assert restored["bulk_reference_relaxed"] is False
    assert restored["gamma_reference_convention"] == "strained_unrelaxed_bulk_subtraction"


@pytest.mark.parametrize(
    "kwargs, expected_message",
    [
        ({"interface_area_A2": 0.0}, "interface_area_A2 must be > 0"),
        ({"interface_area_A2": -1.0}, "interface_area_A2 must be > 0"),
        ({"n_interfaces": 0}, "n_interfaces must be > 0"),
        ({"n_interfaces": 1.5}, "n_interfaces must be > 0"),
        ({"n_interfaces": True}, "n_interfaces must be > 0"),
        ({"n_formula_units_A": -1}, "n_formula_units_A must be >= 0"),
        ({"n_formula_units_A": 1.5}, "non-negative integer"),
        ({"n_formula_units_B": -1}, "n_formula_units_B must be >= 0"),
        ({"interface_energy_eV": float("nan")}, "must be finite"),
        ({"mu_A_eV_per_formula_unit": float("inf")}, "must be finite"),
    ],
)
def test_compute_interface_energy_from_scalars_invalid_inputs(kwargs, expected_message: str) -> None:
    base = dict(
        interface_energy_eV=10.0,
        n_formula_units_A=1,
        n_formula_units_B=1,
        mu_A_eV_per_formula_unit=1.0,
        mu_B_eV_per_formula_unit=1.0,
        interface_area_A2=5.0,
        n_interfaces=2,
    )
    base.update(kwargs)

    with pytest.raises(ValueError, match=expected_message):
        compute_interface_energy_from_scalars(**base)


def test_public_import_path_available() -> None:
    # The public top-level alias was removed; ensure the internal implementation
    # is directly importable from calm.interface.energy.reference
    imported = compute_interface_energy_from_scalars
    assert imported is compute_interface_energy_from_scalars


def test_compute_interface_energy_from_scalars_rejects_overflowed_result() -> None:
    maximum = float.fromhex("0x1.fffffffffffffp+1023")
    with pytest.raises(ValueError, match="finite"):
        compute_interface_energy_from_scalars(
            interface_energy_eV=maximum,
            n_formula_units_A=1,
            n_formula_units_B=1,
            mu_A_eV_per_formula_unit=-maximum,
            mu_B_eV_per_formula_unit=-maximum,
            interface_area_A2=1.0,
            n_interfaces=1,
        )
