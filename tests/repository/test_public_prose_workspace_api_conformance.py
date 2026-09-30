from __future__ import annotations

import ast
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_SOURCE = ROOT / "calm" / "project" / "runtime" / "workspace.py"
PUBLIC_PROSE_PATHS = (
    ROOT / "README.md",
    ROOT / "public_api.md",
    ROOT / "examples" / "README.md",
)
WORKSPACE_CALL_RE = re.compile(r"\bws\.([A-Za-z_]\w*)\s*\(")
FORBIDDEN_WORKSPACE_PATTERNS = {
    "slab_a_id=": "Workspace.start_prototype_search uses `slab_a` or positional arguments.",
    "slab_b_id=": "Workspace.start_prototype_search uses `slab_b` or positional arguments.",
}


def _workspace_methods() -> set[str]:
    tree = ast.parse(WORKSPACE_SOURCE.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "Workspace":
            return {
                item.name
                for item in node.body
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                and item.name != "__init__"
            }
    raise AssertionError(f"Could not find class Workspace in {WORKSPACE_SOURCE}")


def _public_prose() -> tuple[Path, ...]:
    missing = [path.relative_to(ROOT).as_posix() for path in PUBLIC_PROSE_PATHS if not path.is_file()]
    assert missing == [], f"Missing public prose files: {missing}"
    return PUBLIC_PROSE_PATHS


def test_public_prose_does_not_call_missing_workspace_methods() -> None:
    methods = _workspace_methods()
    offenders: list[str] = []

    for path in _public_prose():
        rel = path.relative_to(ROOT).as_posix()
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            for match in WORKSPACE_CALL_RE.finditer(line):
                method = match.group(1)
                if method not in methods:
                    offenders.append(
                        f"{rel}:{line_number}: ws.{method}(...) is not implemented on Workspace"
                    )

    assert offenders == [], "Public prose calls missing Workspace methods:\n" + "\n".join(offenders)


def test_public_prose_avoids_stale_workspace_signature_patterns() -> None:
    offenders: list[str] = []

    for path in _public_prose():
        rel = path.relative_to(ROOT).as_posix()
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            for pattern, reason in FORBIDDEN_WORKSPACE_PATTERNS.items():
                if pattern in line:
                    offenders.append(f"{rel}:{line_number}: contains {pattern!r}. {reason}")

    assert offenders == [], "Public prose contains stale Workspace signatures:\n" + "\n".join(offenders)
