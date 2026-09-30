"""Guardrails for the published CALM stable API and project policy."""

from __future__ import annotations

import inspect
import json
from pathlib import Path

from calm.project.bootstrap import open_workspace
from calm.project.domain.schema import (
    AUTOMATIC_PROJECT_MIGRATION_SUPPORTED,
    CURRENT_SCHEMA_VERSION,
    IN_PLACE_PROJECT_REPAIR_SUPPORTED,
    PROJECT_COMPATIBILITY_POLICY,
    PROJECT_RELEASE_STAGE,
)
from calm.public.project import open_project


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "engineering" / "architecture" / "current-public-contract.json"
DOCUMENTATION_CONTRACT = ROOT / "engineering" / "architecture" / "current-documentation-site.json"


def test_reviewed_contract_publishes_one_stable_surface() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))

    assert contract["release_stage"] == PROJECT_RELEASE_STAGE == "stable"
    assert len(contract["exports"]) == 34
    assert len(contract["project_methods"]) == 68
    assert contract["persistence"] == {
        "database_schema_version": CURRENT_SCHEMA_VERSION,
        "compatibility_policy": PROJECT_COMPATIBILITY_POLICY,
        "automatic_migration": AUTOMATIC_PROJECT_MIGRATION_SUPPORTED,
        "in_place_repair": IN_PLACE_PROJECT_REPAIR_SUPPORTED,
    }


def test_stable_project_policy_has_no_runtime_migration_switch() -> None:
    assert CURRENT_SCHEMA_VERSION == "v2.0.0"
    assert PROJECT_COMPATIBILITY_POLICY == "exact_current_regeneration_only"
    assert AUTOMATIC_PROJECT_MIGRATION_SUPPORTED is False
    assert IN_PLACE_PROJECT_REPAIR_SUPPORTED is False
    assert "migration_policy" not in inspect.signature(open_project).parameters
    assert "migration_policy" not in inspect.signature(open_workspace).parameters
    assert not (ROOT / "calm" / "project" / "migrations").exists()


def test_greenfield_contract_assigns_the_recreation_boundary() -> None:
    documentation = json.loads(DOCUMENTATION_CONTRACT.read_text(encoding="utf-8"))
    requirement = documentation["content_requirements"]["project_compatibility"]
    assert requirement["owner"] == "use/projects.md"
    assert requirement["must_explain"] == [
        "recognizing an older or incompatible project",
        "preserving the original directory unchanged",
        "creating a new project",
        "rerunning supported workflows",
        "not editing project files",
    ]
