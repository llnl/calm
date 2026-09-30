from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

import pytest

from energy_result_fixtures import (
    raw_energy_payload,
    reference_energy_payload,
    thermodynamic_payload,
)
from test_helpers import (
    make_current_registry_result_payload,
    make_current_strain_result_payload,
)

from calm.public.collections.persistence import (
    EnergyResultCollection,
    ReferenceEnergyResultCollection,
    RelaxationResultCollection,
    ThermodynamicResultCollection,
)
from calm.public.records.followups import (
    EnergyWorkflowResult,
    ReferenceEnergyWorkflowResult,
    RegistrySearchRun,
    RelaxationWorkflowResult,
    StrainPartitionScan,
)


RELAXATION_SUMMARY = [
    "id_short",
    "status",
    "target_uid_full",
    "converged",
    "n_steps",
    "final_energy_eV",
    "max_force_eV_per_A",
]
RAW_ENERGY_SUMMARY = [
    "id_short",
    "status",
    "target_uid_full",
    "target_kind",
    "quantity",
    "energy_eV",
]
REFERENCE_ENERGY_SUMMARY = [
    "id_short",
    "status",
    "target_uid_full",
    "reference_kind",
    "side",
    "energy_eV",
    "energy_eV_per_formula_unit",
]
THERMODYNAMIC_SUMMARY = [
    "id_short",
    "status",
    "target_uid_full",
    "quantity",
    "value_eV_per_A2",
    "value_J_per_m2",
]
STRAIN_PARTITION_SUMMARY = [
    "prototype_id",
    "alpha",
    "is_selected",
    "potential_energy_density_eV_per_A2",
    "gamma_eV_per_A2",
    "gamma_J_per_m2",
]
REGISTRY_SEARCH_SUMMARY = [
    "prototype_id",
    "registry_shift_frac_a",
    "gap_A",
    "vacuum_A",
    "score",
    "n_steps",
    "n_accepted",
]


def _relaxation_row() -> dict:
    return {
        "uid_full": "followup:relax",
        "id_short": "f_relax",
        "run_uid_full": "run:relax",
        "run_id_short": "r_relax",
        "prototype_uid_full": "proto:1",
        "target_uid_full": "iface:1",
        "target_kind": "interface",
        "kind": "relaxation_stage",
        "status": "done",
        "best_energy": -8.0,
        "n_points": 12,
        "payload": {
            "relaxed_interface_uid": "iface:relaxed",
            "final_energy_eV": -8.0,
            "n_steps": 12,
            "converged": True,
            "optimizer_reported_converged": True,
            "residual_satisfied": True,
            "max_force_eV_per_A": 0.03,
            "max_optimizer_residual": 0.03,
            "convergence_certificate": {"termination_reason": "fmax_satisfied"},
            "relaxation_backend": "deterministic",
            "backend_identity": {"name": "deterministic"},
            "relaxation_settings": {"fmax": 0.05},
            "artifact_refs": ["artifact:relax"],
        },
        "authority": "authoritative",
    }


def _raw_energy_row() -> dict:
    return {
        "uid_full": "followup:energy",
        "id_short": "f_energy",
        "run_uid_full": "run:energy",
        "run_id_short": "r_energy",
        "prototype_uid_full": "proto:1",
        "target_uid_full": "iface:1",
        "target_kind": "interface",
        "kind": "energy_stage",
        "status": "done",
        "best_energy": -5.0,
        "payload": raw_energy_payload(-5.0),
        "authority": "authoritative",
    }


def _reference_row() -> dict:
    return {
        "uid_full": "followup:reference",
        "id_short": "f_reference",
        "run_uid_full": "run:reference",
        "run_id_short": "r_reference",
        "prototype_uid_full": "proto:1",
        "target_uid_full": "iface:1",
        "target_kind": "interface",
        "kind": "reference_energy",
        "status": "done",
        "best_energy": -2.0,
        "payload": reference_energy_payload(
            reference_uid_full="reference:a",
            reference_kind="strained_bulk_a",
            formula_id="interface_excess_strained_bulk",
            energy_eV=-2.0,
            energy_eV_per_formula_unit=-1.0,
            reference_formula_units=2,
            interface_formula_units=3,
        ),
        "authority": "authoritative",
    }


