"""Exact-current public projection for persisted slab/surface records."""

from __future__ import annotations

from typing import Any, Mapping

from calm.project.domain.contracts.slab_record import (
    canonical_miller,
    canonical_slab_record_payload,
)

from calm.public.projections.atoms import _as_mapping


def _current_value(item: Any, mapping: Mapping[str, Any], key: str) -> Any:
    if key in mapping:
        return mapping[key]
    return getattr(item, key, None)


def _required_string(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"Current persisted surfaces require a non-empty {name}.")
    return value


def normalize_slab_row(
    item: Any,
    *,
    workspace: Any | None = None,
) -> dict[str, Any]:
    """Project one exact-current persisted slab into a public row."""

    mapping = _as_mapping(item) or {}
    uid_full = _required_string("uid_full", _current_value(item, mapping, "uid_full"))
    id_short = _required_string("id_short", _current_value(item, mapping, "id_short"))
    bulk_uid_full = _required_string(
        "bulk_uid_full", _current_value(item, mapping, "bulk_uid_full")
    )
    bulk_id_short = _required_string(
        "bulk_id_short", _current_value(item, mapping, "bulk_id_short")
    )
    miller = canonical_miller(_current_value(item, mapping, "miller"))
    payload_raw = _current_value(item, mapping, "payload")
    if not isinstance(payload_raw, Mapping):
        raise ValueError("Current persisted surfaces require a slab-record payload.")
    payload = canonical_slab_record_payload(
        payload_raw,
        bulk_uid_full=bulk_uid_full,
        miller=miller,
    )

    material = None
    calculator = None
    if workspace is not None:
        bulk = workspace.get_bulk(bulk_uid_full)
        if bulk is not None:
            material = getattr(bulk, "label", None)
            calculator = getattr(bulk, "calculator", None)
    if material is None:
        material = _current_value(item, mapping, "material")

    termination = payload["termination"]
    identity = termination["identity"]
    structure = payload["structure"]
    label = _current_value(item, mapping, "label")
    if label is None and material is not None:
        label = f"{material}-{''.join(str(value) for value in miller)}"
    if label is None:
        label = f"surface_{id_short}"

    symmetry = None if identity is None else identity["surface_symmetry"]
    return {
        "structure_id": id_short,
        "id": id_short,
        "id_short": id_short,
        "uid_full": uid_full,
        "surface_uid_full": uid_full,
        "project_slab_uid_full": uid_full,
        "project_slab_id_short": id_short,
        "name": label,
        "label": label,
        "kind": "surface",
        "stage": "generated_surface",
        "material_a": material,
        "material": material,
        "bulk_uid_full": bulk_uid_full,
        "bulk_id_short": bulk_id_short,
        "parent_id": bulk_id_short,
        "bulk": bulk_id_short,
        "formula": structure["formula"],
        "n_atoms": structure["n_atoms"] or 0,
        "natoms": structure["n_atoms"] or 0,
        "area": structure["area_A2"],
        "vacuum": structure["vacuum_A"],
        "thickness": structure["slab_thickness_A"],
        "layers": structure["layers"],
        "created_at": _current_value(item, mapping, "created_at"),
        "calculation": None,
        "candidate_id": None,
        "surface_pair": miller,
        "miller": miller,
        "tags": payload["user_payload"].get("tags"),
        "has_atoms": structure["atoms"] is not None,
        "termination": termination["label"],
        "termination_top": termination["top"],
        "termination_bottom": termination["bottom"],
        "termination_shift": termination["shift"],
        "termination_identity": None if identity is None else identity["primary"],
        "termination_identity_version": None
        if identity is None
        else identity["version"],
        "termination_identity_status": (
            "not_applicable" if identity is None else "versioned"
        ),
        "termination_top_identity": None if identity is None else identity["top"],
        "termination_bottom_identity": None if identity is None else identity["bottom"],
        "termination_pair_identity": None if identity is None else identity["pair"],
        "termination_surface_symmetry": symmetry,
        "termination_surface_symmetry_status": (
            "not_recorded" if identity is None else "validated"
        ),
        "calculator": calculator,
        "payload": payload,
        "_object": item,
    }
