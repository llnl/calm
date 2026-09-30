"""Ownership guardrails for exact-current persisted bulk provenance."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _function_calls(relative: str, function_name: str) -> set[str]:
    tree = ast.parse(_source(relative))
    function = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == function_name
    )
    calls: set[str] = set()
    for node in ast.walk(function):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            calls.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            calls.add(node.func.attr)
    return calls


def test_bulk_record_contract_owns_persisted_provenance_validation() -> None:
    source = _source("calm/project/domain/contracts/bulk_record.py")

    for required_state in (
        "atoms_conventional",
        "atoms_primitive",
        "standardization",
        "provenance_info_key",
    ):
        assert required_state in source
    assert "validate_bulk_canonicalization_relations" in source
    assert "Metadata-only bulks remain valid current project state" in source


def test_bulk_repository_validates_both_incoming_and_stored_state() -> None:
    relative = "calm/project/infrastructure/db/repos/bulk.py"

    assert "current_bulk_structure_record" in _function_calls(
        relative,
        "_incoming_payload",
    )
    assert "current_bulk_structure_record" in _function_calls(
        relative,
        "_stored_payload",
    )
    assert "get_by_uid_full" in _function_calls(relative, "upsert")
    assert "older CALM versions" not in _source(relative)


def test_bulk_model_does_not_fallback_or_regenerate_persisted_cells() -> None:
    source = _source("calm/project/domain/models.py")

    assert '_atoms_payload("atoms_conventional", "atoms")' not in source
    assert "spglib.standardize_cell" not in source
    assert "from spglib" not in source


def test_workspace_validation_reports_current_bulk_failures_without_legacy_policy() -> None:
    source = _source("calm/project/application/workspace_validation.py")

    assert "legacy workspaces" not in source
    assert "_bulk_provenance_problem" not in source
    assert "uow.bulks.list_reference_records" in source
    assert "MissingBulkCanonicalizationProvenanceError" in source
    assert "InvalidBulkCanonicalizationProvenanceError" in source
    assert 'category="missing_provenance"' in source
    assert 'severity="error"' in source


def test_bulk_writer_standardizes_the_exact_serialized_submission() -> None:
    relative = "calm/project/application/bulk_fingerprinting.py"
    source = _source(relative)

    assert "atoms_from_dict" in _function_calls(
        relative,
        "_standardized_structure_payload",
    )
    assert "atoms_to_dict" in _function_calls(
        relative,
        "assemble_structure_payload",
    )
    assert "return structure, None, None" not in source
    assert "isinstance(structure, Atoms)" not in source
