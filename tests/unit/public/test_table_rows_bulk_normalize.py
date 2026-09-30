from __future__ import annotations

from calm.public.projections.bulk import normalize_bulk_row


def test_normalize_bulk_row_from_mapping(current_atoms_payload_factory) -> None:
    src = {
        "id_short": "b_test",
        "label": "TestBulk",
        "payload": {
            "atoms": current_atoms_payload_factory(
                numbers=(3, 9, 3, 9),
                cell=((4.0, 0.0, 0.0), (0.0, 4.0, 0.0), (0.0, 0.0, 4.0)),
                scaled_positions=(
                    (0.0, 0.0, 0.0),
                    (0.5, 0.5, 0.5),
                    (0.25, 0.25, 0.25),
                    (0.75, 0.75, 0.75),
                ),
            ),
            "derived": {"formula": "LiF", "n_atoms": 4},
        },
    }
    out = normalize_bulk_row(src, name="TestBulk")
    assert isinstance(out, dict)
    # canonical keys present
    assert out.get("id_short") == "b_test"
    assert out.get("label") == "TestBulk"
    assert out.get("natoms") == 4
    assert out.get("formula") == "LiF"
