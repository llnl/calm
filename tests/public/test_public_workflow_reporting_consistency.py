from __future__ import annotations

import csv
from pathlib import Path
from types import SimpleNamespace

import pytest

import calm
from calm.public.inputs.campaigns import (
    CampaignCase,
    CampaignCaseResult,
    CampaignWorkflowResult,
)
from calm.public.errors import AmbiguousProjectQueryError
from calm.public.records.followups import EnergyWorkflowResult, RelaxationWorkflowResult
from calm.public.collections.persistence import RunCollection


def test_strain_partition_settings_is_in_public_star_import_surface() -> None:
    assert "StrainPartitionSettings" in calm.__all__
    namespace: dict[str, object] = {}
    exec("from calm import *", namespace)
    assert namespace["StrainPartitionSettings"] is calm.StrainPartitionSettings


def test_collection_cardinality_methods_are_consistent() -> None:
    runs = RunCollection(
        [
            {
                "uid_full": "run:one",
                "id_short": "r_one",
                "run_type": "demo",
                "status": "completed",
            },
            {
                "uid_full": "run:two",
                "id_short": "r_two",
                "run_type": "demo",
                "status": "failed",
            },
        ]
    )

    assert runs.one_or_none("missing") is None
    assert runs.get("r_one").uid_full == "run:one"

    with pytest.raises(AmbiguousProjectQueryError):
        runs.get(run_type="demo")

    with pytest.raises(AmbiguousProjectQueryError):
        runs.one_or_none(run_type="demo")


def test_campaign_workflow_result_writes_flat_summary_rows(tmp_path: Path) -> None:
    dataset = SimpleNamespace(
        uid_full="dataset:one",
        id_short="d_one",
        name="demo_dataset",
        to_dict=lambda: {
            "uid_full": "dataset:one",
            "id_short": "d_one",
            "name": "demo_dataset",
        },
    )
    result = CampaignWorkflowResult(
        campaign=SimpleNamespace(
            uid_full="campaign:one",
            id_short="y_one",
            name="demo",
        ),
        run=SimpleNamespace(uid_full="campaign_run:one", id_short="x_one"),
        cases=(
            CampaignCaseResult(
                case=CampaignCase(name="case", search_name="search"),
                status="completed",
                dataset=dataset,
                export_path=tmp_path / "bundle",
            ),
        ),
        status="completed",
    )

    row = result.to_rows()[0]
    assert row["case_name"] == "case"
    assert row["dataset_name"] == "demo_dataset"
    assert result.to_rows(view="provenance")[0]["dataset_uid_full"] == (
        "dataset:one"
    )
    assert result.to_rows(view="all")[0]["case"]["search_name"] == "search"

    output = tmp_path / "campaign.csv"
    result.write_table(output)
    with output.open(newline="", encoding="utf-8") as stream:
        written = list(csv.DictReader(stream))
    assert written[0]["case_name"] == "case"
    assert written[0]["dataset_name"] == "demo_dataset"


class _Rows:
    def __init__(self, rows):
        self._rows = list(rows)

    def to_rows(self, *, view="summary"):
        return [dict(row) for row in self._rows]

    def records(self):
        return []

    def failures(self):
        return _Rows([])


def test_followup_workflow_results_offer_table_reporting(tmp_path: Path) -> None:
    relaxation = RelaxationWorkflowResult(
        run=SimpleNamespace(
            uid_full="run:relax",
            id_short="r_relax",
            status="completed",
        ),
        results=_Rows([{"status": "completed", "target_uid_full": "iface:one"}]),
        relaxed_interfaces=[],
    )
    relax_rows = relaxation.to_rows()
    assert list(relax_rows[0]) == [
        "id_short",
        "status",
        "target_uid_full",
        "converged",
        "n_steps",
        "final_energy_eV",
        "max_force_eV_per_A",
    ]
    assert relaxation.to_rows(view="provenance")[0]["run_uid_full"] == (
        "run:relax"
    )
    relaxation.write_table(tmp_path / "relaxation.csv")

    energy = EnergyWorkflowResult(
        energy_run=SimpleNamespace(uid_full="run:energy", id_short="r_energy"),
        energy_results=_Rows([{"status": "completed", "energy_eV": -1.0}]),
        thermodynamic_run=SimpleNamespace(
            uid_full="run:thermo",
            id_short="r_thermo",
        ),
        thermodynamic_results=_Rows(
            [{"status": "completed", "quantity": "work_of_adhesion"}]
        ),
    )
    rows = energy.to_rows(kind="all")
    assert [row["result_kind"] for row in rows] == [
        "raw_energy",
        "thermodynamic_quantity",
    ]
    energy.write_table(tmp_path / "energy.csv", kind="all")


def test_example_10_uses_campaign_reporting_api() -> None:
    source = Path("examples/10_run_interface_campaign.py").read_text(
        encoding="utf-8"
    )
    assert "result.write_table(results_output)" in source
    assert "csv.DictWriter" not in source
