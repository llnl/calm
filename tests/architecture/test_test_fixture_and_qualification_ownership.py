"""Guard exact-current fixture and release qualification test ownership."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "engineering/architecture/release-qualification-test-ownership.json"


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_current_structure_fixture_is_exact_and_dependency_light() -> None:
    source = _source("tests/current_structure_fixtures.py")
    assert "from calm" not in source
    assert "import calm" not in source
    for field in ("numbers", "cell", "scaled_positions", "pbc"):
        assert f'"{field}"' in source
    assert "production canonicalizer" in source


def test_successful_high_level_structure_setup_uses_shared_fixture() -> None:
    paths = (
        "tests/test_row_interface_helpers.py",
        "tests/public/test_collections_materials_table.py",
        "tests/unit/public/test_table_rows_bulk_normalize.py",
        "tests/integration/project/test_resume_provenance_roundtrip.py",
    )
    for path in paths:
        source = _source(path)
        assert "current_atoms_payload_factory" in source, path
        assert '"scaled_positions"' not in source, path


def test_malformed_structure_tests_keep_invalid_payloads_local() -> None:
    paths = (
        "tests/unit/test_exact_atoms_conversion.py",
        "tests/test_atoms_info_persistence.py",
    )
    for path in paths:
        source = _source(path)
        assert "current_atoms_payload_factory" not in source, path
        assert '"scaled_positions"' in source, path
        assert "raises" in source, path


def test_public_interface_reporting_uses_real_project_boundary() -> None:
    forbidden_name = "InMemory" + "InterfaceWorkspace"
    for path in (ROOT / "tests").rglob("*.py"):
        if path == Path(__file__).resolve():
            continue
        assert forbidden_name not in path.read_text(encoding="utf-8"), path

    source = _source("tests/public/test_project_interface_query_reporting_contract.py")
    assert "prototype_graph_factory" in source
    assert "open_project" in source
    assert "record_interface_model" in source
    assert "Project(workspace" not in source


def test_release_qualification_manifest_resolves_to_executable_tests() -> None:
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert payload["schema"] == "calm.release_qualification_test_ownership"
    assert payload["version"] == 2
    assert set(payload["lifecycle_coverage"]) == {
        "create",
        "reopen",
        "resume",
        "retry",
        "failure",
        "materialization",
        "export",
        "lineage",
        "validation",
        "regeneration_policy",
    }

    for coverage_name in ("lifecycle_coverage", "release_coverage"):
        for concern, entries in payload[coverage_name].items():
            assert entries, concern
            for entry in entries:
                path = ROOT / entry["path"]
                assert path.is_file(), entry
                source = path.read_text(encoding="utf-8")
                assert f'def {entry["test"]}(' in source, entry
