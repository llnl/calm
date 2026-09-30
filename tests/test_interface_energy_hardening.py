import math
import pytest

from calm.interface.energy.contract import EV_PER_A2_TO_J_PER_M2
from calm.interface.energy._kernel import compute_interfacial_energy_from_energies


class DummyGeom:
    """Minimal InterfacialEnergyGeometry-like object for scalar kernel tests."""

    def __init__(self, area, denom, n_fu_slab_A, n_fu_slab_B, n_fu_bulk_A, n_fu_bulk_B):
        self.area_A2 = area
        self.denom_A2 = denom
        self.n_fu_slab_A = n_fu_slab_A
        self.n_fu_slab_B = n_fu_slab_B
        self.n_fu_bulk_A = n_fu_bulk_A
        self.n_fu_bulk_B = n_fu_bulk_B


def test_scalar_gamma_two_interface_normalization_and_conversion():
    # numbers chosen from the spec
    interface_total_energy_eV = 100.0
    bulk_A_reference_total_energy_eV = 10.0
    bulk_B_reference_total_energy_eV = 30.0
    n_fu_slab_A = 4
    n_fu_slab_B = 6
    n_fu_bulk_A = 2
    n_fu_bulk_B = 3
    area = 5.0
    denom = 2.0 * area

    geom = DummyGeom(area, denom, n_fu_slab_A, n_fu_slab_B, n_fu_bulk_A, n_fu_bulk_B)

    vals = compute_interfacial_energy_from_energies(
        E_int_eV=interface_total_energy_eV, E_bulk_A_eV=bulk_A_reference_total_energy_eV, E_bulk_B_eV=bulk_B_reference_total_energy_eV, geom=geom
    )

    mu_A = bulk_A_reference_total_energy_eV / n_fu_bulk_A
    mu_B = bulk_B_reference_total_energy_eV / n_fu_bulk_B
    expected_gamma = (interface_total_energy_eV - n_fu_slab_A * mu_A - n_fu_slab_B * mu_B) / denom

    assert math.isclose(vals.mu_bulk_A_eV_per_fu, mu_A)
    assert math.isclose(vals.mu_bulk_B_eV_per_fu, mu_B)
    assert math.isclose(vals.gamma_eV_per_A2, expected_gamma)
    assert math.isclose(vals.gamma_J_per_m2, expected_gamma * EV_PER_A2_TO_J_PER_M2)


def test_scalar_gamma_single_sided_behavior():
    # same numbers but denom = area
    interface_total_energy_eV = 100.0
    bulk_A_reference_total_energy_eV = 10.0
    bulk_B_reference_total_energy_eV = 30.0
    n_fu_slab_A = 4
    n_fu_slab_B = 6
    n_fu_bulk_A = 2
    n_fu_bulk_B = 3
    area = 5.0
    denom = area

    geom = DummyGeom(area, denom, n_fu_slab_A, n_fu_slab_B, n_fu_bulk_A, n_fu_bulk_B)

    vals = compute_interfacial_energy_from_energies(
        E_int_eV=interface_total_energy_eV, E_bulk_A_eV=bulk_A_reference_total_energy_eV, E_bulk_B_eV=bulk_B_reference_total_energy_eV, geom=geom
    )

    mu_A = bulk_A_reference_total_energy_eV / n_fu_bulk_A
    mu_B = bulk_B_reference_total_energy_eV / n_fu_bulk_B
    expected_gamma = (interface_total_energy_eV - n_fu_slab_A * mu_A - n_fu_slab_B * mu_B) / denom

    assert math.isclose(vals.gamma_eV_per_A2, expected_gamma)


