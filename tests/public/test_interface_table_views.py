from __future__ import annotations

from io import StringIO
from types import SimpleNamespace

import numpy as np
import pytest

from calm import BuildSettings
from calm.public.collections.interfaces import InterfaceCollection
from calm.public.records.interfaces import InterfaceModel
from calm.public.records.interface_views import (
    INTERFACE_CONSTRUCTION_COLUMNS,
    INTERFACE_PROVENANCE_COLUMNS,
    INTERFACE_STRAIN_COLUMNS,
    INTERFACE_SUMMARY_COLUMNS,
)
from calm.slab.oriented.cell_contract import (
    INTERFACE_DEFORMATION_ACCOUNTING_INFO_KEY,
)


class _Atoms:
    def __len__(self) -> int:
        return 12

    def get_cell(self):
        return np.diag([4.0, 5.0, 20.0])

    def get_chemical_formula(self, *args, **kwargs) -> str:
        return "Li2O"


class _Cell:
    def __init__(self, array) -> None:
        self.array = np.asarray(array, dtype=float)


class _DiagnosticAtoms(_Atoms):
    def __init__(self, *, lower_matching=None) -> None:
        lower = np.asarray(
            lower_matching
            if lower_matching is not None
            else np.diag([1.02, 0.98, 1.0]),
            dtype=float,
        )
        upper = np.diag([0.99, 1.01, 1.0])
        lower_construction = np.diag([1.01, 1.0, 1.0])
        identity = np.eye(3)
        self.cell = _Cell(np.diag([4.0, 5.0, 20.0]))
        self.info = {
            INTERFACE_DEFORMATION_ACCOUNTING_INFO_KEY: {
                "policy": "composed_slab_deformation",
                "version": 1,
                "lower": {
                    "F_construction_slab": lower_construction.tolist(),
                    "F_interface_slab": lower.tolist(),
                    "F_total_slab": (lower @ lower_construction).tolist(),
                },
                "upper": {
                    "F_construction_slab": identity.tolist(),
                    "F_interface_slab": upper.tolist(),
                    "F_total_slab": upper.tolist(),
                },
            }
        }


class _GeometryWorkspace:
    def __init__(self, atoms=None) -> None:
        self.atoms = atoms or _Atoms()
        self.identifiers: list[str] = []

    def materialize_derived_interface_atoms(self, identifier: str):
        self.identifiers.append(identifier)
        return self.atoms


def _strain_state() -> SimpleNamespace:
    return SimpleNamespace(
        F_A=np.diag([1.02, 0.98, 1.0]),
        F_B=np.diag([0.99, 1.01, 1.0]),
    )


def _persisted_row() -> dict:
    return {
        "uid_full": "iface:1",
        "id_short": "i_1",
        "label": "built_interface_0000",
        "prototype_uid_full": "proto:1",
        "stage": "built",
        "search_name": "search-1",
        "search_id": "search-1",
        "candidate_id": "C0000",
        "candidate_uid": "proto:1",
        "run_uid_full": "run:1",
        "run_id_short": "r_1",
        "slab_a_uid_full": "slab:a",
        "slab_b_uid_full": "slab:b",
        "area_A2": 24.5,
        "n_atoms": 12,
        "artifact_refs": [{"kind": "interface_atoms"}],
        "created_at": "2026-07-31T00:00:00",
        "authority": "authoritative",
        "spec": {
            "stage": "built",
            "strain_alpha": 0.5,
            "registry_shift_frac_a": [0.0, 0.25],
            "z_padding": 1.5,
            "vacuum": 15.0,
            "params": {},
        },
        "gap": 1.5,
        "vacuum": 15.0,
    }


def _in_memory_model() -> InterfaceModel:
    model = InterfaceModel(
        SimpleNamespace(
            atoms=_Atoms(),
            prototype_uid="proto:1",
            build_uid=None,
            area_A2=24.5,
        ),
        candidate={
            "candidate_id": "C0000",
            "candidate_uid": "proto:1",
            "search_name": "search-1",
            "search_id": "search-1",
            "area_A2": 24.5,
        },
        build_settings=BuildSettings(
            alpha=0.5,
            gap=1.5,
            vacuum=15.0,
            translation=(0.0, 0.25),
        ),
    )
    model.project_interface_uid = "iface:1"
    model.project_interface_id = "i_1"
    model._persisted_record = SimpleNamespace(
        uid_full="iface:1",
        id_short="i_1",
        label="built_interface_0000",
        prototype_uid_full="proto:1",
        stage="built",
        spec={
            "stage": "built",
            "strain_alpha": 0.5,
            "registry_shift_frac_a": [0.0, 0.25],
            "z_padding": 1.5,
            "vacuum": 15.0,
            "params": {},
        },
        artifact_refs=[{"kind": "interface_atoms"}],
    )
    return model


