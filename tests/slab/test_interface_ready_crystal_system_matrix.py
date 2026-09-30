"""Atomistic matrix for interface-ready slab cells across crystal systems."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pytest

pytest.importorskip("ase")
pytest.importorskip("spglib")

from ase import Atoms  # noqa: E402
from ase.geometry import cellpar_to_cell  # noqa: E402

from calm.bulk.bulk import Bulk  # noqa: E402
from calm.interface.building._kernel import build_interface_atoms  # noqa: E402
from calm.slab.oriented.builder import build_oriented_slab  # noqa: E402
from calm.slab.oriented.cell_contract import (  # noqa: E402
    assess_oriented_surface_cell,
    require_interface_ready_slab_cell,
)


@dataclass(frozen=True)
class CrystalSystemCase:
    name: str
    cell_parameters: tuple[float, float, float, float, float, float]
    millers: tuple[tuple[int, int, int], ...]


CASES = (
    CrystalSystemCase(
        "cubic",
        (3.6, 3.6, 3.6, 90.0, 90.0, 90.0),
        ((1, 0, 0), (1, 1, 0), (1, 1, 1)),
    ),
    CrystalSystemCase(
        "tetragonal",
        (3.2, 3.2, 5.1, 90.0, 90.0, 90.0),
        ((1, 0, 0), (0, 0, 1), (1, 0, 1)),
    ),
    CrystalSystemCase(
        "orthorhombic",
        (3.1, 4.2, 5.3, 90.0, 90.0, 90.0),
        ((1, 0, 0), (0, 1, 0), (1, 1, 1)),
    ),
    CrystalSystemCase(
        "hexagonal",
        (3.0, 3.0, 5.2, 90.0, 90.0, 120.0),
        ((0, 0, 1), (1, 0, 0), (1, 0, 1)),
    ),
    CrystalSystemCase(
        "trigonal",
        (3.4, 3.4, 3.4, 75.0, 75.0, 75.0),
        ((0, 0, 1), (1, 0, 0), (1, 1, 1)),
    ),
    CrystalSystemCase(
        "monoclinic",
        (3.1, 4.2, 5.3, 90.0, 104.0, 90.0),
        ((1, 0, 0), (0, 1, 0), (1, 0, 1)),
    ),
    CrystalSystemCase(
        "triclinic",
        (3.1, 4.2, 5.3, 78.0, 83.0, 74.0),
        ((1, 0, 0), (0, 1, 0), (1, 1, 1)),
    ),
)


def _bulk(case: CrystalSystemCase) -> Bulk:
    atoms = Atoms(
        "Si",
        scaled_positions=[[0.0, 0.0, 0.0]],
        cell=cellpar_to_cell(case.cell_parameters),
        pbc=True,
    )
    return Bulk(
        atoms,
        label=f"{case.name}_matrix_fixture",
        symprec=1.0e-6,
        no_idealize=True,
    )


@pytest.mark.parametrize(
    ("case", "hkl"),
    [
        pytest.param(case, hkl, id=f"{case.name}-{hkl[0]}{hkl[1]}{hkl[2]}")
        for case in CASES
        for hkl in case.millers
    ],
)
def test_surface_and_supercell_pipeline_remains_interface_ready(
    case: CrystalSystemCase,
    hkl: tuple[int, int, int],
) -> None:
    result = build_oriented_slab(
        _bulk(case),
        hkl=hkl,
        layers=3,
        reduce_inplane=True,
        orthogonalize_c=False,
        vacuum=6.0,
    )

    block_cell = np.asarray(result.block.cell.array, dtype=float)
    slab_cell = np.asarray(result.slab.cell.array, dtype=float)
    block_assessment = assess_oriented_surface_cell(block_cell)
    slab_assessment = require_interface_ready_slab_cell(slab_cell)

    assert block_assessment.signed_volume > 0.0
    assert slab_assessment.signed_volume > 0.0
    assert np.allclose(block_cell[:2], slab_cell[:2], atol=2.0e-11, rtol=0.0)
    assert np.allclose(slab_cell[2, :2], 0.0, atol=2.0e-11, rtol=0.0)
    assert result.transforms.shear_info is None
    assert np.allclose(result.transforms.F_ideal_to_slab, np.eye(3), atol=2.0e-12)

    vacuum_info = result.transforms.vacuum_info
    assert vacuum_info is not None
    assert vacuum_info["interface_ready"] is True
    assert vacuum_info["canonicalization_applies_physical_strain"] is False
    assert vacuum_info["canonicalization_mode"] in {
        "already_orthogonal",
        "boundary_reembedding",
    }

    inplane_supercell = np.array(
        [[2, 0, 0], [1, 1, 0], [0, 0, 1]],
        dtype=int,
    )
    built = build_interface_atoms(
        result.slab,
        result.slab,
        N_A3=inplane_supercell,
        N_B3=inplane_supercell,
        R_A3=np.eye(3),
        R_B3=np.eye(3),
        F_A=np.eye(3),
        F_B=np.eye(3),
        translation_frac=(0.25, 0.75),
        z_padding=2.0,
        vacuum_padding=4.0,
    )

    interface_assessment = require_interface_ready_slab_cell(
        np.asarray(built.atoms.cell.array, dtype=float)
    )
    assert interface_assessment.signed_volume > 0.0
    assert len(built.lower_indices) == 2 * len(result.slab)
    assert len(built.upper_indices) == 2 * len(result.slab)
