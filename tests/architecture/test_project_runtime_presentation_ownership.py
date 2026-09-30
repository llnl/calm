from __future__ import annotations

import ast
import importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "calm" / "project"
RUNTIME = PROJECT / "runtime"
PRESENTATION = PROJECT / "presentation"
REPOSITORIES = PROJECT / "infrastructure" / "db" / "repos"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.add(node.module or "")
    return modules


def _workspace_class() -> ast.ClassDef:
    tree = ast.parse((RUNTIME / "workspace.py").read_text(encoding="utf-8"))
    return next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Workspace"
    )


def test_legacy_project_ux_tree_and_facades_are_retired() -> None:
    ux = PROJECT / "ux"
    assert list(ux.rglob("*.py")) == []

    for module in (
        "calm.project.ux.workspace",
        "calm.project.ux.notebook",
        "calm.project.ux.facades.query",
        "calm.project.ux.facades.mutations",
    ):
        try:
            importlib.import_module(module)
        except ModuleNotFoundError as exc:
            assert exc.name == module or module.startswith(f"{exc.name}.")
        else:
            raise AssertionError(f"Retired project UX module is importable: {module}")


def test_workspace_has_one_direct_internal_operation_surface() -> None:
    workspace = _workspace_class()
    methods = {
        node.name
        for node in workspace.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert {
        "query",
        "mutations",
        "enrichment",
        "artifacts",
        "visualization",
        "export",
        "analysis",
    }.isdisjoint(methods)

    source = (RUNTIME / "workspace.py").read_text(encoding="utf-8")
    assert "_query_facade" not in source
    assert "_mutations_facade" not in source
    assert ".facades" not in source
    assert "Project`` is the sole supported user workflow boundary" in source


def test_bootstrap_composes_the_runtime_workspace_owner() -> None:
    source = (PROJECT / "bootstrap.py").read_text(encoding="utf-8")
    assert "from .runtime.workspace import Workspace" in source
    assert ".ux" not in source


def test_runtime_composition_does_not_import_public_or_database_implementation() -> None:
    path = RUNTIME / "workspace.py"
    source = path.read_text(encoding="utf-8")
    imports = _imports(path)

    assert not any(module.startswith("calm.public") for module in imports)
    assert not any("infrastructure.db" in module for module in imports)
    assert "SqlAlchemy" not in source
    assert "sqlite3" not in imports


def test_presentation_helpers_remain_database_and_sidecar_free() -> None:
    for path in PRESENTATION.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        imports = _imports(path)
        assert not any("application" in module for module in imports)
        assert not any("infrastructure" in module for module in imports)
        assert not any(module.startswith("calm.public") for module in imports)
        for forbidden in (
            "fresh_uow",
            "SqlAlchemy",
            "ensure_short_id",
            "resolve_prototype",
        ):
            assert forbidden not in source


def test_plot_readers_accept_only_current_followup_payloads() -> None:
    workspace = (RUNTIME / "workspace.py").read_text(encoding="utf-8")
    presentation = (PRESENTATION / "workspace.py").read_text(encoding="utf-8")

    assert "strain_partition_scan_plot" not in workspace
    assert "Be tolerant to trace schemas" not in workspace
    assert "Handle tuple/list format" not in workspace
    assert "strain_partition_plot_series(" in workspace
    assert "registry_search_plot_series(" in workspace
    assert "must be a mapping row" in presentation
    assert "must use exact current fields" in presentation
    assert "three-value sequence" not in presentation


def test_notebook_tables_have_one_current_column_selection_parameter() -> None:
    source = (PRESENTATION / "notebook.py").read_text(encoding="utf-8")
    assert "Backwards-compatible alias" not in source
    assert "columns: Sequence[str] | None = None" not in source
    assert "_id_short_from_paths" not in source
    assert 'payload.get("target_kind")' not in source
    assert 'payload.get("target_uid_full")' not in source
    assert "payload.run_uid" not in source
    assert "payload.bulk_uid" not in source
    assert "spec.prototype" not in source
    assert "except Exception" not in source


def test_workspace_conveniences_do_not_rehabilitate_invalid_inputs() -> None:
    methods = {
        node.name: node
        for node in _workspace_class().body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    miller = ast.unparse(methods["run_miller_combination_search"])
    builder = ast.unparse(methods["build_interface_from_prototype"])
    registry = methods["run_registry_stage"]

    assert "Material_A" not in miller
    assert "Material_B" not in miller
    assert "SlabSummary" in miller
    assert "self._fresh_uow()" in builder
    assert "getattr(" not in builder
    assert not any(isinstance(node, ast.ExceptHandler) for node in ast.walk(registry))


def test_repository_implementations_are_split_by_persisted_aggregate() -> None:
    assert not (REPOSITORIES.parent / "repos.py").exists()

    expected = {
        "artifacts.py": "SqlAlchemyArtifactRepository",
        "bulk.py": "SqlAlchemyBulkRepository",
        "calculators.py": "SqlAlchemyCalculatorRepository",
        "campaigns.py": "SqlAlchemyCampaignRepository",
        "configuration.py": "ProjectConfigurationRepository",
        "datasets.py": "SqlAlchemyDatasetRepository",
        "derived_interfaces.py": "SqlAlchemyDerivedInterfaceRepository",
        "followups.py": "SqlAlchemyFollowupResultRepository",
        "lineage.py": "SqlAlchemyEdgeRepository",
        "prototypes.py": "SqlAlchemyPrototypeRepository",
        "runs.py": "SqlAlchemyRunRepository",
        "searches.py": "SqlAlchemyInterfaceSearchRepository",
        "slabs.py": "SqlAlchemySlabRepository",
    }
    assert {path.name for path in REPOSITORIES.glob("*.py")} == {
        "__init__.py",
        "_common.py",
        *expected,
    }

    for filename, class_name in expected.items():
        tree = ast.parse((REPOSITORIES / filename).read_text(encoding="utf-8"))
        actual = [
            node.name for node in tree.body if isinstance(node, ast.ClassDef)
        ]
        assert actual == [class_name]
