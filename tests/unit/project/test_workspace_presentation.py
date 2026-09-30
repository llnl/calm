from __future__ import annotations

import pytest

from calm.project.domain.models import (
    Bulk,
    DerivedInterface,
    FollowupResult,
    PrototypeSummary,
    Slab,
    SlabSummary,
)
from slab_record_fixtures import current_slab_payload

from calm.project.presentation.workspace import (
    enriched_followup_row,
    enriched_interface_row,
    enriched_prototype_row,
    enriched_slab_row,
    format_mapping_table,
    format_payload_mapping,
    material_name,
)


def _bulk(uid: str, short: str, label: str) -> Bulk:
    return Bulk(
        uid_full=uid,
        id_short=short,
        label=label,
        calculator="mace:model",
    )


def _slab(
    uid: str,
    short: str,
    bulk_uid: str,
    bulk_short: str,
    miller: tuple[int, int, int],
) -> Slab:
    return Slab(
        uid_full=uid,
        id_short=short,
        bulk_uid_full=bulk_uid,
        bulk_id_short=bulk_short,
        miller=miller,
        payload=current_slab_payload(
            bulk_uid_full=bulk_uid,
            miller=miller,
            label="T",
            top="T",
            bottom="T",
        ),
    )


def test_enriched_rows_project_current_typed_records() -> None:
    bulk_a = _bulk("bulk:a", "B0001", "LiF conventional")
    bulk_b = _bulk("bulk:b", "B0002", "MgO")
    slab_a = _slab("slab:a", "S0001", bulk_a.uid_full, bulk_a.id_short, (1, 0, 0))
    slab_b = _slab("slab:b", "S0002", bulk_b.uid_full, bulk_b.id_short, (1, 1, 0))
    summary = SlabSummary(
        uid_full=slab_a.uid_full,
        id_short=slab_a.id_short,
        bulk_uid_full=bulk_a.uid_full,
        bulk_id_short=bulk_a.id_short,
        miller=slab_a.miller,
    )

    slab_row = enriched_slab_row(summary, slab=slab_a, bulk=bulk_a)
    assert slab_row == {
        "id_short": "S0001",
        "bulk_id_short": "B0001",
        "bulk": "B0001",
        "miller": (1, 0, 0),
        "label": "LiF-100",
        "material": "LiF",
        "calculator": "mace:model",
        "area": None,
        "natoms": None,
        "termination": "T",
    }
    assert material_name(bulk_a) == "LiF"

    prototype = PrototypeSummary(
        uid_full="prototype:a",
        id_short="P0001",
        run_uid_full="run:a",
        run_id_short="R0001",
        slab_a_uid_full=slab_a.uid_full,
        slab_a_id_short=slab_a.id_short,
        slab_b_uid_full=slab_b.uid_full,
        slab_b_id_short=slab_b.id_short,
        match_score=0.2,
        hencky_norm=0.1,
        interface_area=25.0,
        natoms=40,
        d_cell=0.03,
        is_pareto=True,
        pareto_rank=0,
        pareto_policy="strain_size",
        pareto_policy_version=2,
        pareto_population_scope="run",
        pareto_population_size=4,
        pareto_d_cell_key=3,
        pareto_status="current",
    )
    prototype_row = enriched_prototype_row(
        prototype,
        slab_a=slab_a,
        slab_b=slab_b,
        bulk_a=bulk_a,
        bulk_b=bulk_b,
    )
    assert prototype_row["interface_label"] == "LiF/MgO"
    assert prototype_row["slab_a_uid_full"] == "slab:a"
    assert prototype_row["slab_b_uid_full"] == "slab:b"
    assert prototype_row["pareto_policy_version"] == 2


