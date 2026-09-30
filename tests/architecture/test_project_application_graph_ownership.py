"""Ownership guardrails for the exact project application graph."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _tree(relative_path: str) -> ast.Module:
    return ast.parse((ROOT / relative_path).read_text(encoding="utf-8"))


def _class(relative_path: str, name: str) -> ast.ClassDef:
    for node in _tree(relative_path).body:
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    raise AssertionError(f"{name} not found in {relative_path}")


def _method(node: ast.ClassDef, name: str) -> ast.FunctionDef:
    for item in node.body:
        if isinstance(item, ast.FunctionDef) and item.name == name:
            return item
    raise AssertionError(f"{name} not found in {node.name}")


def _arg_names(function: ast.FunctionDef) -> set[str]:
    return {
        item.arg
        for item in (
            list(function.args.posonlyargs)
            + list(function.args.args)
            + list(function.args.kwonlyargs)
        )
    }


def test_artifact_service_separates_transaction_entry_from_active_writes() -> None:
    node = _class(
        "calm/project/application/artifacts.py",
        "ArtifactsService",
    )
    public = _method(node, "put_bytes")
    active = _method(node, "put_bytes_in")
    public_source = ast.unparse(public)
    active_source = ast.unparse(active)

    assert "fresh_uow" in public_source
    assert "require_entered_uow" in active_source
    assert "run_to_artifact" in active_source
    assert ".commit(" not in active_source
    assert not any(isinstance(item, ast.With) for item in ast.walk(active))


def test_prototype_persistence_owns_rows_and_required_graph_edges() -> None:
    node = _class(
        "calm/project/application/prototypes.py",
        "PrototypesService",
    )
    function = _method(node, "persist_interface_prototypes")
    source = ast.unparse(function)

    assert "run_name" not in _arg_names(function)
    assert "InterfacePrototype" in source
    assert "run_to_prototype" in source
    assert source.count("slab_to_prototype") == 2
    assert "hasattr(" not in source
    assert not any(isinstance(item, ast.ExceptHandler) for item in ast.walk(function))


def test_prototype_search_has_one_current_parameter_and_persistence_path() -> None:
    node = _class(
        "calm/project/application/prototypes.py",
        "PrototypeSearchService",
    )
    function = _method(node, "start_search")
    source = ast.unparse(function)

    assert "payload" not in _arg_names(function)
    assert source.count("persist_interface_prototypes") == 1
    assert "run_to_prototype" not in source
    assert "slab_to_prototype" not in source


def test_derived_interface_service_owns_atoms_rows_and_lineage_in_one_uow() -> None:
    node = _class(
        "calm/project/application/derived_interfaces.py",
        "DerivedInterfaceService",
    )
    function = _method(node, "create_in")
    source = ast.unparse(function)

    assert "require_entered_uow" in source
    assert "put_interface_atoms_in" in source
    assert "prototype_to_interface" in source
    assert "interface_to_interface" in source
    assert "canonical_derived_interface_spec" in source
    assert "seed_iface.artifact_refs" not in source
    assert ".commit(" not in source
    assert not any(isinstance(item, ast.With) for item in ast.walk(function))


def test_followup_interface_derivation_is_one_transactional_owner() -> None:
    node = _class(
        "calm/project/application/interface_derivation.py",
        "InterfaceDerivationService",
    )
    strain = _method(node, "derive_from_strain_scan")
    registry = _method(node, "derive_from_registry_search")
    source = ast.unparse(node)

    assert "edge_kind" not in source
    assert "FollowupsService" not in source
    assert "RunsService" not in source
    assert "followup_to_interface" in source
    assert "create_in" in ast.unparse(strain)
    assert "create_in" in ast.unparse(registry)
    assert ".commit(" not in source


def test_relaxation_reuses_the_active_uow_for_interface_persistence() -> None:
    node = _class(
        "calm/project/application/followups/relaxation.py",
        "RelaxationOrchestrator",
    )
    derive = _method(node, "_derive_relaxed_interface")
    run_stage = _method(node, "run_stage")
    derive_source = ast.unparse(derive)
    run_source = ast.unparse(run_stage)

    assert "create_in" in derive_source
    assert "ArtifactsService(uow," not in derive_source
    assert "DerivedInterfaceService(uow," not in derive_source
    assert "uow_factory=self._existing_uow_factory" in derive_source
    assert "followup_to_interface" in run_source
    assert "except Exception:\n                    pass" not in run_source


def test_workspace_and_public_search_adapters_expose_only_current_signatures() -> None:
    workspace = _class("calm/project/runtime/workspace.py", "Workspace")
    adapter = _class("calm/public/persistence/adapter.py", "WorkspaceAdapter")

    for node in (workspace, adapter):
        persist = _method(node, "persist_interface_prototypes")
        assert "run_name" not in _arg_names(persist)

    for node in (workspace,):
        search = _method(node, "start_prototype_search")
        assert "payload" not in _arg_names(search)
        strain = _method(node, "derive_interfaces_from_strain_partition_scan")
        registry = _method(node, "derive_interfaces_from_registry_search")
        assert "edge_kind" not in _arg_names(strain)
        assert "edge_kind" not in _arg_names(registry)
