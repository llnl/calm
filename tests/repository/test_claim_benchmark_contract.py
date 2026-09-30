from __future__ import annotations

import ast
from pathlib import Path

from benchmarks.benchmarks.claims.claim_ids import ClaimId, ordered_claim_ids
from benchmarks.benchmarks.claims.schemas import (
    BENCHMARK_MANIFEST_SCHEMA,
    CLAIM_RESULT_SCHEMA,
    CLAIM_SUITE_VERSION,
    CLAIM_SUMMARY_SCHEMA,
    GATE_CANDIDATE_SCHEMA,
    IDENTITY_POLICY_OBSERVATION_SCHEMA,
    METAMORPHIC_OBSERVATION_SCHEMA,
    PUBLIC_API_PARITY_COMPARISON_SCHEMA,
    PUBLIC_API_PARITY_FIXTURE_SCHEMA,
    PUBLIC_API_PARITY_INVENTORY_SCHEMA,
    SEARCH_EXTENSION_SNAPSHOT_SCHEMA,
    SEARCH_EXTENSION_TRANSITION_SCHEMA,
    ZSL_ORACLE_COMPARISON_SCHEMA,
    ZSL_ORACLE_FIXTURE_SCHEMA,
    ZSL_ORACLE_KEY_OBSERVATION_SCHEMA,
    ZSL_ORACLE_SUMMARY_SCHEMA,
)
from benchmarks.benchmarks.run_full_suite import build_stage_plan


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
README = REPOSITORY_ROOT / "benchmarks" / "README.md"
CLAIMS_ROOT = REPOSITORY_ROOT / "benchmarks" / "benchmarks" / "claims"
RUNNER = REPOSITORY_ROOT / "benchmarks" / "benchmarks" / "run_claim_suite.py"
WRAPPER = REPOSITORY_ROOT / "benchmarks" / "run_claim_suite.py"


def _import_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", 1)[0])
    return roots


def _top_level_import_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", 1)[0])
    return roots


def test_claim_infrastructure_has_stable_schemas_and_registry() -> None:
    assert CLAIM_SUITE_VERSION == "claims_v1"
    assert CLAIM_RESULT_SCHEMA == "calm.claim_result/v1"
    assert CLAIM_SUMMARY_SCHEMA == "calm.claim_summary/v1"
    assert BENCHMARK_MANIFEST_SCHEMA == "calm.benchmark_manifest/v1"
    assert GATE_CANDIDATE_SCHEMA == "calm.gate_candidate/v1"
    assert IDENTITY_POLICY_OBSERVATION_SCHEMA == "calm.identity_policy_observation/v1"
    assert METAMORPHIC_OBSERVATION_SCHEMA == "calm.metamorphic_observation/v1"
    assert SEARCH_EXTENSION_SNAPSHOT_SCHEMA == "calm.search_extension_snapshot/v1"
    assert SEARCH_EXTENSION_TRANSITION_SCHEMA == "calm.search_extension_transition/v1"
    assert PUBLIC_API_PARITY_FIXTURE_SCHEMA == "calm.public_api_parity_fixture/v1"
    assert PUBLIC_API_PARITY_INVENTORY_SCHEMA == "calm.public_api_parity_inventory/v1"
    assert PUBLIC_API_PARITY_COMPARISON_SCHEMA == "calm.public_api_parity_comparison/v1"
    assert ZSL_ORACLE_SUMMARY_SCHEMA == "calm.zsl_oracle_summary/v1"
    assert ZSL_ORACLE_FIXTURE_SCHEMA == "calm.zsl_oracle_fixture/v1"
    assert ZSL_ORACLE_COMPARISON_SCHEMA == "calm.zsl_oracle_comparison/v1"
    assert ZSL_ORACLE_KEY_OBSERVATION_SCHEMA == "calm.zsl_oracle_key_observation/v1"
    assert ordered_claim_ids() == tuple(ClaimId)
    assert CLAIMS_ROOT.is_dir()


def test_claim_runner_is_parallel_to_not_embedded_in_legacy_full_suite(
    tmp_path: Path,
) -> None:
    assert RUNNER.is_file()
    assert WRAPPER.is_file()
    plan = build_stage_plan(outdir=tmp_path, python_executable="python-test")
    assert all("benchmarks.run_claim_suite" not in stage.command for stage in plan)


def test_claim_scaffold_does_not_import_calm_or_pymatgen_at_module_load() -> None:
    paths = [RUNNER, *sorted(CLAIMS_ROOT.glob("*.py"))]
    imported = set().union(*(_top_level_import_roots(path) for path in paths))
    assert "calm" not in imported
    assert "pymatgen" not in imported


