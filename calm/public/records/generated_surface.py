"""Public facade for one persisted generated surface."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from typing import Any, Optional


@dataclass
class GeneratedSurface:
    """Typed public representation of a persisted slab/surface.

    A surface's scientific identity is the combination of its authoritative
    slab UID, parent material, Miller index, and termination metadata. The
    short ID is a convenient project-local lookup key; it is not a substitute
    for the full persisted UID.
    """

    id_short: Optional[str]
    label: Optional[str]
    material: Optional[str]
    miller: Optional[tuple[int, int, int]]
    natoms: Optional[int]
    area: Optional[float]
    payload: dict | None = None
    uid_full: Optional[str] = None
    authority: str = "projection"
    bulk_uid_full: Optional[str] = None
    bulk_id_short: Optional[str] = None
    termination: Optional[str] = None
    termination_top: Optional[str] = None
    termination_bottom: Optional[str] = None
    termination_shift: Optional[int] = None
    termination_identity: Any | None = None
    termination_identity_version: Optional[int] = None
    termination_top_identity: Any | None = None
    termination_bottom_identity: Any | None = None
    termination_pair_identity: Any | None = None
    termination_surface_symmetry: Any | None = None
    termination_surface_symmetry_status: str = "not_recorded"
    formula: Optional[str] = None
    vacuum: Optional[float] = None
    thickness: Optional[float] = None
    layers: Optional[int] = None
    _object: Any | None = None

    @classmethod
    def from_workspace(
        cls,
        obj: Any,
        *,
        workspace: Any | None = None,
    ) -> "GeneratedSurface":
        from calm.public.projections.slab import normalize_slab_row
        from calm.public.records.persistence import record_authority

        row = normalize_slab_row(obj, workspace=workspace)
        authority = record_authority(
            obj,
            authoritative_keys=(
                "uid_full",
                "project_slab_uid_full",
                "surface_uid_full",
            ),
        ).value
        return cls(
            id_short=row.get("id_short"),
            label=row.get("label"),
            material=row.get("material"),
            miller=row.get("miller"),
            natoms=row.get("natoms"),
            area=row.get("area"),
            payload=dict(row.get("payload") or {}) or None,
            uid_full=row.get("uid_full") or row.get("project_slab_uid_full"),
            authority=authority,
            bulk_uid_full=row.get("bulk_uid_full"),
            bulk_id_short=row.get("bulk_id_short"),
            termination=row.get("termination"),
            termination_top=row.get("termination_top"),
            termination_bottom=row.get("termination_bottom"),
            termination_shift=row.get("termination_shift"),
            termination_identity=row.get("termination_identity"),
            termination_identity_version=row.get("termination_identity_version"),
            termination_top_identity=row.get("termination_top_identity"),
            termination_bottom_identity=row.get("termination_bottom_identity"),
            termination_pair_identity=row.get("termination_pair_identity"),
            termination_surface_symmetry=row.get("termination_surface_symmetry"),
            termination_surface_symmetry_status=row.get(
                "termination_surface_symmetry_status",
                "not_recorded",
            ),
            formula=row.get("formula"),
            vacuum=row.get("vacuum"),
            thickness=row.get("thickness"),
            layers=row.get("layers"),
            _object=row.get("_object") or obj,
        )

    @property
    def project_slab_uid_full(self) -> str | None:
        return self.uid_full

    @property
    def project_slab_id_short(self) -> str | None:
        return self.id_short

    def to_dict(self) -> dict[str, Any]:
        return {
            "id_short": self.id_short,
            "uid_full": self.uid_full,
            "surface_uid_full": self.uid_full,
            "project_slab_uid_full": self.uid_full,
            "project_slab_id_short": self.id_short,
            "label": self.label,
            "material": self.material,
            "bulk_uid_full": self.bulk_uid_full,
            "bulk_id_short": self.bulk_id_short,
            "miller": self.miller,
            "termination": self.termination,
            "termination_top": self.termination_top,
            "termination_bottom": self.termination_bottom,
            "termination_shift": self.termination_shift,
            "termination_identity": self.termination_identity,
            "termination_identity_version": self.termination_identity_version,
            "termination_top_identity": self.termination_top_identity,
            "termination_bottom_identity": self.termination_bottom_identity,
            "termination_pair_identity": self.termination_pair_identity,
            "termination_surface_symmetry": (self.termination_surface_symmetry),
            "termination_surface_symmetry_status": (
                self.termination_surface_symmetry_status
            ),
            "formula": self.formula,
            "natoms": self.natoms,
            "area": self.area,
            "vacuum": self.vacuum,
            "thickness": self.thickness,
            "layers": self.layers,
            "authority": self.authority,
        }

    def to_ase(self):
        """Return ASE atoms, preserving absence and rejecting malformed state."""

        from collections.abc import Mapping

        from calm.structure.payloads import dict_to_atoms

        obj = self._object
        if obj is not None and obj is not self:
            for attribute in ("atoms", "atoms_conventional"):
                atoms = getattr(obj, attribute, None)
                if atoms is None:
                    continue
                if isinstance(atoms, Mapping):
                    return dict_to_atoms(atoms)
                if hasattr(atoms, "get_positions") and hasattr(atoms, "get_cell"):
                    return atoms
                raise TypeError(
                    f"Persisted surface {attribute} must be ASE-compatible, "
                    "a current atoms payload, or None."
                )
            converter = getattr(obj, "to_ase", None)
            if callable(converter):
                atoms = converter()
                if atoms is None:
                    return None
                if isinstance(atoms, Mapping):
                    return dict_to_atoms(atoms)
                if hasattr(atoms, "get_positions") and hasattr(atoms, "get_cell"):
                    return atoms
                raise TypeError(
                    "Persisted surface to_ase() returned an unsupported object."
                )

        payload = self.payload
        if payload is None and isinstance(obj, Mapping):
            nested = obj.get("payload")
            payload = dict(nested) if isinstance(nested, Mapping) else dict(obj)
        if payload is None:
            return None
        if not isinstance(payload, Mapping):
            raise TypeError("Persisted surface payload must be a mapping or None.")
        structure = payload.get("structure")
        if structure is None:
            return None
        if not isinstance(structure, Mapping):
            raise TypeError("Persisted surface structure must be a mapping.")
        if "atoms" not in structure or structure.get("atoms") is None:
            return None
        return dict_to_atoms(structure["atoms"])

    def characterize(self):
        """Return typed structural and termination metadata for this slab."""
        from calm.public.records.characterization import SurfaceCharacterization
        from calm.structure.characterization import (
            canonical_characterization_payload,
            surface_characterization_data,
        )

        payload = self.payload if isinstance(self.payload, dict) else {}
        structure = payload.get("structure")
        stored = (
            structure.get("characterization") if isinstance(structure, dict) else None
        )
        if isinstance(stored, dict):
            data = canonical_characterization_payload(stored, kind="surface")
            data.update(
                {
                    "material": self.material or data.get("material"),
                    "miller": self.miller or data.get("miller"),
                    "termination": (
                        self.termination
                        if self.termination is not None
                        else data.get("termination")
                    ),
                    "termination_top": (
                        self.termination_top
                        if self.termination_top is not None
                        else data.get("termination_top")
                    ),
                    "termination_bottom": (
                        self.termination_bottom
                        if self.termination_bottom is not None
                        else data.get("termination_bottom")
                    ),
                    "termination_shift": (
                        self.termination_shift
                        if self.termination_shift is not None
                        else data.get("termination_shift")
                    ),
                }
            )
            return SurfaceCharacterization.from_mapping(data)

        parent = None
        data = surface_characterization_data(
            self.to_ase(),
            parent_characterization=parent,
            material=self.material,
            miller=self.miller,
            termination=self.termination,
            termination_top=self.termination_top,
            termination_bottom=self.termination_bottom,
            termination_shift=self.termination_shift,
            layers=self.layers,
            area_A2=self.area,
            thickness_A=self.thickness,
            vacuum_A=self.vacuum,
            formula=self.formula,
        )
        return SurfaceCharacterization.from_mapping(data)

    def summary(self) -> str:
        identity = self.uid_full or self.id_short or "unpersisted"
        parts = [
            f"Surface({identity}, material={self.material!r}, miller={self.miller!r}, "
            f"termination={self.termination!r}, shift={self.termination_shift!r})"
        ]
        if self.natoms is not None:
            parts.append(f"natoms={self.natoms}")
        if self.area is not None:
            parts.append(f"area={self.area}")
        return ", ".join(parts)

    def to_file(self, path: str | Path, *, format: str = "vasp") -> Path:
        atoms = self.to_ase()
        if atoms is None:
            raise ValueError("Surface has no atomistic data to export")
        from calm.structure.io import safe_write_structure

        p = Path(path)
        if p.is_dir():
            name = (self.label or self.id_short or "surface").replace(" ", "_")
            p = p / f"{name}.{format}"
        safe_write_structure(p, atoms, format=format)
        return p

    def _requested_target_width(self) -> float | None:
        """Return the persisted construction request, not measured thickness.

        ``GeneratedSurface.thickness`` is the measured Cartesian atom span of
        the generated slab.  Reconstructing a new ``Surface`` must instead
        use the original ``params.target_width`` request when one was recorded.
        In particular, a one-layer slab has a valid measured span of ``0.0``
        angstrom and must not be interpreted as a zero target-width request.
        """

        payload = self.payload if isinstance(self.payload, dict) else {}
        params = payload.get("params")
        if not isinstance(params, dict):
            return None
        raw = params.get("target_width")
        if raw is None:
            return None
        if isinstance(raw, bool):
            raise TypeError("Persisted target_width must be a real number.")
        try:
            value = float(raw)
        except (TypeError, ValueError) as exc:
            raise TypeError("Persisted target_width must be a real number.") from exc
        if not isfinite(value) or value <= 0.0:
            raise ValueError("Persisted target_width must be finite and positive.")
        return value

    def to_surface(self):
        """Convert this persisted surface into a public search request."""
        try:
            from calm.public.records.surfaces import Surface
        except ImportError as exc:
            raise RuntimeError("Public Surface facade is unavailable") from exc

        if self.miller is None:
            raise TypeError(
                "GeneratedSurface lacks Miller indices; cannot convert to Surface"
            )

        obj = self._object
        source = obj
        if source is None:
            source = self.to_ase()
        if source is None:
            raise TypeError(
                "GeneratedSurface has no slab object or atomistic payload "
                "to convert to Surface"
            )

        return Surface(
            source,
            miller=tuple(self.miller),
            material=self.material,
            label=self.label,
            termination=self.termination,
            termination_shift=self.termination_shift,
            termination_identity=self.termination_identity,
            termination_identity_version=self.termination_identity_version,
            termination_top_identity=self.termination_top_identity,
            termination_bottom_identity=self.termination_bottom_identity,
            termination_pair_identity=self.termination_pair_identity,
            termination_surface_symmetry=(self.termination_surface_symmetry),
            vacuum=self.vacuum,
            layers=self.layers,
            thickness=self._requested_target_width(),
            project_slab_uid_full=self.uid_full,
            project_slab_id_short=self.id_short,
        )
