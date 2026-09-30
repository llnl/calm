from __future__ import annotations

from calm.public.collections.interfaces import InterfaceCollection


def test_authoritative_interface_normalization_and_collection(tmp_path) -> None:
    item = {
        "uid_full": "iface:1",
        "id_short": "i_1",
        "label": "iface1",
        "prototype_uid_full": "proto:1",
        "spec": {
            "prototype": "proto:1",
            "strain_alpha": 0.5,
            "registry_shift_frac_a": [0.25, 0.75],
            "vacuum": 12.0,
        },
        "calculator": "grace:GRACE-1L-OMAT",
        "authority": "authoritative",
    }

    collection = InterfaceCollection(items=[item])
    rows = collection.to_rows(view="all")

    assert len(rows) == 1
    row = rows[0]
    assert row["uid_full"] == "iface:1"
    assert row["id_short"] == "i_1"
    assert row["interface_id"] == "i_1"
    assert row["label"] == "iface1"
    assert row["prototype_uid_full"] == "proto:1"
    assert row["calculator"] == "grace:GRACE-1L-OMAT"
    assert row["authority"] == "authoritative"

    summary = collection.to_rows(view="summary")[0]
    assert "calculator" not in summary

    summary_path = tmp_path / "interfaces-summary.csv"
    collection.write_table(summary_path, view="summary")
    summary_header = summary_path.read_text(encoding="utf-8").splitlines()[0]
    assert "calculator" not in summary_header

    included_path = tmp_path / "interfaces-included.csv"
    collection.write_table(
        included_path,
        view="all",
        include=("id_short", "label"),
    )
    assert included_path.read_text(encoding="utf-8").splitlines()[0] == (
        "id_short,label"
    )

    selected_path = tmp_path / "interfaces-selected.csv"
    collection.write_table(
        selected_path,
        view="all",
        exclude=("calculator",),
    )
    selected_header = selected_path.read_text(encoding="utf-8").splitlines()[0]
    assert "calculator" not in selected_header

    full_path = tmp_path / "interfaces-full.csv"
    collection.write_table(full_path, view="all")
    assert "calculator" in full_path.read_text(encoding="utf-8").splitlines()[0]


def test_interface_normalization_preserves_zero_build_parameters() -> None:
    from calm.public.projections.interface import normalize_interface_row

    row = normalize_interface_row(
        {
            "uid_full": "iface:zero",
            "id_short": "i_zero",
            "prototype_uid_full": "proto:zero",
            "spec": {"strain_alpha": 0.0, "vacuum": 0.0},
        }
    )

    assert row["strain_alpha"] == 0.0
    assert row["vacuum"] == 0.0
