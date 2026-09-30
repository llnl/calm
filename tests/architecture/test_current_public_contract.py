"""Authoritative metadata contracts for CALM's single public API."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "engineering" / "architecture" / "current-public-contract.json"
PUBLIC_API = ROOT / "public_api.md"


def _contract() -> dict:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def _marked_rows(begin: str, end: str) -> list[dict[str, str]]:
    lines = PUBLIC_API.read_text(encoding="utf-8").splitlines()
    start = lines.index(begin) + 1
    stop = lines.index(end)
    header: list[str] | None = None
    rows: list[dict[str, str]] = []
    for raw in lines[start:stop]:
        if not raw.startswith("|"):
            continue
        parts = [part.strip() for part in raw.strip("|").split("|")]
        if not parts or set(parts[0]) == {"-"}:
            continue
        if header is None:
            header = parts
        else:
            rows.append(dict(zip(header, parts)))
    return rows


def test_contract_schema_is_complete_unique_and_tier_free() -> None:
    data = _contract()
    assert data["schema_version"] == "calm.public_api_contract.v4"
    assert set(data) == {
        "schema_version",
        "release_stage",
        "scope",
        "exports",
        "project_methods",
        "workflow_objects",
        "retired_top_level_exports",
        "internal_namespaces",
        "retired_duplicate_methods",
        "persistence",
    }

    assert data["release_stage"] == "stable"
    assert data["persistence"] == {
        "database_schema_version": "v2.0.0",
        "compatibility_policy": "exact_current_regeneration_only",
        "automatic_migration": False,
        "in_place_repair": False,
    }

    exports = data["exports"]
    names = [row["name"] for row in exports]
    paths = [row["import_path"] for row in exports]
    assert len(names) == len(set(names))
    assert len(paths) == len(set(paths))
    assert all(path == f"calm.{name}" for path, name in zip(paths, names))
    assert all(
        set(row)
        == {
            "name",
            "import_path",
            "kind",
            "implementation",
            "group",
            "purpose",
            "members",
        }
        for row in exports
    )
    assert all(isinstance(row["members"], list) for row in exports)
    assert all(len(row["members"]) == len(set(row["members"])) for row in exports)
    assert all(
        not member.startswith("_")
        for row in exports
        for member in row["members"]
    )

    methods = [row["name"] for row in data["project_methods"]]
    assert len(methods) == len(set(methods))
    assert all(not name.startswith("_") for name in methods)

    workflow_names = [row["name"] for row in data["workflow_objects"]]
    assert len(workflow_names) == len(set(workflow_names))
    assert all(
        set(row) == {"name", "implementation", "role", "members"}
        for row in data["workflow_objects"]
    )
    assert all(row["members"] for row in data["workflow_objects"])
    assert all(
        len(row["members"]) == len(set(row["members"]))
        for row in data["workflow_objects"]
    )
    assert all(
        not member.startswith("_")
        for row in data["workflow_objects"]
        for member in row["members"]
    )

    serialized = json.dumps(data).lower()
    assert '"tier"' not in serialized
    assert '"stability"' not in serialized
    assert "beginner api" not in serialized
    assert "basic api" not in serialized
    assert "advanced api" not in serialized


def test_public_api_tables_are_exact_projections_of_the_contract() -> None:
    data = _contract()
    export_rows = _marked_rows(
        "<!-- public-api-table:begin -->", "<!-- public-api-table:end -->"
    )
    method_rows = _marked_rows(
        "<!-- project-method-table:begin -->", "<!-- project-method-table:end -->"
    )
    object_rows = _marked_rows(
        "<!-- workflow-object-table:begin -->", "<!-- workflow-object-table:end -->"
    )

    assert [row["Import path"] for row in export_rows] == [
        row["import_path"] for row in data["exports"]
    ]
    assert [row["Method"] for row in method_rows] == [
        f"Project.{row['name']}" for row in data["project_methods"]
    ]
    assert object_rows == [
        {
            "Object": row["name"],
            "Implementation owner": row["implementation"],
            "Role": row["role"],
        }
        for row in data["workflow_objects"]
    ]


def test_retired_and_supported_paths_are_disjoint() -> None:
    data = _contract()
    supported = {row["import_path"] for row in data["exports"]}
    retired = set(data["retired_top_level_exports"])
    assert supported.isdisjoint(retired)
