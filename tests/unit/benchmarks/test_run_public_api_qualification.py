from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]

from benchmarks.benchmarks.run_public_api_qualification import (
    PUBLIC_API_QUALIFICATION_SCHEMA,
    PUBLIC_MATCH_IMPLEMENTATION,
    _validate_candidate_population,
    _validate_pair_identity,
    _validate_persisted_run,
    build_parser,
    pair_identity_digest,
)


def _identity(*, version: int = 1) -> dict[str, object]:
    return {
        "key_version": version,
        "primitive_pair_key": [-1, 0, 0, -1, 1, 0, 0, 1],
        "pair_symmetry_policy": "full",
        "correspondence_orientation": "proper",
        "material_exchange_identified": False,
    }


def test_public_api_qualification_schema_is_versioned() -> None:
    assert PUBLIC_API_QUALIFICATION_SCHEMA.endswith("/v2")


def test_public_pair_identity_validation_requires_complete_versioned_identity() -> None:
    assert _validate_pair_identity(_identity()) == _identity()

    incomplete = _identity()
    incomplete.pop("key_version")
    with pytest.raises(RuntimeError, match="incomplete"):
        _validate_pair_identity(incomplete)

    invalid_key = _identity()
    invalid_key["primitive_pair_key"] = [1, 0]
    with pytest.raises(RuntimeError, match="eight integers"):
        _validate_pair_identity(invalid_key)


def test_public_pair_identity_digest_is_order_independent_and_policy_qualified() -> None:
    first = _identity()
    second = _identity(version=2)
    assert pair_identity_digest([first, second]) == pair_identity_digest(
        [second, first]
    )
    assert pair_identity_digest([first]) != pair_identity_digest([second])


def test_public_candidate_population_uses_persisted_payload_evidence() -> None:
    run_uid = "run:v2:qualification"
    candidate = SimpleNamespace(
        to_dict=lambda: {
            "identity_algorithm": PUBLIC_MATCH_IMPLEMENTATION,
            "run_uid": run_uid,
            "pair_identity": _identity(),
            "pareto_population_size": 1,
        }
    )

    rows, identities, population_size = _validate_candidate_population(
        [candidate],
        run_uid=run_uid,
    )

    assert rows[0]["identity_algorithm"] == PUBLIC_MATCH_IMPLEMENTATION
    assert identities == [_identity()]
    assert population_size == 1


def test_public_run_implementation_is_read_from_spec_not_progress() -> None:
    search_identity = "interface_search:qualification"
    settings = {
        "max_supercell_index": 5,
        "surface_symmetry_mode": "discover",
    }
    surface_uids = {
        "surface_a": "slab:v2:a",
        "surface_b": "slab:v2:b",
    }
    run = SimpleNamespace(
        status="done",
        spec={
            "schema_version": 2,
            "implementation": PUBLIC_MATCH_IMPLEMENTATION,
            "search_identity": search_identity,
            "settings": settings,
            "surface_a": {"uid_full": surface_uids["surface_a"]},
            "surface_b": {"uid_full": surface_uids["surface_b"]},
        },
        progress={
            "phase": "complete",
            "n_candidates": 4,
        },
    )

    spec, progress = _validate_persisted_run(
        run,
        expected_search_identity=search_identity,
        expected_settings=settings,
        expected_surface_uids=surface_uids,
        candidate_count=4,
    )

    assert spec["implementation"] == PUBLIC_MATCH_IMPLEMENTATION
    assert "implementation" not in progress
    assert progress["n_candidates"] == 4


def test_public_run_rejects_implementation_reported_only_in_progress() -> None:
    run = SimpleNamespace(
        status="done",
        spec={
            "schema_version": 2,
            "search_identity": "interface_search:qualification",
            "settings": {},
            "surface_a": {"uid_full": "slab:v2:a"},
            "surface_b": {"uid_full": "slab:v2:b"},
        },
        progress={
            "phase": "complete",
            "n_candidates": 1,
            "implementation": PUBLIC_MATCH_IMPLEMENTATION,
        },
    )

    with pytest.raises(RuntimeError, match="run specification"):
        _validate_persisted_run(
            run,
            expected_search_identity="interface_search:qualification",
            expected_settings={},
            expected_surface_uids={
                "surface_a": "slab:v2:a",
                "surface_b": "slab:v2:b",
            },
            candidate_count=1,
        )


def test_public_workflow_imports_calm_only_through_supported_top_level_api() -> None:
    source_path = (
        REPOSITORY_ROOT
        / "benchmarks"
        / "benchmarks"
        / "run_public_api_qualification.py"
    )
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    calm_imports: list[tuple[str, tuple[str, ...]]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "calm" or alias.name.startswith("calm."):
                    calm_imports.append((alias.name, ()))
        elif isinstance(node, ast.ImportFrom) and (
            node.module == "calm" or str(node.module).startswith("calm.")
        ):
            calm_imports.append(
                (str(node.module), tuple(alias.name for alias in node.names))
            )

    assert calm_imports == [
        ("calm", ()),
        ("calm", ("Material", "SearchSettings", "open_project")),
    ]


def test_public_api_cli_defaults_to_bundled_current_examples() -> None:
    args = build_parser().parse_args([])
    assert Path(args.structure_a).name == "LiF.poscar"
    assert Path(args.structure_b).name == "Li2O.poscar"
    assert args.max_supercell_index == 5
    assert args.max_candidates == 500
    assert args.project == "public_api_qualification.calm"
    assert args.out == "public_api_qualification.json"
    assert args.reset is False
