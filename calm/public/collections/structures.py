"""Material and structure public query collections."""

from __future__ import annotations

from dataclasses import fields
from typing import Any, Iterable

from calm.public.collections.base import _BaseCollection
from calm.public.collections.views import ViewSpec
from calm.public.records.characterization import (
    MaterialCharacterization,
    SurfaceCharacterization,
)


_MATERIAL_SUMMARY_COLUMNS = (
    "id_short",
    "label",
    "kind",
    "formula",
    "natoms",
    "spacegroup",
)
_MATERIAL_CHARACTERIZATION_COLUMNS = (
    "label",
    "reduced_formula",
    "spacegroup_symbol",
    "spacegroup_number",
    "lattice_a_A",
    "lattice_b_A",
    "lattice_c_A",
    "cell_volume_A3",
    "mass_density_g_cm3",
)
_MATERIAL_CHARACTERIZATION_ALL_COLUMNS = (
    "id_short",
    "label",
    *(field.name for field in fields(MaterialCharacterization)),
)
_SURFACE_SUMMARY_COLUMNS = (
    "id_short",
    "label",
    "bulk",
    "miller",
    "termination",
    "area",
    "natoms",
)
_SURFACE_CHARACTERIZATION_COLUMNS = (
    "id_short",
    "material",
    "miller",
    "termination",
    "termination_shift",
    "symmetric_termination",
    "reduced_formula",
    "bulk_formula_units",
    "area_A2",
    "slab_thickness_A",
    "layers",
    "n_atoms",
)
_SURFACE_CHARACTERIZATION_ALL_COLUMNS = (
    "id_short",
    "label",
    *(field.name for field in fields(SurfaceCharacterization)),
)


class MaterialCollection(_BaseCollection):
    _view_specs = (
        ViewSpec(
            name="summary",
            columns=_MATERIAL_SUMMARY_COLUMNS,
            description="Ordinary reader-facing material summary.",
        ),
        ViewSpec(
            name="characterization",
            columns=_MATERIAL_CHARACTERIZATION_COLUMNS,
            aliases=("characterizations",),
            display_labels=(
                ("label", "material"),
                ("reduced_formula", "formula"),
                ("spacegroup_symbol", "spacegroup"),
                ("spacegroup_number", "sg_no"),
                ("lattice_a_A", "a_A"),
                ("lattice_b_A", "b_A"),
                ("lattice_c_A", "c_A"),
                ("cell_volume_A3", "volume_A3"),
                ("mass_density_g_cm3", "density_g_cm3"),
            ),
            description="Concise structural characterization for material comparison.",
        ),
        ViewSpec(
            name="characterization_all",
            columns=_MATERIAL_CHARACTERIZATION_ALL_COLUMNS,
            description="Complete typed material-characterization projection.",
        ),
        ViewSpec(
            name="all",
            columns=_MATERIAL_SUMMARY_COLUMNS,
            allow_extra_columns=True,
            description="Complete normalized persisted material row.",
        ),
    )

    def __init__(
        self,
        workspace: Any | None = None,
        items: Iterable[Any] | None = None,
        repo: Any | None = None,
    ):
        self._ws = workspace
        self._items = list(items) if items is not None else []
        self._loaded = bool(items is not None)
        self._repo = repo

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        if self._repo is None:
            raise RuntimeError(
                "MaterialCollection requires an authoritative project repository."
            )
        self._items = list(self._repo.list_bulks())
        self._loaded = True

    def _clone(self, items):
        return MaterialCollection(workspace=self._ws, items=items, repo=self._repo)

    def _public_item(self, item: Any):
        from calm.public.inputs.materials import Material

        return item if isinstance(item, Material) else Material.from_workspace(item)

    _table_name = "bulks"

    def _normalize_item(self, item: Any) -> dict[str, Any]:
        from calm.public.projections.bulk import normalize_bulk_row

        return normalize_bulk_row(item)

    def characterizations(self):
        """Return typed characterization records for the selected materials."""
        self._ensure_loaded()
        return [self._public_item(item).characterize() for item in self._items]

    def _rows_for_view(self, view: str) -> list[dict[str, Any]]:
        self._ensure_loaded()
        if view in {"characterization", "characterization_all"}:
            rows: list[dict[str, Any]] = []
            for item in self._items:
                base = self._normalize_item(item)
                characterization = self._public_item(item).characterize().to_row()
                rows.append(
                    {
                        "id_short": base.get("id_short"),
                        "label": base.get("label"),
                        "kind": base.get("kind"),
                        **characterization,
                    }
                )
            return rows
        # Use the canonical per-item normalizer which delegates to
        # calm.public.projections.bulk.normalize_bulk_row where possible. This
        # centralizes normalization logic and avoids duplication that caused
        # missing fields in the example output.
        return [self._normalize_item(m) for m in self._items]


