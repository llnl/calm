"""Import-time guardrails for optional calculator and atomistic backends.

The architecture cleanup milestone relies on CALM keeping optional science and
MLIP frameworks lazy. These tests use subprocesses so assertions are isolated
from the current pytest process, which may already have imported optional
packages in earlier tests.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path


OPTIONAL_BACKEND_MODULES = (
    "ase",
    "spglib",
    "lammps",
    "torch",
    "tensorflow",
    "tensorpotential",
    "mace",
    "chgnet",
    "orb_models",
    "sevenn",
    "nequip",
    "allegro",
    "mattersim",
)


def _repo_root() -> Path:
    path = Path(__file__).resolve()
    for parent in [path.parent, *path.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    raise RuntimeError(f"Could not locate repository root from {path}")


def _modules_imported_by(statement: str) -> list[str]:
    repo_root = _repo_root()
    code = textwrap.dedent(
        f"""
        import json
        import sys

        sys.path.insert(0, {str(repo_root)!r})

        {statement}

        optional_modules = {OPTIONAL_BACKEND_MODULES!r}
        loaded = [name for name in optional_modules if name in sys.modules]
        print(json.dumps(loaded))
        """
    ).strip()
    proc = subprocess.run(
        [sys.executable, "-c", code],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=repo_root,
    )
    return json.loads(proc.stdout)


def test_import_calm_does_not_import_optional_backends() -> None:
    loaded = _modules_imported_by("import calm  # noqa: F401")
    assert loaded == []


def test_import_calm_calculators_does_not_import_optional_backends() -> None:
    loaded = _modules_imported_by("import calm.calculators  # noqa: F401")
    assert loaded == []