def _thermodynamic_row() -> dict:
    return {
        "uid_full": "followup:thermo",
        "id_short": "f_thermo",
        "run_uid_full": "run:thermo",
        "run_id_short": "r_thermo",
        "prototype_uid_full": "proto:1",
        "target_uid_full": "iface:1",
        "target_kind": "interface",
        "kind": "thermodynamic_quantity",
        "status": "done",
        "payload": thermodynamic_payload(
            raw_energy_followup_uid="followup:energy",
            value_eV_per_A2=0.1,
            n_interfaces=2,
        ),
        "authority": "authoritative",
    }


@pytest.mark.parametrize(
    ("collection_type", "row", "summary_columns"),
    [
        (RelaxationResultCollection, _relaxation_row(), RELAXATION_SUMMARY),
        (EnergyResultCollection, _raw_energy_row(), RAW_ENERGY_SUMMARY),
        (
            ReferenceEnergyResultCollection,
            _reference_row(),
            REFERENCE_ENERGY_SUMMARY,
        ),
        (
            ThermodynamicResultCollection,
            _thermodynamic_row(),
            THERMODYNAMIC_SUMMARY,
        ),
    ],
)
def test_result_collections_share_explicit_named_view_schemas(
    collection_type,
    row: dict,
    summary_columns: list[str],
    tmp_path: Path,
) -> None:
    collection = collection_type([row])

    assert collection.available_views() == ("summary", "provenance", "all")
    assert list(collection.to_rows()[0]) == summary_columns
    assert "authority" not in collection.to_rows()[0]
    assert "authority" in collection.to_rows(view="provenance")[0]
    assert "payload" in collection.to_rows(view="all")[0]

    frame = collection.to_dataframe()
    assert list(frame.columns) == summary_columns

    path = tmp_path / f"{collection_type.__name__}.csv"
    collection.write_table(path)
    with path.open(newline="", encoding="utf-8") as stream:
        assert next(csv.reader(stream)) == summary_columns

    empty = tmp_path / f"empty-{collection_type.__name__}.csv"
    collection_type([]).write_table(empty)
    with empty.open(newline="", encoding="utf-8") as stream:
        assert next(csv.reader(stream)) == summary_columns

    with pytest.raises(ValueError, match="Unknown table view 'unknown'"):
        collection.to_rows(view="unknown")


def test_workflow_wrappers_share_result_collection_views(tmp_path: Path) -> None:
    relaxation_results = RelaxationResultCollection([_relaxation_row()])
    relaxation = RelaxationWorkflowResult(
        run=SimpleNamespace(uid_full="run:relax", id_short="r_relax"),
        results=relaxation_results,
        relaxed_interfaces=[],
    )
    for view in relaxation.available_views():
        assert list(relaxation.to_rows(view=view)[0]) == list(
            relaxation_results.to_rows(view=view)[0]
        )

    reference_results = ReferenceEnergyResultCollection([_reference_row()])
    reference = ReferenceEnergyWorkflowResult(
        run=SimpleNamespace(uid_full="run:reference", id_short="r_reference"),
        results=reference_results,
        convention=SimpleNamespace(formula="interface_excess_strained_bulk"),
    )
    for view in reference.available_views():
        assert list(reference.to_rows(view=view)[0]) == list(
            reference_results.to_rows(view=view)[0]
        )

    relaxation_path = tmp_path / "relaxation.csv"
    relaxation.write_table(relaxation_path)
    assert relaxation_path.read_text(encoding="utf-8").splitlines()[0].split(",") == (
        RELAXATION_SUMMARY
    )