def _selector_values(value: Any, *attributes: str) -> set[str]:
    if value is None:
        return set()
    values: list[Any] = [value] if isinstance(value, str) else []
    if not isinstance(value, str):
        for attribute in attributes:
            candidate = getattr(value, attribute, None)
            if candidate is not None:
                values.append(candidate)
    return {
        str(candidate).casefold() for candidate in values if candidate not in (None, "")
    }


def _surface_material_values(row: dict[str, Any]) -> set[str]:
    return {
        str(value).casefold()
        for value in (
            row.get("material"),
            row.get("material_a"),
            row.get("bulk_id_short"),
            row.get("bulk_uid_full"),
            row.get("parent_id"),
        )
        if value not in (None, "")
    }


def _surface_description(row: dict[str, Any]) -> str:
    return (
        f"id={row.get('id_short')!r}, uid={row.get('uid_full')!r}, "
        f"material={row.get('material')!r}, miller={row.get('miller')!r}, "
        f"termination={row.get('termination')!r}, "
        f"termination_top={row.get('termination_top')!r}, "
        f"termination_bottom={row.get('termination_bottom')!r}, "
        f"termination_shift={row.get('termination_shift')!r}"
    )


class SurfaceCollection(_BaseCollection):
    """Collection of authoritative persisted generated surfaces."""

    _view_specs = (
        ViewSpec(
            name="summary",
            columns=_SURFACE_SUMMARY_COLUMNS,
            description="Ordinary reader-facing surface summary.",
        ),
        ViewSpec(
            name="characterization",
            columns=_SURFACE_CHARACTERIZATION_COLUMNS,
            aliases=("characterizations",),
            display_labels=(
                ("id_short", "id"),
                ("termination_shift", "shift"),
                ("symmetric_termination", "sym"),
                ("reduced_formula", "formula"),
                ("bulk_formula_units", "bulk_fu"),
                ("slab_thickness_A", "thick_A"),
                ("n_atoms", "atoms"),
            ),
            description="Concise generated-surface characterization.",
        ),
        ViewSpec(
            name="characterization_all",
            columns=_SURFACE_CHARACTERIZATION_ALL_COLUMNS,
            description="Complete typed surface-characterization projection.",
        ),
        ViewSpec(
            name="all",
            columns=_SURFACE_SUMMARY_COLUMNS,
            allow_extra_columns=True,
            description="Complete normalized persisted surface row.",
        ),
    )

    def __init__(
        self,
        workspace: Any | None = None,
        items: Iterable[Any] | None = None,
        repo: Any | None = None,
    ):
        self._ws = workspace
        self._items = list(items) if items is not None else []
        self._loaded = items is not None
        self._repo = repo

    def _normalize_item(self, item: Any) -> dict[str, Any]:
        from calm.public.projections.slab import normalize_slab_row

        return normalize_slab_row(item, workspace=self._ws)

    def _public_item(self, item: Any):
        from calm.public.records.generated_surface import GeneratedSurface

        return (
            item
            if isinstance(item, GeneratedSurface)
            else GeneratedSurface.from_workspace(item, workspace=self._ws)
        )

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        if self._repo is None:
            raise RuntimeError(
                "SurfaceCollection requires an authoritative project repository."
            )
        self._items = list(self._repo.list_slabs(limit=2000))
        self._loaded = True

    def characterizations(self):
        """Return typed characterization records for selected surfaces."""
        self._ensure_loaded()
        return [self._public_item(item).characterize() for item in self._items]

    def _rows_for_view(self, view: str) -> list[dict[str, Any]]:
        self._ensure_loaded()
        if view in {"characterization", "characterization_all"}:
            rows: list[dict[str, Any]] = []
            for item in self._items:
                base = self._normalize_item(item)
                characterization = self._public_item(item).characterize().to_row()
                rows.append(
                    {
                        "id_short": base.get("id_short"),
                        "label": base.get("label"),
                        **characterization,
                    }
                )
            return rows
        return [self._normalize_item(item) for item in self._items]

    def _clone(self, items):
        return SurfaceCollection(workspace=self._ws, items=items, repo=self._repo)

    def usable_surfaces(self) -> "SurfaceCollection":
        """Return surfaces with an authoritative atomistic payload."""
        self._ensure_loaded()
        selected: list[Any] = []
        for item in self._items:
            row = self._normalize_item(item)
            natoms_value = row.get("natoms")
            try:
                natoms = int(natoms_value) if natoms_value is not None else 0
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "Persisted surface atom counts must be integers."
                ) from exc
            if bool(row.get("has_atoms")) or natoms > 0:
                selected.append(item)
        return self._clone(selected)

    def select(
        self,
        *,
        material: Any | None = None,
        miller: tuple[int, int, int] | None = None,
        termination: str | None = None,
        termination_top: str | None = None,
        termination_bottom: str | None = None,
        termination_shift: int | None = None,
    ) -> "SurfaceCollection":
        """Filter persisted surfaces by exact scientific identity fields.

        Material matching accepts an exact material label, bulk short ID, bulk
        UID, or a material-like object carrying one of those attributes.
        Primary, top, and bottom termination labels and integer shifts are
        distinct selectors.
        """
        for name, value in (
            ("termination", termination),
            ("termination_top", termination_top),
            ("termination_bottom", termination_bottom),
        ):
            if value is not None and not isinstance(value, str):
                raise TypeError(f"{name} must be a string label or None")
        if termination_shift is not None and (
            isinstance(termination_shift, bool)
            or not isinstance(termination_shift, int)
        ):
            raise TypeError("termination_shift must be an integer or None")

        material_values = _selector_values(
            material,
            "label",
            "name",
            "id_short",
            "uid_full",
        )
        miller_value = None
        if miller is not None:
            try:
                miller_value = tuple(int(x) for x in miller)
            except (TypeError, ValueError) as exc:
                raise ValueError("miller must be a three-integer sequence") from exc
            if len(miller_value) != 3:
                raise ValueError("miller must be a three-integer sequence")

        termination_value = (
            str(termination).casefold() if termination is not None else None
        )
        termination_top_value = (
            str(termination_top).casefold() if termination_top is not None else None
        )
        termination_bottom_value = (
            str(termination_bottom).casefold()
            if termination_bottom is not None
            else None
        )
        shift_value = termination_shift

        self._ensure_loaded()
        selected: list[Any] = []
        for item in self._items:
            row = self._normalize_item(item)
            if material_values and not (
                material_values & _surface_material_values(row)
            ):
                continue
            if miller_value is not None:
                try:
                    row_miller = tuple(int(x) for x in row.get("miller"))
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        "Persisted surface Miller indices must be a three-integer sequence."
                    ) from exc
                if len(row_miller) != 3:
                    raise ValueError(
                        "Persisted surface Miller indices must be a three-integer sequence."
                    )
                if row_miller != miller_value:
                    continue
            termination_filters = (
                ("termination", termination_value),
                ("termination_top", termination_top_value),
                ("termination_bottom", termination_bottom_value),
            )
            if any(
                expected is not None
                and (row.get(key) is None or str(row.get(key)).casefold() != expected)
                for key, expected in termination_filters
            ):
                continue
            if shift_value is not None:
                row_shift_value = row.get("termination_shift")
                if isinstance(row_shift_value, bool):
                    raise ValueError(
                        "Persisted surface termination shifts must be integers."
                    )
                try:
                    row_shift = int(row_shift_value)
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        "Persisted surface termination shifts must be integers."
                    ) from exc
                if row_shift != shift_value:
                    continue
            selected.append(item)
        return self._clone(selected)

    def one(self, *, selection: str | None = None):
        """Return exactly one surface or raise a descriptive query error."""
        self._ensure_loaded()
        if not self._items:
            suffix = f" for {selection}" if selection else ""
            raise KeyError(f"No persisted surface matched{suffix}.")
        if len(self._items) > 1:
            from calm.public.errors import AmbiguousProjectQueryError

            rows = [self._normalize_item(item) for item in self._items]
            details = "; ".join(_surface_description(row) for row in rows)
            suffix = f" for {selection}" if selection else ""
            raise AmbiguousProjectQueryError(
                f"Surface selection{suffix} matched {len(rows)} persisted "
                f"surfaces. Select by stable slab ID/UID or add primary, top, "
                f"bottom, or shift termination filters. Matches: {details}"
            )
        return self._public_item(self._items[0])