def test_interface_and_followup_rows_use_current_fields() -> None:
    interface = DerivedInterface(
        uid_full="interface:a",
        id_short="I0001",
        prototype_uid_full="prototype:a",
        label="candidate",
        spec={
            "schema": "calm.derived_interface",
            "version": 1,
            "prototype": "prototype:a",
            "stage": "registry_refined",
            "strain_alpha": 0.25,
            "registry_shift_frac_a": [0.125, 0.75],
            "z_padding": 2.0,
            "vacuum": 10.0,
            "params": {},
        },
    )
    interface_row = enriched_interface_row(interface)
    assert interface_row["registry_shift_frac_a"] == [0.125, 0.75]
    assert interface_row["registry_shift_str"] == "[0.1250, 0.7500]"
    assert interface_row["z_padding"] == 2.0

    result = FollowupResult(
        uid_full="followup:a",
        id_short="F0001",
        run_uid_full="run:a",
        run_id_short="R0001",
        prototype_uid_full="prototype:a",
        prototype_id_short="P0001",
        target_kind="prototype",
        target_uid_full="prototype:a",
        target_id_short="P0001",
        kind="strain_partition_scan",
        status="done",
        best_energy=-1.25,
        param1=0.4,
        n_points=11,
        payload={
            "selection": {
                "metric": "potential_energy_density_eV_per_A2",
                "alpha": 0.4,
                "value": -1.25,
            }
        },
    )
    followup_row = enriched_followup_row(result)
    assert followup_row["best_alpha"] == 0.4
    assert followup_row["payload"] == {
        "selection": {
            "metric": "potential_energy_density_eV_per_A2",
            "alpha": 0.4,
            "value": -1.25,
        }
    }


def test_presentation_formatters_accept_only_current_mapping_shapes() -> None:
    rendered = format_mapping_table([{"id": "P0001", "score": 0.2}])
    assert "P0001" in rendered
    assert "score" in rendered

    with pytest.raises(TypeError, match="rows must be mappings"):
        format_mapping_table([object()])  # type: ignore[list-item]

    assert format_payload_mapping(None, max_list_items=5) == "No payload"
    assert "sequence with 3 items" in format_payload_mapping(
        {"values": [1, 2, 3]},
        max_list_items=2,
    )
    with pytest.raises(TypeError, match="non-negative integer"):
        format_payload_mapping(
            {"value": 1},
            max_list_items=1.5,  # type: ignore[arg-type]
        )
    with pytest.raises(TypeError, match="non-negative integer"):
        format_payload_mapping({"value": 1}, max_list_items=True)
    with pytest.raises(ValueError, match="non-negative integer"):
        format_payload_mapping({"value": 1}, max_list_items=-1)


def test_strain_partition_plot_series_requires_current_payload() -> None:
    from calm.project.presentation.workspace import strain_partition_plot_series

    payload = {
        "selection": {
            "metric": "potential_energy_density_eV_per_A2",
            "alpha": 0.5,
            "value": 1.5,
        },
        "points": [
            {
                "alpha": 0.0,
                "potential_energy_density_eV_per_A2": 2.0,
                "gamma_eV_per_A2": 1.0,
            },
            {
                "alpha": 0.5,
                "potential_energy_density_eV_per_A2": 1.5,
                "gamma_eV_per_A2": 0.75,
            },
        ],
    }

    metric, alphas, values = strain_partition_plot_series(payload, metric=None)
    assert metric == "potential_energy_density_eV_per_A2"
    assert alphas == [0.0, 0.5]
    assert values == [2.0, 1.5]

    metric, _, values = strain_partition_plot_series(
        payload,
        metric="gamma_eV_per_A2",
    )
    assert metric == "gamma_eV_per_A2"
    assert values == [1.0, 0.75]

    with pytest.raises(TypeError, match="mapping row"):
        strain_partition_plot_series(
            {
                "selection": {
                    "metric": "potential_energy_density_eV_per_A2",
                    "alpha": 0.0,
                    "value": 2.0,
                },
                "points": [(0.0, 2.0)],
            },
            metric=None,
        )
    with pytest.raises(ValueError, match="Unsupported strain-partition"):
        strain_partition_plot_series(
            {
                "selection": {
                    "metric": "potential_energy_density",
                    "alpha": 0.0,
                    "value": 2.0,
                },
                "points": [
                    {
                        "alpha": 0.0,
                        "potential_energy_density_eV_per_A2": 2.0,
                    }
                ],
            },
            metric=None,
        )


def test_registry_search_plot_series_requires_current_compact_trace() -> None:
    from calm.project.presentation.workspace import registry_search_plot_series

    steps, values = registry_search_plot_series(
        {
            "trace": [
                {"step": 1, "current_score": 4.0, "best_score": 4.0},
                {"step": 2, "current_score": 3.5, "best_score": 3.5},
            ]
        }
    )
    assert steps == [1.0, 2.0]
    assert values == [4.0, 3.5]

    for trace in (
        [{"step": 1, "energy": 4.0}],
        [[0.0, 4.0]],
        [4.0],
    ):
        with pytest.raises((TypeError, ValueError)):
            registry_search_plot_series({"trace": trace})


