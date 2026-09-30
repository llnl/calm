"""Public Material facade for CALM."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


def _atoms_value(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "get_positions") and hasattr(value, "get_cell"):
        return value
    if isinstance(value, Mapping):
        from calm.structure.payloads import dict_to_atoms

        return dict_to_atoms(value)
    raise TypeError(
        "Material atomistic data must be ASE-compatible, a current atoms payload, "
        "or None."
    )


def _payload_mapping(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise TypeError("Persisted material payload must be a mapping or None.")
    return dict(value)


@dataclass
class Material:
    """Represent one user-authored or project-returned bulk material."""

    name: str
    label: Optional[str]
    atoms: Any
    formula: Optional[str] = None
    state: str = "raw_bulk"
    metadata: dict[str, Any] = field(default_factory=dict)
    id_short: Optional[str] = None
    spacegroup: Optional[str] = None
    uid_full: Optional[str] = None
    authority: str = "projection"

    @classmethod
    def from_file(
        cls,
        path: str | Path,
        *,
        name: Optional[str] = None,
        label: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> "Material":
        from calm.structure.io import load_structure

        atoms = load_structure(path)
        formula = (
            atoms.get_chemical_formula()
            if hasattr(atoms, "get_chemical_formula")
            else None
        )
        return cls(
            name=name or formula or Path(path).stem,
            label=label,
            atoms=atoms,
            formula=formula,
            metadata={"source": str(path), **(metadata or {})},
        )

    @classmethod
    def from_ase(
        cls,
        atoms: Any,
        *,
        name: Optional[str] = None,
        label: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> "Material":
        structure = _atoms_value(atoms)
        formula = (
            structure.get_chemical_formula()
            if hasattr(structure, "get_chemical_formula")
            else None
        )
        return cls(
            name=name or formula or "material",
            label=label,
            atoms=structure,
            formula=formula,
            metadata=metadata or {},
        )

    def summary(self) -> str:
        atoms = self.atoms
        if isinstance(atoms, Mapping):
            from calm.structure.payloads import canonical_atoms_payload

            n_atoms: int | str = len(canonical_atoms_payload(atoms)["numbers"])
        else:
            n_atoms = len(atoms) if atoms is not None else "unknown"
        formula = self.formula
        if formula is None and atoms is not None and not isinstance(atoms, Mapping):
            getter = getattr(atoms, "get_chemical_formula", None)
            if callable(getter):
                formula = str(getter())
        parts = [f"Material(name={self.name!r}"]
        if self.id_short:
            parts.append(f"id_short={self.id_short!r}")
        parts.append(f"state={self.state!r}")
        parts.append(f"formula={formula!r}")
        parts.append(f"n_atoms={n_atoms}")
        if self.spacegroup:
            parts.append(f"spacegroup={self.spacegroup!r}")
        return ", ".join(parts) + ")"

    def to_ase(self):
        """Return ASE atoms, preserving absence and rejecting malformed state."""

        return _atoms_value(self.atoms)

    @classmethod
    def from_workspace(cls, obj: Any) -> "Material":
        """Construct a public material from one current workspace record."""

        if isinstance(obj, Material):
            return obj

        if isinstance(obj, Mapping):
            record = dict(obj)
            payload = _payload_mapping(record.get("payload"))
            id_short = record.get("id_short") or record.get("id")
            uid_full = record.get("uid_full") or record.get("project_bulk_uid")
            label = record.get("label") or record.get("name")
            atoms_raw = record.get("atoms")
            if atoms_raw is None:
                atoms_raw = payload.get("atoms")
            formula = record.get("formula") or payload.get("formula")
            state = record.get("kind") or record.get("state") or "reference"
            derived = payload.get("derived")
            if derived is not None and not isinstance(derived, Mapping):
                raise TypeError(
                    "Persisted material derived metadata must be a mapping."
                )
            derived_mapping = dict(derived or {})
            formula = formula or derived_mapping.get("formula")
            spacegroup = record.get("spacegroup") or derived_mapping.get("spacegroup")
            optimized_with = (
                record.get("optimized_with")
                or record.get("calculator")
                or payload.get("optimized_with")
                or payload.get("calculator")
            )
        else:
            id_short = getattr(obj, "id_short", None) or getattr(obj, "id", None)
            uid_full = getattr(obj, "uid_full", None) or getattr(obj, "uid", None)
            label = getattr(obj, "label", None) or getattr(obj, "name", None)
            payload = _payload_mapping(getattr(obj, "payload", None))
            atoms_raw = payload.get("atoms")
            if atoms_raw is None:
                atoms_raw = getattr(obj, "atoms_conventional", None)
            if atoms_raw is None:
                atoms_raw = getattr(obj, "atoms", None)
            formula = getattr(obj, "formula", None)
            state = getattr(obj, "kind", None) or getattr(obj, "state", "reference")
            spacegroup = getattr(obj, "spacegroup", None)
            optimized_with = getattr(obj, "optimized_with", None) or getattr(
                obj, "calculator", None
            )

        if isinstance(atoms_raw, Mapping):
            from calm.structure.payloads import canonical_atoms_payload

            atoms = canonical_atoms_payload(atoms_raw)
        else:
            atoms = _atoms_value(atoms_raw)
        mat_name = label or formula or getattr(obj, "name", None) or "material"
        from calm.public.records.persistence import record_authority

        material = cls(
            name=str(mat_name),
            label=label,
            atoms=atoms,
            formula=formula,
            state=str(state),
            metadata=payload,
            id_short=id_short,
            spacegroup=spacegroup,
            uid_full=uid_full,
            authority=record_authority(
                item=obj,
                authoritative_keys=("uid_full", "project_bulk_uid"),
            ).value,
        )
        if optimized_with is not None:
            setattr(material, "optimized_with", optimized_with)
        return material

    def to_file(self, path: str | Path, *, format: str | None = "vasp") -> Path:
        from calm.structure.io import safe_write_structure

        destination = Path(path)
        if destination.is_dir():
            name = (self.label or self.name or "material").replace(" ", "_")
            destination = destination / f"{name}.{format or 'vasp'}"

        atoms = self.to_ase()
        if atoms is None:
            raise ValueError("Material has no atomistic data to export")
        safe_write_structure(destination, atoms, format=format)
        return destination

    def characterize(self):
        """Return typed structural metadata for polymorph comparison."""

        from calm.structure.characterization import (
            canonical_characterization_payload,
            material_characterization_data,
        )

        from calm.public.records.characterization import MaterialCharacterization

        payload = _payload_mapping(self.metadata)
        if "characterization" in payload:
            stored = payload["characterization"]
            if not isinstance(stored, Mapping):
                raise TypeError(
                    "Persisted material characterization must be a mapping."
                )
            data = canonical_characterization_payload(stored, kind="material")
            data["material"] = self.label or self.name or data.get("material")
            data["kind"] = self.state or data.get("kind")
            return MaterialCharacterization.from_mapping(data)

        derived = payload.get("derived")
        if derived is not None and not isinstance(derived, Mapping):
            raise TypeError("Persisted material derived metadata must be a mapping.")
        data = material_characterization_data(
            self.to_ase(),
            material=self.label or self.name,
            kind=self.state,
            derived=dict(derived or {}),
        )
        return MaterialCharacterization.from_mapping(data)
