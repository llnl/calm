from __future__ import annotations

import pytest

from calm.interface.energy.contract import (
    INTERFACE_EXCESS_ENERGY_QUANTITY,
    INTERFACE_EXCESS_STRAINED_BULK_FORMULA,
)
from calm.interface.config import EnergyConfig
from calm.interface.energy.reference import compute_interface_energy_from_scalars


@pytest.mark.parametrize("n_interfaces", [1, 2, 3, 7])
def test_scalar_interface_excess_uses_explicit_multiplicity(
    n_interfaces: int,
) -> None:
    result = compute_interface_energy_from_scalars(
        interface_energy_eV=-20.0,
        n_formula_units_A=1,
        n_formula_units_B=1,
        mu_A_eV_per_formula_unit=-8.0,
        mu_B_eV_per_formula_unit=-10.0,
        interface_area_A2=5.0,
        n_interfaces=n_interfaces,
    )

    assert result.numerator_eV == pytest.approx(-2.0)
    assert result.denominator_A2 == pytest.approx(5.0 * n_interfaces)
    assert result.gamma_eV_per_A2 == pytest.approx(-2.0 / (5.0 * n_interfaces))
    assert result.thermodynamic_formula == INTERFACE_EXCESS_STRAINED_BULK_FORMULA
    assert result.thermodynamic_quantity == INTERFACE_EXCESS_ENERGY_QUANTITY


def test_energy_config_uses_positive_integer_interface_multiplicity() -> None:
    assert EnergyConfig().n_interfaces == 2
    assert EnergyConfig(n_interfaces=3).n_interfaces == 3
    for value in (0, -1, True, 1.5, float("inf")):
        with pytest.raises(ValueError, match="n_interfaces must be a positive integer"):
            EnergyConfig(n_interfaces=value)  # type: ignore[arg-type]


def test_scalar_helper_requires_interface_multiplicity() -> None:
    import inspect

    parameter = inspect.signature(compute_interface_energy_from_scalars).parameters[
        "n_interfaces"
    ]
    assert parameter.default is inspect.Parameter.empty


def test_energy_kernel_preserves_explicit_multiplicity() -> None:
    from calm.interface.energy._kernel import (
        InterfacialEnergyGeometry,
        compute_interfacial_energy_from_energies,
    )

    geometry = InterfacialEnergyGeometry(
        area_A2=5.0,
        denom_A2=15.0,
        n_fu_slab_A=1,
        n_fu_slab_B=1,
        n_fu_bulk_A=1,
        n_fu_bulk_B=1,
        formula_A="A",
        formula_B="B",
        bulk_A_strained=object(),
        bulk_B_strained=object(),
        n_interfaces=3,
    )
    values = compute_interfacial_energy_from_energies(
        E_int_eV=-20.0,
        E_bulk_A_eV=-8.0,
        E_bulk_B_eV=-10.0,
        geom=geometry,
    )
    assert values.gamma_eV_per_A2 == pytest.approx(-2.0 / 15.0)



def test_obsolete_geometry_level_energy_alias_is_absent() -> None:
    import calm.interface.energy.reference as module

    assert not hasattr(module, "compute_interfacial_energy")


def test_energy_configuration_identity_uses_interface_multiplicity() -> None:
    from calm.keys.uid import energy_config_uid

    default_uid = energy_config_uid(EnergyConfig())
    single_uid = energy_config_uid(EnergyConfig(n_interfaces=1))
    double_uid = energy_config_uid(EnergyConfig(n_interfaces=2))
    triple_uid = energy_config_uid(EnergyConfig(n_interfaces=3))

    assert default_uid == double_uid
    assert len({single_uid, double_uid, triple_uid}) == 3
