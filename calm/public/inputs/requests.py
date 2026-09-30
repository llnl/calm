"""Public request objects for interface searches."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from calm.public.inputs.settings import SearchSettings


@dataclass(frozen=True)
class SurfacePair:
    """Pair two surface requests for coherent-interface matching.

    The order is significant: ``surface_a`` and ``surface_b`` define the two sides
    used by the search, strain-partition, and construction workflows. ``label`` is
    optional descriptive metadata and does not replace the surfaces' scientific
    identity.
    """

    surface_a: Any
    surface_b: Any
    label: str | None = None

    def summary(self) -> str:
        la = (
            getattr(self.surface_a, "label", None)
            or getattr(self.surface_a, "material", None)
            or "surface_a"
        )
        lb = (
            getattr(self.surface_b, "label", None)
            or getattr(self.surface_b, "material", None)
            or "surface_b"
        )
        return f"SurfacePair({la} | {lb})"


@dataclass(frozen=True)
class InterfaceRequest:
    """Bundle a surface pair with deterministic interface-search settings.

    Calling :meth:`run` executes the geometry search and optionally persists it
    when a project or store is supplied. The request is a lightweight serializable
    configuration object; it is not itself an authoritative project record.
    """

    pair: SurfacePair
    search: SearchSettings = SearchSettings()
    name: str | None = None

    def summary(self) -> str:
        return (
            f"InterfaceRequest(name={self.name!r}, pair={self.pair.summary()}, "
            f"search={self.search})"
        )