def _in_memory_diagnostic_model() -> InterfaceModel:
    model = _in_memory_model()
    model._internal.atoms = _DiagnosticAtoms()
    model._internal.strain_state = _strain_state()
    return model


def test_interface_collection_exposes_central_named_views() -> None:
    collection = InterfaceCollection(
        workspace=_GeometryWorkspace(),
        items=[_persisted_row()],
    )

    assert collection.available_views() == (
        "summary",
        "construction",
        "strain",
        "provenance",
        "all",
    )
    assert tuple(collection.to_rows()[0]) == INTERFACE_SUMMARY_COLUMNS
    assert tuple(collection.to_rows(view="construction")[0]) == (
        INTERFACE_CONSTRUCTION_COLUMNS
    )
    assert tuple(collection.to_rows(view="provenance")[0]) == (
        INTERFACE_PROVENANCE_COLUMNS
    )
    with pytest.raises(ValueError, match="Unknown table view 'diagnostic'"):
        collection.to_rows(view="diagnostic")


def test_interface_strain_view_separates_incremental_and_total_strain() -> None:
    collection = InterfaceCollection(interfaces=[_in_memory_diagnostic_model()])

    row = collection.to_rows(view="strain")[0]

    assert tuple(row) == INTERFACE_STRAIN_COLUMNS
    assert row["deformation_state"] == "pre_relaxation"
    assert row[
        "lower_construction_max_abs_principal_log_strain"
    ] == pytest.approx(abs(np.log(1.01)))
    assert row[
        "lower_incremental_matching_max_abs_principal_log_strain"
    ] == pytest.approx(abs(np.log(0.98)))
    assert row[
        "lower_current_total_max_abs_principal_log_strain"
    ] > row["lower_incremental_matching_max_abs_principal_log_strain"]
    assert row["relaxation_cell_max_abs_principal_log_strain"] == pytest.approx(
        0.0
    )


def test_persisted_interface_strain_view_materializes_authoritative_atoms() -> None:
    atoms = _DiagnosticAtoms()

    class _Workspace:
        def __init__(self) -> None:
            self.identifiers: list[str] = []

        def materialize_derived_interface_atoms(self, identifier: str):
            self.identifiers.append(identifier)
            return atoms

    workspace = _Workspace()
    row = _persisted_row()
    row["spec"]["strain_state"] = {
        "F_A": np.diag([1.02, 0.98, 1.0]).tolist(),
        "F_B": np.diag([0.99, 1.01, 1.0]).tolist(),
    }
    collection = InterfaceCollection(workspace=workspace, items=[row])

    result = collection.to_rows(view="strain")[0]

    assert result["id_short"] == "i_1"
    assert workspace.identifiers == ["iface:1"]


def test_persisted_interface_strain_view_requires_owning_workspace() -> None:
    with pytest.raises(RuntimeError, match="owning Project or Workspace"):
        InterfaceCollection(items=[_persisted_row()]).to_rows(view="strain")


def test_persisted_interface_construction_view_reports_realized_geometry() -> None:
    workspace = _GeometryWorkspace()
    row = InterfaceCollection(
        workspace=workspace,
        items=[_persisted_row()],
    ).to_rows(view="construction")[0]

    assert row["n_atoms"] == 12
    assert row["area_A2"] == pytest.approx(20.0)
    assert row["prototype_area_A2"] == pytest.approx(24.5)
    assert workspace.identifiers == ["iface:1"]


def test_persisted_interface_construction_view_requires_owner() -> None:
    with pytest.raises(RuntimeError, match="owning Project or Workspace"):
        InterfaceCollection(items=[_persisted_row()]).to_rows(view="construction")


