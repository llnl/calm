import numpy as np
from ase import Atoms
from ase.build import bulk

from calm.structure.ase_adapter import make_supercell_col
from calm.slab.oriented._primitive import compute_primitive_surface_basis


def diamond_primitive_cell():
    # ASE diamond conventional cell, then primitive via P matrix (simple case)
    at = bulk("Si", "diamond", a=5.43)
    return at


def rocksalt_primitive_cell():
    # Two-species motif in a simple cubic primitive cell
    symbols = ["Na", "Cl"]
    scaled = [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]]
    return Atoms(symbols=symbols, cell=np.eye(3), scaled_positions=scaled, pbc=True)


def custom_low_symmetry_motif_cell():
    symbols = ["H", "He", "Li", "Be"]
    scaled = [
        [0.13, 0.21, 0.34],
        [0.47, 0.58, 0.19],
        [0.72, 0.11, 0.63],
        [0.29, 0.83, 0.77],
    ]
    return Atoms(symbols=symbols, cell=np.array([[3.0, 0.1, 0.0], [0.0, 2.7, 0.2], [0.0, 0.0, 4.1]]), scaled_positions=scaled, pbc=True)


def _assert_species_preserving_supercell(atoms, T, tol=1e-8):
    A_prim = atoms.cell.array.T
    supercell = make_supercell_col(atoms, T)
    motif_frac = atoms.get_scaled_positions() % 1.0
    motif_symbols = np.array(atoms.get_chemical_symbols())
    super_frac_in_prim = np.linalg.solve(A_prim, supercell.get_positions().T).T % 1.0
    super_symbols = np.array(supercell.get_chemical_symbols())

    counts = np.zeros(len(motif_frac), dtype=int)
    for f, sym in zip(super_frac_in_prim, super_symbols):
        diffs = motif_frac - f
        diffs -= np.round(diffs)
        norms = np.linalg.norm(diffs, axis=1)
        idx = int(np.argmin(norms))
        assert norms[idx] < tol
        assert motif_symbols[idx] == sym
        counts[idx] += 1

    det_T_signed = int(np.dot(np.cross(T[:, 0], T[:, 1]), T[:, 2]))
    det_T = abs(det_T_signed)
    assert np.all(counts == det_T)


def test_motif_preservation_atom_count_diamond():
    """Supercell atom count equals |det(T)| * N_prim for a multi-atom motif."""

    atoms = diamond_primitive_cell()
    A_prim = atoms.cell.array.T
    A_conv = A_prim.copy()

    # Use a simple Miller; e.g. (1,1,0)
    u, v, w, m = compute_primitive_surface_basis(1, 1, 0, A_conv, A_prim)
    layers = 2
    T = np.column_stack([u, v, layers * w]).astype(int)

    n_prim = len(atoms)
    supercell = make_supercell_col(atoms, T)
    n_super = len(supercell)

    det_T = int(round(abs(np.linalg.det(T))))
    assert n_super == det_T * n_prim


def test_motif_position_preservation_diamond():
    """Each supercell atom maps back to a primitive motif position modulo Z^3."""

    atoms = diamond_primitive_cell()
    A_prim = atoms.cell.array.T
    A_conv = A_prim.copy()

    u, v, w, m = compute_primitive_surface_basis(1, 1, 0, A_conv, A_prim)
    layers = 2
    T = np.column_stack([u, v, layers * w]).astype(int)
    supercell = make_supercell_col(atoms, T)

    motif_frac = atoms.get_scaled_positions() % 1.0
    super_frac_in_prim = np.linalg.solve(A_prim, supercell.get_positions().T).T
    super_frac_mod = super_frac_in_prim % 1.0

    counts = np.zeros(len(motif_frac), dtype=int)
    tol = 1e-8
    for f in super_frac_mod:
        diffs = motif_frac - f
        diffs -= np.round(diffs)
        norms = np.linalg.norm(diffs, axis=1)
        idx = int(np.argmin(norms))
        assert norms[idx] < tol
        counts[idx] += 1

    det_T = int(round(abs(np.linalg.det(T))))
    assert np.all(counts == det_T)


def test_motif_position_preservation_rocksalt_species_aware():
    atoms = rocksalt_primitive_cell()
    A_prim = atoms.cell.array.T
    A_conv = A_prim.copy()
    u, v, w, m = compute_primitive_surface_basis(1, 1, 1, A_conv, A_prim)
    T = np.column_stack([u, v, 2 * w]).astype(int)
    _assert_species_preserving_supercell(atoms, T)


def test_motif_position_preservation_custom_low_symmetry_species_aware():
    atoms = custom_low_symmetry_motif_cell()
    A_prim = atoms.cell.array.T
    A_conv = A_prim.copy()
    u, v, w, m = compute_primitive_surface_basis(2, 1, 3, A_conv, A_prim, max_denominator=256)
    T = np.column_stack([u, v, 2 * w]).astype(int)
    _assert_species_preserving_supercell(atoms, T)