def test_benchmark_readme_documents_incremental_claim_execution() -> None:
    text = README.read_text(encoding="utf-8")
    assert "python -m benchmarks.run_claim_suite" in text
    assert "claim_summary.json" in text
    assert "benchmark_manifest.json" in text
    assert "not_run" in text
    assert "implemented claim stages" in text
    assert "C1" in text


def test_gate_domain_qualification_is_parallel_versioned_and_documented() -> None:
    runner = (
        REPOSITORY_ROOT
        / "benchmarks"
        / "benchmarks"
        / "run_gate_domain_qualification.py"
    )
    wrapper = REPOSITORY_ROOT / "benchmarks" / "run_gate_domain_qualification.py"
    plot_runner = (
        REPOSITORY_ROOT / "benchmarks" / "benchmarks" / "plot_gate_domain_evidence.py"
    )
    plot_wrapper = REPOSITORY_ROOT / "benchmarks" / "plot_gate_domain_evidence.py"
    module = CLAIMS_ROOT / "gate_domain.py"

    assert runner.is_file()
    assert wrapper.is_file()
    assert plot_runner.is_file()
    assert plot_wrapper.is_file()
    assert module.is_file()
    text = README.read_text(encoding="utf-8")
    assert "python -m benchmarks.run_gate_domain_qualification" in text
    assert "gate_confusion_matrix.csv" in text
    assert "gate_convergence.csv" in text
    assert "principal_strain_histogram_bin_edges.csv" in text
    assert "principal_strain_histogram_summary.csv" in text
    assert "python -m benchmarks.plot_gate_domain_evidence" in text
    assert "--require-clean-repository" in text
    assert "Reduced-parameter accepted" in text
    assert "pymatgen-native" in text
    assert "does not complete claim `C7`" in text

    plan = build_stage_plan(outdir=Path("bench_out"), python_executable="python-test")
    assert all("run_gate_domain_qualification" not in stage.command for stage in plan)


def test_zsl_source_capture_is_parallel_and_documented() -> None:
    runner = REPOSITORY_ROOT / "benchmarks" / "benchmarks" / "run_zsl_source_capture.py"
    wrapper = REPOSITORY_ROOT / "benchmarks" / "run_zsl_source_capture.py"
    zsl_root = CLAIMS_ROOT / "zsl"

    assert runner.is_file()
    assert wrapper.is_file()
    assert (zsl_root / "raw_adapter.py").is_file()
    assert (zsl_root / "transformation_reconstruction.py").is_file()
    imported = set().union(
        _top_level_import_roots(runner),
        *(_top_level_import_roots(path) for path in sorted(zsl_root.glob("*.py"))),
    )
    assert "pymatgen" not in imported

    text = README.read_text(encoding="utf-8")
    assert "python -m benchmarks.run_zsl_source_capture" in text
    assert "raw_zsl_matches.jsonl" in text
    assert "zsl_source_reconstruction.jsonl" in text
    assert "does not evaluate claim `C7`" in text

    plan = build_stage_plan(outdir=Path("bench_out"), python_executable="python-test")
    assert all("run_zsl_source_capture" not in stage.command for stage in plan)


def test_zsl_projection_is_parallel_versioned_and_documented() -> None:
    runner = REPOSITORY_ROOT / "benchmarks" / "benchmarks" / "run_zsl_projection.py"
    wrapper = REPOSITORY_ROOT / "benchmarks" / "run_zsl_projection.py"
    zsl_root = CLAIMS_ROOT / "zsl"

    assert runner.is_file()
    assert wrapper.is_file()
    assert (zsl_root / "metric_projection.py").is_file()
    assert (zsl_root / "coupled_projection.py").is_file()
    assert (zsl_root / "projection_suite.py").is_file()

    text = README.read_text(encoding="utf-8")
    assert "python -m benchmarks.run_zsl_projection" in text
    assert "zsl_metric_projection.jsonl" in text
    assert "zsl_coupled_projection.jsonl" in text
    assert "unique reconstructed source pairs" in text
    assert "does not evaluate claim `C7`" in text
    assert "external results projected onto CALM's equivalence" in text

    plan = build_stage_plan(outdir=Path("bench_out"), python_executable="python-test")
    assert all("run_zsl_projection" not in stage.command for stage in plan)


def test_reference_differential_is_parallel_versioned_and_documented() -> None:
    runner = (
        REPOSITORY_ROOT / "benchmarks" / "benchmarks" / "run_reference_differential.py"
    )
    wrapper = REPOSITORY_ROOT / "benchmarks" / "run_reference_differential.py"
    module = CLAIMS_ROOT / "differential_search.py"
    reference = CLAIMS_ROOT / "reference" / "coupled_match_reference.py"

    assert runner.is_file()
    assert wrapper.is_file()
    assert module.is_file()
    assert reference.is_file()
    assert "calm" not in _top_level_import_roots(reference)
    assert "numpy" not in _top_level_import_roots(reference)

    text = README.read_text(encoding="utf-8")
    assert "python -m benchmarks.run_reference_differential" in text
    assert "reference_comparisons.jsonl" in text
    assert "reference_fixture_results.jsonl" in text
    assert "exact rational" in text
    assert "C2" in text

    plan = build_stage_plan(outdir=Path("bench_out"), python_executable="python-test")
    assert all("run_reference_differential" not in stage.command for stage in plan)


