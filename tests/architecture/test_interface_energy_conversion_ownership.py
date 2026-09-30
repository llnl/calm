"""Ownership guardrails for interface-energy unit conversion."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = ROOT / "calm"
CONSTANT_NAME = "EV_PER_A2_TO_J_PER_M2"
CONTRACT_MODULE = "calm.interface.energy.contract"
CONTRACT_PATH = Path("calm/interface/energy/contract.py")


def _relative(path: Path) -> Path:
    return path.relative_to(ROOT)


def _assigned_names(node: ast.AST) -> set[str]:
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return {node.target.id}
    if isinstance(node, ast.Assign):
        return {
            target.id
            for target in node.targets
            if isinstance(target, ast.Name)
        }
    return set()


def _symbol_imports(path: Path, symbol: str) -> list[ast.alias]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [
        alias
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module == CONTRACT_MODULE
        for alias in node.names
        if alias.name == symbol
    ]


def test_interface_energy_conversion_has_one_literal_owner() -> None:
    assignments: list[tuple[Path, ast.expr | None]] = []

    for path in sorted(PACKAGE_ROOT.rglob("*.py")):
        relative = _relative(path)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if CONSTANT_NAME in _assigned_names(node):
                value = (
                    node.value
                    if isinstance(node, (ast.Assign, ast.AnnAssign))
                    else None
                )
                assignments.append((relative, value))

    assert len(assignments) == 1
    owner_path, owner_value = assignments[0]
    assert owner_path == CONTRACT_PATH
    assert isinstance(owner_value, ast.Constant)
    assert isinstance(owner_value.value, float)

    literal_sites = {
        _relative(path)
        for path in sorted(PACKAGE_ROOT.rglob("*.py"))
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.Constant) and node.value == owner_value.value
    }
    assert literal_sites == {CONTRACT_PATH}


def test_result_module_explicitly_reexports_the_contract_value() -> None:
    imports = _symbol_imports(
        ROOT / "calm" / "interface" / "results.py",
        CONSTANT_NAME,
    )
    assert len(imports) == 1
    assert imports[0].asname == CONSTANT_NAME


def test_internal_energy_kernels_use_private_contract_bindings() -> None:
    for relative in (
        "calm/interface/energy/_kernel.py",
        "calm/interface/energy/reference.py",
    ):
        imports = _symbol_imports(ROOT / relative, CONSTANT_NAME)
        assert len(imports) == 1
        assert imports[0].asname == f"_{CONSTANT_NAME}"
