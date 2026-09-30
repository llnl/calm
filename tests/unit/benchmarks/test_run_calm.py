from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import numpy as np


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
    spglib.__version__ = "stage12a-test-stub"
    sys.modules["spglib"] = spglib
    _INSERTED_STUBS.append("spglib")

try:
    from benchmarks.benchmarks.run_calm import (
        DETAIL_FIELDS,
        DETAIL_SCHEMA,
        main,
        run_calm_for_pair,
    )
finally:
    for _module_name in _INSERTED_STUBS:
        sys.modules.pop(_module_name, None)


def _pair_keys(rows: list[dict[str, object]]) -> tuple[tuple[int, ...], ...]:
    return tuple(tuple(json.loads(str(row["pair_key"]))) for row in rows)


def test_detailed_runner_uses_only_coupled_primitive_classes() -> None:
    rows = run_calm_for_pair(
        pair_name="equal_square_test",
        A2=np.eye(2),
        B2=np.eye(2),
        max_area=1.0,
        eps_principal_max=0.0,
        tau_max=0.0,
        N_at_max=2,
        w_match=1.0,
    )

    assert rows
    assert len(set(_pair_keys(rows))) == len(rows)
    for row in rows:
        assert tuple(row) == DETAIL_FIELDS
        assert row["schema"] == DETAIL_SCHEMA
        assert row["method"] == "calm_coupled_v2"
        assert row["implementation"] == "primitive_coupled_pair_v2"
        assert row["surface_symmetry_mode"] == "identity_only"
        assert row["surface_symmetry_A_status"] == "identity_only"
        assert row["surface_symmetry_A_operation_count"] == 1
        assert row["pair_key_version"] == 1
        identity = json.loads(str(row["pair_identity"]))
        assert identity == {
            "key_version": 1,
            "primitive_pair_key": list(json.loads(str(row["pair_key"]))),
            "pair_symmetry_policy": "full",
            "correspondence_orientation": "proper",
            "material_exchange_identified": False,
        }
        assert json.loads(str(row["source_index_pairs"]))
        assert row["max_abs_principal_strain"] == 0.0
        assert row["log_area_ratio"] == 0.0
        assert "dedupe_by_key" not in row
        assert "matching_algorithm" not in row


def test_detailed_runner_is_scale_equivariant_and_deterministic() -> None:
    basis_a = np.array([[1.0, 0.2], [0.0, 1.3]])
    basis_b = np.array([[1.01, 0.2], [0.0, 1.29]])
    first = run_calm_for_pair(
        pair_name="scaled_oblique",
        A2=basis_a,
        B2=basis_b,
        max_area=6.0,
        eps_principal_max=0.05,
        N_at_max=100,
    )
    repeated = run_calm_for_pair(
        pair_name="scaled_oblique",
        A2=basis_a,
        B2=basis_b,
        max_area=6.0,
        eps_principal_max=0.05,
        N_at_max=100,
    )
    scaled = run_calm_for_pair(
        pair_name="scaled_oblique",
        A2=3.0 * basis_a,
        B2=3.0 * basis_b,
        max_area=54.0,
        eps_principal_max=0.05,
        N_at_max=100,
    )

    assert first
    assert _pair_keys(first) == _pair_keys(repeated)
    assert _pair_keys(first) == _pair_keys(scaled)
    assert [row["match_sig"] for row in first] == [
        row["match_sig"] for row in repeated
    ]
    assert np.allclose(
        [row["d_cell"] for row in first],
        [row["d_cell"] for row in scaled],
        rtol=1.0e-10,
        atol=1.0e-12,
    )


def test_detailed_runner_cli_writes_current_calm_rows(tmp_path: Path) -> None:
    output = tmp_path / "calm.csv"
    assert main(
        [
            "--out",
            str(output),
            "--pair",
            "rect_small_mismatch",
            "--max-areas",
            "25",
            "--eps-principal-max",
            "0.1",
        ]
    ) == 0

    with output.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    assert tuple(rows[0]) == DETAIL_FIELDS
    assert {row["schema"] for row in rows} == {DETAIL_SCHEMA}
    assert {row["method"] for row in rows} == {"calm_coupled_v2"}
    assert {row["implementation"] for row in rows} == {
        "primitive_coupled_pair_v2"
    }


def test_gate_diagnostic_csv_helpers_filter_numerical_area(tmp_path: Path) -> None:
    from benchmarks.benchmarks.common_metrics import filter_rows, load_csv

    path = tmp_path / "rows.csv"
    path.write_text(
        "pair,max_area,value\n"
        "case_a,25.0,one\n"
        "case_a,50.0,two\n"
        "case_b,25.0,three\n",
        encoding="utf-8",
    )

    rows = filter_rows(load_csv(path), pair="case_a", max_area=25)
    assert rows == [{"pair": "case_a", "max_area": "25.0", "value": "one"}]
