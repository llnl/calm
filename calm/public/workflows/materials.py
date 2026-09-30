"""Authoritative material-ingest helpers for the public Project facade."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from calm.public.presentation.reporting import ensure_console_reporter


def _mapping_atoms(value: Any) -> Any:
    if value is None or hasattr(value, "get_positions"):
        return value
    if isinstance(value, Mapping):
        from calm.structure.payloads import dict_to_atoms

        return dict_to_atoms(dict(value))
    raise TypeError("material atoms must be ASE-compatible or a current atoms payload")


def material_from_input(obj: Any, *, name: str | None = None):
    """Normalize one supported material input without persistence fallbacks."""
    from calm.public.inputs.materials import Material

    if isinstance(obj, Material):
        return obj
    if isinstance(obj, (str, Path)):
        return Material.from_file(obj, name=name)
    if isinstance(obj, Mapping):
        payload = obj.get("payload")
        metadata = dict(payload) if isinstance(payload, Mapping) else {}
        atoms_value = obj.get("atoms")
        if atoms_value is None and isinstance(payload, Mapping):
            atoms_value = payload.get("atoms")
        atoms = _mapping_atoms(atoms_value)
        label = obj.get("label") or obj.get("name")
        formula = obj.get("formula")
        material = Material(
            name=name or label or formula or "material",
            label=label,
            atoms=atoms,
            formula=formula,
            state=str(obj.get("kind") or obj.get("state") or "raw_bulk"),
            metadata=metadata,
        )
        optimized_with = (
            obj.get("optimized_with")
            or obj.get("calculator")
            or metadata.get("optimized_with")
            or metadata.get("calculator")
        )
        if optimized_with is not None:
            setattr(material, "optimized_with", optimized_with)
        return material
    if hasattr(obj, "get_positions") and hasattr(obj, "get_cell"):
        return Material.from_ase(obj, name=name)
    if hasattr(obj, "uid_full") and hasattr(obj, "payload"):
        return Material.from_workspace(obj)
    raise TypeError(
        "material input must be a Material, structure path, ASE-compatible "
        "atoms object, current material mapping, or persisted bulk record"
    )


def _workspace_kind(material: Any) -> str:
    state = str(getattr(material, "state", "raw_bulk"))
    if state in {"raw_bulk", "reference", "bulk"}:
        return "reference"
    if state in {"optimized_bulk", "optimized"}:
        return "optimized"
    raise ValueError(
        "Material.state must be one of raw_bulk, reference, optimized_bulk, "
        f"or optimized; received {state!r}"
    )


def _authoritative_identity(item: Any) -> tuple[str | None, str | None]:
    if isinstance(item, Mapping):
        return item.get("uid_full"), item.get("id_short")
    return getattr(item, "uid_full", None), getattr(item, "id_short", None)


def persist_material(
    *,
    workspace: Any,
    obj: Any,
    name: str | None = None,
    reporter: Any | None = None,
):
    """Persist one material through the exact current workspace contract."""
    material = material_from_input(obj, name=name)
    label = name or material.label or material.name
    metadata = dict(material.metadata or {})
    structure = material.to_ase()
    kind = _workspace_kind(material)
    optimized_with = getattr(material, "optimized_with", None)
    rep = ensure_console_reporter(reporter)

    with rep.stage("import_material", name=label):
        persisted = workspace.add_bulk(
            structure=structure,
            label=label,
            payload=metadata or None,
            kind=kind,
            optimized_with=optimized_with,
        )
        uid_full, id_short = _authoritative_identity(persisted)
        if not uid_full or not id_short:
            raise RuntimeError(
                "Authoritative material persistence must return uid_full and id_short"
            )
        rep.mapping(
            {
                "name": label,
                "uid_full": uid_full,
                "id_short": id_short,
                "kind": kind,
            },
            title="Material persistence summary",
        )

    from calm.public.inputs.materials import Material

    result = Material.from_workspace(persisted)
    merged = dict(result.metadata or {})
    for key, value in metadata.items():
        merged.setdefault(key, value)
    result.metadata = merged
    return result
