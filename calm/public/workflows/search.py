"""Public search helpers and convenience wrappers."""

from __future__ import annotations

from typing import Any

from calm.public.inputs.requests import InterfaceRequest, SurfacePair
from calm.public.records.interfaces import InterfaceSearchResult
from calm.public.inputs.settings import SearchSettings
from calm.public.records.surfaces import Surface


def _coerce_surface(obj: Any) -> Surface:
    """Return one current project-generated or explicit Surface request."""
    if isinstance(obj, Surface):
        return obj
    to_surface = getattr(obj, "to_surface", None)
    if not callable(to_surface):
        raise TypeError(
            "Interface searches require Surface objects or project-generated "
            "surfaces returned by Project.generate_surfaces(...)."
        )
    surface = to_surface()
    if not isinstance(surface, Surface):
        raise TypeError("to_surface() must return a calm public Surface object.")
    return surface


def search_interfaces(
    surface_a: Any,
    surface_b: Any,
    *,
    settings: SearchSettings | None = None,
    name: str | None = None,
    reporter: Any | None = None,
) -> InterfaceSearchResult:
    """Run the in-memory scientific kernel for one Project-owned search."""
    resolved_settings = settings or SearchSettings()
    surf_a = _coerce_surface(surface_a)
    surf_b = _coerce_surface(surface_b)
    request = InterfaceRequest(
        pair=SurfacePair(surf_a, surf_b, label=name),
        search=resolved_settings,
        name=name,
    )

    cfg = resolved_settings.to_internal_config()
    slab_a = surf_a.to_slab()
    slab_b = surf_b.to_slab()

    from calm.interface.pipeline import find_prototypes
    from calm.public.presentation.reporting import ensure_console_reporter

    rep = ensure_console_reporter(reporter)
    with rep.section("Search interfaces"):
        rep.mapping(
            {
                "name": name or "<unnamed>",
                "surface_a": getattr(surf_a, "label", None),
                "surface_b": getattr(surf_b, "label", None),
            },
            title="search",
        )
        internal = find_prototypes(slab_a, slab_b, config=cfg)

    return InterfaceSearchResult.from_internal(
        internal,
        request=request,
        surface_a=surf_a,
        surface_b=surf_b,
    )
