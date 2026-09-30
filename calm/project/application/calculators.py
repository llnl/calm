"""Authoritative calculator-registry application service."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from calm.calculators.spec import CalculatorSpec
from calm.project.domain.identity_v2 import (
    calculator_identity_payload,
    persisted_entity_uid_v2,
)

from ..domain.models import Calculator, CalculatorSummary
from ._uow import fresh_uow, require_entered_uow, require_uow_factory


class CalculatorsService:
    """Register and query calculator specifications through exact UoW scopes."""

    def __init__(self, *, uow_factory: Callable[[], Any]) -> None:
        self._uow_factory = require_uow_factory(
            uow_factory,
            owner="CalculatorsService",
        )

    @staticmethod
    def register_in(uow: Any, spec: CalculatorSpec) -> Calculator:
        """Register ``spec`` inside an already active transaction."""

        require_entered_uow(uow, owner="CalculatorsService.register_in")
        if not isinstance(spec, CalculatorSpec):
            raise TypeError("Calculator registration requires a CalculatorSpec.")

        canonical_spec = spec.to_dict()
        uid_full = persisted_entity_uid_v2(
            "calculator",
            calculator_identity_payload(spec=canonical_spec),
        )
        existing = uow.calculators.get_by_uid_full(uid_full)
        if existing is not None:
            return existing

        id_short = uow.ids.ensure_short_id(tag="c", uid_full=uid_full)
        calc = Calculator(
            uid_full=uid_full,
            id_short=id_short,
            family=spec.family,
            model=spec.model,
            device=spec.device or "cpu",
            spec=canonical_spec,
        )
        stored = uow.calculators.upsert(calc)
        if stored.uid_full != uid_full or stored.id_short != id_short:
            raise RuntimeError(
                "Calculator repository returned an identity inconsistent with "
                "the canonical calculator specification."
            )
        return stored

    def register(self, spec: CalculatorSpec) -> Calculator:
        """Register a calculator specification atomically and idempotently."""

        with fresh_uow(self._uow_factory, owner="CalculatorsService") as uow:
            return self.register_in(uow, spec)

    def get(self, uid_or_short: str) -> Calculator | None:
        """Return one calculator by canonical UID or short ID."""

        identifier = str(uid_or_short).strip()
        if not identifier:
            raise ValueError("Calculator identifier must be non-empty.")
        with fresh_uow(self._uow_factory, owner="CalculatorsService") as uow:
            uid_full = uow.ids.resolve(identifier, expected_tag="c")
            return uow.calculators.get_by_uid_full(uid_full)

    def list(self, *, limit: int | None = None) -> list[CalculatorSummary]:
        """List persisted calculator summaries."""

        with fresh_uow(self._uow_factory, owner="CalculatorsService") as uow:
            return uow.calculators.list(limit=limit)
