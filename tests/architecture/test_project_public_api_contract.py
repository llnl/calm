"""The reviewed Project method inventory is the sole workflow surface."""

from __future__ import annotations

import inspect
import json
from pathlib import Path

from calm.public.project import Project


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "engineering" / "architecture" / "current-public-contract.json"


def _contract() -> dict:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def test_project_public_methods_match_the_reviewed_contract_exactly() -> None:
    expected = [row["name"] for row in _contract()["project_methods"]]
    actual = [
        name
        for name, value in Project.__dict__.items()
        if inspect.isfunction(value) and not name.startswith("_")
    ]
    assert actual == expected


def test_duplicate_low_level_project_operations_are_internal() -> None:
    retired = {
        "materials_import",
        "get_interface_atoms",
        "build_interface_from_prototype",
        "create_derived_interface",
        "get_derived_interface",
        "start_strain_partition_scan",
        "derive_interfaces_from_strain_partition_scan",
        "start_registry_search",
        "derive_interfaces_from_registry_search",
        "check_prototype_buildability",
        "check_prototypes_buildability",
        "run_build_stage",
        "run_registry_stage",
        "run_relaxation_stage",
        "run_energy_stage",
        "get",
    }
    assert retired.isdisjoint(_contract_method_names())
    for name in retired:
        assert not hasattr(Project, name)

    service_owned = {
        "build_interface_from_prototype",
        "create_derived_interface",
        "get_derived_interface",
        "get_interface_atoms",
        "check_prototype_buildability",
        "check_prototypes_buildability",
        "start_strain_partition_scan",
        "derive_interfaces_from_strain_partition_scan",
        "start_registry_search",
        "derive_interfaces_from_registry_search",
    }
    for name in service_owned:
        assert not hasattr(Project, f"_{name}")

    removed_stage_adapters = {
        "run_build_stage",
        "run_registry_stage",
        "run_relaxation_stage",
        "run_energy_stage",
    }
    for name in removed_stage_adapters:
        assert not hasattr(Project, f"_{name}")

    internalized = (
        retired
        - {"materials_import", "get"}
        - service_owned
        - removed_stage_adapters
    )
    for name in internalized:
        assert hasattr(Project, f"_{name}")

    assert not hasattr(Project, "_get")

    assert hasattr(Project, "add_material")
    assert not hasattr(Project, "_materials_import")


def _contract_method_names() -> set[str]:
    return {row["name"] for row in _contract()["project_methods"]}


def test_high_level_project_signatures_retain_expert_controls() -> None:
    surfaces = inspect.signature(Project.generate_surfaces).parameters
    assert {"millers", "layers", "vacuum"} <= set(surfaces)
    assert "strict" not in surfaces

    search = inspect.signature(Project.search_interfaces).parameters
    assert {"surface_a", "surface_b", "settings"} <= set(search)

    relax = inspect.signature(Project.relax_interfaces).parameters
    assert {"interfaces", "settings"} <= set(relax)
