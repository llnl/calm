from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path
from types import ModuleType


_INSERTED_STUBS: list[str] = []
if "ase" not in sys.modules and importlib.util.find_spec("ase") is None:
    ase = ModuleType("ase")

    class Atoms:
        pass

    ase.Atoms = Atoms
    sys.modules["ase"] = ase
    _INSERTED_STUBS.append("ase")
if "spglib" not in sys.modules and importlib.util.find_spec("spglib") is None:
    spglib = ModuleType("spglib")
    spglib.__version__ = "stage10d-test-stub"
    sys.modules["spglib"] = spglib
    _INSERTED_STUBS.append("spglib")

try:
    from benchmarks.benchmarks.run_coupled_qualification import (
        CSV_FIELDS,
        QUALIFICATION_SCHEMA,
        default_qualification_cases,
        main,
        pair_identity_digest,
        pair_key_digest,
        run_qualification_case,
    )
finally:
    for _module_name in _INSERTED_STUBS:
        sys.modules.pop(_module_name, None)


def test_default_qualification_matrix_covers_required_geometry_families() -> None:
    cases = default_qualification_cases()
    assert [case.name for case in cases] == [
        "equal_square",
        "rect_small_mismatch",
        "hex_near_degenerate",
        "oblique_tradeoff",
    ]
    assert {case.family for case in cases} == {
        "square",
        "rectangular",
        "hexagonal",
        "oblique",
    }
    assert cases[0].symmetry_fixture == "full_square_d4"
    assert cases[0].default_eps_principal_max == 1.0e-10
    assert all(case.symmetry_fixture is None for case in cases[1:])


def test_pair_key_digest_is_order_independent_and_exact() -> None:
    first = (1, 0, 0, 1, 1, 0, 0, 1)
    second = (-1, 0, 0, -1, 1, 0, 0, 1)
    assert pair_key_digest([first, second]) == pair_key_digest([second, first])
    assert pair_key_digest([first]) != pair_key_digest([second])


def test_pair_identity_digest_includes_policy_and_key_version() -> None:
    class Policy:
        key_version = 1
        pair_symmetry = "full"
        correspondence_orientation = "proper"
        identify_material_exchange = False

    class Representative:
        pair_identity_policy = Policy()

    class MatchClass:
        pair_key = (-1, 0, 0, -1, 1, 0, 0, 1)
        representative = Representative()

    baseline = pair_identity_digest([MatchClass()])
    Policy.key_version = 2
    changed = pair_identity_digest([MatchClass()])
    Policy.key_version = 1
    assert baseline != changed


def test_equal_square_smoke_row_uses_full_d4_and_versioned_identity() -> None:
    square = default_qualification_cases()[0]
    row = run_qualification_case(square, k_max=1)

    assert tuple(row) == CSV_FIELDS
    assert row["schema"] == QUALIFICATION_SCHEMA
    assert row["implementation"] == "primitive_coupled_pair_v2"
    assert row["symmetry_source"] == "full_square_d4"
    assert row["surface_symmetry_mode"] == "explicit_fixture"
    assert row["surface_symmetry_A_operation_count"] == 8
    assert row["surface_symmetry_B_operation_count"] == 8
    assert row["eps_principal_max"] == 1.0e-10
    assert row["pair_key_version"] == 1
    assert row["class_count"] == 1
    assert row["oracle_status"] == "pass"
    assert row["surface_A_hnf_generated"] == 1
    assert row["surface_B_hnf_generated"] == 1
    assert row["primitive_classes_created"] == row["class_count"]
    assert row["correspondence_limit_failures"] == 0
    repeated = run_qualification_case(square, k_max=1)
    assert row["pair_key_sha256"] == repeated["pair_key_sha256"]
    assert row["pair_identity_sha256"] == repeated["pair_identity_sha256"]
    assert len(row["pair_key_sha256"]) == 64
    assert len(row["pair_identity_sha256"]) == 64


def test_equal_square_k5_reproduces_manuscript_oracle() -> None:
    square = default_qualification_cases()[0]
    row = run_qualification_case(square, k_max=5)

    assert row["oracle_status"] == "pass"
    assert row["class_count"] == 2
    assert row["surface_A_hnf_generated"] == 21
    assert row["surface_A_comparison_orbits"] == 12
    assert row["orbit_pairs_considered"] == 34
    assert row["strain_admissible_correspondences"] == 92
    assert row["primitive_classes_created"] == 2
    assert row["sources_aggregated_by_pair_key"] == 90


def test_cli_writes_stable_csv_schema(tmp_path: Path) -> None:
    output = tmp_path / "qualification.csv"
    assert main([
        "--out",
        str(output),
        "--case",
        "equal_square",
        "--k-max",
        "1",
    ]) == 0

    with output.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows and tuple(rows[0]) == CSV_FIELDS
    assert rows[0]["case"] == "equal_square"
    assert int(rows[0]["class_count"]) > 0
