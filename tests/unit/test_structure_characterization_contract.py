from __future__ import annotations

import math

import numpy as np

from calm.public.records.characterization import (
    MaterialCharacterization,
    SurfaceCharacterization,
)
from calm.structure.characterization import (
    MASS_DENSITY_CONVERSION_G_CM3_PER_AMU_A3,
    MATERIAL_CHARACTERIZATION_CONTRACT,
    SURFACE_CHARACTERIZATION_CONTRACT,
    bulk_composition_relation,
    characterization_contract_status,
    material_characterization_data,
    normalize_composition_counts,
    reduce_composition,
    round_characterization_value,
    surface_characterization_data,
    surface_geometry_projection,
)


class _Cell:
    def __init__(self, matrix):
        self.array = np.asarray(matrix, dtype=float)

    def cellpar(self):
        a, b, c = np.linalg.norm(self.array, axis=1)
        return np.asarray([a, b, c, 90.0, 90.0, 90.0])


class _Atoms:
    _masses = {"Li": 6.94, "F": 18.998403163, "O": 15.999}

    def __init__(self, symbols, positions, cell):
        self._symbols = list(symbols)
        self._positions = np.asarray(positions, dtype=float)
        self.cell = _Cell(cell)

    def get_cell(self):
        return self.cell

    def get_positions(self):
        return self._positions.copy()

    def get_chemical_symbols(self):
        return list(self._symbols)

    def get_masses(self):
        return np.asarray([self._masses[symbol] for symbol in self._symbols])

    def get_chemical_formula(self, mode="metal", empirical=False):
        del mode
        counts = {symbol: self._symbols.count(symbol) for symbol in dict.fromkeys(self._symbols)}
        if empirical:
            from math import gcd

            divisor = 0
            for count in counts.values():
                divisor = gcd(divisor, count)
            counts = {symbol: count // divisor for symbol, count in counts.items()}
        return "".join(
            symbol + (str(count) if count != 1 else "")
            for symbol, count in counts.items()
        )


def _lif_bulk() -> _Atoms:
    return _Atoms(
        ["Li", "F", "Li", "F"],
        [[0.0, 0.0, 0.0]] * 4,
        np.diag([4.0, 4.0, 4.0]),
    )


def test_rounding_contract_is_half_even_and_normalizes_negative_zero() -> None:
    assert round_characterization_value(1.25, 1) == 1.2
    assert round_characterization_value(1.35, 1) == 1.4
    rounded_zero = round_characterization_value(-1.0e-12, 8)
    assert rounded_zero == 0.0
    assert math.copysign(1.0, rounded_zero) == 1.0


def test_composition_projection_accepts_only_exact_positive_integer_counts() -> None:
    normalized = normalize_composition_counts(
        {
            " Li ": 2.0,
            "F": "2",
            "O": 1.5,
            "bool": True,
            "zero": 0,
            "negative": -3,
        }
    )
    assert normalized == {"F": 2, "Li": 2}
    assert reduce_composition(normalized) == ({"F": 1, "Li": 1}, 2)


def test_material_volume_formula_units_and_density_are_reconstructible() -> None:
    data = material_characterization_data(_lif_bulk())
    expected_mass = 2.0 * (6.94 + 18.998403163)
    expected_density = (
        expected_mass * MASS_DENSITY_CONVERSION_G_CM3_PER_AMU_A3 / 64.0
    )

    assert data["contract"] == MATERIAL_CHARACTERIZATION_CONTRACT
    assert data["contract_status"] == "complete_v1"
    assert data["composition"] == {"F": 2, "Li": 2}
    assert data["reduced_composition"] == {"F": 1, "Li": 1}
    assert data["n_formula_units"] == 2
    assert data["cell_volume_A3"] == 64.0
    assert data["volume_per_atom_A3"] == 16.0
    assert data["volume_per_formula_unit_A3"] == 32.0
    assert data["mass_density_g_cm3"] == round(expected_density, 8)
    assert data["provenance"]["cell_volume_source"] == "atoms_cell"
    assert data["provenance"]["total_mass_source"] == "atoms_masses"


def test_surface_geometry_uses_row_cell_area_and_normal_projection() -> None:
    atoms = _Atoms(
        ["Li", "F"],
        [[0.0, 0.0, 2.0], [1.0, 1.0, 5.0]],
        [[2.0, 0.0, 0.0], [1.0, 3.0, 0.0], [0.5, 0.0, 10.0]],
    )
    projection = surface_geometry_projection(atoms)

    assert projection == {
        "area_A2": 6.0,
        "cell_height_A": 10.0,
        "slab_thickness_A": 3.0,
        "vacuum_A": 7.0,
    }


def test_bulk_composition_relation_covers_exact_excess_and_unknown_cases() -> None:
    exact = bulk_composition_relation({"Li": 2, "F": 2}, {"Li": 1, "F": 1})
    assert exact["bulk_composition_relation"] == "exact_integer_multiple"
    assert exact["bulk_formula_units"] == 2
    assert exact["max_complete_bulk_formula_units"] == 2
    assert exact["excess_composition"] == {}
    assert exact["requires_chemical_potential_reservoir"] is False
    assert exact["reservoir_status"] == "not_required"

    excess = bulk_composition_relation({"Li": 2, "F": 1}, {"Li": 1, "F": 1})
    assert excess["bulk_composition_relation"] == "nonstoichiometric"
    assert excess["bulk_formula_units"] is None
    assert excess["max_complete_bulk_formula_units"] == 1
    assert excess["excess_composition"] == {"Li": 1}
    assert excess["requires_chemical_potential_reservoir"] is True
    assert excess["reservoir_status"] == "required"

    unknown = bulk_composition_relation({}, {"Li": 1, "F": 1})
    assert unknown["bulk_composition_relation"] == "unknown_missing_composition"
    assert unknown["requires_chemical_potential_reservoir"] is None
    assert unknown["reservoir_status"] == "unknown"


def test_surface_characterization_records_geometry_sources_and_reservoir_rule() -> None:
    parent = material_characterization_data(_lif_bulk())
    slab = _Atoms(
        ["Li", "F", "Li"],
        [[0.0, 0.0, 4.0], [1.0, 1.0, 6.0], [0.5, 0.5, 8.0]],
        np.diag([4.0, 4.0, 20.0]),
    )
    data = surface_characterization_data(
        slab,
        parent_characterization=parent,
        miller=(1, 0, 0),
        layers=3,
    )

    assert data["contract"] == SURFACE_CHARACTERIZATION_CONTRACT
    assert data["contract_status"] == "complete_v1"
    assert data["bulk_composition_relation"] == "nonstoichiometric"
    assert data["max_complete_bulk_formula_units"] == 1
    assert data["excess_composition"] == {"Li": 1}
    assert data["reservoir_status"] == "required"
    assert data["area_A2"] == 16.0
    assert data["cell_height_A"] == 20.0
    assert data["slab_thickness_A"] == 4.0
    assert data["vacuum_A"] == 16.0
    assert data["provenance"]["geometry_sources"] == {
        "area_A2": "atoms",
        "cell_height_A": "atoms",
        "slab_thickness_A": "atoms",
        "vacuum_A": "atoms",
    }


def test_surface_characterization_records_provided_geometry_when_atoms_are_absent() -> None:
    data = surface_characterization_data(
        None,
        parent_characterization={"reduced_composition": {"Li": 1, "F": 1}},
        area_A2=12.0,
        thickness_A=3.0,
        vacuum_A=7.0,
    )
    assert data["area_A2"] == 12.0
    assert data["cell_height_A"] is None
    assert data["slab_thickness_A"] == 3.0
    assert data["vacuum_A"] == 7.0
    assert data["provenance"]["geometry_sources"] == {
        "area_A2": "provided",
        "cell_height_A": "unavailable",
        "slab_thickness_A": "provided",
        "vacuum_A": "provided",
    }
    assert data["reservoir_status"] == "unknown"


def test_public_records_recompute_contract_status_instead_of_trusting_payload() -> None:
    material = MaterialCharacterization.from_mapping(
        {
            "schema": "calm.material_characterization.v1",
            "contract_status": "complete_v1",
            "composition": {"Li": 1},
        }
    )
    assert material.contract_status == "legacy_unrecorded"

    invalid_surface = SurfaceCharacterization.from_mapping(
        {
            "schema": "calm.surface_characterization.v1",
            "contract": {"policy": "wrong", "version": 1},
            "contract_status": "complete_v1",
        }
    )
    assert invalid_surface.contract_status == "invalid"

    complete = MaterialCharacterization.from_mapping(material_characterization_data(_lif_bulk()))
    assert complete.contract_status == "complete_v1"
    assert characterization_contract_status(complete.to_dict(), kind="material") == "complete_v1"
