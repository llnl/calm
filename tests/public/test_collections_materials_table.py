from __future__ import annotations

from calm.public.collections.structures import MaterialCollection


def _item(*, uid: str, short: str, label: str, number: int, formula: str, atoms_factory) -> dict:
    return {
        "uid_full": uid,
        "id_short": short,
        "label": label,
        "kind": "reference",
        "payload": {
            "atoms": atoms_factory(numbers=(number,)),
            "derived": {"formula": formula, "n_atoms": 1},
        },
    }


def test_material_collection_to_rows_and_where(current_atoms_payload_factory) -> None:
    items = [
        _item(uid="bulk:a", short="b_a", label="A", number=3, formula="Li", atoms_factory=current_atoms_payload_factory),
        _item(uid="bulk:b", short="b_b", label="B", number=8, formula="O", atoms_factory=current_atoms_payload_factory),
    ]

    collection = MaterialCollection(items=items)
    rows = collection.to_rows()
    all_rows = collection.to_rows(view="all")

    assert isinstance(rows, list)
    assert tuple(rows[0]) == (
        "id_short",
        "label",
        "kind",
        "formula",
        "natoms",
        "spacegroup",
    )
    assert {row["uid_full"] for row in all_rows} == {"bulk:a", "bulk:b"}
    selected = collection.where(label="A")
    assert len(list(selected)) == 1
