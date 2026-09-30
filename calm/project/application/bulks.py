"""Application service for authoritative bulk-structure persistence."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from calm.calculators.spec import CalculatorSpec
from calm.project.application.bulk_fingerprinting import BulkFingerprintService
from calm.project.domain.identity_v2 import (
    bulk_metadata_identity_payload,
    bulk_structure_identity_payload,
    persisted_entity_uid_v2,
)
from calm.project.domain.models import Bulk, BulkSummary

from ._uow import fresh_uow, require_entered_uow, require_uow_factory
from .calculators import CalculatorsService


class BulksService:
    """Persist and query bulk records through one exact transaction boundary."""

    def __init__(self, *, uow_factory: Callable[[], Any]) -> None:
        self._uow_factory = require_uow_factory(
            uow_factory,
            owner="BulksService",
        )
        self._fingerprinter = BulkFingerprintService()

    def add_bulk(
        self,
        *,
        structure: Any | None = None,
        label: str | None = None,
        payload: dict[str, Any] | None = None,
        kind: str = "reference",
        optimized_with: CalculatorSpec | str | None = None,
    ) -> Bulk:
        """Create or reopen one authoritative bulk record.

        Calculator registration, short-ID allocation, and bulk persistence occur
        in the same transaction.
        """

        kind_norm = self._normalize_bulk_kind(kind, optimized_with)
        with fresh_uow(self._uow_factory, owner="BulksService") as uow:
            calc_uid_full, calc_compact = self._register_calculator_if_needed(
                uow,
                optimized_with,
            )
            if kind_norm == "optimized" and calc_uid_full is None:
                raise ValueError(
                    "Optimized bulks must declare optimized_with (calculator)."
                )

            if structure is None:
                return self._create_metadata_bulk(
                    uow,
                    label=label,
                    payload=payload,
                    kind=kind_norm,
                    calc_uid_full=calc_uid_full,
                    calc_compact=calc_compact,
                )
            return self._create_structure_bulk(
                uow,
                structure=structure,
                label=label,
                user_metadata=payload,
                kind=kind_norm,
                calc_uid_full=calc_uid_full,
                calc_compact=calc_compact,
            )

    @staticmethod
    def _normalize_bulk_kind(
        kind: str,
        optimized_with: CalculatorSpec | str | None,
    ) -> str:
        kind_norm = (kind or "reference").strip().lower()
        if kind_norm not in {"reference", "optimized"}:
            raise ValueError(
                f"Invalid bulk kind {kind!r}; expected 'reference' or 'optimized'."
            )
        if optimized_with is not None:
            return "optimized"
        return kind_norm

    @staticmethod
    def _calculator_spec(
        optimized_with: CalculatorSpec | str | None,
    ) -> CalculatorSpec | None:
        if optimized_with is None:
            return None
        if isinstance(optimized_with, str):
            family, separator, model = optimized_with.strip().partition(":")
            if separator != ":" or not family.strip() or not model.strip():
                raise ValueError(
                    "optimized_with must be in 'family:model' form when "
                    "provided as a string."
                )
            return CalculatorSpec(family=family.strip(), model=model.strip())
        if not isinstance(optimized_with, CalculatorSpec):
            raise TypeError(
                "optimized_with must be a CalculatorSpec or 'family:model' "
                f"string; got {type(optimized_with).__name__}"
            )
        return optimized_with

    @classmethod
    def _register_calculator_if_needed(
        cls,
        uow: Any,
        optimized_with: CalculatorSpec | str | None,
    ) -> tuple[str | None, str | None]:
        require_entered_uow(uow, owner="BulksService")
        spec = cls._calculator_spec(optimized_with)
        if spec is None:
            return None, None
        calculator = CalculatorsService.register_in(uow, spec)
        return calculator.uid_full, f"{calculator.family}:{calculator.model}"

    @staticmethod
    def _persist_bulk(uow: Any, bulk: Bulk) -> Bulk:
        require_entered_uow(uow, owner="BulksService")
        stored = uow.bulks.upsert(bulk)
        if stored.uid_full != bulk.uid_full or stored.id_short != bulk.id_short:
            raise RuntimeError(
                "Bulk repository returned an identity inconsistent with the "
                "canonical bulk payload."
            )
        return stored

    def _create_metadata_bulk(
        self,
        uow: Any,
        *,
        label: str | None,
        payload: dict[str, Any] | None,
        kind: str,
        calc_uid_full: str | None,
        calc_compact: str | None,
    ) -> Bulk:
        payload_out = dict(payload or {})
        uid_full = persisted_entity_uid_v2(
            "bulk",
            bulk_metadata_identity_payload(payload=payload_out),
        )
        id_short = uow.ids.ensure_bulk_id(uid_full)
        return self._persist_bulk(
            uow,
            Bulk(
                uid_full=uid_full,
                id_short=id_short,
                label=label,
                payload=payload_out,
                kind=kind,
                optimized_with_calculator_uid_full=calc_uid_full,
                calculator=calc_compact,
            ),
        )

    def _create_structure_bulk(
        self,
        uow: Any,
        *,
        structure: Any,
        label: str | None,
        user_metadata: dict[str, Any] | None,
        kind: str,
        calc_uid_full: str | None,
        calc_compact: str | None,
    ) -> Bulk:
        payload_out = self._fingerprinter.assemble_structure_payload(
            structure,
            user_metadata=user_metadata,
        )
        fingerprint = payload_out.get("fingerprint")
        if not isinstance(fingerprint, dict):
            raise ValueError("Structure-backed bulk payload lacks fingerprint data.")
        uid_full = persisted_entity_uid_v2(
            "bulk",
            bulk_structure_identity_payload(fingerprint=fingerprint),
        )
        id_short = uow.ids.ensure_bulk_id(uid_full)
        return self._persist_bulk(
            uow,
            Bulk(
                uid_full=uid_full,
                id_short=id_short,
                label=label,
                payload=payload_out,
                kind=kind,
                optimized_with_calculator_uid_full=calc_uid_full,
                calculator=calc_compact,
            ),
        )

    def list_bulks(self, *, limit: int = 50) -> list[BulkSummary]:
        """List persisted bulk summaries."""

        with fresh_uow(self._uow_factory, owner="BulksService") as uow:
            return uow.bulks.list(limit=limit)
