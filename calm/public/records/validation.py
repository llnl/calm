"""User-facing validation helpers for CALM public objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


@dataclass(frozen=True)
class ValidationReport:
    """Structured validation result returned by public facades.

    The report is intentionally small and dependency-free so it can be used by
    examples without importing the project/database stack.
    """

    subject: str
    errors: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    suggestions: tuple[str, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        lines = [f"ValidationReport(subject={self.subject!r}, ok={self.ok})"]
        if self.errors:
            lines.append("  errors:")
            lines.extend(f"    - {x}" for x in self.errors)
        if self.warnings:
            lines.append("  warnings:")
            lines.extend(f"    - {x}" for x in self.warnings)
        if self.suggestions:
            lines.append("  suggestions:")
            lines.extend(f"    - {x}" for x in self.suggestions)
        return "\n".join(lines)

    def raise_for_errors(self) -> None:
        if self.errors:
            raise ValueError(self.summary())


def make_report(
    subject: str,
    *,
    errors: Iterable[str] = (),
    warnings: Iterable[str] = (),
    suggestions: Iterable[str] = (),
) -> ValidationReport:
    return ValidationReport(
        subject=str(subject),
        errors=tuple(str(x) for x in errors),
        warnings=tuple(str(x) for x in warnings),
        suggestions=tuple(str(x) for x in suggestions),
    )
