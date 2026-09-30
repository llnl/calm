"""Static guardrail: DeprecationWarning must set stacklevel.

When we deprecate public APIs, `warnings.warn(..., DeprecationWarning)` should
always pass an explicit `stacklevel` so the warning points at *user code*
(rather than CALM internals). This test prevents regressions.

We scope the scan to the `calm/` package and perform a lightweight AST walk to
avoid false positives from comments/strings.
"""

from __future__ import annotations

import ast
from pathlib import Path


_DEPRECATION_WARNING_NAMES: set[str] = {
    "DeprecationWarning",
    "PendingDeprecationWarning",
}


def _warnings_import_aliases(tree: ast.AST) -> tuple[set[str], set[str]]:
    """Return (warnings_module_aliases, warnings_warn_aliases)."""

    warnings_modules: set[str] = set()
    warn_names: set[str] = set()

    for node in getattr(tree, "body", []):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "warnings":
                    warnings_modules.add(alias.asname or "warnings")

        elif isinstance(node, ast.ImportFrom):
            if node.module != "warnings":
                continue

            for alias in node.names:
                if alias.name == "warn":
                    warn_names.add(alias.asname or "warn")

    return warnings_modules, warn_names


def _iter_warnings_warn_calls(
    tree: ast.AST,
    *,
    warnings_modules: set[str],
    warn_names: set[str],
) -> list[ast.Call]:
    """Find calls that are (likely) `warnings.warn(...)` invocations."""

    calls: list[ast.Call] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        func = node.func

        # warnings.warn(...)
        if isinstance(func, ast.Attribute) and func.attr == "warn":
            if isinstance(func.value, ast.Name) and func.value.id in warnings_modules:
                calls.append(node)
                continue

        # warn(...) where `warn` came from `from warnings import warn`
        if isinstance(func, ast.Name) and func.id in warn_names:
            calls.append(node)

    return calls


def _category_expr(call: ast.Call) -> ast.expr | None:
    """Best-effort extraction of the warning category expression."""

    for kw in call.keywords:
        if kw.arg == "category":
            return kw.value

    # warnings.warn(message, category, ...)
    if len(call.args) >= 2:
        return call.args[1]

    return None


def _expr_is_deprecationwarning(expr: ast.expr) -> bool:
    if isinstance(expr, ast.Name):
        return expr.id in _DEPRECATION_WARNING_NAMES

    # e.g. warnings.DeprecationWarning
    if isinstance(expr, ast.Attribute):
        return expr.attr in _DEPRECATION_WARNING_NAMES

    return False


def _has_explicit_stacklevel(call: ast.Call) -> bool:
    for kw in call.keywords:
        if kw.arg == "stacklevel":
            return True

    # warnings.warn(message, category, stacklevel)
    return len(call.args) >= 3


def test_deprecation_warnings_use_stacklevel() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    calm_pkg = repo_root / "calm"

    assert calm_pkg.is_dir(), (
        "Expected a `calm/` package directory next to `tests/`. "
        f"Got: {calm_pkg}"
    )

    offenders: list[str] = []

    for py_file in sorted(calm_pkg.rglob("*.py")):
        text = py_file.read_text(encoding="utf-8")

        try:
            tree = ast.parse(text, filename=str(py_file))
        except SyntaxError as exc:
            raise AssertionError(f"Failed to parse {py_file}: {exc}") from exc

        warnings_modules, warn_names = _warnings_import_aliases(tree)
        if not warnings_modules and not warn_names:
            continue

        for call in _iter_warnings_warn_calls(
            tree, warnings_modules=warnings_modules, warn_names=warn_names
        ):
            cat = _category_expr(call)
            if cat is None or not _expr_is_deprecationwarning(cat):
                continue

            if _has_explicit_stacklevel(call):
                continue

            lineno = getattr(call, "lineno", "?")
            rel = py_file.relative_to(repo_root)
            offenders.append(f"{rel}:{lineno}")

    assert not offenders, (
        "DeprecationWarning/PendingDeprecationWarning must pass an explicit "
        "stacklevel so the warning points at user code rather than CALM internals.\n"
        "Add `stacklevel=...` (or a 3rd positional arg) to each call site:\n"
        + "\n".join(offenders)
    )
