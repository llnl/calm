"""Scientific kernels are implementation owners, not a parallel public API."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "engineering" / "architecture" / "current-public-contract.json"
PUBLIC_API = ROOT / "public_api.md"


def test_scientific_kernel_names_are_absent_from_the_public_registry() -> None:
    import calm.api as api

    kernels = {
        "find_prototypes",
        "compute_strain_state",
        "build_interface",
        "compute_interfacial_energy",
        "search_interfaces",
        "search_interface_grid",
    }
    assert kernels.isdisjoint(api.PUBLIC_EXPORTS)
    assert kernels.isdisjoint(api._EXPORT_MAP)


def test_implementation_namespaces_are_not_documented_as_user_imports() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    text = PUBLIC_API.read_text(encoding="utf-8")
    supported = {row["import_path"] for row in contract["exports"]}
    import_table = text.split("<!-- public-api-table:begin -->", 1)[1].split(
        "<!-- public-api-table:end -->", 1
    )[0]
    for namespace in contract["internal_namespaces"]:
        assert namespace not in supported
        assert f"| {namespace}." not in import_table
    assert "one Project-centered public API" in text