def test_energy_workflow_uses_kind_specific_and_combined_views(tmp_path: Path) -> None:
    raw = EnergyResultCollection([_raw_energy_row()])
    thermodynamic = ThermodynamicResultCollection([_thermodynamic_row()])
    workflow = EnergyWorkflowResult(
        energy_run=SimpleNamespace(uid_full="run:energy", id_short="r_energy"),
        energy_results=raw,
        thermodynamic_run=SimpleNamespace(
            uid_full="run:thermo",
            id_short="r_thermo",
        ),
        thermodynamic_results=thermodynamic,
    )

    assert workflow.available_views(kind="raw") == (
        "summary",
        "provenance",
        "all",
    )
    assert list(workflow.to_rows(kind="raw")[0]) == RAW_ENERGY_SUMMARY
    assert list(workflow.to_rows(kind="thermodynamic")[0]) == (
        THERMODYNAMIC_SUMMARY
    )

    combined = workflow.to_rows(kind="all")
    assert [row["result_kind"] for row in combined] == [
        "raw_energy",
        "thermodynamic_quantity",
    ]
    assert list(combined[0]) == list(combined[1])
    assert combined[0]["energy_eV"] == -5.0
    assert combined[0]["value_J_per_m2"] is None
    assert combined[1]["energy_eV"] is None
    assert combined[1]["value_J_per_m2"] is not None

    path = tmp_path / "combined.csv"
    workflow.write_table(path, kind="all")
    with path.open(newline="", encoding="utf-8") as stream:
        header = next(csv.reader(stream))
    assert header[0] == "result_kind"
    assert "energy_eV" in header
    assert "value_J_per_m2" in header

    with pytest.raises(ValueError, match="kind must be"):
        workflow.to_rows(kind="unsupported")
    with pytest.raises(ValueError, match="Unknown table view 'unknown'"):
        workflow.to_rows(kind="raw", view="unknown")


class _Followup:
    def __init__(self, *, kind: str, payload: dict):
        self.id_short = "f_one"
        self.run_id_short = "r_one"
        self.prototype_id_short = "p_one"
        self.target_kind = "prototype"
        self.payload = payload


class _Project:
    def __init__(self, result: _Followup):
        self.result = result

    def followups(self, *, run, kind):
        assert run == "r_one"
        assert kind in {"strain_partition_scan", "registry_search"}
        return [self.result]


def test_refinement_results_use_summary_provenance_and_all_views(
    tmp_path: Path,
) -> None:
    scan = StrainPartitionScan(
        project=_Project(
            _Followup(
                kind="strain_partition_scan",
                payload=make_current_strain_result_payload(alpha=0.25),
            )
        ),
        run=SimpleNamespace(id_short="r_one"),
    )
    assert scan.available_views() == ("summary", "provenance", "all")
    summary = scan.to_rows()[0]
    assert list(summary) == STRAIN_PARTITION_SUMMARY
    assert summary["is_selected"] is True
    assert "side_a_principal_log_strains" not in summary
    assert "side_a_principal_log_strains" in scan.to_rows(view="all")[0]
    assert "target_metric" in scan.to_rows(view="provenance")[0]

    rendered = StringIO()
    scan.to_table(title="Strain partition", file=rendered).display()
    assert "…" not in rendered.getvalue().splitlines()[2]

    registry = RegistrySearchRun(
        project=_Project(
            _Followup(
                kind="registry_search",
                payload=make_current_registry_result_payload(
                    z_padding=1.5,
                    vacuum=20.0,
                ),
            )
        ),
        run=SimpleNamespace(id_short="r_one"),
    )
    registry_summary = registry.to_rows()[0]
    assert list(registry_summary) == REGISTRY_SEARCH_SUMMARY
    assert registry_summary["gap_A"] == 1.5
    assert registry_summary["vacuum_A"] == 20.0
    assert "registry_provenance_status" not in registry_summary
    assert (
        registry.to_rows(view="provenance")[0]["registry_provenance_status"]
        == "complete_v1"
    )

    scan_path = tmp_path / "scan.csv"
    registry_path = tmp_path / "registry.csv"
    scan.write_table(scan_path)
    registry.write_table(registry_path)
    assert scan_path.read_text(encoding="utf-8").startswith("prototype_id,alpha,")
    assert registry_path.read_text(encoding="utf-8").startswith(
        "prototype_id,registry_shift_frac_a,gap_A,vacuum_A,"
    )
