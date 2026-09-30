"""Final production-reachability ownership guardrails for audit 0309."""

from __future__ import annotations

import inspect
from pathlib import Path

from calm import Project
from calm.project.domain.models import DerivedInterface
from calm.public.collections.candidates import CandidateCollection
from calm.public.collections.interfaces import InterfaceCollection
from calm.public.records.search import PersistedInterfaceSearch
from calm.public.records.interfaces import InterfaceCandidate, InterfaceModel, InterfaceSearchResult
from calm.public.persistence.adapter import WorkspaceAdapter


ROOT = Path(__file__).resolve().parents[2]


def test_retired_runtime_and_test_only_modules_remain_absent() -> None:
    retired = (
        "calm/calculators/availability.py",
        "calm/interface/ops/registry_search_runner.py",
        "calm/interface/registry_search_geometry.py",
        "calm/project/infrastructure/logging",
        "calm/public/_export.py",
        "calm/public/filters.py",
        "calm/public/project_lookup.py",
        "calm/public/project_search.py",
        "calm/public/selection.py",
        "calm/slab/ops/_numeric.py",
        "calm/slab/ops/validate_surface_basis.py",
        "calm/slab/surface_primitive.py",
    )
    for relative in retired:
        path = ROOT / relative
        if path.is_dir():
            assert not list(path.rglob("*.py")), relative
        else:
            assert not path.exists(), relative


def test_project_has_no_generic_or_heterogeneous_persistence_query_paths() -> None:
    for retired in ("_get", "_persist", "structures"):
        assert not hasattr(Project, retired)


def test_result_objects_do_not_execute_project_workflows() -> None:
    retired_by_type = {
        InterfaceCandidate: ("build", "search_registry", "_search_registry"),
        InterfaceSearchResult: ("build", "builds", "search_registry"),
        InterfaceModel: ("energy", "relax"),
        CandidateCollection: ("build", "build_top", "refine", "search_registry"),
        InterfaceCollection: ("energy", "relax", "refine"),
        PersistedInterfaceSearch: (
            "build",
            "build_top",
            "refine",
            "refine_interfaces",
            "relax",
            "run_energy",
        ),
    }
    for owner, retired in retired_by_type.items():
        for name in retired:
            assert not hasattr(owner, name), f"{owner.__name__}.{name}"


def test_workspace_adapter_is_an_explicit_projection_only() -> None:
    source = inspect.getsource(WorkspaceAdapter)
    for residue in (
        "def __getattr__",
        "self._workspace.query",
        "_uow_factory",
        "_datasets_service",
        "_followups_service",
        "except Exception",
    ):
        assert residue not in source


def test_surface_export_has_one_exact_selection_contract() -> None:
    from calm.public.workflows.surfaces import export_surfaces

    signature = inspect.signature(export_surfaces)
    assert all(param.kind is not inspect.Parameter.VAR_KEYWORD for param in signature.parameters.values())
    assert "ids_or_names" in signature.parameters
    assert "materials" in signature.parameters
    assert "millers" in signature.parameters


def test_derived_interfaces_are_artifact_backed_only() -> None:
    source = inspect.getsource(DerivedInterface)
    assert "def atoms(" not in source
    assert "def to_ase(" not in source
    assert 'self.spec.get("atoms")' not in source
    assert 'self.spec.get("atoms_artifact_uid")' in source
