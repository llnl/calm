"""Read-only authoritative structure retrieval for public views and exports."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class ProjectStructureQueryService:
    """Load persisted interface structures through one authoritative path."""

    def __init__(self, *, workspace: Any, repository: Any) -> None:
        self._workspace = workspace
        self._repo = repository

    def get_interface_atoms(
        self,
        identifier: str,
        *,
        registry_shift: tuple[float, float] | None = None,
    ) -> Any:
        """Return atomistic content for one authoritative derived interface.

        Without an override, artifact-backed structures are loaded verbatim and
        spec-only built, strain-partitioned, and registry-refined interfaces are
        reconstructed from their exact persisted construction state. Passing
        ``registry_shift`` reconstructs one non-persisted structural variant at
        the requested fractional-torus coordinate while retaining the persisted
        prototype, strain allocation, internal gap, and boundary vacuum. Relaxed
        structures cannot be reconstructed with an alternate registry shift.
        """
        if not isinstance(identifier, str) or not identifier.strip():
            raise TypeError(
                "interface structure lookup requires a non-empty identifier."
            )
        record = self._repo.get_interface(identifier.strip())
        if not isinstance(record, Mapping):
            raise TypeError("Authoritative interface lookup must return a mapping.")
        row = dict(record)
        durable_identifier = row.get("uid_full") or row.get("id_short")
        if durable_identifier in (None, ""):
            raise RuntimeError(
                "Authoritative interface records must expose durable identity."
            )
        return self._workspace.materialize_derived_interface_atoms(
            str(durable_identifier),
            registry_shift_frac_a=registry_shift,
        )
