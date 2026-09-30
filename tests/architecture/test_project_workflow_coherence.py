"""Guardrails for the canonical Project workflow established in audit 0308."""

from __future__ import annotations

import inspect
from pathlib import Path

from calm import Project


ROOT = Path(__file__).resolve().parents[2]


def test_project_exposes_explicit_workflow_operations_only() -> None:
    assert hasattr(Project, "add_material")
    assert hasattr(Project, "search_interfaces")
    assert hasattr(Project, "build_interfaces")
    assert hasattr(Project, "refine_interfaces")
    assert hasattr(Project, "energy_results")

    for retired in (
        "save",
        "energies",
        "plot_pareto",
        "strain_partition_scan_plot",
        "registry_search_plot",
    ):
        assert not hasattr(Project, retired)


def test_named_search_operations_share_one_selector_contract() -> None:
    for method_name in ("search", "build_interfaces", "refine_interfaces"):
        signature = inspect.signature(getattr(Project, method_name))
        assert "search" in signature.parameters


def test_reporting_energy_collection_module_is_retired() -> None:
    assert not (ROOT / "calm" / "public" / "energy_collections.py").exists()


def test_public_api_guidance_teaches_current_workflow_owners() -> None:
    public_api = (ROOT / "public_api.md").read_text(encoding="utf-8")

    assert "Project.add_material" in public_api
    assert "Project.search_interfaces" in public_api
    assert "Project.energy_results" in public_api
    assert "PersistedInterfaceSearch" in public_api
    assert "Project.save" not in public_api
    assert "Project.energies" not in public_api
