"""Current packaging and lint tooling must not retain legacy root shims."""

from __future__ import annotations

from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10
    import tomli as tomllib


REPO_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = REPO_ROOT / "pyproject.toml"
PACKAGING_CHECKER = (
    REPO_ROOT / "engineering" / "qualification" / "check_packaging_contract.py"
)


def test_legacy_root_packaging_and_flake8_shims_are_absent() -> None:
    assert not (REPO_ROOT / "setup.py").exists()
    assert not (REPO_ROOT / ".flake8").exists()


def test_pyproject_is_the_only_python_build_configuration() -> None:
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    assert data["build-system"] == {
        "requires": ["setuptools>=77", "wheel"],
        "build-backend": "setuptools.build_meta",
    }


def test_ruff_does_not_carry_unreachable_per_file_ignores() -> None:
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    ruff = data["tool"]["ruff"]
    excluded = set(ruff.get("extend-exclude", ()))
    per_file_ignores = ruff.get("lint", {}).get("per-file-ignores", {})
    assert not (set(per_file_ignores) & excluded)


def test_packaging_checker_rejects_legacy_root_shims() -> None:
    text = PACKAGING_CHECKER.read_text(encoding="utf-8")
    assert 'FORBIDDEN_LEGACY_ROOT_FILES = (".flake8", "setup.py")' in text
    assert "legacy packaging or lint shim must be removed" in text
