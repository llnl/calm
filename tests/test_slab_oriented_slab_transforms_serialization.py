import numpy as np

from ase import Atoms

from calm.bulk.bulk import Bulk
from calm.slab.oriented.builder import build_oriented_slab, OrientedSlabTransforms


def test_oriented_slab_transforms_json_roundtrip() -> None:
    a = 3.0
    conv = Atoms("Cu", positions=[[0.0, 0.0, 0.0]], cell=np.eye(3) * a, pbc=True)
    bulk_obj = Bulk(conv)

    res = build_oriented_slab(
        bulk_obj,
        hkl=(1, 0, 0),
        layers=2,
        vacuum=None,
        reduce_inplane=True,
        reduce_c_tilt=True,
        orthogonalize_c=False,
    )

    t = res.transforms
    s = t.to_json(sort_keys=True)
    t2 = OrientedSlabTransforms.from_json(s)

    # Compare key arrays.
    assert t.hkl_reduced == t2.hkl_reduced
    assert t.layers == t2.layers
    assert np.array_equal(np.asarray(t.S_conv_to_surface_col, int), np.asarray(t2.S_conv_to_surface_col, int))
    assert np.array_equal(np.asarray(t.U_inplane_col, int), np.asarray(t2.U_inplane_col, int))
    assert np.array_equal(np.asarray(t.P_supercell_row, int), np.asarray(t2.P_supercell_row, int))
    assert np.allclose(np.asarray(t.R_conv_to_slab, float), np.asarray(t2.R_conv_to_slab, float))
    assert np.allclose(np.asarray(t.R_slab_to_conv, float), np.asarray(t2.R_slab_to_conv, float))
    assert np.allclose(np.asarray(t.R_align, float), np.asarray(t2.R_align, float))

    # Optional fields round-trip.
    assert t.c_tilt_mn == t2.c_tilt_mn
    assert t.shear_info == t2.shear_info
    assert t.vacuum_info == t2.vacuum_info