def test_scalar_energy_provenance_chain_keeps_excess_energy_separate_from_density():
    """The scalar kernel keeps total, reference, excess, and density quantities distinct."""

    interface_total_energy_eV = 100.0
    bulk_A_reference_total_energy_eV = 10.0
    bulk_B_reference_total_energy_eV = 30.0
    n_fu_slab_A = 4
    n_fu_slab_B = 6
    n_fu_bulk_A = 2
    n_fu_bulk_B = 3
    area_A2 = 5.0
    denom_A2 = 2.0 * area_A2

    geom = DummyGeom(
        area_A2,
        denom_A2,
        n_fu_slab_A,
        n_fu_slab_B,
        n_fu_bulk_A,
        n_fu_bulk_B,
    )

    vals = compute_interfacial_energy_from_energies(
        E_int_eV=interface_total_energy_eV,
        E_bulk_A_eV=bulk_A_reference_total_energy_eV,
        E_bulk_B_eV=bulk_B_reference_total_energy_eV,
        geom=geom,
    )

    bulk_A_reference_energy_per_formula_unit = bulk_A_reference_total_energy_eV / n_fu_bulk_A
    bulk_B_reference_energy_per_formula_unit = bulk_B_reference_total_energy_eV / n_fu_bulk_B
    interface_excess_energy_eV = (
        interface_total_energy_eV
        - n_fu_slab_A * bulk_A_reference_energy_per_formula_unit
        - n_fu_slab_B * bulk_B_reference_energy_per_formula_unit
    )
    interfacial_energy_density_eV_per_A2 = interface_excess_energy_eV / denom_A2

    assert math.isclose(vals.mu_bulk_A_eV_per_fu, bulk_A_reference_energy_per_formula_unit)
    assert math.isclose(vals.mu_bulk_B_eV_per_fu, bulk_B_reference_energy_per_formula_unit)
    assert math.isclose(interface_excess_energy_eV, 20.0)
    assert math.isclose(vals.gamma_eV_per_A2, interfacial_energy_density_eV_per_A2)
    assert not math.isclose(interface_excess_energy_eV, vals.gamma_eV_per_A2)


def test_scalar_energy_provenance_chain_rejects_invalid_reference_denominators():
    """Reference total energies cannot be reduced without positive bulk formula-unit counts."""

    geom = DummyGeom(
        area=5.0,
        denom=10.0,
        n_fu_slab_A=4,
        n_fu_slab_B=6,
        n_fu_bulk_A=0,
        n_fu_bulk_B=3,
    )

    with pytest.raises(ValueError, match="Invalid bulk formula-unit counts"):
        compute_interfacial_energy_from_energies(
            E_int_eV=100.0,
            E_bulk_A_eV=10.0,
            E_bulk_B_eV=30.0,
            geom=geom,
        )

@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("E_int_eV", float("nan")),
        ("E_bulk_A_eV", float("inf")),
        ("E_bulk_B_eV", float("-inf")),
    ],
)
def test_scalar_kernel_rejects_nonfinite_energies(field, value):
    geom = DummyGeom(5.0, 10.0, 4, 6, 2, 3)
    kwargs = {
        "E_int_eV": 100.0,
        "E_bulk_A_eV": 10.0,
        "E_bulk_B_eV": 30.0,
        "geom": geom,
    }
    kwargs[field] = value
    with pytest.raises(ValueError, match="must be finite"):
        compute_interfacial_energy_from_energies(**kwargs)


@pytest.mark.parametrize("count", [True, 1.5, 0])
def test_scalar_kernel_requires_exact_positive_formula_counts(count):
    geom = DummyGeom(5.0, 10.0, count, 6, 2, 3)
    with pytest.raises(ValueError, match="positive integer|Invalid bulk formula-unit"):
        compute_interfacial_energy_from_energies(
            E_int_eV=100.0,
            E_bulk_A_eV=10.0,
            E_bulk_B_eV=30.0,
            geom=geom,
        )


def test_scalar_kernel_rejects_overflowed_derived_energy():
    maximum = float.fromhex("0x1.fffffffffffffp+1023")
    geom = DummyGeom(5.0, 10.0, 4, 6, 1, 1)
    with pytest.raises(ValueError, match="nonfinite"):
        compute_interfacial_energy_from_energies(
            E_int_eV=maximum,
            E_bulk_A_eV=-maximum,
            E_bulk_B_eV=-maximum,
            geom=geom,
        )
