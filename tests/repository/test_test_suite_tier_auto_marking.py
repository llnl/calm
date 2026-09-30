from __future__ import annotations

from pathlib import Path

import conftest


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_primary_tier_directories_have_automatic_markers() -> None:
    examples = {
        "tests/architecture/test_boundary.py": {"arch"},
        "tests/repository/test_contract.py": {"repository"},
        "tests/public/test_contract.py": {"public"},
        "tests/examples/test_example.py": {"examples"},
        "tests/slab/test_algorithm.py": {"slab"},
        "tests/integration/test_backend.py": {"integration"},
        "tests/integration/project/test_workflow.py": {"integration", "project"},
        "tests/unit/test_helper.py": {"unit"},
        "tests/unit/interface/test_kernel.py": {"unit", "interface"},
        "tests/unit/project/test_service.py": {"unit"},
        "tests/unit/slab/test_geometry.py": {"unit", "slab"},
    }

    for path, expected in examples.items():
        assert expected <= conftest.markers_for_test_path(REPO_ROOT / path)


def test_established_root_level_test_families_have_automatic_markers() -> None:
    examples = {
        "tests/test_examples_smoke.py": "examples",
        "tests/test_calculators_registry.py": "calculators",
        "tests/test_workspace_followups_smoke.py": "project",
        "tests/test_project_deprecation_warning.py": "project",
        "tests/test_oriented_slab_transforms_json.py": "slab",
        "tests/test_interface_build_kernel.py": "interface",
        "tests/test_registry_search_monte_carlo.py": "interface",
    }

    for path, marker in examples.items():
        assert marker in conftest.markers_for_test_path(REPO_ROOT / path)


def test_marker_rule_tables_use_declared_marker_names() -> None:
    declared = {
        "arch",
        "calculators",
        "examples",
        "integration",
        "interface",
        "project",
        "public",
        "repository",
        "slab",
        "unit",
    }
    marker_names = {marker for _fragment, marker in conftest.TEST_PATH_MARKER_RULES}
    marker_names |= {marker for _prefix, marker in conftest.TEST_FILENAME_MARKER_RULES}

    assert marker_names <= declared


def test_marker_rules_are_unique_by_fragment_or_prefix() -> None:
    path_fragments = [fragment for fragment, _marker in conftest.TEST_PATH_MARKER_RULES]
    filename_prefixes = [prefix for prefix, _marker in conftest.TEST_FILENAME_MARKER_RULES]

    assert len(path_fragments) == len(set(path_fragments))
    assert len(filename_prefixes) == len(set(filename_prefixes))
