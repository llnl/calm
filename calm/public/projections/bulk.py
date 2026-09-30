"""Normalization helpers for bulk rows (extracted from _table_rows)."""

from __future__ import annotations

from typing import Any, Mapping

from calm.public.projections.atoms import (
    _as_mapping,
    actual_natoms_from_atoms,
    compact_calculator,
    extract_atoms_like,
    normalize_spacegroup,
    reduced_formula_from_atoms,
)


def normalize_bulk_row(item: Any, *, name: str | None = None) -> dict[str, Any]:
    """Return a canonical bulk row from either a mapping or object.

    Precedence: top-level canonical fields > payload-derived > atoms-derived.
    """
    m = _as_mapping(item)
    payload: Mapping[str, Any] = {}
    if isinstance(m, Mapping):
        raw_payload = m.get("payload")
        if raw_payload is not None:
            if not isinstance(raw_payload, Mapping):
                raise TypeError("Persisted bulk payload must be a mapping or None.")
            payload = raw_payload

    # durable identity and display label
    uid_full = None
    id_short = None
    label = None
    if isinstance(m, Mapping):
        uid_full = m.get("uid_full") or m.get("project_bulk_uid")
        id_short = m.get("id_short") or m.get("id")
        label = m.get("label") or name or m.get("name")
    else:
        uid_full = getattr(item, "uid_full", None) or getattr(
            item, "project_bulk_uid", None
        )
        id_short = getattr(item, "id_short", None) or getattr(item, "id", None)
        label = name or getattr(item, "label", None) or getattr(item, "name", None)

    # kind
    kind = None
    if isinstance(m, Mapping):
        kind = m.get("kind") or payload.get("kind")
        if kind is not None:
            kind = str(kind).strip().lower()
            if kind in {"optimized", "optimized_bulk"}:
                kind = "optimized"
            elif kind in {"reference", "raw_bulk", "bulk"}:
                kind = "reference"
    if kind is None:
        kind = getattr(item, "kind", None) or getattr(item, "state", None)

    # atoms
    atoms_like = extract_atoms_like(item)

    # formula: prefer explicit derived/payload then atoms
    formula = None
    if isinstance(m, Mapping):
        derived = payload.get("derived")
        if derived is not None and not isinstance(derived, Mapping):
            raise TypeError("Persisted bulk derived metadata must be a mapping.")
        if isinstance(derived, Mapping):
            formula = derived.get("formula")
        if not formula:
            formula = m.get("formula") or payload.get("formula")
    if not formula:
        formula = getattr(item, "formula", None)
    if not formula and atoms_like is not None:
        formula = reduced_formula_from_atoms(atoms_like)

    # natoms: prefer explicit fields then atoms
    natoms = None
    if isinstance(m, Mapping):
        derived = payload.get("derived")
        if derived is not None and not isinstance(derived, Mapping):
            raise TypeError("Persisted bulk derived metadata must be a mapping.")
        if isinstance(derived, Mapping):
            natoms = derived.get("n_atoms") or derived.get("natoms")
        if natoms is None:
            natoms = m.get("natoms") or m.get("n_atoms")
    if natoms is None:
        natoms = actual_natoms_from_atoms(atoms_like)
    if natoms is not None:
        if isinstance(natoms, bool):
            raise TypeError("Persisted atom count must be an integer.")
        try:
            natoms = int(natoms)
        except (TypeError, ValueError) as exc:
            raise TypeError("Persisted atom count must be an integer.") from exc
        if natoms < 0:
            raise ValueError("Persisted atom count must be non-negative.")

    # spacegroup
    spacegroup = None
    if isinstance(m, Mapping):
        spacegroup = normalize_spacegroup(
            m.get("spacegroup"),
            payload=payload,
            atoms_like=atoms_like,
        )
    if spacegroup is None:
        spacegroup = normalize_spacegroup(
            getattr(item, "spacegroup", None),
            payload=payload,
            atoms_like=atoms_like,
        )

    # calculator
    calculator = None
    if isinstance(m, Mapping):
        calculator = compact_calculator(
            m.get("calculator")
            or payload.get("calculator")
            or payload.get("optimized_with")
            or m.get("optimized_with")
        )
    if calculator is None:
        calculator = compact_calculator(
            getattr(item, "calculator", None) or getattr(item, "optimized_with", None)
        )

    out = {
        "uid_full": uid_full,
        "id_short": id_short,
        "label": label,
        "kind": kind,
        "formula": formula,
        "natoms": natoms,
        "spacegroup": spacegroup,
        "calculator": calculator,
    }
    # Preserve payload for provenance if present
    if isinstance(payload, Mapping) and payload:
        out["payload"] = dict(payload)
    return out
