"""Contract tests for basic-facing interface write behavior."""

from __future__ import annotations

from pathlib import Path

import pytest

from calm import SearchSettings
from calm.public.workflows.search import search_interfaces
from calm.public.records.surfaces import Surface


EXAMPLE_STRUCTURES = Path(__file__).resolve().parents[2] / "examples" / "Structures"


def _build_lif_li2o_interface():
    surface_a = Surface(
        EXAMPLE_STRUCTURES / "LiF.poscar",
        miller=(1, 1, 1),
        thickness=10.0,
        material="LiF",
        label="LiF(111)",
    )
    surface_b = Surface(
        EXAMPLE_STRUCTURES / "Li2O.poscar",
        miller=(1, 1, 1),
        thickness=10.0,
        material="Li2O",
        label="Li2O(111)",
    )
    result = search_interfaces(
        surface_a,
        surface_b,
        settings=SearchSettings(
            max_principal_strain=0.10,
            max_atoms=300,
            max_supercell_index=12,
            max_candidates=1,
        ),
    )
    assert result.best is not None
    from calm.interface.config import InterfaceBuildConfig
    from calm.interface.pipeline import build_interface, compute_strain_state
    from calm.public.records.interfaces import InterfaceModel

    candidate = result.best
    prototype = candidate.prototype
    internal = build_interface(
        prototype,
        compute_strain_state(prototype),
        InterfaceBuildConfig(z_padding=1.5, vacuum_padding=12.0),
    )
    return InterfaceModel(internal, candidate=candidate)


def test_interface_model_write_creates_requested_structure_file(tmp_path: Path) -> None:
    """InterfaceModel.write writes the built interface atoms to the requested path."""
    pytest.importorskip("ase")
    pytest.importorskip("spglib")
    from ase.io import read

    interface = _build_lif_li2o_interface()

    output_path = tmp_path / "nested" / "LiF_Li2O_interface.vasp"
    interface.write(output_path, format="vasp")

    assert output_path.is_file()
    written_atoms = read(output_path, format="vasp")
    assert len(written_atoms) == len(interface.atoms)
    assert written_atoms.cell.lengths() == pytest.approx(interface.atoms.cell.lengths())
