"""Shared named-view contract for constructed and derived interfaces."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import isfinite
from numbers import Real
from typing import Any

from calm.public.collections.views import (
    ResolvedTableProjection,
    ViewSpec,
    resolve_table_projection,
    resolve_view_spec,
)
from calm.public.projections.atoms import (
    actual_interface_area_A2_from_atoms,
    actual_natoms_from_atoms,
)
from calm.public.projections.interface import normalize_interface_row


INTERFACE_SUMMARY_COLUMNS = (
    "id_short",
    "label",
    "stage",
    "search_name",
    "candidate_id",
    "n_atoms",
    "area_A2",
)

INTERFACE_CONSTRUCTION_COLUMNS = (
    "id_short",
    "label",
    "stage",
    "search_name",
    "candidate_id",
    "strain_alpha",
    "registry_shift_frac_a",
    "gap_A",
    "vacuum_A",
    "n_atoms",
    "area_A2",
    "prototype_area_A2",
)

INTERFACE_STRAIN_COLUMNS = (
    "id_short",
    "label",
    "stage",
    "strain_alpha",
    "deformation_state",
    "lower_construction_max_abs_principal_log_strain",
    "upper_construction_max_abs_principal_log_strain",
    "lower_incremental_matching_max_abs_principal_log_strain",
    "upper_incremental_matching_max_abs_principal_log_strain",
    "lower_current_total_max_abs_principal_log_strain",
    "upper_current_total_max_abs_principal_log_strain",
    "relaxation_cell_max_abs_principal_log_strain",
)

INTERFACE_PROVENANCE_COLUMNS = (
    "id_short",
    "uid_full",
    "prototype_uid_full",
    "candidate_uid",
    "search_name",
    "search_id",
    "run_uid_full",
    "run_id_short",
    "source_interface_uid",
    "source_followup_uid",
    "source_run_uid",
    "project_interface_uid",
    "project_interface_id",
    "slab_a_uid_full",
    "slab_b_uid_full",
    "artifact_refs",
    "authority",
    "created_at",
)


def _ordered_union(*groups: Sequence[str]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for name in group:
            if name not in seen:
                result.append(name)
                seen.add(name)
    return tuple(result)


INTERFACE_ALL_BASE_COLUMNS = _ordered_union(
    INTERFACE_SUMMARY_COLUMNS,
    INTERFACE_CONSTRUCTION_COLUMNS,
    INTERFACE_PROVENANCE_COLUMNS,
    ("spec", "metadata", "payload", "structure_id", "kind"),
)

INTERFACE_VIEW_SPECS = (
    ViewSpec(
        name="summary",
        columns=INTERFACE_SUMMARY_COLUMNS,
        description="Concise identity and size summary for persisted interfaces.",
    ),
    ViewSpec(
        name="construction",
        columns=INTERFACE_CONSTRUCTION_COLUMNS,
        description=(
            "Interface construction controls with realized atom count and cell "
            "area; the source prototype area remains explicit."
        ),
    ),
    ViewSpec(
        name="strain",
        columns=INTERFACE_STRAIN_COLUMNS,
        display_labels=(
            ("id_short", "id"),
            ("strain_alpha", "alpha"),
            ("deformation_state", "state"),
            (
                "lower_construction_max_abs_principal_log_strain",
                "lower_construct",
            ),
            (
                "upper_construction_max_abs_principal_log_strain",
                "upper_construct",
            ),
            (
                "lower_incremental_matching_max_abs_principal_log_strain",
                "lower_match",
            ),
            (
                "upper_incremental_matching_max_abs_principal_log_strain",
                "upper_match",
            ),
            (
                "lower_current_total_max_abs_principal_log_strain",
                "lower_total",
            ),
            (
                "upper_current_total_max_abs_principal_log_strain",
                "upper_total",
            ),
            (
                "relaxation_cell_max_abs_principal_log_strain",
                "relax_cell",
            ),
        ),
        description=(
            "Construction, incremental matching, current total, and relaxation "
            "principal-log-strain diagnostics."
        ),
    ),
    ViewSpec(
        name="provenance",
        columns=INTERFACE_PROVENANCE_COLUMNS,
        description="Interface identity, lineage, artifact, and authority metadata.",
    ),
    ViewSpec(
        name="all",
        columns=INTERFACE_ALL_BASE_COLUMNS,
        aliases=("full",),
        allow_extra_columns=True,
        description="Complete normalized public interface row.",
    ),
)


def attach_interface_realized_geometry(
    row: Mapping[str, Any],
    atoms: Any,
) -> dict[str, Any]:
    """Attach geometry derived from the realized atomistic interface cell."""

    result = dict(row)
    if result.get("prototype_area_A2") is None:
        result["prototype_area_A2"] = result.get("area_A2")
    n_atoms = actual_natoms_from_atoms(atoms)
    if n_atoms is None or n_atoms < 1:
        raise ValueError("A realized interface must contain at least one atom.")
    area = actual_interface_area_A2_from_atoms(atoms)
    result.update(
        {
            "n_atoms": int(n_atoms),
            "natoms": int(n_atoms),
            "area_A2": area,
            "interface_area": area,
            "interface_area_A2": area,
        }
    )
    return result


def attach_interface_deformation_diagnostics(
    row: Mapping[str, Any],
    diagnostics: Mapping[str, Any],
) -> dict[str, Any]:
    """Attach one validated deformation-diagnostics projection to an interface."""

    result = dict(row)
    lower = diagnostics["lower"]
    upper = diagnostics["upper"]

    def maximum(side: Mapping[str, Any], component: str) -> float:
        value = side[component]["max_abs_principal_log_strain"]
        return float(value)

    result.update(
        {
            "deformation_state": str(diagnostics["deformation_state"]),
            "lower_construction_max_abs_principal_log_strain": maximum(
                lower, "construction"
            ),
            "upper_construction_max_abs_principal_log_strain": maximum(
                upper, "construction"
            ),
            "lower_incremental_matching_max_abs_principal_log_strain": maximum(
                lower, "incremental_matching"
            ),
            "upper_incremental_matching_max_abs_principal_log_strain": maximum(
                upper, "incremental_matching"
            ),
            "lower_current_total_max_abs_principal_log_strain": maximum(
                lower, "current_total"
            ),
            "upper_current_total_max_abs_principal_log_strain": maximum(
                upper, "current_total"
            ),
            "relaxation_cell_max_abs_principal_log_strain": float(
                diagnostics["relaxation_cell"][
                    "max_abs_principal_log_strain"
                ]
            ),
            "deformation_diagnostics": dict(diagnostics),
        }
    )
    return result


def _mapping(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return {
            str(key): item
            for key, item in value.items()
            if not str(key).startswith("_")
        }
    converter = getattr(value, "to_dict", None)
    if callable(converter):
        result = converter()
        if not isinstance(result, Mapping):
            raise TypeError("to_dict() must return a mapping.")
        return {
            str(key): item
            for key, item in result.items()
            if not str(key).startswith("_")
        }
    state = getattr(value, "__dict__", None)
    if isinstance(state, dict):
        return {
            str(key): item
            for key, item in state.items()
            if not str(key).startswith("_")
        }
    return {}


def _merge_present(target: dict[str, Any], source: Mapping[str, Any]) -> None:
    for key, value in source.items():
        if value is not None:
            target[key] = value
        elif key not in target:
            target[key] = None


def _candidate_context(item: Any) -> dict[str, Any]:
    candidate = getattr(item, "candidate", None)
    if candidate is None:
        return {}
    row = _mapping(candidate)
    allowed = (
        "candidate_id",
        "candidate_uid",
        "prototype_uid",
        "project_prototype_uid",
        "project_prototype_id",
        "search_id",
        "search_name",
        "run_uid",
        "run_id",
        "run_uid_full",
        "run_id_short",
        "material_a",
        "material_b",
        "surface_a",
        "surface_b",
        "surface_a_uid_full",
        "surface_b_uid_full",
        "slab_a_uid_full",
        "slab_b_uid_full",
        "miller_a",
        "miller_b",
        "termination_a",
        "termination_b",
        "termination_shift_a",
        "termination_shift_b",
        "score",
        "d_cell",
        "d_area",
        "d_shape",
        "max_principal_strain",
        "strain_norm",
        "n_atoms_estimate",
        "area_A2",
        "is_pareto",
        "pareto_rank",
    )
    return {key: row.get(key) for key in allowed if row.get(key) is not None}


def _build_context(item: Any) -> dict[str, Any]:
    settings = getattr(item, "build_settings", None)
    if settings is None:
        return {}
    row = _mapping(settings)
    result: dict[str, Any] = {}
    alpha = row.get("alpha")
    if alpha is not None:
        result["strain_alpha"] = float(alpha)
    gap = row.get("gap")
    if gap is not None:
        result["gap_A"] = float(gap)
    vacuum = row.get("vacuum")
    if vacuum is not None:
        result["vacuum_A"] = float(vacuum)
    translation = row.get("translation")
    if isinstance(translation, (list, tuple)) and len(translation) == 2:
        tx, ty = float(translation[0]), float(translation[1])
        result.update(
            {
                "translation_x": tx,
                "translation_y": ty,
                "registry_shift_frac_a": [tx, ty],
            }
        )
    return result


def normalize_interface_public_row(item: Any) -> dict[str, Any]:
    """Return one complete interface row across in-memory and persisted forms."""

    row: dict[str, Any] = {}
    persisted = getattr(item, "_persisted_record", None)

    for source in (persisted, item):
        source_row = _mapping(source)
        if source is item:
            source_row.pop("candidate", None)
            source_row.pop("build_settings", None)
        _merge_present(row, source_row)
        if source is not None:
            _merge_present(row, normalize_interface_row(source))

    for key, value in _candidate_context(item).items():
        row.setdefault(key, value)
    for key, value in _build_context(item).items():
        row.setdefault(key, value)

    spec = row.get("spec") if isinstance(row.get("spec"), Mapping) else {}
    raw_shift = row.get("registry_shift_frac_a")
    if raw_shift is None:
        raw_shift = spec.get("registry_shift_frac_a")
    if raw_shift is None:
        tx, ty = row.get("translation_x"), row.get("translation_y")
        if tx is not None and ty is not None:
            raw_shift = (tx, ty)
    if raw_shift is not None:
        if not isinstance(raw_shift, (list, tuple)) or len(raw_shift) != 2:
            raise TypeError(
                "Interface registry_shift_frac_a must be a two-value sequence."
            )
        if any(
            isinstance(value, bool) or not isinstance(value, Real)
            for value in raw_shift
        ):
            raise TypeError(
                "Interface registry_shift_frac_a values must be real numbers."
            )
        tx, ty = float(raw_shift[0]), float(raw_shift[1])
        if not isfinite(tx) or not isfinite(ty):
            raise ValueError(
                "Interface registry_shift_frac_a values must be finite."
            )
        row["registry_shift_frac_a"] = [tx, ty]

    gap = row.get("gap_A")
    if gap is None:
        gap = row.get("gap")
    if gap is None:
        gap = spec.get("z_padding")
    if gap is not None:
        row["gap_A"] = float(gap)

    vacuum = row.get("vacuum_A")
    if vacuum is None:
        vacuum = row.get("vacuum")
    if vacuum is None:
        vacuum = spec.get("vacuum")
    if vacuum is not None:
        row["vacuum_A"] = float(vacuum)

    project_uid = getattr(item, "project_interface_uid", None)
    project_id = getattr(item, "project_interface_id", None)
    if project_uid is not None:
        row["project_interface_uid"] = str(project_uid)
        row.setdefault("uid_full", str(project_uid))
    if project_id is not None:
        row["project_interface_id"] = str(project_id)
        row.setdefault("id_short", str(project_id))

    row.setdefault("interface_id", row.get("id_short"))
    row.setdefault("interface_uid", row.get("uid_full"))
    row.setdefault("id", row.get("id_short"))
    row.setdefault("structure_id", row.get("id_short"))
    row.setdefault("kind", "interface")
    row.setdefault("stage", "built")
    row.setdefault("n_atoms", row.get("natoms"))
    row.setdefault("natoms", row.get("n_atoms"))
    row.setdefault("area_A2", row.get("interface_area"))
    if row.get("prototype_area_A2") is None:
        row["prototype_area_A2"] = row.get("area_A2")
    row.setdefault("prototype_uid_full", row.get("prototype_uid"))
    row.setdefault("candidate_uid", row.get("prototype_uid_full"))
    row.pop("build_uid", None)
    if persisted is not None:
        row["authority"] = "authoritative"
    else:
        row.setdefault("authority", "projection")
    return row


def resolve_interface_projection(
    rows: Sequence[Any],
    *,
    view: str | None = None,
    include: Sequence[str] | None = None,
    exclude: Sequence[str] | None = None,
) -> ResolvedTableProjection:
    """Resolve interfaces through the shared named-view registry."""

    spec = resolve_view_spec(
        INTERFACE_VIEW_SPECS,
        view=view,
        default_view="summary",
    )
    normalized = [normalize_interface_public_row(row) for row in rows]
    return resolve_table_projection(
        spec,
        normalized,
        include=include,
        exclude=exclude,
    )
