"""Followup result query service."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ...domain.models import FollowupResult
from .._uow import fresh_uow, require_uow_factory


class FollowupQueryService:
    """Service for querying followup results.

    This service handles parameter resolution and current-schema database
    filtering for runs, prototypes, and derived interfaces.
    """

    def __init__(self, *, uow_factory: Callable[[], Any]) -> None:
        self._uow_factory = require_uow_factory(
            uow_factory,
            owner="FollowupQueryService",
        )

    def list_results(
        self,
        *,
        run: str | None = None,
        prototype: str | None = None,
        kind: str | None = None,
        limit: int | None = None,
    ) -> list[FollowupResult]:
        """List persisted follow-up summaries.

        Parameters
        ----------
        run : str, optional
            Optional run identifier (r_... or full uid) to filter results.
        prototype : str, optional
            Optional target filter. This may be either:

            - a prototype identifier (p_...) to list results for that *base*
              prototype, regardless of whether the follow-up run was seeded from
              the prototype itself or from a derived interface; or
            - a derived-interface identifier (i_...) to list only results whose
              recorded target was that specific interface variant.
        kind : str, optional
            Optional follow-up kind filter (e.g., "strain_partition_scan").
        limit : int, optional
            Optional maximum number of results to return.

        Returns
        -------
        list[FollowupResult]
            List of followup results matching the filters.

        Raises
        ------
        KeyError
            If derived interface not found.
        ValueError
            If prototype filter is invalid.
        """
        with fresh_uow(
            self._uow_factory,
            owner="FollowupQueryService",
        ) as uow:
            run_uid_full = uow.ids.resolve_run(run) if run is not None else None

            proto_uid_full: str | None = None
            iface_uid_full: str | None = None

            if prototype is not None:
                proto_uid_full, iface_uid_full = self._resolve_prototype_filter(
                    uow, prototype
                )

            # Interface filters use the dedicated target columns.
            if iface_uid_full is not None:
                return self._list_interface_results(
                    uow,
                    run_uid_full=run_uid_full,
                    proto_uid_full=proto_uid_full,
                    iface_uid_full=iface_uid_full,
                    kind=kind,
                    limit=limit,
                )

            # Standard prototype-level query
            return uow.followups.list(
                run_uid_full=run_uid_full,
                prototype_uid_full=proto_uid_full,
                kind=kind,
                limit=limit,
            )

    def get_result(self, identifier: str) -> FollowupResult:
        """Return one authoritative follow-up result by full or short ID."""
        with fresh_uow(
            self._uow_factory,
            owner="FollowupQueryService",
        ) as uow:
            uid_full = uow.ids.resolve(identifier, expected_tag="f")
            result = uow.followups.get_by_uid_full(uid_full)
            if result is None:
                raise KeyError(f"Follow-up result not found: {identifier}")
            return result

    def _resolve_prototype_filter(
        self, uow: Any, prototype: str
    ) -> tuple[str | None, str | None]:
        """Resolve prototype filter to prototype and interface UIDs.

        Parameters
        ----------
        uow : Any
            Unit of work for ID resolution.
        prototype : str
            Prototype or interface identifier.

        Returns
        -------
        tuple[str | None, str | None]
            Tuple of (proto_uid_full, iface_uid_full).

        Raises
        ------
        KeyError
            If derived interface not found.
        ValueError
            If identifier resolves to invalid type.
        """
        resolved = uow.ids.resolve(prototype)

        if resolved.startswith("proto:"):
            return resolved, None

        if resolved.startswith("iface:"):
            iface = uow.derived_interfaces.get_by_uid_full(resolved)
            if iface is None:
                raise KeyError(
                    f"No derived interface found for identifier {prototype!r}"
                )
            return iface.prototype_uid_full, resolved

        raise ValueError(
            "prototype filter must resolve to a prototype or derived-interface uid_full. "
            f"Got {prototype!r} -> {resolved!r}."
        )

    def _list_interface_results(
        self,
        uow: Any,
        *,
        run_uid_full: str | None,
        proto_uid_full: str | None,
        iface_uid_full: str,
        kind: str | None,
        limit: int | None,
    ) -> list[FollowupResult]:
        """List follow-up results for one derived interface."""

        return uow.followups.list(
            run_uid_full=run_uid_full,
            prototype_uid_full=proto_uid_full,
            target_uid_full=iface_uid_full,
            target_kind="interface",
            kind=kind,
            limit=limit,
        )
