"""Guardrails for failure paths that may affect scientific or persisted meaning."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _tree(relative_path: str) -> ast.Module:
    return ast.parse((ROOT / relative_path).read_text(encoding="utf-8"))


def _function(relative_path: str, name: str, *, class_name: str | None = None):
    body = _tree(relative_path).body
    if class_name is not None:
        body = next(
            node.body
            for node in body
            if isinstance(node, ast.ClassDef) and node.name == class_name
        )
    return next(
        node
        for node in body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == name
    )


def _broad_handlers(node: ast.AST) -> list[ast.ExceptHandler]:
    handlers = []
    for item in ast.walk(node):
        if not isinstance(item, ast.ExceptHandler):
            continue
        if item.type is None:
            handlers.append(item)
        elif isinstance(item.type, ast.Name) and item.type.id in {
            "Exception",
            "BaseException",
        }:
            handlers.append(item)
    return handlers


def test_exact_serializers_do_not_suppress_conversion_failures() -> None:
    cases = (
        ("calm/structure/payloads.py", "_sanitize_for_json", None),
        ("calm/structure/payloads.py", "atoms_to_dict", None),
        ("calm/project/application/_json.py", "json_native", None),
        ("calm/project/reproducibility.py", "jsonable", None),
    )
    for path, name, class_name in cases:
        assert not _broad_handlers(_function(path, name, class_name=class_name))


def test_followup_target_and_optional_gamma_boundaries_are_explicit() -> None:
    resolver = _function(
        "calm/project/application/followups/common.py",
        "resolve_followup_targets_as_results",
    )
    handled = {
        ast.unparse(handler.type)
        for handler in ast.walk(resolver)
        if isinstance(handler, ast.ExceptHandler) and handler.type is not None
    }
    assert handled == {
        "KeyError",
        "ValueError",
        "FollowupTargetNotFoundError",
        "InvalidFollowupTargetError",
    }

    gamma = _function(
        "calm/project/application/followups/interface_energy.py",
        "compute_strain_scan_energy_point",
    )
    handled = {
        ast.unparse(handler.type)
        for handler in ast.walk(gamma)
        if isinstance(handler, ast.ExceptHandler) and handler.type is not None
    }
    assert handled == {"StrainedBulkReferenceUnavailableError"}


def test_public_structure_io_has_one_validated_write_path() -> None:
    for path, class_name, method in (
        ("calm/public/records/surfaces.py", "Surface", "write"),
        ("calm/public/records/interfaces.py", "InterfaceModel", "write"),
    ):
        node = _function(path, method, class_name=class_name)
        assert not _broad_handlers(node)
        source = ast.unparse(node)
        assert "write_structure" in source
        assert "ase.io" not in source

    loader = _function("calm/public/records/surfaces.py", "_load_atoms", class_name="Surface")
    assert not _broad_handlers(loader)
    assert "load_structure" in ast.unparse(loader)


def test_reference_frame_fallback_is_explicitly_opt_in() -> None:
    config = _tree("calm/interface/config.py")
    energy = next(
        node
        for node in config.body
        if isinstance(node, ast.ClassDef) and node.name == "EnergyConfig"
    )
    assignment = next(
        node
        for node in energy.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "strict_reference_frame"
    )
    assert isinstance(assignment.value, ast.Constant)
    assert assignment.value.value is True


def test_strain_scan_persists_results_and_edges_through_shared_owner() -> None:
    run_stage = _function(
        "calm/project/application/followups/strain_scan.py",
        "run_stage",
        class_name="StrainPartitionScanOrchestrator",
    )
    source = ast.unparse(run_stage)
    assert "persist_followups_with_edges" in source
    assert "followups.upsert_many" not in source


def test_scientific_query_and_refinement_paths_do_not_hide_failures() -> None:
    cases = (
        ("calm/analysis/pareto.py", "_feature_value", None),
        (
            "calm/public/collections/candidates.py",
            "miller_pair",
            "CandidateCollection",
        ),
        (
            "calm/public/collections/candidates.py",
            "select_top",
            "CandidateCollection",
        ),
        (
            "calm/project/application/followups/registry_search.py",
            "_registry_energy_density",
            None,
        ),
        (
            "calm/project/application/followups/strain_scan.py",
            "_compute_alpha_scan_points",
            "StrainPartitionScanOrchestrator",
        ),
        (
            "calm/project/application/followups/thermodynamics.py",
            "_resolve_raw_results",
            "ThermodynamicOrchestrator",
        ),
    )
    for path, name, class_name in cases:
        assert not _broad_handlers(_function(path, name, class_name=class_name))
