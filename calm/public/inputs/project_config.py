"""Authoritative project-configuration helpers.

Project-wide MLIP, calculator, and workflow-default configuration is persisted
exclusively in the workspace database through
:mod:`calm.project.application.configuration`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _uow_factory(project: Any):
    workspace = getattr(project, "_workspace", None)
    factory = getattr(workspace, "_uow_factory", None)
    return factory if callable(factory) else None


def load_configuration(project: Any) -> dict[str, Any]:
    """Load the authoritative project-configuration row.

    Lightweight test doubles that do not expose a project unit-of-work have no
    authoritative configuration and therefore return an empty mapping. Real
    directory-backed projects always provide ``_uow_factory``.
    """

    factory = _uow_factory(project)
    if factory is None:
        return {}

    from calm.project.application.configuration import get_project_configuration

    return dict(get_project_configuration(factory) or {})


def _calculator_spec(value: Any):
    from calm.calculators.spec import CalculatorSpec

    if isinstance(value, CalculatorSpec):
        return value
    if isinstance(value, Mapping):
        return CalculatorSpec.from_dict(value)
    raise TypeError(
        "calculator must be a CalculatorSpec or its exact mapping representation"
    )


def configure(
    project: Any,
    *,
    mlip: str | None = None,
    calculator: Any | None = None,
    defaults: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Persist project-wide configuration in the authoritative database.

    The application service owns single-MLIP and single-calculator conflict
    checks. Workflow defaults are merged explicitly with the current row so a
    partial update cannot erase unrelated defaults.
    """

    factory = _uow_factory(project)
    if factory is None:
        from calm.public.errors import ProjectPersistenceError

        raise ProjectPersistenceError(
            "Project configuration requires a workspace-backed project database."
        )

    existing = load_configuration(project)
    calculator_uid_full = None
    if calculator is not None:
        spec = _calculator_spec(calculator)
        from calm.project.domain.identity_v2 import (
            calculator_identity_payload,
            persisted_entity_uid_v2,
        )

        expected_uid = persisted_entity_uid_v2(
            "calculator",
            calculator_identity_payload(spec=spec.to_dict()),
        )
        current_uid = existing.get("default_calculator_uid_full")
        if current_uid and str(current_uid) != expected_uid:
            raise RuntimeError(
                "Project already uses a different calculator identity; "
                "create a new project to change calculators."
            )

        register = getattr(project._workspace, "register_calculator", None)
        if not callable(register):
            from calm.public.errors import ProjectPersistenceError

            raise ProjectPersistenceError(
                "Workspace backend does not support calculator registration."
            )
        persisted = register(spec)
        calculator_uid_full = str(getattr(persisted, "uid_full", "") or "")
        if calculator_uid_full != expected_uid:
            from calm.public.errors import ProjectPersistenceError

            raise ProjectPersistenceError(
                "Calculator registration returned an identity inconsistent "
                "with the exact CalculatorSpec."
            )

    workflow_defaults = dict(existing.get("workflow_defaults") or {})
    if defaults is not None:
        workflow_defaults.update(dict(defaults))

    from calm.project.application.configuration import set_project_configuration

    updated = set_project_configuration(
        factory,
        mlip=mlip,
        calculator_uid_full=calculator_uid_full,
        workflow_defaults=workflow_defaults or None,
    )
    project._configuration = dict(updated)
    return dict(updated)
