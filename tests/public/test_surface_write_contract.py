"""Contract tests for basic-facing Surface write behavior."""

from __future__ import annotations

from pathlib import Path

import pytest

from calm.public.records.surfaces import Surface


EXAMPLE_STRUCTURES = Path(__file__).resolve().parents[2] / "examples" / "Structures"


def test_surface_write_materializes_requested_slab(tmp_path: Path) -> None:
    """Surface.write writes the requested slab, not the source bulk cell."""
    pytest.importorskip("ase")
    pytest.importorskip("spglib")
    from ase.io import read

    surface = Surface(
        EXAMPLE_STRUCTURES / "LiF.poscar",
        miller=(1, 1, 1),
        layers=4,
        vacuum=12.0,
        material="LiF",
        label="LiF(111)",
    )

    source_atoms = surface.to_ase()
    slab_atoms = surface.to_slab().atoms

    assert slab_atoms.cell.lengths() != pytest.approx(source_atoms.cell.lengths())

    output_path = tmp_path / "LiF_111_slab.cif"
    surface.write(output_path)

    written_atoms = read(output_path)
    assert len(written_atoms) == len(slab_atoms)
    assert written_atoms.cell.lengths() == pytest.approx(slab_atoms.cell.lengths())
    assert written_atoms.cell.lengths() != pytest.approx(source_atoms.cell.lengths())
