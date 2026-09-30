"""Deterministic identity helpers for persisted interface searches."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from calm.public.inputs.settings import SearchSettings

SEARCH_IDENTITY_SCHEMA_VERSION = 2
SEARCH_IMPLEMENTATION = "primitive_coupled_pair_v2"


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _surface_identity(surface: Any, *, role: str) -> dict[str, Any]:
    uid_full = getattr(surface, "project_slab_uid_full", None)
    id_short = getattr(surface, "project_slab_id_short", None)
    if not uid_full:
        raise ValueError(
            "Project-backed interface searches require persisted surfaces with "
            f"authoritative slab identities; {role} has no project_slab_uid_full. "
            "Select it through project.surface(...) or project.surfaces(...)."
        )
    miller = getattr(surface, "miller", None)
    return {
        "uid_full": str(uid_full),
        "id_short": str(id_short) if id_short is not None else None,
        "material": getattr(surface, "material", None),
        "miller": list(miller) if miller is not None else None,
        "termination": getattr(surface, "termination", None),
        "termination_shift": getattr(surface, "termination_shift", None),
    }


def build_search_identity(
    surface_a: Any,
    surface_b: Any,
    settings: SearchSettings,
) -> tuple[str, dict[str, Any]]:
    """Return ``(search_identity, canonical_run_spec)``.

    Human-readable names are intentionally excluded from the canonical spec so
    the scientific identity depends only on the selected persisted surfaces,
    operational settings, and implementation version.
    """

    settings.validate()
    scientific_spec: dict[str, Any] = {
        "schema_version": SEARCH_IDENTITY_SCHEMA_VERSION,
        "implementation": SEARCH_IMPLEMENTATION,
        "surface_a": _surface_identity(surface_a, role="surface_a"),
        "surface_b": _surface_identity(surface_b, role="surface_b"),
        "settings": settings.to_dict(),
    }
    digest = hashlib.sha256(_stable_json(scientific_spec).encode("utf-8")).hexdigest()
    identity = f"interface_search:{digest}"
    run_spec = dict(scientific_spec)
    run_spec["search_identity"] = identity
    return identity, run_spec


def normalize_search_error(exc: BaseException) -> dict[str, Any]:
    """Return a compact JSON-serializable failure payload."""

    return {
        "type": type(exc).__name__,
        "message": str(exc),
        "module": type(exc).__module__,
    }
