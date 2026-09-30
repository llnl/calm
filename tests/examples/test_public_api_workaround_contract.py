"""Guardrails against avoidable public-API workarounds in numbered examples."""

from __future__ import annotations

import re
from pathlib import Path


EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "examples"


def _source(name: str) -> str:
    return (EXAMPLES_DIR / name).read_text(encoding="utf-8")


def _numbered_sources() -> dict[str, str]:
    return {
        path.name: path.read_text(encoding="utf-8")
        for path in sorted(EXAMPLES_DIR.glob("[0-9][0-9]_*.py"))
    }


def test_numbered_examples_do_not_expose_internal_access_patterns() -> None:
    forbidden = (
        "open_workspace",
        "_workspace",
        "ws.query",
        "ws.mutations",
        ".metadata",
        "uid_full",
        ".to_dict()",
    )
    for name, source in _numbered_sources().items():
        for token in forbidden:
            assert token not in source, f"{name} exposes forbidden pattern: {token}"


def test_examples_01_and_02_do_not_refetch_by_internal_identifier() -> None:
    example_01 = _source("01_optimize_materials.py")
    example_02 = _source("02_generate_surfaces.py")

    assert "project.material(lif_opt.id_short)" not in example_01
    assert "project.material(lif_opt.id_short)" not in example_02
    assert "canonical id" not in example_01.lower()
    assert "canonical id" not in example_02.lower()


def test_example_03_uses_returned_durable_search_view() -> None:
    source = _source("03_search_interfaces.py")

    assert "search = project.search_interfaces(" in source
    assert "search.candidates()" in source
    assert "search.buildability_summary()" in source
    assert "project.search(search_name)" not in source
    assert "project.candidates().search(search_name)" not in source


def test_example_05_uses_collection_cardinality_without_row_materialization() -> None:
    source = _source("05_build_interfaces.py")

    assert source.count("project.search(search_name)") == 1
    assert "if not candidates:" in source
    assert "if not sel:" in source
    assert ".to_rows(" not in source
    assert "except Exception" not in source
    assert "project.candidates().to_table" not in source


def test_examples_07_and_08_use_workflow_level_reporting() -> None:
    example_07 = _source("07_relax_interfaces.py")
    example_08 = _source("08_evaluate_interface_energetics.py")

    assert "workflow.write_table(" in example_07
    assert "workflow.results.write_table(" not in example_07
    assert 'view="all"' not in example_07

    assert len(re.findall(r"(?<!reference_)workflow\.write_table\(", example_08)) == 2
    assert "reference_workflow.write_table(" in example_08
    assert 'kind="raw"' in example_08
    assert 'kind="thermodynamic"' in example_08
    assert "workflow.energy_results.write_table(" not in example_08
    assert "workflow.thermodynamic_results.write_table(" not in example_08
    assert 'view="all"' not in example_08


def test_example_10_checks_prerequisites_and_relies_on_summary() -> None:
    source = _source("10_run_interface_campaign.py")

    assert "if not PROJECT_DIR.is_dir():" in source
    assert "result.write_table(results_output)" in source
    assert "result.comparison().rank_by(" in source
    assert "comparison.write_table(comparison_output)" in source
    assert "print(result.summary())" in source
    assert "print(comparison.summary())" in source
    assert "project.write_reproducibility_manifest(overwrite=True)" in source
    assert "project.verify_reproducibility_manifest()" in source
    assert "verification.raise_for_errors()" in source
    assert "print(manifest.summary())" in source
    assert "print(verification.summary())" in source
    assert "Campaign run:" not in source


def test_example_09_uses_joined_learning_dataset_contract() -> None:
    source = _source("09_build_interface_dataset.py")

    assert "DatasetFeature" in source
    assert "DatasetTarget" in source
    assert "DatasetSplitSettings" in source
    assert 'schema_version="calm.interface_learning.v1"' in source
    assert 'group_by=("lineage.prototype",)' in source
    assert "dataset.validate_ml()" in source
    assert 'view="learning"' in source
    assert "project.energy_results()" not in source
