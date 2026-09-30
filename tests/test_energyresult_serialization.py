import json
import numpy as np
from calm.interface.results import EnergyResult


def make_dummy_result():
    # Minimal EnergyResult with provenance fields populated
    # EnergyResult is frozen (immutable dataclass); construct with fields set in init
    from calm.interface.results import EV_PER_A2_TO_J_PER_M2

    r = EnergyResult(
        interface_uid="i",
        calc_uid="c",
        econf_uid="e",
        energy_uid="u",
        gamma_eV_per_A2=1.23,
        gamma_J_per_m2=1.23 * EV_PER_A2_TO_J_PER_M2,
        area_A2=5.0,
        E_int_eV=100.0,
        n_fu_slab_A=4,
        n_fu_slab_B=6,
        mu_bulk_A_eV_per_fu=5.0,
        mu_bulk_B_eV_per_fu=10.0,
        formula_A="A",
        formula_B="B",
    )

    F = np.eye(3).tolist()
    # pass provenance through constructor kwargs
    r = EnergyResult(
        interface_uid="i",
        calc_uid="c",
        econf_uid="e",
        energy_uid="u",
        gamma_eV_per_A2=1.23,
        gamma_J_per_m2=1.23 * EV_PER_A2_TO_J_PER_M2,
        area_A2=5.0,
        E_int_eV=100.0,
        n_fu_slab_A=4,
        n_fu_slab_B=6,
        mu_bulk_A_eV_per_fu=5.0,
        mu_bulk_B_eV_per_fu=10.0,
        formula_A="A",
        formula_B="B",
        F_A_slab=F,
        F_B_slab=F,
        F_A_construction_slab=F,
        F_B_construction_slab=F,
        F_A_total_slab=F,
        F_B_total_slab=F,
        F_A_conv=F,
        F_B_conv=F,
        F_A_construction_conv=F,
        F_B_construction_conv=F,
        F_A_total_conv=F,
        F_B_total_conv=F,
        slab_deformation_accounting_policy="composed_slab_deformation",
        slab_deformation_accounting_version=1,
        strained_bulk_cell_A_3x3=np.eye(3).tolist(),
        strained_bulk_cell_B_3x3=np.eye(3).tolist(),
        strained_bulk_reference_mode="unrelaxed_scaled_positions",
        bulk_reference_relaxed=False,
        bulk_reference_calculation_id_A=None,
        bulk_reference_calculation_id_B=None,
        gamma_reference_convention="strained_unrelaxed_bulk_subtraction",
    )

    return r


def test_energyresult_to_dict_contains_provenance_and_roundtrip():
    r = make_dummy_result()
    d = r.to_dict()
    # Check keys
    keys = [
        "F_A_slab",
        "F_B_slab",
        "F_A_construction_slab",
        "F_B_construction_slab",
        "F_A_total_slab",
        "F_B_total_slab",
        "F_A_conv",
        "F_B_conv",
        "F_A_construction_conv",
        "F_B_construction_conv",
        "F_A_total_conv",
        "F_B_total_conv",
        "slab_deformation_accounting_policy",
        "slab_deformation_accounting_version",
        "strained_bulk_cell_A_3x3",
        "strained_bulk_cell_B_3x3",
        "strained_bulk_reference_mode",
        "bulk_reference_relaxed",
        "bulk_reference_calculation_id_A",
        "bulk_reference_calculation_id_B",
        "gamma_reference_convention",
    ]
    for k in keys:
        assert k in d

    # Defaults
    assert d["strained_bulk_reference_mode"] == "unrelaxed_scaled_positions"
    assert d["bulk_reference_relaxed"] is False
    assert d["gamma_reference_convention"] == "strained_unrelaxed_bulk_subtraction"

    # JSON round-trip
    s = json.dumps(d)
    d2 = json.loads(s)
    for k in keys:
        assert k in d2


def test_signature_includes_physical_provenance_not_ids():
    r = make_dummy_result()
    sig = r.signature()
    # signature includes matrices and mode, but not calculation ids (IDs are None)
    assert "F_A_slab" in sig
    assert "F_A_total_slab" in sig
    assert "F_A_total_conv" in sig
    assert sig["slab_deformation_accounting_policy"] == "composed_slab_deformation"
    assert sig["slab_deformation_accounting_version"] == 1
    assert "strained_bulk_reference_mode" in sig
    # calculation IDs are not part of signature
    assert "bulk_reference_calculation_id_A" not in sig


def test_energyresult_rejects_retired_constructor_aliases():
    import pytest

    with pytest.raises(TypeError, match="unexpected keyword argument 'build_uid'"):
        EnergyResult(build_uid="interface-1")

    with pytest.raises(
        TypeError,
        match="unexpected keyword argument 'gamma_eVA2'",
    ):
        EnergyResult(gamma_eVA2=2.0)
