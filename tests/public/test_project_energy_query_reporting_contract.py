"""Authoritative public query and presentation contract for energy results."""

from __future__ import annotations

from pathlib import Path

import pytest

from energy_result_fixtures import raw_energy_payload

from calm.public.project import Project
from calm.public.records.persistence import ProjectEnergyResult


class _EnergyWorkspace:
    def __init__(self) -> None:
        self.rows = [
            {
                "uid_full": "followup:energy:1",
                "id_short": "f_energy_1",
                "run_uid_full": "run:energy:1",
                "run_id_short": "r_energy_1",
                "prototype_uid_full": "proto:1",
                "target_uid_full": "interface:1",
                "target_kind": "interface",
                "kind": "energy_stage",
                "status": "done",
                "payload": raw_energy_payload(
                    -100.0,
                    backend_name="real",
                    backend_identity={
                        "name": "real",
                        "family": "chgnet",
                        "model": "0.3.0",
                    },
                    workflow_metadata={"max_principal_strain": 0.012},
                ),
            }
        ]

    def list_followup_results(
        self,
        *,
        run=None,
        prototype=None,
        kind=None,
        limit=None,
    ):
        rows = [
            row
            for row in self.rows
            if (run is None or run in {row["run_uid_full"], row["run_id_short"]})
            and (prototype is None or prototype == row["prototype_uid_full"])
            and (kind is None or kind == row["kind"])
        ]
        return rows if limit is None else rows[:limit]

    def get_followup_result(self, identifier):
        for row in self.rows:
            if identifier in {row["uid_full"], row["id_short"]}:
                return row
        raise KeyError(identifier)


def test_project_energy_results_are_typed_and_authoritative(tmp_path: Path) -> None:
    project = Project(_EnergyWorkspace(), path=tmp_path / "example.calm")

    results = project.energy_results()
    assert len(results) == 1
    result = results[0]

    assert isinstance(result, ProjectEnergyResult)
    assert result.is_authoritative
    assert result.uid_full == "followup:energy:1"
    assert result.target_uid_full == "interface:1"
    assert result.energy_eV == pytest.approx(-100.0)
    assert result.backend_identity == {
        "name": "real",
        "family": "chgnet",
        "model": "0.3.0",
    }
    assert results.interface("interface:1")[0] == result
    assert results.completed()[0] == result
    assert project.energy_result("f_energy_1") == result


def test_energy_queries_have_no_parallel_reporting_api(tmp_path: Path) -> None:
    project = Project(_EnergyWorkspace(), path=tmp_path / "example.calm")

    assert not hasattr(project, "energies")
    assert not hasattr(project, "_public_records")
    assert not (tmp_path / "example.calm" / "calm-public-records.json").exists()
    assert project.energy_results().to_rows(view="all")[0]["energy_eV"] == -100.0


def test_authoritative_energy_collection_writes_tables_and_plots(
    tmp_path: Path,
) -> None:
    pytest.importorskip("matplotlib")
    project = Project(_EnergyWorkspace(), path=tmp_path / "example.calm")
    results = project.energy_results()

    table_path = tmp_path / "tables" / "energies.csv"
    distribution_path = tmp_path / "figures" / "energy_distribution.png"
    strain_path = tmp_path / "figures" / "energy_vs_strain.png"

    results.write_table(table_path, view="all")
    fig1, ax1 = results.plot_distribution(save=distribution_path)
    fig2, ax2 = results.plot_energy_vs_strain(save=strain_path)

    assert table_path.exists()
    assert "energy_eV" in table_path.read_text(encoding="utf-8")
    assert distribution_path.exists()
    assert strain_path.exists()
    assert fig1 is not None and ax1 is not None
    assert fig2 is not None and ax2 is not None
