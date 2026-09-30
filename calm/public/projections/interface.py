"""Normalization helpers for interface rows (extracted from _table_rows)."""

from __future__ import annotations

from typing import Any, Mapping

from calm.public.projections.atoms import (
    _as_mapping,
    actual_natoms_from_atoms,
    compact_calculator,
    extract_atoms_like,
    reduced_formula_from_atoms,
)


def _first_present(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def normalize_interface_row(item: Any, *, name: str | None = None) -> dict[str, Any]:
    m = _as_mapping(item)
    payload = (
        m.get("payload")
        if isinstance(m, Mapping) and isinstance(m.get("payload"), Mapping)
        else {}
    )
    spec = (
        m.get("spec")
        if isinstance(m, Mapping) and isinstance(m.get("spec"), Mapping)
        else {}
    )
    params = spec.get("params") if isinstance(spec.get("params"), Mapping) else {}
    atoms_like = extract_atoms_like(item)

    # identity
    id_short = None
    label = None
    if isinstance(m, Mapping):
        id_short = m.get("interface_id") or m.get("id_short") or m.get("id")
        label = m.get("label") or name or m.get("name")
    else:
        id_short = getattr(item, "id_short", None) or getattr(item, "id", None)
        label = name or getattr(item, "label", None) or getattr(item, "name", None)

    # prototype uid short
    proto_uid = None
    if isinstance(m, Mapping):
        proto_uid = (
            m.get("prototype_uid")
            or m.get("prototype_uid_full")
            or _as_mapping(m).get("spec", {}).get("prototype")
        )
    if proto_uid is None:
        proto_uid = getattr(item, "prototype_uid", None)

    prototype_id_short = None
    if isinstance(proto_uid, str) and proto_uid:
        prototype_id_short = proto_uid

    # strain_alpha
    strain_alpha = None
    if isinstance(m, Mapping):
        strain_alpha = _first_present(
            m.get("strain_alpha"),
            m.get("alpha"),
            _as_mapping(m).get("spec", {}).get("strain_alpha"),
        )
    if strain_alpha is None:
        strain_alpha = _first_present(
            getattr(item, "strain_alpha", None),
            getattr(item, "alpha", None),
        )

    # registry shift formatting
    registry_shift = None
    if isinstance(m, Mapping):
        rs = m.get("registry_shift") or _as_mapping(m).get("spec", {}).get(
            "registry_shift_frac_a"
        )
        if isinstance(rs, (list, tuple)) and len(rs) == 2:
            registry_shift = f"[{float(rs[0]):.4f}, {float(rs[1]):.4f}]"
    if registry_shift is None:
        rs2 = getattr(item, "registry_shift", None) or getattr(
            item, "registry_shift_frac_a", None
        )
        if isinstance(rs2, (list, tuple)) and len(rs2) == 2:
            registry_shift = f"[{float(rs2[0]):.4f}, {float(rs2[1]):.4f}]"

    # vacuum
    vacuum = None
    if isinstance(m, Mapping):
        vacuum = _first_present(
            m.get("vacuum"),
            _as_mapping(m).get("spec", {}).get("vacuum"),
        )
    if vacuum is None:
        vacuum = getattr(item, "vacuum", None)

    # formula / natoms
    formula = None
    natoms = None
    if isinstance(m, Mapping):
        formula = m.get("formula")
        natoms = _first_present(m.get("n_atoms"), m.get("natoms"))
    if not formula and atoms_like is not None:
        formula = reduced_formula_from_atoms(atoms_like)
    if natoms is None:
        natoms = actual_natoms_from_atoms(atoms_like)

    calculator = None
    if isinstance(m, Mapping):
        calculator = compact_calculator(
            m.get("calculator") or payload.get("calculator") or m.get("optimized_with")
        )
    if calculator is None:
        calculator = compact_calculator(
            getattr(item, "calculator", None) or getattr(item, "optimized_with", None)
        )

    out = {
        "id_short": id_short,
        "interface_id": id_short,
        "id": id_short,
        "structure_id": id_short,
        "label": label,
        "name": label,
        "build_uid": m.get("build_uid") or getattr(item, "build_uid", None),
        "kind": "interface",
        "prototype_uid": proto_uid,
        "prototype_id_short": prototype_id_short,
        "strain_alpha": float(strain_alpha) if strain_alpha is not None else None,
        "registry_shift": registry_shift,
        "vacuum": float(vacuum) if vacuum is not None else None,
        "formula": formula,
        "natoms": int(natoms) if natoms is not None else None,
        "calculator": calculator,
    }
    # Preserve common provenance/display fields
    for k in (
        "candidate_id",
        "candidate_uid",
        "search_id",
        "search_name",
        "surface_a",
        "surface_b",
        "miller_a",
        "miller_b",
        "area_A2",
        "gap",
        "tags",
    ):
        v = None
        if isinstance(m, Mapping):
            v = m.get(k)
        if v is None:
            v = getattr(item, k, None)
        if v is not None:
            out[k] = v
    # Keep the exact persisted stage and lineage metadata explicit.
    out.setdefault(
        "stage",
        spec.get("stage") or m.get("stage") or getattr(item, "stage", None) or "built",
    )
    out.setdefault(
        "name", out.get("name") or m.get("name") or getattr(item, "name", None)
    )
    for key in (
        "search_name",
        "source_followup_uid",
        "source_run_uid",
        "strain_target_metric",
        "registry_settings",
        "relaxation_backend",
        "relaxation_settings",
        "source_interface_uid",
    ):
        if out.get(key) is None and params.get(key) is not None:
            out[key] = params[key]

    # Ensure presence of common provenance/display fields expected by callers
    if "material_a" not in out:
        out["material_a"] = (
            m.get("material_a") or getattr(item, "material_a", None) or None
        )
    if "material_b" not in out:
        out["material_b"] = (
            m.get("material_b") or getattr(item, "material_b", None) or None
        )
    if "n_atoms" not in out:
        out["n_atoms"] = out.get("natoms")
    # Preserve authoritative project identifiers when present on the row.
    proj_uid = m.get("project_interface_uid") if isinstance(m, Mapping) else None
    if proj_uid is None:
        proj_uid = getattr(item, "project_interface_uid", None)
    if proj_uid is not None:
        out["project_interface_uid"] = proj_uid

    proj_id = m.get("project_interface_id") if isinstance(m, Mapping) else None
    if proj_id is None:
        proj_id = getattr(item, "project_interface_id", None)
    if proj_id is not None:
        out["project_interface_id"] = proj_id
    # propagate explicit translation fields if present
    tx = m.get("translation_x") if isinstance(m, Mapping) else None
    ty = m.get("translation_y") if isinstance(m, Mapping) else None
    if tx is None:
        tx = getattr(item, "translation_x", None)
    if ty is None:
        ty = getattr(item, "translation_y", None)
    if tx is not None:
        out["translation_x"] = tx
    if ty is not None:
        out["translation_y"] = ty
    if isinstance(payload, Mapping) and payload:
        out["payload"] = dict(payload)
    return out
