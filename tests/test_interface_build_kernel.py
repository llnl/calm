import numpy as np
import pytest
from ase import Atoms

from calm.interface.building._kernel import (
    build_interface_atoms,
    quantize_translation_frac,
)


def test_quantize_translation_frac_wraps_and_rounds() -> None:
    # Use values that would otherwise produce floating representation artifacts.
    t = quantize_translation_frac((1.2, -0.1), round_decimals=12)
    assert t == (0.2, 0.9)


def test_quantize_translation_frac_rewraps_rounded_unit_value() -> None:
    assert quantize_translation_frac((0.9999999999, 0.0), 8) == (0.0, 0.0)


def test_build_interface_atoms_basic_stacking() -> None:
    slab_a = Atoms(
        symbols="H2",
        positions=[[0.0, 0.0, 0.0], [0.0, 0.0, 1.0]],
        cell=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 5.0]],
        pbc=[True, True, True],
    )
    slab_b = Atoms(
        symbols="He",
        positions=[[0.0, 0.0, 0.5]],
        cell=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 5.0]],
        pbc=[True, True, True],
    )

    N = np.eye(3, dtype=int)
    R = np.eye(3, dtype=float)
    F = np.eye(3, dtype=float)

    built_structure = build_interface_atoms(
        slab_A_atoms=slab_a,
        slab_B_atoms=slab_b,
        N_A3=N,
        N_B3=N,
        R_A3=R,
        R_B3=R,
        F_A=F,
        F_B=F,
        translation_frac=(0.0, 0.0),
        z_padding=2.0,
    )

    assert len(built_structure.atoms) == len(slab_a) + len(slab_b)
    assert built_structure.lower_indices.tolist() == [0, 1]
    assert built_structure.upper_indices.tolist() == [2]

    z = built_structure.atoms.positions[:, 2]
    z_lower_max = float(np.max(z[built_structure.lower_indices]))
    z_upper_min = float(np.min(z[built_structure.upper_indices]))

    # The stacking convention places slab B above slab A with a z_padding separation.
    assert z_upper_min >= z_lower_max + 2.0 - 1e-9
