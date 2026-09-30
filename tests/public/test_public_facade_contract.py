"""Contract tests for CALM's single top-level public facade."""

from __future__ import annotations

import json
from pathlib import Path

import calm
import calm.api as api


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "engineering" / "architecture" / "current-public-contract.json"


def _contract() -> dict:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def test_public_exports_match_the_reviewed_single_surface() -> None:
    expected = [row["name"] for row in _contract()["exports"]]
    assert list(api.PUBLIC_EXPORTS) == expected
    assert list(calm.__all__) == [name for name in expected if name != "__version__"]
    for name in expected:
        assert getattr(calm, name) is getattr(api, name)


def test_star_import_surface_matches_api_all() -> None:
    assert calm.__all__ == list(api.__all__)
    assert set(calm.__all__).issubset(set(api.PUBLIC_EXPORTS))


def test_parallel_and_retired_top_level_names_do_not_resolve() -> None:
    retired = {
        path.removeprefix("calm.")
        for path in _contract()["retired_top_level_exports"]
    }
    retired.update({"Bulk", "Slab", "Workspace", "open_workspace"})
    assert retired.isdisjoint(api._EXPORT_MAP)
    assert not hasattr(api, "COMPAT_TOP_LEVEL_EXPORTS")
