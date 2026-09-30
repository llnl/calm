from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from typing import Any

from benchmarks.benchmarks.qualification_fixtures import (
    FULL_D4_DISCOVERY_BY_INDEX,
    INDEX5_PAIR_ORACLE,
    INDEX5_SURFACE_ORACLE,
    PAIR_KEY_VERSION,
    expected_full_d4_keys,
)
from benchmarks.benchmarks.run_calm import (
    DETAIL_FIELDS,
    DETAIL_SCHEMA,
    build_parser as build_calm_parser,
)
from benchmarks.benchmarks.run_coupled_qualification import (
    CSV_FIELDS,
    QUALIFICATION_SCHEMA,
    build_parser as build_coupled_parser,
    pair_key_digest,
)
from benchmarks.benchmarks.run_full_suite import (
    BENCHMARK_TEST_TARGETS,
    build_parser as build_full_suite_parser,
)
from benchmarks.benchmarks.run_public_api_qualification import (
    PUBLIC_API_QUALIFICATION_SCHEMA,
    PUBLIC_MATCH_IMPLEMENTATION,
    build_parser as build_public_api_parser,
    pair_identity_digest,
)
from benchmarks.benchmarks.run_pymatgen_zsl import ZSL_DETAIL_FIELDS


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
LEGACY_ROOT = REPOSITORY_ROOT / "benchmarks" / "legacy"
MANIFEST_PATH = LEGACY_ROOT / "baseline_manifest.json"
GOLDEN_ROOT = LEGACY_ROOT / "golden"


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _literal_argparse_defaults(path: Path) -> dict[str, Any]:
    """Extract literal argparse defaults from a legacy module without running it."""

    tree = ast.parse(path.read_text(encoding="utf-8"))
    defaults: dict[str, Any] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        if not isinstance(function, ast.Attribute) or function.attr != "add_argument":
            continue
        flags = [
            ast.literal_eval(argument)
            for argument in node.args
            if isinstance(argument, ast.Constant)
            and isinstance(argument.value, str)
        ]
        long_flags = [flag for flag in flags if flag.startswith("--")]
        if not long_flags:
            continue
        name = long_flags[0][2:].replace("-", "_")
        default_node = next(
            (keyword.value for keyword in node.keywords if keyword.arg == "default"),
            None,
        )
        if default_node is None:
            continue
        try:
            defaults[name] = ast.literal_eval(default_node)
        except (ValueError, TypeError):
            continue
    return defaults


