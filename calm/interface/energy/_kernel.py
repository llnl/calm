"""Interfacial energy evaluation kernel.

This module contains *calculator-free* preparation logic and *pure* scalar reductions
used by :func:`calm.interface.pipeline.compute_interfacial_energy`.

Rationale
---------
The public pipeline runner needs to:
- derive slab/bulk formula-unit counts and reference structures, and
- evaluate energies with a (potentially heavy) ASE calculator.

By factoring the geometry preparation and scalar formula into a dedicated kernel,
we improve testability and reduce coupling between the pipeline runner and ASE
calculator behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from numbers import Integral
from typing import Any

import numpy as np

from calm.interface.energy.contract import (
    EV_PER_A2_TO_J_PER_M2 as _EV_PER_A2_TO_J_PER_M2,
    INTERFACE_EXCESS_ENERGY_QUANTITY,
    INTERFACE_EXCESS_REFERENCE_CONVENTION,
    INTERFACE_EXCESS_STRAINED_BULK_FORMULA,
    positive_interface_multiplicity,
)

from calm.interface.building._kernel import _embed_2x2_in_3x3
from calm.interface.config import EnergyConfig


@dataclass(frozen=True)
class InterfacialEnergyGeometry:
    """Prepared geometry + bookkeeping for interfacial energy evaluation.

    Notes
    -----
    ``bulk_A_strained`` and ``bulk_B_strained`` are ASE Atoms-like objects returned by
    :func:`calm.interface.energy.reference.get_strained_bulk`. They are intentionally
    left untyped here to keep optional/ASE typing minimal.

    Convention note
    ---------------
    By default the strained-bulk reference convention used by the pipeline is
    ``strained_bulk_reference_mode = "unrelaxed_scaled_positions"`` (i.e., the
    strained cell is set and atomic positions are scaled; no ionic relaxation
    is performed). This choice is recorded in the geometry and propagated into
    the EnergyResult for provenance.
    """

    area_A2: float
    denom_A2: float

    n_fu_slab_A: int
    n_fu_slab_B: int
    n_fu_bulk_A: int
    n_fu_bulk_B: int

    formula_A: str
    formula_B: str

    bulk_A_strained: Any
    bulk_B_strained: Any
    n_interfaces: int = 2
    thermodynamic_formula: str = INTERFACE_EXCESS_STRAINED_BULK_FORMULA
    thermodynamic_quantity: str = INTERFACE_EXCESS_ENERGY_QUANTITY
    # Provenance: deformation gradients and strained-cell matrices (cartesian, 3x3)
    F_A_slab: Any = None
    F_B_slab: Any = None
    F_A_construction_slab: Any = None
    F_B_construction_slab: Any = None
    F_A_total_slab: Any = None
    F_B_total_slab: Any = None
    F_A_conv: Any = None
    F_B_conv: Any = None
    F_A_construction_conv: Any = None
    F_B_construction_conv: Any = None
    F_A_total_conv: Any = None
    F_B_total_conv: Any = None
    slab_deformation_accounting_policy: str | None = None
    slab_deformation_accounting_version: int | None = None
    strained_bulk_cell_A_3x3: Any = None
    strained_bulk_cell_B_3x3: Any = None
    # Reference mode (explicitly document current default)
    strained_bulk_reference_mode: str = "unrelaxed_scaled_positions"
    bulk_reference_relaxed: bool = False
    bulk_reference_calculation_id_A: Any = None
    bulk_reference_calculation_id_B: Any = None
    gamma_reference_convention: str = INTERFACE_EXCESS_REFERENCE_CONVENTION


@dataclass(frozen=True)
class InterfacialEnergyValues:
    """Scalar interfacial energy results derived from energies."""

    mu_bulk_A_eV_per_fu: float
    mu_bulk_B_eV_per_fu: float
    gamma_eV_per_A2: float
    gamma_J_per_m2: float


def prepare_interfacial_energy_geometry(  # noqa: C901
    interface: Any,
    config: EnergyConfig,
) -> InterfacialEnergyGeometry:
    """Prepare strained bulk references and stoichiometric bookkeeping.

    Parameters
    ----------
    interface
        Built interface object (must have ``atoms``) with ``prototype`` and
        ``strain_state`` attributes.
    config
        Energy evaluation configuration.

    Returns
    -------
    InterfacialEnergyGeometry
        Calculator-free prepared structures and counts needed by the energy runner.
    """

    if interface.atoms is None:
        raise ValueError(
            "Interface has no atoms (build_interface must be called first)."
        )

    proto = interface.prototype
    strain = interface.strain_state

    slab_A = proto.slab_a
    slab_B = proto.slab_b

    from calm.slab.oriented.cell_contract import require_interface_stackable_slab

    require_interface_stackable_slab(
        slab_A.atoms,
        name="Lower interfacial-energy source slab",
    )
    require_interface_stackable_slab(
        slab_B.atoms,
        name="Upper interfacial-energy source slab",
    )

    if config.require_stoichiometric:
        if not getattr(slab_A, "is_stoichiometric", True) or not getattr(
            slab_B, "is_stoichiometric", True
        ):
            raise ValueError(
                "Non-stoichiometric slabs are not allowed under require_stoichiometric=True. "
                "Set EnergyConfig.require_stoichiometric=False to override."
            )

    area = float(interface.area())
    if not np.isfinite(area) or area <= 0:
        raise ValueError(f"Invalid interface area: {area}")

    n_interfaces = positive_interface_multiplicity(getattr(config, "n_interfaces", 2))
    denom = float(n_interfaces) * area
    if not np.isfinite(denom) or denom <= 0:
        raise ValueError(f"Invalid interfacial-energy denominator: {denom}")

    # Lazy imports to keep module import overhead low.
    from ase.formula import Formula

    from calm.structure.ase_adapter import make_supercell_col
    from calm.interface.energy.reference import _strained_bulk_deformation

    # Build slab supercells in the interface surface cell basis.
    N_A3 = _embed_2x2_in_3x3(proto.supercell_a.N_tot, dtype="int")
    N_B3 = _embed_2x2_in_3x3(proto.supercell_b.N_tot, dtype="int")
    R_A3 = _embed_2x2_in_3x3(proto.supercell_a.R_sup, dtype="float")
    R_B3 = _embed_2x2_in_3x3(proto.supercell_b.R_sup, dtype="float")

    slab_A_super = make_supercell_col(slab_A.atoms, N_A3)
    slab_B_super = make_supercell_col(slab_B.atoms, N_B3)

    # Count slab formula units in the surface supercell.
    f = Formula(slab_A_super.get_chemical_formula(mode="hill"))
    f_red_slab_A, n_fu_slab_A = f.reduce()

    f = Formula(slab_B_super.get_chemical_formula(mode="hill"))
    f_red_slab_B, n_fu_slab_B = f.reduce()

    # Bulk reference formula units are taken from the conventional cell.
    f = Formula(slab_A.bulk.conv.get_chemical_formula(mode="hill"))
    f_red_bulk_A, n_fu_bulk_A = f.reduce()

    f = Formula(slab_B.bulk.conv.get_chemical_formula(mode="hill"))
    f_red_bulk_B, n_fu_bulk_B = f.reduce()

    if config.require_stoichiometric:
        if (f_red_slab_A != f_red_bulk_A) or (f_red_slab_B != f_red_bulk_B):
            raise ValueError(
                "Stoichiometry mismatch between slab supercell and bulk conventional cell. "
                "Set EnergyConfig.require_stoichiometric=False to override."
            )

    # Compose physical slab-construction deformation with the later interface
    # matching deformation.  The source slab already carries the construction
    # deformation geometrically, so interface assembly applies only F_A/F_B.
    # Bulk references, however, begin from pristine conventional cells and
    # therefore require the total composed deformation.
    F_A_slab = np.asarray(strain.F_A, dtype=float)
    F_B_slab = np.asarray(strain.F_B, dtype=float)
    deformation_A = _strained_bulk_deformation(
        slab_A,
        slab_A_super,
        F_A_slab,
        gauge_rotation=R_A3,
        config=config,
    )
    deformation_B = _strained_bulk_deformation(
        slab_B,
        slab_B_super,
        F_B_slab,
        gauge_rotation=R_B3,
        config=config,
    )

    bulk_A_strained = slab_A.bulk.conv.copy()
    bulk_A_strained.set_cell(
        (deformation_A.F_total_conv @ slab_A.bulk.conv_cell).T,
        scale_atoms=True,
    )
    bulk_B_strained = slab_B.bulk.conv.copy()
    bulk_B_strained.set_cell(
        (deformation_B.F_total_conv @ slab_B.bulk.conv_cell).T,
        scale_atoms=True,
    )

    F_A_construction_slab = deformation_A.F_construction_slab
    F_B_construction_slab = deformation_B.F_construction_slab
    F_A_total_slab = deformation_A.F_total_slab
    F_B_total_slab = deformation_B.F_total_slab
    F_A_conv = deformation_A.F_interface_conv
    F_B_conv = deformation_B.F_interface_conv
    F_A_construction_conv = deformation_A.F_construction_conv
    F_B_construction_conv = deformation_B.F_construction_conv
    F_A_total_conv = deformation_A.F_total_conv
    F_B_total_conv = deformation_B.F_total_conv

    strained_bulk_cell_A_3x3 = np.asarray(bulk_A_strained.cell.array).T
    strained_bulk_cell_B_3x3 = np.asarray(bulk_B_strained.cell.array).T

    strained_bulk_reference_mode = getattr(
        config, "strained_bulk_reference_mode", "unrelaxed_scaled_positions"
    )
    bulk_reference_relaxed = bool(getattr(config, "bulk_reference_relaxed", False))
    bulk_reference_calculation_id_A = None
    bulk_reference_calculation_id_B = None
    from calm.slab.oriented.cell_contract import (
        SLAB_DEFORMATION_ACCOUNTING_POLICY,
        SLAB_DEFORMATION_ACCOUNTING_VERSION,
    )

    gamma_reference_convention = INTERFACE_EXCESS_REFERENCE_CONVENTION

    return InterfacialEnergyGeometry(
        area_A2=float(area),
        denom_A2=float(denom),
        n_interfaces=n_interfaces,
        thermodynamic_formula=INTERFACE_EXCESS_STRAINED_BULK_FORMULA,
        thermodynamic_quantity=INTERFACE_EXCESS_ENERGY_QUANTITY,
        n_fu_slab_A=int(n_fu_slab_A),
        n_fu_slab_B=int(n_fu_slab_B),
        n_fu_bulk_A=int(n_fu_bulk_A),
        n_fu_bulk_B=int(n_fu_bulk_B),
        formula_A=str(f_red_bulk_A),
        formula_B=str(f_red_bulk_B),
        bulk_A_strained=bulk_A_strained,
        bulk_B_strained=bulk_B_strained,
        F_A_slab=F_A_slab,
        F_B_slab=F_B_slab,
        F_A_construction_slab=F_A_construction_slab,
        F_B_construction_slab=F_B_construction_slab,
        F_A_total_slab=F_A_total_slab,
        F_B_total_slab=F_B_total_slab,
        F_A_conv=F_A_conv,
        F_B_conv=F_B_conv,
        F_A_construction_conv=F_A_construction_conv,
        F_B_construction_conv=F_B_construction_conv,
        F_A_total_conv=F_A_total_conv,
        F_B_total_conv=F_B_total_conv,
        slab_deformation_accounting_policy=SLAB_DEFORMATION_ACCOUNTING_POLICY,
        slab_deformation_accounting_version=SLAB_DEFORMATION_ACCOUNTING_VERSION,
        strained_bulk_cell_A_3x3=strained_bulk_cell_A_3x3,
        strained_bulk_cell_B_3x3=strained_bulk_cell_B_3x3,
        strained_bulk_reference_mode=strained_bulk_reference_mode,
        bulk_reference_relaxed=bulk_reference_relaxed,
        bulk_reference_calculation_id_A=bulk_reference_calculation_id_A,
        bulk_reference_calculation_id_B=bulk_reference_calculation_id_B,
        gamma_reference_convention=gamma_reference_convention,
    )


def compute_interfacial_energy_from_energies(  # noqa: C901
    *,
    E_int_eV: float,
    E_bulk_A_eV: float,
    E_bulk_B_eV: float,
    geom: InterfacialEnergyGeometry,
) -> InterfacialEnergyValues:
    """Compute ``(mu_bulk_A, mu_bulk_B, gamma)`` from energies and prepared geometry."""

    counts: dict[str, int] = {}
    for name in (
        "n_fu_slab_A",
        "n_fu_slab_B",
        "n_fu_bulk_A",
        "n_fu_bulk_B",
    ):
        value = getattr(geom, name)
        if isinstance(value, bool) or not isinstance(value, Integral):
            raise ValueError(f"{name} must be a positive integer; got {value!r}.")
        count = int(value)
        if count < 1:
            raise ValueError(
                "Invalid bulk formula-unit counts or slab formula-unit counts: "
                f"{name}={value!r}."
            )
        counts[name] = count

    area = float(geom.area_A2)
    denominator = float(geom.denom_A2)
    if not isfinite(area) or area <= 0.0:
        raise ValueError(f"Invalid interface area (Å^2): area_A2={geom.area_A2!r}")
    if not isfinite(denominator) or denominator <= 0.0:
        raise ValueError(f"Invalid denominator (Å^2): denom_A2={geom.denom_A2!r}")

    energies: dict[str, float] = {}
    for name, value in (
        ("E_int_eV", E_int_eV),
        ("E_bulk_A_eV", E_bulk_A_eV),
        ("E_bulk_B_eV", E_bulk_B_eV),
    ):
        number = float(value)
        if not isfinite(number):
            raise ValueError(f"{name} must be finite; got {value!r}.")
        energies[name] = number

    mu_bulk_A = energies["E_bulk_A_eV"] / counts["n_fu_bulk_A"]
    mu_bulk_B = energies["E_bulk_B_eV"] / counts["n_fu_bulk_B"]

    gamma_eV_per_A2 = (
        energies["E_int_eV"]
        - counts["n_fu_slab_A"] * mu_bulk_A
        - counts["n_fu_slab_B"] * mu_bulk_B
    ) / denominator
    if not isfinite(gamma_eV_per_A2):
        raise ValueError("The derived interfacial energy density is nonfinite.")

    gamma_J_per_m2 = float(gamma_eV_per_A2) * _EV_PER_A2_TO_J_PER_M2

    return InterfacialEnergyValues(
        mu_bulk_A_eV_per_fu=float(mu_bulk_A),
        mu_bulk_B_eV_per_fu=float(mu_bulk_B),
        gamma_eV_per_A2=float(gamma_eV_per_A2),
        gamma_J_per_m2=float(gamma_J_per_m2),
    )
