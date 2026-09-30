"""Dependency-light tests for the package-organization retirement checker."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from engineering.qualification import check_package_organization as checker


def _current_retirement() -> dict[str, object]:
    retirement = checker._load_contract()["retirement"]
    assert isinstance(retirement, dict)
    return deepcopy(retirement)


def test_retirement_schema_rejects_duplicate_import_authority() -> None:
    retirement = _current_retirement()
    retired_modules = retirement["retired_modules"]
    additional = retirement["additional_prohibited_import_prefixes"]
    assert isinstance(retired_modules, list)
    assert isinstance(additional, list)
    additional.append(retired_modules[0])
    additional.sort()

    with pytest.raises(ValueError, match="duplicates retired_modules"):
        checker._validate_retirement_contract({"retirement": retirement})


def test_retired_module_file_and_tree_verifiers_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(checker, "REPO_ROOT", tmp_path)
    module_path = tmp_path / "calm" / "legacy.py"
    module_path.parent.mkdir(parents=True)
    module_path.write_text("VALUE = 1\n", encoding="utf-8")
    retirement = {
        "retired_modules": ["calm.legacy"],
        "additional_prohibited_import_prefixes": [],
        "retired_files": ["calm/legacy.py"],
        "retired_source_trees": ["calm"],
    }

    with pytest.raises(AssertionError, match="Retired module paths"):
        checker._verify_retired_modules(retirement)
    with pytest.raises(AssertionError, match="Retired files"):
        checker._verify_retired_files(retirement)
    with pytest.raises(AssertionError, match="Retired source trees"):
        checker._verify_retired_source_trees(retirement)


def test_retired_source_symbol_verifier_requires_active_owner_and_absence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(checker, "REPO_ROOT", tmp_path)
    retirement = {
        "retired_source_symbols": {
            "calm/current.py": ["def retired_alias("],
        }
    }

    with pytest.raises(AssertionError, match="missing active source"):
        checker._verify_retired_source_symbols(retirement)

    source = tmp_path / "calm" / "current.py"
    source.parent.mkdir(parents=True)
    source.write_text("def retired_alias():\n    return None\n", encoding="utf-8")
    with pytest.raises(AssertionError, match="Retired source symbols"):
        checker._verify_retired_source_symbols(retirement)


def test_retired_attribute_verifier_rejects_runtime_alias(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        checker.importlib,
        "import_module",
        lambda _name: SimpleNamespace(retired_alias=object()),
    )
    retirement = {
        "retired_attributes": {"calm.current": ["retired_alias"]},
    }

    with pytest.raises(AssertionError, match="Retired runtime attributes"):
        checker._verify_retired_attributes(retirement)


@pytest.mark.parametrize(
    "authority",
    ("retired_modules", "additional_prohibited_import_prefixes"),
)
def test_active_import_verifier_uses_retirement_authority(
    authority: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = tmp_path / "calm"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "current.py").write_text("import calm.legacy\n", encoding="utf-8")
    monkeypatch.setattr(checker, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(checker, "PACKAGE_ROOT", package)
    retirement = {
        "retired_modules": [],
        "additional_prohibited_import_prefixes": [],
    }
    retirement[authority] = ["calm.legacy"]
    contract = {
        "active_import_roots": ["calm"],
        "retirement": retirement,
    }

    with pytest.raises(AssertionError, match="imports retired CALM paths"):
        checker._verify_active_imports(contract)
