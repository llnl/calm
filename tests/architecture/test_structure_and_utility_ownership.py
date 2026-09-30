"""Guardrails for structure, fingerprint, and serialization ownership."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "calm"


def _imports(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return tuple(modules)


def test_generic_util_source_package_is_deleted_without_compatibility_shims() -> None:
    util = PACKAGE / "util"
    assert not (util / "__init__.py").exists()
    assert not any(
        path.suffix in {".py", ".pyi"}
        for path in util.rglob("*")
        if path.is_file()
    )
    for module in (
        "calm.util.ase_atoms",
        "calm.util.atoms_validation",
        "calm.util.bulk_fingerprinting",
        "calm.util.signature",
        "calm.util.warnings",
    ):
        try:
            importlib.import_module(module)
        except ModuleNotFoundError as exc:
            assert exc.name in {"calm.util", module}
        else:
            raise AssertionError(f"Retired compatibility module is importable: {module}")


def test_current_python_sources_do_not_import_retired_util_paths() -> None:
    offenders: list[str] = []
    for path in sorted(PACKAGE.rglob("*.py")):
        for module in _imports(path):
            if module == "calm.util" or module.startswith("calm.util."):
                offenders.append(f"{path.relative_to(ROOT)}: {module}")
    assert offenders == [], "Retired util imports found:\n" + "\n".join(offenders)


def test_exact_atom_payload_serialization_has_one_structure_owner() -> None:
    owner = (PACKAGE / "structure" / "payloads.py").read_text(encoding="utf-8")
    bulk = (PACKAGE / "bulk" / "fingerprinting.py").read_text(encoding="utf-8")
    service = (
        PACKAGE / "project" / "application" / "bulk_fingerprinting.py"
    ).read_text(encoding="utf-8")

    for name in (
        "canonical_atoms_payload",
        "atoms_to_dict",
        "atoms_from_dict",
        "dict_to_atoms",
    ):
        assert f"def {name}(" in owner
        assert f"def {name}(" not in bulk
    assert "from calm.structure.payloads import atoms_to_dict" in service


def test_bulk_and_regression_helpers_have_explicit_domain_owners() -> None:
    bulk = (PACKAGE / "bulk" / "fingerprinting.py").read_text(encoding="utf-8")
    regression = (
        PACKAGE / "serialization" / "regression.py"
    ).read_text(encoding="utf-8")

    assert "def atoms_fingerprint_to_dict(" in bulk
    assert "def bulk_uid_full_from_atoms_dict(" in bulk
    assert "def deterministic_json(" in regression
    assert "def fingerprint_json(" in regression
    assert "def sha256_hex(" in regression
