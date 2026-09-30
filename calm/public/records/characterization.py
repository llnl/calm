"""Typed material and surface characterization records.

These records expose deterministic structural metadata needed to compare bulk
polymorphs and generated surface terminations.  They intentionally exclude
bonding, charge, defect, reconstruction, and other deferred scientific-analysis
capabilities.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Sequence

from calm.structure.characterization import (
    MATERIAL_CHARACTERIZATION_SCHEMA,
    SURFACE_CHARACTERIZATION_SCHEMA,
    characterization_contract_status,
    material_characterization_data,
    normalize_composition_counts,
    surface_characterization_data,
)


def _composition(value: Any) -> dict[str, int]:
    return normalize_composition_counts(value) if isinstance(value, Mapping) else {}


def _composition_text(value: Mapping[str, int]) -> str:
    return json.dumps(
        dict(sorted(value.items())), sort_keys=True, separators=(",", ":")
    )


@dataclass(frozen=True)
class MaterialCharacterization:
    """Typed, persisted structural metadata for one bulk material."""

    schema: str = MATERIAL_CHARACTERIZATION_SCHEMA
    contract: dict[str, Any] = field(default_factory=dict)
    contract_status: str = "legacy_unrecorded"
    provenance: dict[str, Any] = field(default_factory=dict)
    material: str | None = None
    kind: str | None = None
    formula: str | None = None
    reduced_formula: str | None = None
    composition: dict[str, int] = field(default_factory=dict)
    reduced_composition: dict[str, int] = field(default_factory=dict)
    n_atoms: int | None = None
    n_formula_units: int | None = None
    lattice_a_A: float | None = None
    lattice_b_A: float | None = None
    lattice_c_A: float | None = None
    alpha_deg: float | None = None
    beta_deg: float | None = None
    gamma_deg: float | None = None
    cell_volume_A3: float | None = None
    volume_per_atom_A3: float | None = None
    volume_per_formula_unit_A3: float | None = None
    total_mass_amu: float | None = None
    mass_density_g_cm3: float | None = None
    spacegroup_symbol: str | None = None
    spacegroup_number: int | None = None
    crystal_system: str | None = None

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "MaterialCharacterization":
        data = dict(value)
        data["composition"] = _composition(data.get("composition"))
        data["reduced_composition"] = _composition(data.get("reduced_composition"))
        contract = data.get("contract")
        data["contract"] = dict(contract) if isinstance(contract, Mapping) else {}
        provenance = data.get("provenance")
        data["provenance"] = dict(provenance) if isinstance(provenance, Mapping) else {}
        data["contract_status"] = characterization_contract_status(
            data, kind="material"
        )
        allowed = cls.__dataclass_fields__.keys()
        return cls(**{key: data.get(key) for key in allowed if key in data})

    @classmethod
    def from_atoms(
        cls,
        atoms: Any,
        *,
        material: str | None = None,
        kind: str | None = None,
        derived: Mapping[str, Any] | None = None,
    ) -> "MaterialCharacterization":
        return cls.from_mapping(
            material_characterization_data(
                atoms,
                material=material,
                kind=kind,
                derived=derived,
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_row(self) -> dict[str, Any]:
        row = self.to_dict()
        row["composition"] = _composition_text(self.composition)
        row["reduced_composition"] = _composition_text(self.reduced_composition)
        return row

    def summary(self) -> str:
        identity = self.material or self.reduced_formula or self.formula or "material"
        parts = [f"MaterialCharacterization({identity!r}"]
        if self.spacegroup_symbol or self.spacegroup_number:
            label = self.spacegroup_symbol or "?"
            number = (
                f" ({self.spacegroup_number})"
                if self.spacegroup_number is not None
                else ""
            )
            parts.append(f"spacegroup={label}{number}")
        if self.crystal_system:
            parts.append(f"crystal_system={self.crystal_system}")
        if self.cell_volume_A3 is not None:
            parts.append(f"volume={self.cell_volume_A3:.6g} A^3")
        if self.mass_density_g_cm3 is not None:
            parts.append(f"density={self.mass_density_g_cm3:.6g} g/cm^3")
        return ", ".join(parts) + ")"


@dataclass(frozen=True)
class SurfaceCharacterization:
    """Typed, persisted structural metadata for one generated surface slab."""

    schema: str = SURFACE_CHARACTERIZATION_SCHEMA
    contract: dict[str, Any] = field(default_factory=dict)
    contract_status: str = "legacy_unrecorded"
    provenance: dict[str, Any] = field(default_factory=dict)
    material: str | None = None
    miller: tuple[int, int, int] | None = None
    termination: Any = None
    termination_top: Any = None
    termination_bottom: Any = None
    termination_shift: int | None = None
    symmetric_termination: bool | None = None
    formula: str | None = None
    reduced_formula: str | None = None
    composition: dict[str, int] = field(default_factory=dict)
    reduced_composition: dict[str, int] = field(default_factory=dict)
    n_atoms: int | None = None
    n_formula_units: int | None = None
    parent_reduced_formula: str | None = None
    parent_reduced_composition: dict[str, int] = field(default_factory=dict)
    bulk_composition_compatible: bool | None = None
    bulk_formula_units: int | None = None
    max_complete_bulk_formula_units: int | None = None
    excess_composition: dict[str, int] = field(default_factory=dict)
    bulk_composition_relation: str | None = None
    requires_chemical_potential_reservoir: bool | None = None
    reservoir_status: str | None = None
    reservoir_reason: str | None = None
    area_A2: float | None = None
    cell_height_A: float | None = None
    slab_thickness_A: float | None = None
    vacuum_A: float | None = None
    layers: int | None = None

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "SurfaceCharacterization":
        data = dict(value)
        for key in (
            "composition",
            "reduced_composition",
            "parent_reduced_composition",
            "excess_composition",
        ):
            data[key] = _composition(data.get(key))
        relation = data.pop("relation", None)
        if data.get("bulk_composition_relation") is None:
            data["bulk_composition_relation"] = relation
        contract = data.get("contract")
        data["contract"] = dict(contract) if isinstance(contract, Mapping) else {}
        provenance = data.get("provenance")
        data["provenance"] = dict(provenance) if isinstance(provenance, Mapping) else {}
        data["contract_status"] = characterization_contract_status(data, kind="surface")
        miller = data.get("miller")
        try:
            miller_value = (
                tuple(int(item) for item in miller) if miller is not None else None
            )
        except (TypeError, ValueError):
            miller_value = None
        data["miller"] = (
            miller_value
            if miller_value is not None and len(miller_value) == 3
            else None
        )
        allowed = cls.__dataclass_fields__.keys()
        return cls(**{key: data.get(key) for key in allowed if key in data})

    @classmethod
    def from_atoms(
        cls,
        atoms: Any,
        *,
        parent: MaterialCharacterization | Mapping[str, Any] | None = None,
        material: str | None = None,
        miller: Sequence[int] | None = None,
        termination: Any = None,
        termination_top: Any = None,
        termination_bottom: Any = None,
        termination_shift: int | None = None,
        layers: int | None = None,
        area_A2: float | None = None,
        thickness_A: float | None = None,
        vacuum_A: float | None = None,
        formula: str | None = None,
    ) -> "SurfaceCharacterization":
        parent_mapping = (
            parent.to_dict() if isinstance(parent, MaterialCharacterization) else parent
        )
        return cls.from_mapping(
            surface_characterization_data(
                atoms,
                parent_characterization=parent_mapping,
                material=material,
                miller=miller,
                termination=termination,
                termination_top=termination_top,
                termination_bottom=termination_bottom,
                termination_shift=termination_shift,
                layers=layers,
                area_A2=area_A2,
                thickness_A=thickness_A,
                vacuum_A=vacuum_A,
                formula=formula,
            )
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.miller is not None:
            data["miller"] = list(self.miller)
        return data

    def to_row(self) -> dict[str, Any]:
        row = self.to_dict()
        for key in (
            "composition",
            "reduced_composition",
            "parent_reduced_composition",
            "excess_composition",
        ):
            row[key] = _composition_text(getattr(self, key))
        return row

    def summary(self) -> str:
        identity = f"{self.material or 'surface'} {self.miller or ''}".strip()
        parts = [f"SurfaceCharacterization({identity!r}"]
        if self.termination is not None:
            parts.append(f"termination={self.termination!r}")
        if self.symmetric_termination is not None:
            parts.append(f"symmetric={self.symmetric_termination}")
        if self.bulk_composition_compatible is not None:
            parts.append(f"bulk_compatible={self.bulk_composition_compatible}")
        if self.area_A2 is not None:
            parts.append(f"area={self.area_A2:.6g} A^2")
        if self.slab_thickness_A is not None:
            parts.append(f"thickness={self.slab_thickness_A:.6g} A")
        return ", ".join(parts) + ")"