def test_interface_strain_exports_share_one_schema(tmp_path) -> None:
    collection = InterfaceCollection(interfaces=[_in_memory_diagnostic_model()])

    rows = collection.to_rows(view="strain")
    frame = collection.to_dataframe(view="strain")
    assert list(rows[0]) == list(INTERFACE_STRAIN_COLUMNS)
    assert list(frame.columns) == list(INTERFACE_STRAIN_COLUMNS)

    output = StringIO()
    collection.to_table(
        view="strain",
        title="",
        max_width=240,
        file=output,
    ).display()
    headings = [part.strip() for part in output.getvalue().splitlines()[0].split("|")]
    assert headings == [
        "id",
        "label",
        "stage",
        "alpha",
        "state",
        "lower_construct",
        "upper_construct",
        "lower_match",
        "upper_match",
        "lower_total",
        "upper_total",
        "relax_cell",
    ]

    path = tmp_path / "interface-strain.csv"
    collection.write_table(path, view="strain")
    assert path.read_text(encoding="utf-8").splitlines()[0] == ",".join(
        INTERFACE_STRAIN_COLUMNS
    )

    empty = tmp_path / "interface-strain-empty.csv"
    InterfaceCollection(items=[]).write_table(empty, view="strain")
    assert empty.read_text(encoding="utf-8") == (
        ",".join(INTERFACE_STRAIN_COLUMNS) + "\n"
    )


def test_interface_summary_and_construction_exclude_project_level_calculator() -> None:
    row = _persisted_row()
    row["calculator"] = "grace:GRACE-1L-OMAT"
    collection = InterfaceCollection(
        workspace=_GeometryWorkspace(),
        items=[row],
    )

    assert "calculator" not in collection.to_rows()[0]
    assert "calculator" not in collection.to_rows(view="construction")[0]
    assert collection.to_rows(view="all")[0]["calculator"] == (
        "grace:GRACE-1L-OMAT"
    )


def test_in_memory_and_reopened_interfaces_share_view_schemas() -> None:
    persisted = InterfaceCollection(
        workspace=_GeometryWorkspace(),
        items=[_persisted_row()],
    )
    in_memory = InterfaceCollection(interfaces=[_in_memory_model()])

    for view in ("summary", "construction", "provenance"):
        persisted_row = persisted.to_rows(view=view)[0]
        in_memory_row = in_memory.to_rows(view=view)[0]
        assert list(persisted_row) == list(in_memory_row)

    construction = in_memory.to_rows(view="construction")[0]
    assert construction == {
        "id_short": "i_1",
        "label": "built_interface_0000",
        "stage": "built",
        "search_name": "search-1",
        "candidate_id": "C0000",
        "strain_alpha": 0.5,
        "registry_shift_frac_a": [0.0, 0.25],
        "gap_A": 1.5,
        "vacuum_A": 15.0,
        "n_atoms": 12,
        "area_A2": 20.0,
        "prototype_area_A2": 24.5,
    }


def test_interface_exports_share_one_ordered_schema(tmp_path) -> None:
    collection = InterfaceCollection(
        workspace=_GeometryWorkspace(),
        items=[_persisted_row()],
    )

    rows = collection.to_rows(view="construction")
    frame = collection.to_dataframe(view="construction")
    assert list(rows[0]) == list(INTERFACE_CONSTRUCTION_COLUMNS)
    assert list(frame.columns) == list(INTERFACE_CONSTRUCTION_COLUMNS)

    output = StringIO()
    collection.to_table(
        view="construction",
        title="",
        max_width=200,
        file=output,
    ).display()
    assert [part.strip() for part in output.getvalue().splitlines()[0].split("|")] == (
        list(INTERFACE_CONSTRUCTION_COLUMNS)
    )

    path = tmp_path / "interfaces.csv"
    collection.write_table(path, view="construction")
    assert path.read_text(encoding="utf-8").splitlines()[0] == ",".join(
        INTERFACE_CONSTRUCTION_COLUMNS
    )

    empty_path = tmp_path / "empty.csv"
    InterfaceCollection(items=[]).write_table(empty_path, view="construction")
    assert empty_path.read_text(encoding="utf-8") == (
        ",".join(INTERFACE_CONSTRUCTION_COLUMNS) + "\n"
    )


def test_interface_provenance_contains_lineage_not_construction_controls() -> None:
    row = InterfaceCollection(items=[_persisted_row()]).to_rows(
        view="provenance"
    )[0]

    assert row["uid_full"] == "iface:1"
    assert row["prototype_uid_full"] == "proto:1"
    assert row["authority"] == "authoritative"
    assert "strain_alpha" not in row
    assert "registry_shift_frac_a" not in row
    assert "vacuum_A" not in row
