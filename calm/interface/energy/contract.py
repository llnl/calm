"""Dependency-light energy and thermodynamic contract."""

from __future__ import annotations

from math import isfinite
from numbers import Integral, Real
from typing import Any, Mapping

EV_PER_A2_TO_J_PER_M2: float = 16.02176634

INTERFACE_EXCESS_STRAINED_BULK_FORMULA = "interface_excess_strained_bulk"
INTERFACE_EXCESS_ENERGY_QUANTITY = "interface_excess_energy"
INTERFACE_EXCESS_REFERENCE_CONVENTION = "strained_unrelaxed_bulk_subtraction"

FORMULA_TO_QUANTITY = {
    INTERFACE_EXCESS_STRAINED_BULK_FORMULA: INTERFACE_EXCESS_ENERGY_QUANTITY,
    "work_of_separation_unrelaxed_surfaces": "work_of_separation",
    "work_of_adhesion_relaxed_surfaces": "work_of_adhesion",
}


class UnsupportedReferenceWorkflowError(ValueError):
    """Raised when a valid convention has no supported calculated-reference path."""


def _finite_float(value: Any, *, name: str) -> float:
    """Return one finite scalar or raise a stable contract error."""

    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{name} must be a finite real number.")
    number = float(value)
    if not isfinite(number):
        raise ValueError(f"{name} must be finite.")
    return number


def _positive_integer(value: Any, *, name: str) -> int:
    """Return one exact positive integer without bool or float coercion."""

    if isinstance(value, bool) or not isinstance(value, Integral):
        raise ValueError(f"{name} must be a positive integer.")
    integer = int(value)
    if integer < 1:
        raise ValueError(f"{name} must be a positive integer.")
    return integer


_REFERENCE_CAPABILITY_CONTRACTS = {
    "interface_excess_strained_bulk": {
        "calculated_reference_mode": "first_class",
        "reference_kinds": ("strained_bulk_a", "strained_bulk_b"),
        "manual_reference_fields": (
            "bulk_a_eV_per_formula_unit",
            "bulk_b_eV_per_formula_unit",
            "n_formula_units_a",
            "n_formula_units_b",
        ),
        "requirements": (
            "authoritative interface with exact deformation accounting",
            "explicit strain partition",
            "integer bulk formula-unit count on each interface side",
        ),
        "limitations": (
            "non-stoichiometric reservoir conventions are not supported",
        ),
    },
    "work_of_separation_unrelaxed_surfaces": {
        "calculated_reference_mode": "first_class",
        "reference_kinds": ("isolated_surface_a", "isolated_surface_b"),
        "manual_reference_fields": (
            "surface_a_total_energy_eV",
            "surface_b_total_energy_eV",
        ),
        "requirements": (
            "authoritative fixed-cell relaxed interface",
            "explicit strain partition",
            "source slabs with authoritative atomistic structures",
        ),
        "limitations": (
            "references are unrelaxed isolated surfaces",
            "variable-cell relaxed interfaces require references rebuilt "
            "from the final cell",
        ),
    },
    "work_of_adhesion_relaxed_surfaces": {
        "calculated_reference_mode": "first_class",
        "reference_kinds": ("relaxed_surface_a", "relaxed_surface_b"),
        "manual_reference_fields": (
            "surface_a_total_energy_eV",
            "surface_b_total_energy_eV",
        ),
        "requirements": (
            "authoritative fixed-cell calculator-relaxed interface",
            "persisted atomistic interface structure",
            "independent fixed-cell relaxation of both cleaved slab blocks",
            "one calculator identity shared by interface and references",
        ),
        "limitations": (
            "surface relaxations are local optimizations, not global minima",
            "variable-cell interface relaxation is not supported",
            "surface reconstruction that changes composition or cell is not supported",
        ),
    },
}


def positive_interface_multiplicity(value: Any) -> int:
    """Return an exact positive periodic-interface multiplicity."""

    return _positive_integer(value, name="n_interfaces")


def canonical_energy_formula(value: object) -> tuple[str, str]:
    if not isinstance(value, str):
        raise TypeError("Energy formula must be a string.")
    formula = value
    try:
        return formula, FORMULA_TO_QUANTITY[formula]
    except KeyError as exc:
        raise ValueError(
            f"Energy formula must be one of {sorted(FORMULA_TO_QUANTITY)}."
        ) from exc


def reference_energy_capability_contract(value: str) -> dict[str, Any]:
    """Return the import-light stable reference-support contract for one formula."""
    formula, quantity = canonical_energy_formula(value)
    contract = _REFERENCE_CAPABILITY_CONTRACTS[formula]
    return {
        "formula": formula,
        "quantity": quantity,
        "calculated_reference_mode": str(contract["calculated_reference_mode"]),
        "reference_kinds": tuple(contract["reference_kinds"]),
        "manual_reference_fields": tuple(contract["manual_reference_fields"]),
        "requirements": tuple(contract["requirements"]),
        "limitations": tuple(contract["limitations"]),
    }


