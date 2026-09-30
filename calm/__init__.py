"""CALM's single supported public API.

Use top-level ``calm`` imports and begin persistent workflows with
:func:`open_project`.  Subpackages are implementation details rather than
parallel user APIs.
"""

from __future__ import annotations

from typing import Any

from . import api as _api

__all__ = list(_api.__all__)


def __getattr__(name: str) -> Any:
    if name in _api.PUBLIC_EXPORTS:
        value = _api.resolve(name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_api.PUBLIC_EXPORTS))
