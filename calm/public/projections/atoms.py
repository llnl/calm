"""Dependency-light helpers for exact atomistic public-row projections."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _as_mapping(obj: Any) -> Mapping | None:
    if obj is None:
        return None
    if isinstance(obj, Mapping):
        return obj
    converter = getattr(obj, "to_dict", None)
    if callable(converter):
        value = converter()
        if not isinstance(value, Mapping):
            raise TypeError("to_dict() must return a mapping.")
        return dict(value)
    value = getattr(obj, "__dict__", None)
    return value if isinstance(value, dict) else None


def compact_calculator(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        result = value.strip()
        return result or None
    if isinstance(value, Mapping):
        family = value.get("family") or value.get("calculator_family")
        model = value.get("model") or value.get("calculator_model")
    else:
        family = getattr(value, "family", None)
        model = getattr(value, "model", None)
    if isinstance(family, str) and isinstance(model, str):
        family = family.strip()
        model = model.strip()
        if family and model:
            return f"{family}:{model}"
    return None


def extract_atoms_like(obj: Any) -> Any | None:
    """Return an ASE object or exact current atoms payload when present."""

    if obj is None:
        return None
    mapping = _as_mapping(obj)
    if mapping is not None:
        for key in ("atoms", "atoms_conventional"):
            if key in mapping and mapping[key] is not None:
                return mapping[key]
        payload = mapping.get("payload")
        if payload is not None:
            if not isinstance(payload, Mapping):
                raise TypeError("Persisted payload must be a mapping or None.")
            for key in ("atoms", "atoms_conventional"):
                if key in payload and payload[key] is not None:
                    return payload[key]
            structure = payload.get("structure")
            if structure is not None:
                if not isinstance(structure, Mapping):
                    raise TypeError("Persisted structure must be a mapping or None.")
                if structure.get("atoms") is not None:
                    return structure.get("atoms")
    for attribute in ("atoms", "atoms_conventional"):
        if hasattr(obj, attribute):
            value = getattr(obj, attribute)
            if value is not None:
                return value
    return None


def actual_natoms_from_atoms(atoms_like: Any) -> int | None:
    if atoms_like is None:
        return None
    if isinstance(atoms_like, Mapping):
        from calm.structure.payloads import canonical_atoms_payload

        return len(canonical_atoms_payload(atoms_like)["numbers"])
    count = len(atoms_like)
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise ValueError("Atom-like object length must be a non-negative integer.")
    return int(count)


def actual_interface_area_A2_from_atoms(atoms_like: Any) -> float:
    """Return the positive realized area spanned by cell rows zero and one."""

    if atoms_like is None:
        raise ValueError("Interface geometry requires atomistic content.")
    if isinstance(atoms_like, Mapping):
        from calm.structure.payloads import canonical_atoms_payload

        cell = canonical_atoms_payload(atoms_like)["cell"]
    else:
        getter = getattr(atoms_like, "get_cell", None)
        cell = getter() if callable(getter) else getattr(atoms_like, "cell", None)
        if hasattr(cell, "array"):
            cell = cell.array

    import numpy as np

    matrix = np.asarray(cell, dtype=float)
    if matrix.shape != (3, 3) or not np.isfinite(matrix).all():
        raise ValueError("Interface atoms must have one finite 3x3 cell.")
    area = float(np.linalg.norm(np.cross(matrix[0], matrix[1])))
    if not np.isfinite(area) or area <= 0.0:
        raise ValueError("The realized interface cell area must be positive.")
    return area


def reduced_formula_from_atoms(atoms_like: Any) -> str | None:
    if atoms_like is None:
        return None
    if isinstance(atoms_like, Mapping):
        # Current persisted bulk/slab rows own formula separately. Do not invent
        # a chemical formula from atomic numbers at the presentation layer.
        from calm.structure.payloads import canonical_atoms_payload

        canonical_atoms_payload(atoms_like)
        return None
    getter = getattr(atoms_like, "get_chemical_formula", None)
    if not callable(getter):
        raise TypeError("Atom-like objects must provide get_chemical_formula().")
    try:
        formula = str(getter(mode="metal", empirical=True)).strip()
    except TypeError:
        formula = str(getter(empirical=True)).strip()
    return formula or None


def normalize_spacegroup(
    value: Any,
    *,
    payload: Mapping | None = None,
    atoms_like: Any | None = None,
) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, Mapping):
        symbol = value.get("international") or value.get("symbol") or value.get("label")
        number = value.get("number") or value.get("num")
        if isinstance(symbol, str) and symbol.strip() and not isinstance(number, bool):
            if isinstance(number, int) or (
                isinstance(number, str) and number.isdigit()
            ):
                return f"{symbol.strip()} ({int(number)})"
    if isinstance(payload, Mapping):
        derived = payload.get("derived")
        if derived is not None and not isinstance(derived, Mapping):
            raise TypeError("Persisted derived metadata must be a mapping.")
        spacegroup = derived.get("spacegroup") if isinstance(derived, Mapping) else None
        if isinstance(spacegroup, Mapping):
            symbol = spacegroup.get("international") or spacegroup.get("symbol")
            number = spacegroup.get("number")
            if (
                isinstance(symbol, str)
                and symbol.strip()
                and not isinstance(number, bool)
            ):
                if isinstance(number, int) or (
                    isinstance(number, str) and number.isdigit()
                ):
                    return f"{symbol.strip()} ({int(number)})"
    if atoms_like is None or isinstance(atoms_like, Mapping):
        return None
    if not (
        hasattr(atoms_like, "get_cell") and hasattr(atoms_like, "get_scaled_positions")
    ):
        return None
    try:
        from calm.symmetry.spglib_adapter import get_spacegroup
    except ImportError:
        return None
    return get_spacegroup(atoms_like)
