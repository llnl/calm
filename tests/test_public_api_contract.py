from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "engineering" / "architecture" / "current-public-contract.json"


def test_contract_module_matches_top_level() -> None:
    import calm
    import calm.api as api

    expected = [
        row["name"]
        for row in json.loads(CONTRACT.read_text(encoding="utf-8"))["exports"]
    ]
    assert list(api.PUBLIC_EXPORTS) == expected
    assert list(calm.__all__) == [name for name in expected if name != "__version__"]
    for name in expected:
        assert getattr(calm, name) is getattr(api, name)


def test_parallel_top_level_namespaces_are_not_explicit_exports() -> None:
    import calm.api as api

    assert {
        "viz",
        "project",
        "interface",
        "slab",
        "bulk",
        "calculators",
        "Workspace",
        "open_workspace",
    }.isdisjoint(api.PUBLIC_EXPORTS)
