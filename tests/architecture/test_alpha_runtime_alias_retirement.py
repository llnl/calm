"""Guardrails for retired alpha aliases and duplicate runtime paths."""

from __future__ import annotations

import ast
from dataclasses import fields
from pathlib import Path

from calm.interface.config import PrototypeSearchConfig
from calm.interface.results import EnergyResult


ROOT = Path(__file__).resolve().parents[2]
PROJECT_SOURCE = ROOT / "calm" / "public" / "project.py"
MATERIAL_SOURCE = ROOT / "calm" / "public" / "inputs" / "materials.py"
MATERIAL_SERVICE_SOURCE = (
    ROOT / "calm" / "public" / "workflows" / "material_optimization.py"
)
COLLECTION_SOURCE = ROOT / "calm" / "public" / "collections" / "base.py"
SURFACE_COLLECTION_SOURCE = ROOT / "calm" / "public" / "collections" / "structures.py"
SETTINGS_SOURCE = ROOT / "calm" / "public" / "inputs" / "settings.py"
MODEL_SOURCE = ROOT / "calm" / "interface" / "model.py"
MATCHING_SOURCE = ROOT / "calm" / "interface" / "matching" / "search.py"
BUILD_KERNEL_SOURCE = ROOT / "calm" / "interface" / "building" / "_kernel.py"
ORIENTED_SLAB_SOURCE = ROOT / "calm" / "slab" / "oriented" / "builder.py"


def _project_method(name: str) -> ast.FunctionDef:
    tree = ast.parse(PROJECT_SOURCE.read_text(encoding="utf-8"))
    project = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Project"
    )
    return next(
        node
        for node in project.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )


def _self_attributes(node: ast.AST) -> set[str]:
    return {
        item.attr
        for item in ast.walk(node)
        if isinstance(item, ast.Attribute)
        and isinstance(item.value, ast.Name)
        and item.value.id == "self"
    }


def test_material_optimization_has_one_project_workflow_owner() -> None:
    method = _project_method("optimize_material")
    assert _self_attributes(method) == {"_material_optimizations"}
    assert method.args.kwarg is None
    assert [arg.arg for arg in method.args.kwonlyargs] == [
        "potential",
        "calculator",
        "fmax",
        "steps",
        "relax_cell",
        "optimizer",
        "name",
        "reporter",
    ]

    material_source = MATERIAL_SOURCE.read_text(encoding="utf-8")
    service_source = MATERIAL_SERVICE_SOURCE.read_text(encoding="utf-8")
    assert "def _optimize(" not in material_source
    assert "class ProjectMaterialOptimizationService" in service_source
    assert "def optimize_material(" in service_source

    api_source = (ROOT / "calm" / "api.py").read_text(encoding="utf-8")
    assert "ProjectMaterialOptimizationService" not in api_source


def test_retired_collection_cardinality_alias_cannot_return() -> None:
    collection_source = COLLECTION_SOURCE.read_text(encoding="utf-8")
    surface_source = SURFACE_COLLECTION_SOURCE.read_text(encoding="utf-8")
    assert "def require_one(" not in collection_source
    assert "def require_one(" not in surface_source
    assert "def one(" in surface_source


def test_retired_result_and_search_config_aliases_are_absent() -> None:
    energy_fields = {item.name for item in fields(EnergyResult)}
    assert {
        "build_uid",
        "gamma_eVA2",
        "gamma_Jm2",
        "interface_area_A2",
        "E_interface_eV",
        "n_atoms_interface",
        "E_slab_a_eV",
        "E_slab_b_eV",
    }.isdisjoint(energy_fields)

    config_fields = PrototypeSearchConfig.__dataclass_fields__
    assert "top_k" not in config_fields

    settings_source = SETTINGS_SOURCE.read_text(encoding="utf-8")
    assert "class ReferenceEnergies" not in settings_source


def test_prototype_uses_one_canonical_field_vocabulary() -> None:
    source = MODEL_SOURCE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    prototype = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "InterfacePrototype"
    )
    method_names = {
        node.name
        for node in prototype.body
        if isinstance(node, ast.FunctionDef)
    }
    assert "uid" not in method_names
    assert "d_gamma" not in method_names
    signature = next(
        node
        for node in prototype.body
        if isinstance(node, ast.FunctionDef) and node.name == "signature"
    )
    assert [arg.arg for arg in signature.args.kwonlyargs] == ["ndigits"]
    prototype_source = ast.get_source_segment(source, prototype) or ""
    assert '"prototype_uid": self.prototype_uid' in prototype_source
    assert '"d_gamma":' not in prototype_source


def test_private_compatibility_reexports_cannot_return() -> None:
    matching = MATCHING_SOURCE.read_text(encoding="utf-8")
    build_kernel = BUILD_KERNEL_SOURCE.read_text(encoding="utf-8")
    oriented_slab = ORIENTED_SLAB_SOURCE.read_text(encoding="utf-8")

    assert "surface_pointgroup_ops_2d =" not in matching
    for alias in (
        "_apply_deformation_gradient =",
        "_rotate_atoms_cartesian =",
        "_zmin_zmax =",
        "_cell_array =",
        "_set_atoms_cell_no_scale =",
    ):
        assert alias not in build_kernel
    assert "verify_surface_kernel_is_primitive =" not in oriented_slab
