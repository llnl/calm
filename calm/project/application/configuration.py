"""Application service for authoritative project configuration."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ._uow import fresh_uow, require_uow_factory


def get_project_configuration(
    uow_factory: Callable[[], Any],
) -> dict[str, Any] | None:
    """Return the sole authoritative project-configuration row."""

    factory = require_uow_factory(
        uow_factory,
        owner="get_project_configuration",
    )
    with fresh_uow(factory, owner="get_project_configuration") as uow:
        return uow.project_configuration.get()


def set_project_configuration(
    uow_factory: Callable[[], Any],
    *,
    mlip: str | None = None,
    calculator_uid_full: str | None = None,
    workflow_defaults: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create or update the exact authoritative configuration row.

    A project may acquire one MLIP family and one calculator identity. Repeating
    either value is idempotent; replacing it is rejected. Omitted fields preserve
    the existing row.
    """

    factory = require_uow_factory(
        uow_factory,
        owner="set_project_configuration",
    )
    with fresh_uow(factory, owner="set_project_configuration") as uow:
        repository = uow.project_configuration
        existing = dict(repository.get() or {})
        current_mlip = existing.get("default_mlip")
        current_calculator = existing.get("default_calculator_uid_full")

        if current_mlip and mlip:
            if str(current_mlip).strip().lower() != str(mlip).strip().lower():
                raise RuntimeError(
                    f"Project already uses MLIP {current_mlip!r}; "
                    f"cannot replace it with {mlip!r}."
                )
        if current_calculator and calculator_uid_full:
            if str(current_calculator) != str(calculator_uid_full):
                raise RuntimeError(
                    "Project already uses a different calculator identity; "
                    "create a new project to change calculators."
                )

        return repository.upsert(
            default_mlip=mlip or current_mlip,
            default_calculator_uid_full=(calculator_uid_full or current_calculator),
            workflow_defaults=(
                dict(workflow_defaults)
                if workflow_defaults is not None
                else existing.get("workflow_defaults")
            ),
        )
