"""Compile fenced Python snippets in the root README without executing them."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


FENCE_RE = re.compile(r"```(?P<lang>[^\n`]*)\n(?P<body>.*?)\n```", re.DOTALL)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _extract_python_fences(markdown: str) -> Iterable[str]:
    for match in FENCE_RE.finditer(markdown):
        if (match.group("lang") or "").strip().lower() in {"python", "py", "python3"}:
            yield match.group("body") or ""


def _normalize_doctest_prompts(code: str) -> str:
    lines: list[str] = []
    for line in code.splitlines():
        if line.startswith(">>>") or line.startswith("..."):
            lines.append(line[3:].lstrip())
        else:
            lines.append(line)
    normalized = "\n".join(lines).strip()
    return normalized + ("\n" if normalized else "")


@dataclass(frozen=True)
class FenceError:
    block_index: int
    message: str
    snippet: str


def test_readme_python_fenced_code_blocks_compile() -> None:
    readme = _repo_root() / "README.md"
    assert readme.is_file(), "Missing README.md"

    errors: list[FenceError] = []
    for index, body in enumerate(_extract_python_fences(readme.read_text(encoding="utf-8")), start=1):
        code = _normalize_doctest_prompts(body)
        if not code.strip():
            continue
        try:
            compile(code, filename=str(readme), mode="exec")
        except SyntaxError as exc:
            errors.append(
                FenceError(
                    block_index=index,
                    message=f"{type(exc).__name__}: {exc}",
                    snippet="\n".join(body.strip().splitlines()[:25]),
                )
            )

    assert errors == [], "README Python fences failed to compile:\n" + "\n".join(
        f"- block {error.block_index}: {error.message}\n{error.snippet}"
        for error in errors
    )
