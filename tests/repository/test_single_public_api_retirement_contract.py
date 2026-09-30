"""Retirement guardrails for public aliases and transitional API machinery."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "engineering" / "architecture" / "current-public-contract.json"


def _contract() -> dict:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def test_retired_entry_points_have_no_runtime_compatibility_registry() -> None:
    import calm.api as api

    data = _contract()
    retired = {path.removeprefix("calm.") for path in data["retired_top_level_exports"]}
    assert retired.isdisjoint(api.PUBLIC_EXPORTS)
    assert retired.isdisjoint(api._EXPORT_MAP)
    assert not hasattr(api, "COMPAT_TOP_LEVEL_EXPORTS")


def test_duplicate_object_execution_methods_remain_internal() -> None:
    from calm.public.collections.candidates import CandidateCollection
    from calm.public.collections.interfaces import InterfaceCollection
    from calm.public.inputs.materials import Material
    from calm.public.records.search import PersistedInterfaceSearch
    from calm.public.records.interfaces import InterfaceCandidate, InterfaceModel, InterfaceSearchResult

    owners = {
        "Material.optimize": Material,
        "InterfaceCandidate.build": InterfaceCandidate,
        "InterfaceCandidate.search_registry": InterfaceCandidate,
        "InterfaceSearchResult.build": InterfaceSearchResult,
        "InterfaceSearchResult.build_all": InterfaceSearchResult,
        "CandidateCollection.build_all": CandidateCollection,
        "InterfaceModel.energy": InterfaceModel,
        "InterfaceModel.relax": InterfaceModel,
        "InterfaceCollection.relax": InterfaceCollection,
        "InterfaceCollection.evaluate_reference_energies": InterfaceCollection,
        "InterfaceCollection.evaluate_energies": InterfaceCollection,
        "PersistedInterfaceSearch.build_top": PersistedInterfaceSearch,
        "PersistedInterfaceSearch.refine_interfaces": PersistedInterfaceSearch,
        "PersistedInterfaceSearch.relax_interfaces": PersistedInterfaceSearch,
        "PersistedInterfaceSearch.evaluate_reference_energies": PersistedInterfaceSearch,
        "PersistedInterfaceSearch.evaluate_energies": PersistedInterfaceSearch,
    }
    retired = set(_contract()["retired_duplicate_methods"])
    project_retirements = {
        "Project.save",
        "Project.energies",
        "Project.strain_partition_scan_plot",
        "Project.registry_search_plot",
        "Project.plot_pareto",
        "Project.structures",
    }
    assert set(owners) | project_retirements == retired
    for qualified, owner in owners.items():
        method = qualified.rsplit(".", 1)[1]
        assert not hasattr(owner, method)
