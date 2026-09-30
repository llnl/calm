from __future__ import annotations



from calm.structure.io import write_structure
import numpy as np


def _approx(a, b, tol=1e-6):
    return abs(a - b) <= tol


def test_slab_vacuum_symmetry_and_cell_gauge(tmp_path):
    from calm.bulk.bulk import Bulk
    from calm.slab.oriented.builder import build_oriented_slab

    # Use example conventional structure to build an oriented slab
    # Create a simple conventional cell (2-atom primitive) for testing
    from ase import Atoms

    conv = Atoms(symbols=["Li", "O"], positions=[[0, 0, 0], [0.5, 0.5, 0.5]], cell=[4.0, 4.0, 4.0], pbc=True)

    # Build oriented slab with vacuum and centering using the exact Bulk-based API
    res = build_oriented_slab(Bulk(conv), hkl=(1, 0, 0), layers=4, vacuum=15.0, center_slab=True)
    slab = res.slab

    # canonical cell gauge
    C = slab.get_cell()
    assert C[0, 0] > 0.0
    assert C[1, 1] > 0.0
    # Use z-axis component tested in oriented_slab
    assert C[2, 2] > 0.0
    # sanity: determinant positive
    assert float(np.linalg.det(C)) > 0.0

    # vacuum symmetry
    z = slab.get_positions()[:, 2]
    z_min = float(z.min())
    z_max = float(z.max())
    Lz = float(C[2, 2])
    bottom = z_min
    top = Lz - z_max
    assert _approx(bottom, top, tol=1e-6)
    # for requested vacuum=15
    assert _approx(bottom, 15.0, tol=1e-6)


def test_vasp_write_groups_elements(tmp_path):
    # Create a deliberately unsorted Atoms ordering
    from ase import Atoms

    atoms = Atoms(symbols=["Li", "O", "Li"], positions=[[0, 0, 0], [0.5, 0.5, 0.5], [0.25, 0.25, 0.25]], cell=[4.0, 4.0, 4.0], pbc=True)

    out = tmp_path / "poscar.vasp"
    # Use direct write to avoid verification race in tests
    write_structure(out, atoms, format="vasp")

    # Read back with ASE to inspect grouping
    from ase.io import read

    atoms_back = read(str(out), format="vasp")
    symbols = atoms_back.get_chemical_symbols()
    # For each element, indices must form a contiguous block
    for sym in set(symbols):
        idxs = [i for i, s in enumerate(symbols) if s == sym]
        assert max(idxs) - min(idxs) + 1 == len(idxs)
