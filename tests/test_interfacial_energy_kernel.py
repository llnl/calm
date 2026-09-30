from __future__ import annotations

import math

from ase import Atoms

from calm.interface.energy._kernel import (
    InterfacialEnergyGeometry,
    compute_interfacial_energy_from_energies,
)


def test_compute_interfacial_energy_from_energies_smoke() -> None:
    # The scalar kernel should be testable without any calculator.
    geom = InterfacialEnergyGeometry(
        area_A2=10.0,
        denom_A2=20.0,  # double-sided => 2 * area
        n_fu_slab_A=3,
        n_fu_slab_B=5,
        n_fu_bulk_A=1,
        n_fu_bulk_B=2,
        formula_A="H",
        formula_B="He",
        bulk_A_strained=Atoms("H"),
        bulk_B_strained=Atoms("He"),
    )

    vals = compute_interfacial_energy_from_energies(
        E_int_eV=100.0,
        E_bulk_A_eV=10.0,   # mu_A = 10 / 1 = 10
        E_bulk_B_eV=20.0,   # mu_B = 20 / 2 = 10
        geom=geom,
    )

    assert vals.mu_bulk_A_eV_per_fu == 10.0
    assert vals.mu_bulk_B_eV_per_fu == 10.0
    assert vals.gamma_eV_per_A2 == 1.0
    from calm.interface.results import EV_PER_A2_TO_J_PER_M2 as CANON_EV_PER_A2_TO_J_PER_M2
    assert math.isclose(vals.gamma_J_per_m2, CANON_EV_PER_A2_TO_J_PER_M2, rel_tol=0.0, abs_tol=1e-12)
