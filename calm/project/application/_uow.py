"""Shared Unit-of-Work ownership helpers for application services."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def require_uow_factory(
    uow_factory: Callable[[], Any],
    *,
    owner: str,
) -> Callable[[], Any]:
    """Validate and return one application-service Unit-of-Work factory."""

    if not callable(uow_factory):
        raise TypeError(f"{owner} requires a callable UnitOfWork factory.")
    return uow_factory


def fresh_uow(uow_factory: Callable[[], Any], *, owner: str) -> Any:
    """Return one fresh, non-entered UnitOfWork from ``uow_factory``."""

    uow = uow_factory()
    if uow is None:
        raise RuntimeError(f"{owner} UnitOfWork factory returned None.")
    if int(getattr(uow, "_depth", 0) or 0) != 0:
        raise ValueError(f"{owner} requires a fresh non-entered UnitOfWork.")
    return uow


def require_entered_uow(uow: Any, *, owner: str) -> Any:
    """Require a UnitOfWork whose transaction context is already active."""

    depth = getattr(uow, "_depth", None)
    if depth is not None and int(depth or 0) <= 0:
        raise ValueError(f"{owner} requires an entered UnitOfWork.")
    return uow
