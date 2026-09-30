"""Public contract tests for shared collection table projections."""

from __future__ import annotations

from pathlib import Path

import pytest

from calm.public.collections.base import _BaseCollection
from calm.public.collections.views import ViewSpec


class _ProjectionCollection(_BaseCollection):
    _view_specs = (
        ViewSpec(name="summary", columns=("id", "value"), aliases=("brief",)),
        ViewSpec(name="all", allow_extra_columns=True),
    )

    def __init__(self, items):
        self._items = list(items)

    def _public_item(self, item):
        return item

    def _normalize_item(self, item):
        return dict(item)

    def _clone(self, items):
        return _ProjectionCollection(items)


def test_collection_exposes_canonical_view_names_and_accepts_aliases() -> None:
    collection = _ProjectionCollection([{"id": "x", "value": 1, "extra": 2}])

    assert collection.available_views() == ("summary", "all")
    assert collection.to_rows(view="brief") == [{"id": "x", "value": 1}]


def test_dynamic_all_view_uses_ordered_union_across_every_row() -> None:
    collection = _ProjectionCollection(
        [
            {"id": "x", "first": 1},
            {"id": "y", "second": 2},
        ]
    )

    assert collection.to_rows(view="all") == [
        {"id": "x", "first": 1, "second": None},
        {"id": "y", "first": None, "second": 2},
    ]


def test_include_and_exclude_are_validated_after_view_resolution(
    tmp_path: Path,
) -> None:
    collection = _ProjectionCollection([{"id": "x", "value": 1, "extra": 2}])

    path = tmp_path / "selected.csv"
    collection.write_table(path, include=("value",))
    assert path.read_text(encoding="utf-8") == "value\n1\n"

    with pytest.raises(KeyError, match="Unknown included table columns: 'extra'"):
        collection.write_table(tmp_path / "bad-include.csv", include=("extra",))
    with pytest.raises(KeyError, match="Unknown excluded table columns: 'extra'"):
        collection.write_table(tmp_path / "bad-exclude.csv", exclude=("extra",))
    with pytest.raises(ValueError, match="both included and excluded"):
        collection.write_table(
            tmp_path / "overlap.csv",
            include=("id",),
            exclude=("id",),
        )


def test_empty_declared_view_retains_header_across_dataframe_and_csv(
    tmp_path: Path,
) -> None:
    collection = _ProjectionCollection([])

    assert collection.to_rows() == []
    assert list(collection.to_dataframe().columns) == ["id", "value"]

    path = tmp_path / "empty.csv"
    collection.write_table(path)
    assert path.read_text(encoding="utf-8") == "id,value\n"


def test_projection_contract_rejects_non_string_names_and_row_keys() -> None:
    with pytest.raises(TypeError, match="ViewSpec.name must be a string"):
        ViewSpec(name=1)  # type: ignore[arg-type]

    collection = _ProjectionCollection([{"id": "x", "value": 1}])
    with pytest.raises(TypeError, match="Table view names must be strings"):
        collection.to_rows(view=1)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="include values must be strings"):
        collection.to_table(include=(1,))  # type: ignore[arg-type]

    malformed = _ProjectionCollection([{1: "not-a-public-column"}])
    with pytest.raises(TypeError, match="row keys must be strings"):
        malformed.to_rows(view="all")


def test_view_display_labels_affect_tables_not_canonical_exports(tmp_path: Path) -> None:
    import io

    class _LabeledCollection(_BaseCollection):
        _view_specs = (
            ViewSpec(
                name="summary",
                columns=("spacegroup_number", "mass_density_g_cm3"),
                display_labels=(
                    ("spacegroup_number", "sg_no"),
                    ("mass_density_g_cm3", "density_g_cm3"),
                ),
            ),
        )

        def __init__(self, items):
            self._items = list(items)

        def _public_item(self, item):
            return item

        def _normalize_item(self, item):
            return dict(item)

        def _clone(self, items):
            return _LabeledCollection(items)

    collection = _LabeledCollection(
        [{"spacegroup_number": 225, "mass_density_g_cm3": 2.6804}]
    )
    stream = io.StringIO()
    collection.to_table(title="", file=stream).display()
    header = stream.getvalue().splitlines()[0]
    assert "sg_no" in header
    assert "density_g_cm3" in header
    assert "spacegroup_number" not in header
    assert "mass_density_g_cm3" not in header

    assert list(collection.to_dataframe().columns) == [
        "spacegroup_number",
        "mass_density_g_cm3",
    ]
    output = tmp_path / "canonical.csv"
    collection.write_table(output)
    assert output.read_text(encoding="utf-8").splitlines()[0] == (
        "spacegroup_number,mass_density_g_cm3"
    )


def test_view_display_labels_are_validated() -> None:
    with pytest.raises(ValueError, match="unknown column"):
        ViewSpec(
            name="summary",
            columns=("id",),
            display_labels=(("missing", "value"),),
        )
    with pytest.raises(ValueError, match="not unique"):
        ViewSpec(
            name="summary",
            columns=("id", "value"),
            display_labels=(("id", "field"), ("value", "field")),
        )
    with pytest.raises(ValueError, match="effective display labels"):
        ViewSpec(
            name="summary",
            columns=("id", "value"),
            display_labels=(("value", "id"),),
        )
