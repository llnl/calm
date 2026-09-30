"""Guard complete retirement of the automatic public reporting sidecar."""

from __future__ import annotations

import inspect
import json
from pathlib import Path

from calm.public.project import Project
from calm.public.queries.project import PublicProjectQueries


ROOT = Path(__file__).resolve().parents[2]


def test_reporting_sidecar_modules_and_project_state_are_absent() -> None:
    for relative in (
        "calm/public/sidecar.py",
        "calm/public/sidecar_store.py",
        "calm/public/records.py",
        "calm/public/_row_energy.py",
    ):
        assert not (ROOT / relative).exists()

    assert not hasattr(Project, "_public_records")
    assert not hasattr(Project, "_record_path")
    assert not hasattr(Project, "_flush_public_records")


def test_query_composition_has_no_reporting_records_dependency() -> None:
    assert tuple(inspect.signature(PublicProjectQueries).parameters) == (
        "workspace_adapter",
        "repo",
        "project",
    )
    source = (ROOT / "calm" / "public" / "queries" / "project.py").read_text(
        encoding="utf-8"
    )
    assert "_records" not in source
    assert "calm-public-records.json" not in source


def test_public_contract_has_no_sidecar_export_or_schema() -> None:
    contract = json.loads(
        (ROOT / "engineering" / "architecture" / "current-public-contract.json").read_text(
            encoding="utf-8"
        )
    )
    exports = {row["name"] for row in contract["exports"]}
    assert "UnsupportedPublicSidecarSchemaError" not in exports
    persistence = contract["persistence"]
    assert persistence["database_schema_version"] == "v2.0.0"
    assert "public_sidecar_schema_version" not in persistence
    assert all("sidecar" not in key for key in persistence)
