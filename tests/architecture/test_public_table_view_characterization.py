"""Protect the staged public table-view consolidation boundaries.

Collections and workflow result objects use shared named-view projection
mechanics. Named views are the sole domain schema selector; the renderer only
formats resolved projections or explicitly selected generic mapping columns.
"""

from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest

from calm.project.presentation.notebook import display_table
from calm.public.collections.base import _BaseCollection
from calm.public.collections.candidates import CandidateCollection
from calm.public.collections.persistence import DatasetItemCollection
from calm.public.collections.views import ViewSpec
from calm.public.records.interfaces import InterfaceCandidate, InterfaceSearchResult


class _HeterogeneousCollection(_BaseCollection):
    _view_specs = (
        ViewSpec(name="summary", columns=("a", "b")),
        ViewSpec(name="all"),
    )

    def __init__(self, items):
        self._items = list(items)

    def _public_item(self, item):
        return item

    def _normalize_item(self, item):
        return dict(item)

    def _clone(self, items):
        return _HeterogeneousCollection(items)


def _candidate_row() -> dict:
    return {
        "candidate_id": "C0000",
        "rank": 0,
        "score": 0.2,
        "d_cell": 0.1,
        "d_area": 0.05,
        "d_shape": 0.03,
        "max_principal_strain": 0.02,
        "n_atoms_estimate": 20,
        "d_size": 0.2,
        "k_a": 1,
        "k_b": 1,
        "material_a": "A",
        "material_b": "B",
    }


def test_collection_view_names_are_validated_centrally() -> None:
    collections = (
        _HeterogeneousCollection([{"a": 1}]),
        CandidateCollection(items=[_candidate_row()]),
        DatasetItemCollection(
            [
                {
                    "dataset_index": 0,
                    "source_id_short": "src_0000",
                    "source_kind": "interface",
                }
            ]
        ),
    )

    for collection in collections:
        with pytest.raises(ValueError, match="Unknown table view 'misspelled'"):
            collection.to_rows(view="misspelled")


def test_collection_exports_share_one_resolved_schema(tmp_path: Path) -> None:
    collection = _HeterogeneousCollection(
        [
            {"a": 1},
            {"a": 2, "b": 3},
        ]
    )

    assert collection.to_rows() == [
        {"a": 1, "b": None},
        {"a": 2, "b": 3},
    ]

    output = StringIO()
    collection.to_table(title="", file=output).display()
    assert output.getvalue().splitlines()[0] == "a | b"

    frame = collection.to_dataframe()
    assert list(frame.columns) == ["a", "b"]
    assert frame["a"].tolist() == [1, 2]
    assert frame["b"].isna().tolist() == [True, False]
    assert frame["b"].iloc[1] == 3.0

    csv_path = tmp_path / "rows.csv"
    collection.write_table(csv_path)
    assert csv_path.read_text(encoding="utf-8") == "a,b\n1,\n2,3\n"

    empty_path = tmp_path / "empty.csv"
    _HeterogeneousCollection([]).write_table(empty_path)
    assert empty_path.read_text(encoding="utf-8") == "a,b\n"


def test_candidate_collection_and_search_result_share_named_view_schemas() -> None:
    row = _candidate_row()
    persisted = CandidateCollection(items=[row])
    in_memory = InterfaceSearchResult(
        request=None,
        candidates=[InterfaceCandidate(**row)],
    )

    assert persisted.available_views() == (
        "summary",
        "strain",
        "provenance",
        "all",
    )
    assert in_memory.available_views() == persisted.available_views()

    for view in persisted.available_views():
        persisted_rows = persisted.to_rows(view=view)
        in_memory_rows = in_memory.to_rows(view=view)
        assert list(persisted_rows[0]) == list(in_memory_rows[0])

    assert list(persisted.to_rows()[0]) == [
        "candidate_id",
        "d_cell",
        "d_area",
        "d_shape",
        "max_principal_strain",
        "n_atoms_estimate",
        "score",
        "is_pareto",
    ]
    assert "authority" not in persisted.to_rows()[0]
    assert "authority" in persisted.to_rows(view="provenance")[0]


def test_renderer_no_longer_accepts_legacy_table_presets() -> None:
    output = StringIO()
    with pytest.raises(TypeError, match="unexpected keyword argument 'table'"):
        display_table(
            [{"candidate_id": "C0000"}],
            title="",
            table="candidates",  # type: ignore[call-arg]
            file=output,
        )

    display_table(
        [{"candidate_id": "C0000", "authority": "authoritative"}],
        title="",
        include=("candidate_id",),
        file=output,
    )
    assert output.getvalue().splitlines()[0] == "candidate_id"
