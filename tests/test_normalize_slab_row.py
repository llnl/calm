from types import SimpleNamespace

import pytest

from calm.public.projections.slab import normalize_slab_row
from slab_record_fixtures import current_atoms, current_slab_payload, current_slab_uid


def _atoms_payload(
    numbers: list[int],
    *,
    cell: list[list[float]],
) -> dict[str, object]:
    atoms = current_atoms()
    atoms["numbers"] = list(numbers)
    atoms["cell"] = [list(vector) for vector in cell]
    atoms["scaled_positions"] = [
        [index / max(1, len(numbers)), 0.0, 0.0]
        for index in range(len(numbers))
    ]
    return atoms


def _current_surface_mapping(
    *,
    id_short: str,
    miller: tuple[int, int, int],
    atoms: dict[str, object] | None,
    bulk_uid_full: str = "bulk:test:surface",
    bulk_id_short: str = "b_surface",
) -> dict[str, object]:
    payload = current_slab_payload(
        bulk_uid_full=bulk_uid_full,
        miller=miller,
        atoms=atoms,
    )
    return {
        "uid_full": current_slab_uid(
            bulk_uid_full=bulk_uid_full,
            miller=miller,
            payload=payload,
        ),
        "id_short": id_short,
        "bulk_uid_full": bulk_uid_full,
        "bulk_id_short": bulk_id_short,
        "miller": miller,
        "payload": payload,
    }


def test_normalize_slab_row_from_current_mapping_with_atoms():
    item = _current_surface_mapping(
        id_short="s_map",
        miller=(1, 0, 0),
        atoms=_atoms_payload(
            [3, 3],
            cell=[
                [4.0, 0.0, 0.0],
                [0.0, 3.075, 0.0],
                [0.0, 0.0, 10.0],
            ],
        ),
    )

    row = normalize_slab_row(item)

    assert row["id_short"] == "s_map"
    assert row["kind"] == "surface"
    assert row["natoms"] == 2
    assert row["n_atoms"] == 2
    assert row["area"] == pytest.approx(12.3)
    assert row["has_atoms"] is True


def test_normalize_slab_row_from_current_object_with_atoms():
    item = _current_surface_mapping(
        id_short="s_obj",
        miller=(1, 1, 0),
        atoms=_atoms_payload(
            [13, 13, 8],
            cell=[
                [3.0, 0.0, 0.0],
                [0.0, 3.0, 0.0],
                [0.0, 0.0, 3.0],
            ],
        ),
    )
    slab = SimpleNamespace(**item)

    row = normalize_slab_row(slab)

    assert row["id_short"] == "s_obj"
    assert row["natoms"] == 3
    assert row["miller"] == (1, 1, 0)
    assert row["has_atoms"] is True


def test_normalize_slab_row_enriches_from_authoritative_parent_bulk():
    item = _current_surface_mapping(
        id_short="s_ws",
        miller=(0, 0, 1),
        atoms=_atoms_payload(
            [3],
            cell=[
                [2.0, 0.0, 0.0],
                [0.0, 2.0, 0.0],
                [0.0, 0.0, 2.0],
            ],
        ),
        bulk_uid_full="bulk:test:parent",
        bulk_id_short="b_parent",
    )

    class FakeBulk:
        label = "MyMaterial X"
        calculator = {"family": "emt", "model": "default"}

    class FakeWS:
        def get_bulk(self, uid: str):
            assert uid == "bulk:test:parent"
            return FakeBulk()

    row = normalize_slab_row(SimpleNamespace(**item), workspace=FakeWS())

    assert row["material"] == "MyMaterial X"
    assert row["calculator"] == {"family": "emt", "model": "default"}


def test_normalize_slab_row_rejects_alpha_flat_payload():
    with pytest.raises(ValueError, match="uid_full"):
        normalize_slab_row(
            {
                "id_short": "s_alpha",
                "miller": (1, 0, 0),
                "payload": {
                    "atoms": _atoms_payload(
                        [1],
                        cell=[
                            [1, 0, 0],
                            [0, 1, 0],
                            [0, 0, 1],
                        ],
                    )
                },
            }
        )
