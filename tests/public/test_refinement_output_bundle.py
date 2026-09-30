"""Contracts for the public interface-refinement output bundle."""

from __future__ import annotations

import csv
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from calm.public.records.followups import InterfaceRefinementResult
from calm.public.records.interface_views import INTERFACE_STRAIN_COLUMNS
from calm.slab.oriented.cell_contract import (
    INTERFACE_DEFORMATION_ACCOUNTING_INFO_KEY,
)


class _Cell:
    def __init__(self, array) -> None:
        self.array = np.asarray(array, dtype=float)


class _DiagnosticAtoms:
    def __len__(self) -> int:
        return 88

    def __init__(self) -> None:
        lower = np.diag([1.02, 0.98, 1.0])
        upper = np.diag([0.99, 1.01, 1.0])
        identity = np.eye(3)
        self.cell = _Cell(np.diag([4.0, 5.0, 20.0]))
        self.info = {
            INTERFACE_DEFORMATION_ACCOUNTING_INFO_KEY: {
                "policy": "composed_slab_deformation",
                "version": 1,
                "lower": {
                    "F_construction_slab": identity.tolist(),
                    "F_interface_slab": lower.tolist(),
                    "F_total_slab": lower.tolist(),
                },
                "upper": {
                    "F_construction_slab": identity.tolist(),
                    "F_interface_slab": upper.tolist(),
                    "F_total_slab": upper.tolist(),
                },
            }
        }


class _FakeStructureQueries:
    def __init__(self) -> None:
        self.identifiers: list[str] = []

    def get_interface_atoms(self, identifier: str):
        self.identifiers.append(identifier)
        return _DiagnosticAtoms()


class _FakeProject:
    def __init__(self) -> None:
        self._structure_queries = _FakeStructureQueries()


_FAKE_PROJECT = _FakeProject()


class _FakeStrainScan:
    project = _FAKE_PROJECT
    run = SimpleNamespace(id_short="run_strain")

    def write_table(self, path: str | Path) -> None:
        Path(path).write_text("prototype_id,alpha\nP0000,0.5\n", encoding="utf-8")

    def plot(self, *, metric: str | None = None, filename: str | Path | None = None):
        assert metric == "potential_energy_density_eV_per_A2"
        assert filename is not None
        Path(filename).write_bytes(b"plot")
        return None


class _FakeRegistryRun:
    project = _FAKE_PROJECT
    run = SimpleNamespace(id_short="run_registry")

    def write_table(self, path: str | Path) -> None:
        Path(path).write_text("prototype_id,score\nP0000,-1.0\n", encoding="utf-8")

    def write_trace(self, path: str | Path) -> None:
        Path(path).write_text("step,best_score\n0,-1.0\n", encoding="utf-8")


def _interface_row(*, stage: str, suffix: str) -> dict[str, object]:
    return {
        "uid_full": f"interface:{suffix}",
        "id_short": f"i_{suffix}",
        "label": f"{stage} interface",
        "stage": stage,
        "search_name": "LiF_Li2O_100_interface_match",
        "candidate_id": "C0000",
        "strain_alpha": 0.5,
        "registry_shift_frac_a": [0.125, 0.25],
        "gap_A": 2.0,
        "vacuum_A": 30.0,
        "n_atoms": 88,
        "area_A2": 10.0,
        "spec": {
            "stage": stage,
            "strain_state": {
                "F_A": np.diag([1.02, 0.98, 1.0]).tolist(),
                "F_B": np.diag([0.99, 1.01, 1.0]).tolist(),
            },
        },
    }


def test_refinement_output_bundle_uses_prefix_and_shared_interface_view(
    tmp_path: Path,
) -> None:
    result = InterfaceRefinementResult(
        ok=True,
        issues=[],
        strain_scan=_FakeStrainScan(),
        registry_run=_FakeRegistryRun(),
        strain_interfaces=[
            _interface_row(stage="strain_partitioned", suffix="strain")
        ],
        registry_interfaces=[
            _interface_row(stage="registry_refined", suffix="registry")
        ],
    )

    outputs = result.write_outputs(
        tmp_path,
        filename_prefix="06_",
        plots=("potential_energy_density_eV_per_A2",),
    )

    assert {path.name for path in outputs.values()} == {
        "06_strain_partition_results.csv",
        "06_registry_search_results.csv",
        "06_registry_search_trace.csv",
        "06_strain_partitioned_interfaces.csv",
        "06_strain_partitioned_interface_strain.csv",
        "06_registry_refined_interfaces.csv",
        "06_registry_refined_interface_strain.csv",
        "06_strain_partition_potential_energy_density_eV_per_A2.png",
    }

    with outputs["strain_interfaces"].open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert tuple(rows[0]) == (
        "id_short",
        "label",
        "stage",
        "search_name",
        "candidate_id",
        "strain_alpha",
        "registry_shift_frac_a",
        "gap_A",
        "vacuum_A",
        "n_atoms",
        "area_A2",
        "prototype_area_A2",
    )
    assert rows[0]["id_short"] == "i_strain"
    assert rows[0]["stage"] == "strain_partitioned"
    assert int(rows[0]["n_atoms"]) == 88
    assert float(rows[0]["area_A2"]) == pytest.approx(20.0)
    assert float(rows[0]["prototype_area_A2"]) == pytest.approx(10.0)

    with outputs["registry_interfaces"].open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert rows[0]["id_short"] == "i_registry"
    assert rows[0]["stage"] == "registry_refined"
    assert int(rows[0]["n_atoms"]) == 88
    assert float(rows[0]["area_A2"]) == pytest.approx(20.0)
    assert float(rows[0]["prototype_area_A2"]) == pytest.approx(10.0)

    for key in ("strain_interface_strain", "registry_interface_strain"):
        with outputs[key].open(newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        assert tuple(rows[0]) == INTERFACE_STRAIN_COLUMNS
        assert rows[0]["deformation_state"] == "pre_relaxation"


def test_refinement_output_prefix_cannot_escape_output_directory(
    tmp_path: Path,
) -> None:
    result = InterfaceRefinementResult(ok=True, issues=[])

    for prefix in ("nested/", "nested\\", "bad\x00"):
        with pytest.raises(ValueError, match="filename prefix"):
            result.write_outputs(tmp_path, filename_prefix=prefix, plots=())
