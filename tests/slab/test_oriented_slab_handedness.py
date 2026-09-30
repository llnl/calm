"""Regression coverage for the oriented surface-cell handedness gauge."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("ase")
pytest.importorskip("spglib")

from ase.build import bulk as ase_bulk  # noqa: E402
from ase.io import read as ase_read  # noqa: E402

from calm.bulk.bulk import Bulk  # noqa: E402
from calm.slab.oriented.builder import build_oriented_slab  # noqa: E402
from calm.slab.oriented.terminations import (  # noqa: E402
    enumerate_all_terminations,
    identify_unique_terminations,
)
from calm.slab.oriented.transforms import (  # noqa: E402
    ORIENTED_SLAB_TRANSFORMS_INFO_KEY,
)


EXAMPLE_STRUCTURES = Path(__file__).resolve().parents[2] / "examples" / "Structures"


@pytest.mark.parametrize("hkl", [(1, 0, 0), (1, 1, 0), (1, 1, 1)])
def test_reduced_fcc_surface_cells_use_the_right_handed_cartesian_gauge(
    hkl: tuple[int, int, int],
) -> None:
    material = Bulk(ase_bulk("Al", "fcc", a=4.05, cubic=True))
    result = build_oriented_slab(
        material,
        hkl=hkl,
        layers=4,
        reduce_inplane=True,
        vacuum=8.0,
    )

    for structure in (result.block, result.slab):
        cell = np.asarray(structure.cell.array, dtype=float)
        inplane_area = float(
            np.linalg.det(np.column_stack([cell[0, :2], cell[1, :2]]))
        )
        assert float(np.linalg.det(cell)) > 0.0
        assert inplane_area > 0.0
        assert cell[0, 0] > 0.0
        assert cell[1, 1] > 0.0
        assert cell[2, 2] > 0.0

    slab_cell = np.asarray(result.slab.cell.array, dtype=float)
    assert np.allclose(slab_cell[2, :2], 0.0, atol=2e-12, rtol=0.0)
    assert result.transforms.vacuum_info is not None
    assert result.transforms.vacuum_info["orthogonal_vacuum_axis"] is True
    assert result.transforms.vacuum_info["c_xy_norm_after"] == pytest.approx(0.0)

    if hkl == (1, 1, 1):
        block_cell = np.asarray(result.block.cell.array, dtype=float)
        assert np.linalg.norm(block_cell[2, :2]) > 1e-8
        assert result.transforms.vacuum_info["c_xy_norm_before"] > 1e-8
        assert result.transforms.shear_info is None


def test_right_handed_li2o_100_catalog_keeps_oxygen_on_bottom_at_shift_one() -> None:
    material = Bulk(ase_read(EXAMPLE_STRUCTURES / "Li2O.poscar"))
    candidates = identify_unique_terminations(
        material,
        (1, 0, 0),
        layers=4,
    )

    oxygen_facing = [
        candidate
        for candidate in candidates
        if candidate["bottom_composition"] == "O"
    ]

    assert len(oxygen_facing) == 1
    assert oxygen_facing[0]["shift"] == 1


def test_li2o_111_terminations_use_an_orthogonal_vacuum_axis() -> None:
    material = Bulk(ase_read(EXAMPLE_STRUCTURES / "Li2O.poscar"))
    terminations = enumerate_all_terminations(
        material,
        (1, 1, 1),
        layers=4,
        vacuum=15.0,
    )

    assert terminations
    for termination in terminations:
        cell = np.asarray(termination.slab.cell.array, dtype=float)
        assert np.allclose(cell[2, :2], 0.0, atol=2e-12, rtol=0.0)
        assert float(np.linalg.det(cell)) > 0.0
        transforms = termination.slab.info[ORIENTED_SLAB_TRANSFORMS_INFO_KEY]
        assert transforms["vacuum_info"]["orthogonal_vacuum_axis"] is True
        assert transforms["vacuum_info"]["c_xy_norm_before"] > 1e-8
        assert transforms["vacuum_info"]["c_xy_norm_after"] == pytest.approx(0.0)
