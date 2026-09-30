"""Guardrails for exact current names and settings introduced by update 0332."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _function(path: str, name: str) -> ast.FunctionDef:
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    return next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == name
    )


def _class(path: str, name: str) -> ast.ClassDef:
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    return next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == name
    )


def test_internal_scientific_keywords_have_one_name() -> None:
    compute = _function("calm/interface/pipeline.py", "compute_strain_state")
    assert [arg.arg for arg in compute.args.args] == ["prototype", "model"]
    assert not compute.args.kwonlyargs

    cholesky = _function("calm/math2d/spd2x2.py", "cholesky2_spd")
    assert [arg.arg for arg in cholesky.args.kwonlyargs] == ["upper", "tol"]

    chol_upper = _function("calm/math2d/spd2x2.py", "chol_upper")
    assert [arg.arg for arg in chol_upper.args.kwonlyargs] == ["tol"]


def test_slab_settings_use_current_mapping_vocabulary() -> None:
    slab_spec = _class("calm/slab/slab.py", "SlabSpec")
    fields = {
        node.target.id
        for node in slab_spec.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
    }
    assert "stamp_transforms" in fields
    assert "stamp_transforms_json" not in fields
    assert "ase_periodic" not in fields

    to_atoms = _function("calm/slab/slab.py", "to_atoms")
    assert [arg.arg for arg in to_atoms.args.kwonlyargs] == ["stamp_transforms"]


def test_duplicate_regression_json_alias_is_absent() -> None:
    source = (ROOT / "calm/serialization/regression.py").read_text(encoding="utf-8")
    assert "def deterministic_json(" in source
    assert "def stable_json_dumps(" not in source


def test_retired_setting_and_backend_aliases_are_absent() -> None:
    refinement = (ROOT / "calm/interface/refinement/contract.py").read_text(encoding="utf-8")
    for retired in (
        '"gamma":',
        '"interfacial_energy":',
        '"potential_energy":',
        '"e_per_a2":',
    ):
        assert retired not in refinement

    relaxation = (ROOT / "calm/project/domain/contracts/relaxation.py").read_text(encoding="utf-8")
    assert '"L-BFGS"' not in relaxation

    registry = (ROOT / "calm/calculators/registry.py").read_text(encoding="utf-8")
    for retired in ("ase.emt", "ase.lj", "lennardjones", "lennard-jones", "ase.morse"):
        assert retired not in registry

    providers = (ROOT / "calm/calculators/providers.py").read_text(encoding="utf-8")
    for retired in ('"lammpsrun"', '"subprocess"', '"lammpslib"', '"inprocess"'):
        assert retired not in providers

    plotting = (ROOT / "calm/public/presentation/plotting.py").read_text(encoding="utf-8")
    assert "_METRIC_ALIASES" not in plotting
    assert "def resolve_metric_alias(" not in plotting

    collections = (ROOT / "calm/public/collections/base.py").read_text(encoding="utf-8")
    assert "resolve_metric_alias" not in collections