def test_identity_policy_qualification_is_parallel_versioned_and_documented() -> None:
    runner = (
        REPOSITORY_ROOT
        / "benchmarks"
        / "benchmarks"
        / "run_identity_policy_qualification.py"
    )
    wrapper = REPOSITORY_ROOT / "benchmarks" / "run_identity_policy_qualification.py"
    module = CLAIMS_ROOT / "identity_policy.py"

    assert runner.is_file()
    assert wrapper.is_file()
    assert module.is_file()
    assert "calm" not in _top_level_import_roots(module)

    text = README.read_text(encoding="utf-8")
    assert "python -m benchmarks.run_identity_policy_qualification" in text
    assert "identity_policy_observations.jsonl" in text
    assert "metamorphic_observations.jsonl" in text
    assert "common-right" in text
    assert "C3" in text and "C4" in text

    plan = build_stage_plan(outdir=Path("bench_out"), python_executable="python-test")
    assert all(
        "run_identity_policy_qualification" not in stage.command for stage in plan
    )


def test_extension_stability_is_parallel_versioned_and_documented() -> None:
    runner = (
        REPOSITORY_ROOT
        / "benchmarks"
        / "benchmarks"
        / "run_extension_stability_qualification.py"
    )
    wrapper = (
        REPOSITORY_ROOT / "benchmarks" / "run_extension_stability_qualification.py"
    )
    module = CLAIMS_ROOT / "extension_stability.py"

    assert runner.is_file()
    assert wrapper.is_file()
    assert module.is_file()
    assert "calm" not in _top_level_import_roots(module)

    text = README.read_text(encoding="utf-8")
    assert "python -m benchmarks.run_extension_stability_qualification" in text
    assert "search_extension_snapshots.jsonl" in text
    assert "search_extension_transitions.jsonl" in text
    assert "K=1" in text and "K=30" in text
    assert "C5" in text

    plan = build_stage_plan(outdir=Path("bench_out"), python_executable="python-test")
    assert all(
        "run_extension_stability_qualification" not in stage.command for stage in plan
    )


def test_public_api_parity_is_parallel_versioned_and_documented() -> None:
    runner = (
        REPOSITORY_ROOT
        / "benchmarks"
        / "benchmarks"
        / "run_public_api_parity_qualification.py"
    )
    wrapper = REPOSITORY_ROOT / "benchmarks" / "run_public_api_parity_qualification.py"
    module = CLAIMS_ROOT / "public_api_parity.py"

    assert runner.is_file()
    assert wrapper.is_file()
    assert module.is_file()
    assert "calm" not in _top_level_import_roots(module)

    text = README.read_text(encoding="utf-8")
    assert "python -m benchmarks.run_public_api_parity_qualification" in text
    assert "public_api_parity_fixture_results.jsonl" in text
    assert "public_api_parity_inventories.jsonl" in text
    assert "public_api_parity_comparisons.jsonl" in text
    assert "completed-search resume" in text
    assert "C6" in text

    plan = build_stage_plan(outdir=Path("bench_out"), python_executable="python-test")
    assert all(
        "run_public_api_parity_qualification" not in stage.command for stage in plan
    )


def test_zsl_oracle_comparison_is_parallel_versioned_and_documented() -> None:
    runner = (
        REPOSITORY_ROOT / "benchmarks" / "benchmarks" / "run_zsl_oracle_comparison.py"
    )
    wrapper = REPOSITORY_ROOT / "benchmarks" / "run_zsl_oracle_comparison.py"
    module = CLAIMS_ROOT / "zsl" / "oracle_comparison.py"

    assert runner.is_file()
    assert wrapper.is_file()
    assert module.is_file()
    assert "pymatgen" not in _top_level_import_roots(module)
    assert "calm" not in _top_level_import_roots(module)

    text = README.read_text(encoding="utf-8")
    assert "python -m benchmarks.run_zsl_oracle_comparison" in text
    assert "zsl_oracle_comparisons.jsonl" in text
    assert "zsl_oracle_key_observations.jsonl" in text
    assert "descriptive_only" in text
    assert "equal-square" in text
    assert "C7" in text

    plan = build_stage_plan(outdir=Path("bench_out"), python_executable="python-test")
    assert all("run_zsl_oracle_comparison" not in stage.command for stage in plan)
