from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPOSITORY_ROOT / "examples" / "lif_li2o_low_index_redundancy_audit.py"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "low_index_redundancy_audit",
        SCRIPT_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Candidates:
    def to_rows(self, *, view: str):
        assert view == "all"
        return [
            {
                "candidate_id": "candidate:1",
                "pair_identity": {
                    "primitive_pair_key": [1, 0, 0, 1, 1, 0, 0, 1]
                },
                "source_provenance": {
                    "source_count": 4,
                    "source_index_pairs": [[1, 1], [2, 2]],
                    "repeat_indices": [1, 2],
                },
            },
            {
                "candidate_id": "candidate:2",
                "pair_identity": {
                    "primitive_pair_key": [1, 0, 0, 1, 1, 0, 1, 1]
                },
                "source_provenance": {
                    "source_count": 2,
                    "source_index_pairs": [[3, 3]],
                    "repeat_indices": [1],
                },
            },
        ]


def _search(module, *, schema: str | None = None, include_global: bool = True):
    search_space = (
        {
            "raw_hnf_pairs": 100,
            "searchable_hnf_pairs": 90,
            "area_admissible_hnf_pairs": 40,
            "atom_lower_bound_admissible_hnf_pairs": 30,
            "orbit_prefilter_surviving_hnf_pairs": 20,
        }
        if include_global
        else None
    )
    identity_reduction = (
        {
            "admitted_descriptions": 6,
            "unique_admitted_source_pairs": 5,
            "unique_admitted_primitive_pairs": 4,
            "unique_admitted_common_right_classes": 3,
            "unique_final_pair_classes": 2,
        }
        if include_global
        else None
    )
    audit = SimpleNamespace(
        schema=schema or module.REQUIRED_AUDIT_SCHEMA,
        implementation="primitive_coupled_pair_v2",
        k_max=5,
        search_space=search_space,
        identity_reduction=identity_reduction,
        totals={
            "surface_A": {
                "hnf_generated": 10,
                "reduction_failed": 0,
                "condition_rejected": 0,
                "admitted_members": 10,
                "comparison_orbits": 6,
            },
            "surface_B": {
                "hnf_generated": 10,
                "reduction_failed": 0,
                "condition_rejected": 1,
                "admitted_members": 9,
                "comparison_orbits": 5,
            },
            "pairs": {
                "index_pairs_scheduled": 12,
                "orbit_pairs_considered": 10,
                "orbit_prefilter_rejected": 3,
                "orbit_prefilter_inconclusive": 1,
                "orbit_prefilter_admitted": 6,
                "member_pairs_expanded": 20,
                "correspondence_column_pairs_tested": 60,
                "unimodular_correspondences_tested": 50,
                "strain_admissible_correspondences": 6,
                "correspondence_limit_failures": 0,
                "nonprimitive_repetitions": 2,
                "primitive_atom_rejected": 0,
                "strict_strain_rejected": 0,
            }
        },
    )
    return SimpleNamespace(
        uid_full="search:uid",
        record=SimpleNamespace(
            search_identity="search:identity",
            settings={"max_supercell_index": 5},
        ),
        has_enumeration_audit=True,
        enumeration_audit=lambda: audit,
        candidates=lambda: _Candidates(),
    )


def test_example_imports_only_the_public_calm_root() -> None:
    tree = ast.parse(SCRIPT_PATH.read_text(encoding="utf-8"))
    calm_imports = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        and (
            (isinstance(node, ast.ImportFrom) and node.module or "").startswith("calm")
            or (
                isinstance(node, ast.Import)
                and any(alias.name.startswith("calm") for alias in node.names)
            )
        )
    ]

    assert len(calm_imports) == 1
    assert isinstance(calm_imports[0], ast.ImportFrom)
    assert calm_imports[0].module == "calm"


def test_example_builds_exact_accounting_and_identity_funnel() -> None:
    module = _load_module()
    project = SimpleNamespace(search=lambda name: _search(module))

    row, multiplicities = module.collect_search(project, "search-a")
    stages, funnel, summary = module.build_outputs([row], multiplicities)

    assert row["raw_hnf_pairs"] == 100
    assert row["orbit_prefilter_surviving_hnf_pairs"] == 20
    assert row["candidate_source_count_total"] == 6
    assert [stage["stage_key"] for stage in stages[:5]] == [
        "raw_hnf_pairs",
        "searchable_hnf_pairs",
        "area_admissible_hnf_pairs",
        "atom_lower_bound_admissible_hnf_pairs",
        "orbit_prefilter_surviving_hnf_pairs",
    ]
    assert stages[0]["operation"] == "baseline"
    assert stages[1]["unit"] == "HNF-pair descriptions"
    assert [stage["count"] for stage in funnel] == [6, 5, 4, 3, 2]
    assert len(stages) == 18
    assert summary["identity_reduction"]["unique_final_pair_classes"] == 2
    assert summary["correspondence_disposition"] == {
        "strain_admissible_correspondences": 6,
        "primitive_atom_rejected": 0,
        "strict_strain_rejected": 0,
        "admitted_descriptions": 6,
    }
    assert summary["checks"]["admitted_descriptions_equal_candidate_source_count"]


def test_example_rejects_duplicate_search_aggregation() -> None:
    module = _load_module()
    project = SimpleNamespace(search=lambda name: _search(module))
    row, multiplicities = module.collect_search(project, "search-a")

    with pytest.raises(RuntimeError, match="unique"):
        module.build_outputs([row, row], multiplicities + multiplicities)


def test_example_rejects_legacy_audit_without_global_counts() -> None:
    module = _load_module()
    legacy = _search(
        module,
        schema="calm.coupled_match_enumeration_audit/v1",
        include_global=False,
    )
    project = SimpleNamespace(search=lambda name: legacy)

    with pytest.raises(RuntimeError, match="resume=False"):
        module.collect_search(project, "legacy-search")


def test_example_help_is_available_without_opening_a_project() -> None:
    module = _load_module()

    with pytest.raises(SystemExit) as exc_info:
        module._parse_args(["--help"])

    assert exc_info.value.code == 0


def test_example_main_writes_all_five_outputs(tmp_path, monkeypatch) -> None:
    module = _load_module()
    project_dir = tmp_path / "project.calm"
    project_dir.mkdir()
    output_dir = tmp_path / "audit"
    project = SimpleNamespace(search=lambda name: _search(module))
    monkeypatch.setattr(module, "open_project", lambda path: project)

    result = module.main(
        [
            "--project-dir",
            str(project_dir),
            "--output-dir",
            str(output_dir),
            "--search-name",
            "search-a",
        ]
    )

    assert result == 0
    assert {path.name for path in output_dir.iterdir()} == {
        "per-search-accounting.csv",
        "aggregate-stage-accounting.csv",
        "deduplication-funnel.csv",
        "class-multiplicity.csv",
        "summary.json",
    }
