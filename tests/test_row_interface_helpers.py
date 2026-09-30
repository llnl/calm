from __future__ import annotations

from calm.public.projections.interface import normalize_interface_row


def test_normalize_interface_row_minimal(current_atoms_payload_factory):
    src = {
        "id_short": "i_test",
        "payload": {
            "atoms": current_atoms_payload_factory(
                numbers=(3,),
                cell=((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
            ),
        },
    }
    out = normalize_interface_row(src)
    assert out["id_short"] == "i_test"
    assert out["kind"] == "interface"
