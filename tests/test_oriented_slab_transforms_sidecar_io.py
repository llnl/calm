from __future__ import annotations

from ase.build import bulk as ase_bulk

from calm.bulk.bulk import Bulk
from calm.slab.slab import Slab
from calm.slab.slab import SlabSpec


def _make_al_slab(*, stamp: bool) -> Slab:
    bulk = Bulk(ase_bulk("Al", "fcc", a=4.05))
    spec = SlabSpec(miller=(1, 1, 1), n_layers=8, vacuum=12.0, stamp_transforms=stamp)
    return Slab(bulk, spec)


def test_oriented_slab_transforms_can_roundtrip_via_json_sidecar_file(tmp_path) -> None:
    slab = _make_al_slab(stamp=False)

    ts = slab.oriented_slab_transforms
    assert ts is not None

    path = tmp_path / "al_111_oriented_slab_transforms.json"

    out = ts.write_json(path)
    assert out == path
    assert out.exists()

    # Writing again without overwrite should be refused.
    try:
        ts.write_json(path)
        raise AssertionError("Expected FileExistsError")
    except FileExistsError:
        pass

    # Overwrite should be allowed explicitly.
    ts.write_json(path, overwrite=True)

    ts2 = type(ts).from_json_file(path)
    assert ts2.json == ts.json
    assert ts2.payload == ts.payload