def test_default_structure_views_omit_project_calculator() -> None:
    import io

    from calm.public.collections.base import _BaseCollection
    from calm.public.collections.structures import MaterialCollection
    from calm.public.collections.views import ViewSpec

    class _SurfaceSummaryCollection(_BaseCollection):
        _view_specs = (
            ViewSpec(
                name="summary",
                columns=(
                    "id_short",
                    "label",
                    "bulk",
                    "miller",
                    "termination",
                    "area",
                    "natoms",
                ),
            ),
            ViewSpec(name="all", allow_extra_columns=True),
        )

        def __init__(self, items):
            self._items = list(items)

        def _normalize_item(self, item):
            return dict(item)

    calculator = "grace:GRACE-1L-OMAT"
    bulk = {
        "id_short": "b_lif",
        "label": "LiF_opt",
        "kind": "optimized",
        "formula": "LiF",
        "natoms": 8,
        "spacegroup": "Fm-3m",
        "calculator": calculator,
    }
    slab = {
        "id_short": "s_lif_100",
        "label": "LiF-100",
        "bulk": "b_lif",
        "miller": (1, 0, 0),
        "termination": "LiF",
        "area": 16.0,
        "natoms": 32,
        "calculator": calculator,
    }

    for collection in (
        MaterialCollection(items=[bulk]),
        _SurfaceSummaryCollection(items=[slab]),
    ):
        stream = io.StringIO()
        collection.to_table(title="", file=stream).display()
        rendered = stream.getvalue()
        assert "calculator" not in rendered.splitlines()[0]
        assert calculator not in rendered

    explicit = io.StringIO()
    MaterialCollection(items=[bulk]).to_table(
        view="all",
        include=("id_short", "calculator"),
        title="",
        file=explicit,
    ).display()
    assert calculator in explicit.getvalue()

def test_table_outputs_use_plain_ascii_chemical_subscripts(tmp_path) -> None:
    import csv
    import io

    from calm.project.presentation.notebook import display_table
    from calm.public.collections.base import _BaseCollection

    row = {
        "termination": "Li₂",
        "reduced_formula": "Li₂O",
    }

    stream = io.StringIO()
    display_table(
        [row],
        include=("termination", "reduced_formula"),
        title="",
        file=stream,
    )
    rendered = stream.getvalue()
    assert "Li2" in rendered
    assert "Li2O" in rendered
    assert "₂" not in rendered

    mapping_rendered = format_mapping_table([row], style="plain")
    assert "Li2" in mapping_rendered
    assert "Li2O" in mapping_rendered
    assert "₂" not in mapping_rendered

    class _RowsCollection(_BaseCollection):
        def __init__(self, items):
            self._items = list(items)

        def _normalize_item(self, item):
            return dict(item)

        def _normalize_item(self, item):
            return dict(item)

        def _clone(self, items):
            return _RowsCollection(items)

    output = tmp_path / "surface_table.csv"
    collection = _RowsCollection([row])
    collection.write_table(
        output,
        include=("termination", "reduced_formula"),
    )
    with output.open(newline="", encoding="utf-8") as stream:
        written = next(csv.DictReader(stream))
    assert written == {
        "termination": "Li2",
        "reduced_formula": "Li2O",
    }

    assert collection.to_rows()[0] == row


def test_display_table_rejects_retired_columns_alias() -> None:
    from calm.project.presentation.notebook import TableView, display_table

    with pytest.raises(TypeError, match="columns"):
        display_table([], columns=["id_short"])  # type: ignore[call-arg]
    with pytest.raises(TypeError, match="columns"):
        TableView(rows=[], columns=["id_short"])  # type: ignore[call-arg]


def test_interface_projection_surfaces_malformed_current_values() -> None:
    from calm.public.collections.interfaces import InterfaceCollection

    with pytest.raises(TypeError, match="two-value sequence"):
        InterfaceCollection(
            items=[
                {
                    "id_short": "i_bad",
                    "prototype_uid_full": "proto:1",
                    "spec": {
                        "strain_alpha": 0.5,
                        "registry_shift_frac_a": [0.25],
                        "vacuum": 10.0,
                    },
                }
            ]
        ).to_rows(view="construction")
