from __future__ import annotations

from pathlib import Path

import numpy as np


def test_load_and_write_structure_roundtrip(tmp_path: Path) -> None:
    """`calm.load_structure` / `calm.write_structure` should be stable UX helpers.

    This is intentionally a lightweight smoke test that exercises the public
    import paths without depending on example scripts.
    """

    from ase import Atoms

    import calm as sg

    atoms = Atoms("Al", positions=[[0.0, 0.0, 0.0]], cell=np.eye(3) * 4.05, pbc=True)

    path = tmp_path / "POSCAR"
    sg.write_structure(path, atoms, format="vasp")

    loaded = sg.load_structure(path)

    assert len(loaded) == len(atoms)
    assert loaded.get_chemical_symbols() == atoms.get_chemical_symbols()
    assert np.allclose(loaded.cell.array, atoms.cell.array)


def test_public_api_does_not_export_stage() -> None:
    import calm as sg

    assert not hasattr(sg, "stage")