def _identity_digest_from_keys(keys: tuple[tuple[int, ...], ...]) -> str:
    identities = [
        {
            "key_version": PAIR_KEY_VERSION,
            "primitive_pair_key": list(key),
            "pair_symmetry_policy": "full",
            "correspondence_orientation": "proper",
            "material_exchange_identified": False,
        }
        for key in keys
    ]
    ordered = sorted(
        identities,
        key=lambda item: (
            item["key_version"],
            tuple(item["primitive_pair_key"]),
            item["pair_symmetry_policy"],
            item["correspondence_orientation"],
            item["material_exchange_identified"],
        ),
    )
    payload = json.dumps(ordered, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


def test_legacy_manifest_freezes_current_entry_points_and_outputs() -> None:
    manifest = _load_json(MANIFEST_PATH)

    assert manifest["schema"] == "calm.legacy_benchmark_baseline/v1"
    assert manifest["baseline_id"] == "legacy_v1"
    assert manifest["status"] == "frozen"
    assert manifest["calm_match_implementation"] == PUBLIC_MATCH_IMPLEMENTATION

    expected_entry_points = {
        "calm_cross_tool": "benchmarks.run_calm",
        "pymatgen_zsl_cross_tool": "benchmarks.run_pymatgen_zsl",
        "cross_tool_orchestrator": "benchmarks.run_all",
        "plotting": "benchmarks.plot_benchmarks",
        "diagnostics": "benchmarks.diagnose_pair",
        "coupled_qualification": "benchmarks.run_coupled_qualification",
        "public_api_qualification": "benchmarks.run_public_api_qualification",
        "complete_suite": "benchmarks.run_full_suite",
    }
    assert manifest["entry_points"] == expected_entry_points
    for module in expected_entry_points.values():
        wrapper = REPOSITORY_ROOT / Path(*module.split(".")).with_suffix(".py")
        assert wrapper.is_file(), module

    outputs = manifest["outputs"]
    assert outputs["calm_cross_tool_csv"]["schema"] == DETAIL_SCHEMA
    assert tuple(outputs["calm_cross_tool_csv"]["fields"]) == DETAIL_FIELDS
    assert outputs["pymatgen_zsl_cross_tool_csv"]["schema"] is None
    assert tuple(outputs["pymatgen_zsl_cross_tool_csv"]["fields"]) == (
        ZSL_DETAIL_FIELDS
    )
    assert outputs["coupled_qualification_csv"]["schema"] == (
        QUALIFICATION_SCHEMA
    )
    assert tuple(outputs["coupled_qualification_csv"]["fields"]) == CSV_FIELDS
    assert outputs["public_api_qualification_json"]["schema"] == (
        PUBLIC_API_QUALIFICATION_SCHEMA
    )

    for relative_path in manifest["golden_files"]:
        assert (LEGACY_ROOT / relative_path).is_file(), relative_path


def test_legacy_default_profiles_match_current_cli_defaults() -> None:
    profiles = _load_json(MANIFEST_PATH)["default_profiles"]

    calm_args = build_calm_parser().parse_args([])
    calm_profile = profiles["calm_cross_tool"]
    for name in (
        "out",
        "max_areas",
        "cond_max",
        "eps_principal_max",
        "tau_max",
        "surface_symmetry_mode",
        "pair_symmetry_policy",
        "correspondence_orientation",
        "identify_material_exchange",
    ):
        assert getattr(calm_args, name) == calm_profile[name]

    coupled_args = build_coupled_parser().parse_args(
        ["--out", "qualification.csv", "--k-max", "5"]
    )
    coupled_profile = profiles["coupled_qualification"]
    for name in (
        "cond_max",
        "N_at_max",
        "w_match",
        "n_atoms_A",
        "n_atoms_B",
        "surface_symmetry_mode",
        "pair_symmetry_policy",
        "correspondence_orientation",
        "identify_material_exchange",
    ):
        assert getattr(coupled_args, name) == coupled_profile[name]

    public_args = build_public_api_parser().parse_args([])
    public_profile = profiles["public_api_qualification"]
    for name in (
        "project",
        "out",
        "max_principal_strain",
        "max_supercell_index",
        "max_atoms",
        "max_candidates",
        "mismatch_weight",
    ):
        assert getattr(public_args, name) == public_profile[name]

    full_args = build_full_suite_parser().parse_args([])
    full_profile = profiles["complete_suite"]
    for name in ("outdir", "max_areas", "pareto_area"):
        assert getattr(full_args, name) == full_profile[name]
    assert (not full_args.no_measure_memory) is full_profile["measure_memory"]

    zsl_defaults = _literal_argparse_defaults(
        REPOSITORY_ROOT
        / "benchmarks"
        / "benchmarks"
        / "run_pymatgen_zsl.py"
    )
    zsl_profile = profiles["pymatgen_zsl_cross_tool"]
    assert zsl_defaults["out"] == zsl_profile["out"]
    assert zsl_defaults["max_areas"] == zsl_profile["max_areas"]
    assert zsl_defaults["max_length_tol"] == zsl_profile["max_length_tol"]
    assert zsl_defaults["max_angle_tol"] == zsl_profile["max_angle_tol"]
    assert zsl_defaults["max_area_ratio_tol"] == zsl_profile[
        "max_area_ratio_tol"
    ]
    assert zsl_defaults["eps_principal_max"] == zsl_profile[
        "eps_principal_max_for_score"
    ]

    run_all_defaults = _literal_argparse_defaults(
        REPOSITORY_ROOT / "benchmarks" / "benchmarks" / "run_all.py"
    )
    assert run_all_defaults["outdir"] == full_profile["outdir"]
    assert run_all_defaults["max_areas"] == full_profile["max_areas"]
    assert run_all_defaults["pareto_area"] == full_profile["pareto_area"]


def test_legacy_coupled_csv_header_is_frozen() -> None:
    header = _load_json(GOLDEN_ROOT / "coupled_smoke_headers.json")
    assert header["schema"] == QUALIFICATION_SCHEMA
    assert tuple(header["fields"]) == CSV_FIELDS


def test_legacy_equal_square_k5_golden_matches_exact_fixture() -> None:
    golden = _load_json(GOLDEN_ROOT / "equal_square_k5_summary.json")
    keys = expected_full_d4_keys(5)

    assert golden["schema"] == QUALIFICATION_SCHEMA
    assert golden["implementation"] == PUBLIC_MATCH_IMPLEMENTATION
    assert golden["k_max"] == 5
    assert golden["class_count"] == len(keys) == 2
    assert golden["first_discovery_indices"] == [1, 5]
    assert golden["primitive_pair_keys"] == [list(key) for key in keys]
    assert golden["pair_key_sha256"] == pair_key_digest(keys)
    assert golden["pair_identity_sha256"] == _identity_digest_from_keys(keys)
    assert golden["index5_surface_oracle"] == INDEX5_SURFACE_ORACLE
    assert golden["index5_pair_oracle"] == INDEX5_PAIR_ORACLE
    assert golden["oracle_status"] == "pass"


def test_legacy_equal_square_k30_golden_matches_exact_fixture() -> None:
    golden = _load_json(GOLDEN_ROOT / "equal_square_k30_summary.json")
    keys = expected_full_d4_keys(30)

    assert golden["schema"] == QUALIFICATION_SCHEMA
    assert golden["implementation"] == PUBLIC_MATCH_IMPLEMENTATION
    assert golden["k_max"] == 30
    assert golden["class_count"] == len(keys) == 6
    assert golden["first_discovery_indices"] == [
        index for index, _ in FULL_D4_DISCOVERY_BY_INDEX
    ]
    assert golden["primitive_pair_keys"] == [list(key) for key in keys]
    assert golden["pair_key_sha256"] == pair_key_digest(keys)
    assert golden["pair_identity_sha256"] == _identity_digest_from_keys(keys)
    assert golden["oracle_status"] == "pass"


def test_legacy_public_api_golden_has_recomputable_identity_evidence() -> None:
    golden = _load_json(GOLDEN_ROOT / "public_api_summary.json")
    identities = golden["pair_identities"]

    assert golden["schema"] == PUBLIC_API_QUALIFICATION_SCHEMA
    assert golden["implementation"] == PUBLIC_MATCH_IMPLEMENTATION
    assert golden["public_entry_point"] == "Project.search_interfaces"
    assert golden["candidate_identity_algorithm"] == PUBLIC_MATCH_IMPLEMENTATION
    assert golden["candidate_count"] == len(identities) == 4
    assert golden["run_progress_candidate_count"] == len(identities)
    assert golden["retained_count"] == len(identities)
    assert golden["pareto_population_size"] == len(identities)
    normalized_identities = [
        {
            "key_version": identity["key_version"],
            "primitive_pair_key": identity["primitive_pair_key"],
            "pair_symmetry_policy": identity["pair_symmetry_policy"],
            "correspondence_orientation": identity[
                "correspondence_orientation"
            ],
            "material_exchange_identified": identity[
                "material_exchange_identified"
            ],
        }
        for identity in identities
    ]
    assert golden["pair_identity_sha256"] == pair_identity_digest(
        normalized_identities
    )
    assert golden["pair_key_versions"] == [PAIR_KEY_VERSION]
    assert golden["pair_identity_policies"] == [["full", "proper", False]]


def test_complete_suite_runs_the_legacy_and_performance_contract_tests() -> None:
    assert "tests/repository/test_legacy_benchmark_contract.py" in (
        BENCHMARK_TEST_TARGETS
    )
    assert "tests/repository/test_performance_qualification_contract.py" in (
        BENCHMARK_TEST_TARGETS
    )


def test_legacy_benchmarks_use_current_interface_implementation_owners() -> None:
    benchmark_root = REPOSITORY_ROOT / "benchmarks" / "benchmarks"
    benchmark_sources = {
        path.relative_to(benchmark_root).as_posix(): path.read_text(encoding="utf-8")
        for path in benchmark_root.rglob("*.py")
    }
    retired_paths = (
        "calm.interface._coupled_matching_orchestrator",
        "calm.interface._matching_pair_identity",
        "calm.interface._matching_types",
        "calm.interface.audit",
        "calm.interface.conditioning",
        "from calm.interface.matching import search_primitive_match_classes",
    )
    for name, source in benchmark_sources.items():
        for retired in retired_paths:
            assert retired not in source, f"{name} imports retired path {retired}"

    assert (
        "from calm.interface.matching._orchestrator import"
        in benchmark_sources["run_coupled_qualification.py"]
    )
    assert (
        "from calm.interface.matching.audit import CoupledMatchEnumerationAudit"
        in benchmark_sources["run_coupled_qualification.py"]
    )
    for name in ("run_calm.py", "run_coupled_qualification.py"):
        source = benchmark_sources[name]
        assert "from calm.interface.matching.conditioning import" in source
        assert (
            "from calm.interface.matching.search import "
            "search_primitive_match_classes"
        ) in source

    for name in (
        "claims/zsl/coupled_projection.py",
        "claims/zsl/projection_suite.py",
    ):
        assert "from calm.interface.matching._types import" in benchmark_sources[name]
    assert (
        "from calm.interface.matching._pair_identity import"
        in benchmark_sources["claims/zsl/coupled_projection.py"]
    )