def require_calculated_reference_support(value: str) -> dict[str, Any]:
    """Return the capability contract or raise the typed unsupported-workflow error."""
    contract = reference_energy_capability_contract(value)
    if contract["calculated_reference_mode"] != "first_class":
        formula = contract["formula"]
        raise UnsupportedReferenceWorkflowError(
            f"{formula} has no calculated-reference workflow in the current contract. "
            "Supply explicit ReferenceEnergySettings with relaxed isolated-surface "
            "total energies instead."
        )
    return contract


def derive_thermodynamic_quantity(
    *,
    interface_total_energy_eV: float,
    area_A2: float,
    convention: Mapping[str, Any],
    references: Mapping[str, Any],
) -> tuple[str, float, dict[str, float]]:
    """Evaluate one explicit formula and return eV/angstrom^2."""
    formula, quantity = canonical_energy_formula(convention["formula"])
    declared_quantity = convention.get("quantity")
    if declared_quantity is not None:
        if not isinstance(declared_quantity, str):
            raise TypeError("Energy convention quantity must be a string.")
        if declared_quantity != quantity:
            raise ValueError(
                f"Energy convention quantity {declared_quantity!r} does not match "
                f"formula {formula!r}, which defines {quantity!r}."
            )
    area_source = convention.get(
        "area_source",
        "authoritative_interface_area",
    )
    if not isinstance(area_source, str):
        raise TypeError("area_source must be a string.")
    if area_source not in {
        "authoritative_interface_area",
        "prototype_interface_area",
    }:
        raise ValueError(
            "area_source must be 'authoritative_interface_area' or "
            "'prototype_interface_area'."
        )
    n_interfaces = positive_interface_multiplicity(convention["n_interfaces"])
    area = _finite_float(area_A2, name="The interface normalization area")
    if area <= 0:
        raise ValueError(
            "The interface normalization area must be positive and finite."
        )
    try:
        denominator_value = n_interfaces * area
    except OverflowError as exc:
        raise ValueError(
            "The interface normalization denominator must be finite."
        ) from exc
    denominator = _finite_float(
        denominator_value,
        name="The interface normalization denominator",
    )
    e_interface = _finite_float(
        interface_total_energy_eV,
        name="The interface total energy",
    )

    if formula == "interface_excess_strained_bulk":
        mu_a = _finite_float(
            references["bulk_a_eV_per_formula_unit"],
            name="Bulk A reference energy",
        )
        mu_b = _finite_float(
            references["bulk_b_eV_per_formula_unit"],
            name="Bulk B reference energy",
        )
        n_a = _positive_integer(
            references["n_formula_units_a"],
            name="n_formula_units_a",
        )
        n_b = _positive_integer(
            references["n_formula_units_b"],
            name="n_formula_units_b",
        )
        try:
            bulk_a_total = n_a * mu_a
            bulk_b_total = n_b * mu_b
        except OverflowError as exc:
            raise ValueError("The bulk reference total must be finite.") from exc
        bulk_a_total = _finite_float(
            bulk_a_total,
            name="The bulk A reference total",
        )
        bulk_b_total = _finite_float(
            bulk_b_total,
            name="The bulk B reference total",
        )
        reference_total = _finite_float(
            bulk_a_total + bulk_b_total,
            name="The bulk reference total",
        )
        numerator = _finite_float(
            e_interface - reference_total,
            name="The interface excess numerator",
        )
        value = _finite_float(
            numerator / denominator,
            name="The derived interfacial quantity",
        )
        return (
            quantity,
            value,
            {
                "interface_total_energy_eV": e_interface,
                "bulk_a_reference_total_eV": bulk_a_total,
                "bulk_b_reference_total_eV": bulk_b_total,
                "reference_total_eV": reference_total,
                "excess_energy_eV": numerator,
            },
        )

    surface_a = _finite_float(
        references["surface_a_total_energy_eV"],
        name="Surface A reference energy",
    )
    surface_b = _finite_float(
        references["surface_b_total_energy_eV"],
        name="Surface B reference energy",
    )
    surface_total = _finite_float(
        surface_a + surface_b,
        name="The surface reference total",
    )
    numerator = _finite_float(
        surface_total - e_interface,
        name="The surface-separation numerator",
    )
    value = _finite_float(
        numerator / denominator,
        name="The derived interfacial quantity",
    )
    numerator_key = (
        "adhesion_energy_eV"
        if formula == "work_of_adhesion_relaxed_surfaces"
        else "separation_energy_eV"
    )
    return (
        quantity,
        value,
        {
            "interface_total_energy_eV": e_interface,
            "surface_a_total_energy_eV": surface_a,
            "surface_b_total_energy_eV": surface_b,
            numerator_key: numerator,
        },
    )
