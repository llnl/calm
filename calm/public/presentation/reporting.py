"""Reporter boundary for user-facing CALM workflows.

Computational kernels remain silent.  Public orchestration layers may emit
stages, messages, mappings, paths, and summaries through a small structural
reporter protocol.  The default implementation writes human-readable output to
stdout; callers may supply any object implementing the same methods.
"""

from __future__ import annotations

import os
from time import perf_counter
from typing import Any, Iterable, Mapping, Optional, Protocol


class Reporter(Protocol):
    """Structural reporting interface consumed by public orchestration code."""

    def stage(self, label: str, **meta: Any):
        """Return a context manager for a timed workflow stage."""

    def info(self, message: str, **meta: Any) -> None:
        """Emit an informational message."""

    def warn(self, message: str, **meta: Any) -> None:
        """Emit a warning message."""

    def section(self, title: str, **meta: Any):
        """Return a context manager for an untimed logical section."""

    def mapping(self, mapping: Mapping[str, Any], *, title: str | None = None) -> None:
        """Emit a key/value mapping."""

    def paths(self, paths: Iterable[str], *, title: str | None = None) -> None:
        """Emit paths or strings as a bullet list."""

    def summary(self, message: str, **meta: Any) -> None:
        """Emit a short workflow summary."""


def _format_mapping(mapping: Mapping[str, Any], *, indent: int = 2) -> str:
    if not mapping:
        return "(no items)"
    return "\n".join(" " * indent + f"{key}: {value}" for key, value in mapping.items())


def _format_paths(paths: Iterable[str], *, indent: int = 2) -> str:
    items = list(paths)
    if not items:
        return "(no paths)"
    return "\n".join(" " * indent + f"- {path}" for path in items)


class ConsoleReporter:
    """Human-readable stdout reporter with stage timing."""

    def __init__(self, *, enabled: bool = True):
        self.enabled = bool(enabled)
        self._use_color = os.environ.get("CALM_COLOR", "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    def _colorize(self, text: str, color: str) -> str:
        if not self._use_color:
            return text
        codes = {
            "red": "0;31",
            "green": "0;32",
            "yellow": "0;33",
            "blue": "0;34",
            "cyan": "0;36",
        }
        return f"\x1b[{codes.get(color, '0')}m{text}\x1b[0m"

    class _Stage:
        def __init__(self, parent: "ConsoleReporter", label: str, meta: dict[str, Any]):
            self.parent = parent
            self.label = label
            self.meta = meta
            self.started = 0.0

        def __enter__(self):
            if self.parent.enabled:
                print()
                suffix = ""
                if self.meta:
                    suffix = (
                        " ("
                        + " ".join(f"{key}={value}" for key, value in self.meta.items())
                        + ")"
                    )
                print(
                    self.parent._colorize(f"[stage] {self.label}{suffix} ...", "cyan")
                )
                self.started = perf_counter()
            return self

        def __exit__(self, exc_type, exc, tb):
            if not self.parent.enabled:
                return False
            elapsed = perf_counter() - self.started
            if exc_type is None:
                print(
                    self.parent._colorize(
                        f"[done ] {self.label} ({elapsed:.3f}s)", "green"
                    )
                )
            else:
                print(
                    self.parent._colorize(
                        f"[fail ] {self.label} ({elapsed:.3f}s) -> "
                        f"{exc_type.__name__}: {exc}",
                        "red",
                    )
                )
            return False

    class _Section:
        def __init__(self, parent: "ConsoleReporter", title: str, meta: dict[str, Any]):
            self.parent = parent
            self.title = title
            self.meta = meta

        def __enter__(self):
            if self.parent.enabled:
                print()
                suffix = ""
                if self.meta:
                    suffix = (
                        " ("
                        + " ".join(f"{key}={value}" for key, value in self.meta.items())
                        + ")"
                    )
                print(f"[section] {self.title}{suffix}")
                print()
            return self

        def __exit__(self, exc_type, exc, tb):
            if self.parent.enabled and exc_type is not None:
                print(f"[error] section {self.title} -> {exc_type.__name__}: {exc}")
            return False

    def stage(self, label: str, **meta: Any):
        return ConsoleReporter._Stage(self, str(label), dict(meta))

    def info(self, message: str, **meta: Any) -> None:
        if self.enabled:
            print(self._colorize(f"[info ] {message}", "blue"))

    def warn(self, message: str, **meta: Any) -> None:
        if self.enabled:
            print(self._colorize(f"[warn ] {message}", "yellow"))

    def section(self, title: str, **meta: Any):
        return ConsoleReporter._Section(self, str(title), dict(meta))

    def mapping(self, mapping: Mapping[str, Any], *, title: str | None = None) -> None:
        if not self.enabled:
            return
        if title:
            print(f"[info] {title}")
        print()
        print(_format_mapping(mapping))
        print()

    def paths(self, paths: Iterable[str], *, title: str | None = None) -> None:
        if not self.enabled:
            return
        if title:
            print(f"[info] {title}")
        print()
        print(_format_paths(paths))
        print()

    def summary(self, message: str, **meta: Any) -> None:
        if self.enabled:
            print(f"[summary] {message}")


_DEFAULT_CONSOLE_REPORTER: Reporter = ConsoleReporter()


def ensure_console_reporter(reporter: Optional[Reporter]) -> Reporter:
    """Return ``reporter`` or the process-wide console reporter singleton."""

    return reporter if reporter is not None else _DEFAULT_CONSOLE_REPORTER


__all__ = [
    "Reporter",
    "ConsoleReporter",
    "ensure_console_reporter",
]
