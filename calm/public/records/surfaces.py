"""Public Surface facade.

A :class:`Surface` is a user-facing request for a material surface. It may be
constructed from an ASE ``Atoms`` object, a path to a structure file, a public
``Material``, an internal ``Bulk``, or an already generated slab-like object.
The lower-level ``Bulk``/``SlabSpec``/``Slab`` objects remain implementation
objects and are created lazily only when a workflow needs them.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Iterable, Optional, Tuple

from calm.public.records.validation import ValidationReport, make_report

try:  # import-light fallback for environments without ASE
    from ase import Atoms as ASEAtoms
except ImportError:  # pragma: no cover
    ASEAtoms = object  # type: ignore[assignment]


class TerminationCollection:
    """Small table-like collection returned by :meth:`Surface.terminations`.

    Rows describe enumerated termination candidates and their layer labels.
    They report enumeration multiplicity explicitly and mark polarity as
    ``not_evaluated`` because no charge or electrostatic model is applied.
    """

    def __init__(self, rows: Iterable[dict[str, Any]]):
        self._rows = [dict(r) for r in rows]

    def __iter__(self):
        return iter(self._rows)

    def __len__(self) -> int:
        return len(self._rows)

    def __getitem__(self, idx):
        return self._rows[idx]

    def to_rows(self) -> list[dict[str, Any]]:
        return list(self._rows)

    def to_dataframe(self):
        try:
            import pandas as pd
        except ImportError as e:
            raise ImportError(
                "TerminationCollection.to_dataframe() requires pandas."
            ) from e
        return pd.DataFrame.from_records(self._rows)

    def __repr__(self) -> str:  # pragma: no cover - convenience
        return repr(self._rows)


def _looks_like_ase_atoms(obj: Any) -> bool:
    return hasattr(obj, "get_positions") and hasattr(obj, "get_cell")


def _is_pathlike(obj: Any) -> bool:
    return isinstance(obj, (str, Path))


def _termination_selection_matches(item: Any, selection: Any) -> bool:
    """Return whether one enumerated class matches an explicit selector."""

    metadata = dict(getattr(item, "metadata", {}) or {})
    if isinstance(selection, bool):
        return False
    if isinstance(selection, int):
        return int(item.shift) == int(selection)

    digest = None
    if isinstance(selection, dict):
        digest = selection.get("digest")
    elif isinstance(selection, str) and selection.startswith("sha256:"):
        digest = selection
    if digest is not None:
        identities = (
            metadata.get("termination_identity"),
            metadata.get("termination_pair_identity"),
        )
        return any(
            isinstance(identity, dict) and identity.get("digest") == digest
            for identity in identities
        )

    return str(item.label) == str(selection)


@dataclass(frozen=True)
class Surface:
    """Describe a crystallographic surface request or reopened surface record.

    A surface couples an input structure with Miller indices, slab-size controls,
    and an optional exact termination selection. Persisted surface identities are
    carried by ``project_slab_uid_full`` and ``project_slab_id_short`` when the
    object originates from a project.

    The request is not necessarily an already-built slab. Use the conversion and
    termination methods to construct or inspect atomistic surface models.
    """

    structure: Any
    miller: Tuple[int, int, int]
    thickness: Optional[float] = None
    layers: Optional[int] = None
    material: Optional[str] = None
    label: Optional[str] = None
    termination: Optional[str | int] = None
    termination_shift: Optional[int] = None
    termination_identity: Any | None = None
    termination_identity_version: Optional[int] = None
    termination_top_identity: Any | None = None
    termination_bottom_identity: Any | None = None
    termination_pair_identity: Any | None = None
    termination_surface_symmetry: Any | None = None
    vacuum: Optional[float] = None
    symprec: float = 1e-5
    no_idealize: bool = False
    project_slab_uid_full: Optional[str] = None
    project_slab_id_short: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "miller", tuple(int(x) for x in self.miller))
        if self.thickness is None and self.layers is None:
            # Keep object constructible for exploratory inspection, but the
            # validation report/search facade will ask for a size before use.
            pass
        # Allow optional termination to be present on construction; preserve
        # on the Surface object so higher-level facades (e.g., Project.surface)
        # and search result annotation can access it.
        # If termination was passed as a value (string/int), ensure it is
        # stored as a normalized string for downstream consumers.
        term = getattr(self, "termination", None)
        if term is not None:
            object.__setattr__(self, "termination", term)
        shift = getattr(self, "termination_shift", None)
        if shift is not None:
            object.__setattr__(self, "termination_shift", int(shift))

    @classmethod
    def from_file(cls, path: str | Path, *, miller, **kwargs) -> "Surface":
        return cls(path, miller=tuple(miller), **kwargs)

    @classmethod
    def from_ase(cls, atoms: Any, *, miller, **kwargs) -> "Surface":
        return cls(atoms, miller=tuple(miller), **kwargs)

    @property
    def name(self) -> str:
        return self.label or self.material or f"surface{self.miller}"

    def _load_atoms(self) -> Any:
        """Return an ASE Atoms object without standardizing/building a slab."""

        # Public Material object
        if hasattr(self.structure, "to_ase") and not _looks_like_ase_atoms(
            self.structure
        ):
            return self.structure.to_ase()

        # Internal Bulk object
        if hasattr(self.structure, "conv") and hasattr(self.structure, "prim"):
            return self.structure.conv

        # Internal Slab object or already generated public Surface from a slab
        if hasattr(self.structure, "atoms") and _looks_like_ase_atoms(
            getattr(self.structure, "atoms")
        ):
            return getattr(self.structure, "atoms")

        if _looks_like_ase_atoms(self.structure):
            return self.structure

        if _is_pathlike(self.structure):
            from calm.structure.io import load_structure

            return load_structure(self.structure)

        raise TypeError(
            "Surface.structure must be a path, ASE Atoms, public Material, "
            "internal Bulk, or slab-like object."
        )

    def to_ase(self):
        return self._load_atoms()

    def to_bulk(self):
        if hasattr(self.structure, "conv") and hasattr(self.structure, "prim"):
            return self.structure
        from calm.bulk.bulk import Bulk

        return Bulk(
            self._load_atoms(),
            label=self.material or self.label,
            symprec=float(self.symprec),
            no_idealize=bool(self.no_idealize),
        )

    def _slab_spec(self):
        from calm.slab.slab import SlabSpec

        n_layers = int(self.layers) if self.layers is not None else 4
        max_layers = max(10, n_layers)
        return SlabSpec(
            miller=tuple(self.miller),
            n_layers=n_layers,
            target_width=float(self.thickness) if self.thickness is not None else None,
            max_n_layers=max_layers,
            vacuum=float(self.vacuum) if self.vacuum is not None else 10.0,
            termination=None if self.termination is None else str(self.termination),
            symprec=float(self.symprec),
            no_idealize=bool(self.no_idealize),
        )

    def to_slab(self):  # noqa: C901
        from calm.slab.slab import Slab

        # Project-backed generated surfaces already contain their authoritative
        # finite slab geometry.  Wrap that geometry directly; never reinterpret
        # slab atoms as a new bulk and construct the surface a second time.
        if self.project_slab_uid_full is not None:
            return Slab.from_materialized(
                self._load_atoms(),
                miller=self.miller,
                project_slab_uid_full=self.project_slab_uid_full,
                project_slab_id_short=self.project_slab_id_short,
                layers=self.layers,
                vacuum=self.vacuum,
            )

        # If the object is already an internal slab, return it.
        if (
            hasattr(self.structure, "bulk")
            and hasattr(self.structure, "spec")
            and hasattr(self.structure, "atoms")
        ):
            slab = self.structure
            # Preserve any authoritative workspace slab ids when present on the
            # underlying object so later persistence can link prototypes to the
            # workspace slab records instead of internal transient ids.
            project_uid = getattr(slab, "uid_full", None) or getattr(slab, "uid", None)
            project_id = getattr(slab, "id_short", None) or getattr(slab, "id", None)
            if project_uid:
                setattr(slab, "project_slab_uid_full", project_uid)
            if project_id:
                setattr(slab, "project_slab_id_short", project_id)
            return slab
        slab = Slab(self.to_bulk(), self._slab_spec())
        # If this Surface originated from a persisted GeneratedSurface, prefer
        # to propagate that workspace identity onto the internal slab object so
        # prototype persistence can prefer authoritative ids.
        proj_uid = self.project_slab_uid_full
        proj_id = self.project_slab_id_short
        if proj_uid is not None:
            setattr(slab, "project_slab_uid_full", proj_uid)
        if proj_id is not None:
            setattr(slab, "project_slab_id_short", proj_id)
        return slab

    def summary(self) -> str:
        errors: list[str] = []
        n = "unknown"
        formula = None
        try:
            atoms = self._load_atoms()
            n = len(atoms) if hasattr(atoms, "__len__") else "unknown"
            if hasattr(atoms, "get_chemical_formula"):
                formula = atoms.get_chemical_formula()
        except Exception as exc:
            errors.append(str(exc))

        lines = [
            (
                f"Surface(label={self.label!r}, material={self.material!r}, "
                f"miller={self.miller})"
            )
        ]
        lines.append(f"  source_atoms: {n}")
        if formula:
            lines.append(f"  formula: {formula}")
        if self.thickness is not None:
            lines.append(f"  target thickness: {self.thickness} Å")
        if self.layers is not None:
            lines.append(f"  layers: {self.layers}")
        if self.termination is not None:
            lines.append(f"  termination: {self.termination}")
        if self.termination_shift is not None:
            lines.append(f"  termination shift: {self.termination_shift}")
        if self.project_slab_uid_full is not None:
            lines.append(f"  persisted surface UID: {self.project_slab_uid_full}")
        if errors:
            lines.append("  warnings:")
            lines.extend(f"    - {e}" for e in errors)
        return "\n".join(lines)

    def validate(self) -> ValidationReport:
        errors: list[str] = []
        warnings: list[str] = []
        suggestions: list[str] = []
        if len(tuple(self.miller)) != 3:
            errors.append("miller must be a 3-index tuple, e.g. (1, 1, 1).")
        if self.thickness is None and self.layers is None:
            warnings.append(
                "Neither thickness nor layers was provided; CALM will use a default "
                "layer count for slab construction."
            )
            suggestions.append(
                "Provide thickness=... or layers=... for reproducible slab generation."
            )
        try:
            atoms = self._load_atoms()
            if hasattr(atoms, "pbc") and not all(bool(x) for x in atoms.pbc):
                warnings.append(
                    "Input structure is not fully periodic; bulk-to-surface "
                    "construction usually expects a 3D periodic bulk cell."
                )
        except Exception as exc:
            errors.append(str(exc))
        return make_report(
            f"Surface({self.name})",
            errors=errors,
            warnings=warnings,
            suggestions=suggestions,
        )

    def terminations(
        self,
        *,
        layers: int | None = None,
        tolerance: float = 0.3,
        surface_symmetry_mode: str = "discover",
        surface_symprec: float | None = None,
        surface_angle_tolerance: float = 1e-8,
        surface_metric_tolerance: float = 1e-5,
    ) -> TerminationCollection:
        """Enumerate available terminations and return a table-like collection.

        The selected symmetry policy is authoritative. Discovery and finite-group
        validation failures raise rather than silently changing the equivalence
        relation to the identity group.
        """

        try:
            from calm.slab.oriented.terminations import (
                _cluster_atoms_by_z,
                enumerate_all_terminations,
            )
        except ImportError as e:
            raise ImportError(
                "Surface.terminations() requires the slab termination utilities "
                "plus ASE/spglib."
            ) from e

        bulk_obj = self.to_bulk()
        hkl = tuple(self.miller)
        n_layers = int(layers if layers is not None else (self.layers or 10))
        vacuum = float(self.vacuum) if self.vacuum is not None else 10.0
        enumerated = enumerate_all_terminations(
            bulk_obj,
            hkl,
            n_layers,
            vacuum=vacuum,
            tolerance=tolerance,
            surface_symmetry_mode=surface_symmetry_mode,
            surface_symprec=(
                float(self.symprec) if surface_symprec is None else surface_symprec
            ),
            surface_angle_tolerance=surface_angle_tolerance,
            surface_metric_tolerance=surface_metric_tolerance,
        )

        rows: list[dict[str, Any]] = []
        enumeration_count = len(enumerated)
        has_multiple = enumeration_count > 1
        for idx, item in enumerate(enumerated):
            slab_atoms, label, shift = item
            metadata = dict(getattr(item, "metadata", {}) or {})
            layer_info = _cluster_atoms_by_z(slab_atoms, tolerance=tolerance)
            bottom_species = layer_info[0].composition if layer_info else ""
            top_species = layer_info[-1].composition if layer_info else ""
            rows.append(
                {
                    "termination_id": int(idx),
                    "label": str(label),
                    "formula": (
                        slab_atoms.get_chemical_formula()
                        if hasattr(slab_atoms, "get_chemical_formula")
                        else ""
                    ),
                    "stoichiometric": None,
                    "enumeration_count": enumeration_count,
                    "has_multiple_enumerated_terminations": has_multiple,
                    "polarity_status": "not_evaluated",
                    "dipole_z": None,
                    "n_atoms": int(len(slab_atoms)),
                    "thickness": None,
                    "top_species": top_species,
                    "bottom_species": bottom_species,
                    "warnings": None,
                    "shift": int(shift),
                    "termination_identity_version": metadata.get(
                        "termination_identity_version"
                    ),
                    "termination_identity": metadata.get("termination_identity"),
                    "termination_top_identity": metadata.get(
                        "termination_top_identity"
                    ),
                    "termination_bottom_identity": metadata.get(
                        "termination_bottom_identity"
                    ),
                    "termination_pair_identity": metadata.get(
                        "termination_pair_identity"
                    ),
                    "decorated_stacking_period_layers": metadata.get(
                        "decorated_stacking_period_layers"
                    ),
                    "stacking_translation_order": metadata.get(
                        "stacking_translation_order"
                    ),
                    "cut_fractional": metadata.get("cut_fractional"),
                    "surface_symmetry": metadata.get("surface_symmetry"),
                }
            )
        return TerminationCollection(rows)

    def with_termination(
        self,
        termination,
        *,
        surface_symmetry_mode: str = "discover",
        surface_symprec: float | None = None,
        surface_angle_tolerance: float = 1e-8,
        surface_metric_tolerance: float = 1e-5,
    ) -> "Surface":
        try:
            from calm.slab.oriented.terminations import (
                enumerate_all_terminations,
            )
        except ImportError as e:
            raise ImportError(
                "Surface.with_termination() requires the slab termination utilities "
                "plus ASE/spglib."
            ) from e

        bulk_obj = self.to_bulk()
        hkl = tuple(self.miller)
        n_layers = int(self.layers) if self.layers is not None else 10
        vacuum = float(self.vacuum) if self.vacuum is not None else 10.0

        enumerated = enumerate_all_terminations(
            bulk_obj,
            hkl,
            n_layers,
            vacuum=vacuum,
            surface_symmetry_mode=surface_symmetry_mode,
            surface_symprec=(
                float(self.symprec) if surface_symprec is None else surface_symprec
            ),
            surface_angle_tolerance=surface_angle_tolerance,
            surface_metric_tolerance=surface_metric_tolerance,
        )
        matches = [
            item
            for item in enumerated
            if _termination_selection_matches(item, termination)
        ]
        if not matches:
            raise ValueError(
                f"Termination {termination!r} not found for Miller index {hkl}."
            )
        if len(matches) > 1:
            shifts = [int(item.shift) for item in matches]
            raise ValueError(
                f"Termination label {termination!r} is ambiguous for Miller "
                f"index {hkl}; matching canonical shifts are {shifts}. Select "
                "by shift or version-2 identity digest instead."
            )

        item = matches[0]
        slab_atoms, label, shift = item
        metadata = dict(getattr(item, "metadata", {}) or {})
        return replace(
            self,
            structure=slab_atoms,
            layers=n_layers,
            termination=label,
            termination_shift=int(shift),
            termination_identity=metadata.get("termination_identity"),
            termination_identity_version=metadata.get("termination_identity_version"),
            termination_top_identity=metadata.get("termination_top_identity"),
            termination_bottom_identity=metadata.get("termination_bottom_identity"),
            termination_pair_identity=metadata.get("termination_pair_identity"),
            termination_surface_symmetry=metadata.get("surface_symmetry"),
        )

    def _write_atoms(self):
        """Return the atomistic structure represented by this surface request.

        For source bulk structures, a public ``Surface`` represents a slab
        request, so writes should materialize that slab. For already generated
        termination selections, the structure payload is already slab-like and
        should be written directly rather than being interpreted as a new bulk.
        """

        if self.termination is not None and _looks_like_ase_atoms(self.structure):
            return self.to_ase()

        if (
            hasattr(self.structure, "bulk")
            and hasattr(self.structure, "spec")
            and hasattr(self.structure, "atoms")
        ):
            return self.to_slab().atoms

        return self.to_slab().atoms

    def write(self, path: str | Path, *, format: str | None = None) -> None:
        from calm.structure.io import write_structure

        write_structure(path, self._write_atoms(), format=format)
