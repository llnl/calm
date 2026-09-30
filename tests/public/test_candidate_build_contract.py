"""Scientific build-kernel coverage after candidate workflow retirement."""

from __future__ import annotations

from pathlib import Path

import pytest

from calm import SearchSettings
from calm.public.workflows.search import search_interfaces
from calm.public.records.surfaces import Surface


EXAMPLE_STRUCTURES = Path(__file__).resolve().parents[2] / "examples" / "Structures"


def _best_lif_li2o_candidate():
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
    return result.best


def test_build_kernel_vacuum_changes_interface_cell() -> None:
    """The retained scientific kernel honors out-of-plane vacuum padding."""
    pytest.importorskip("ase")
    pytest.importorskip("spglib")

    candidate = _best_lif_li2o_candidate()

    from calm.interface.config import InterfaceBuildConfig
    from calm.interface.pipeline import build_interface, compute_strain_state

    prototype = candidate.prototype
    strain = compute_strain_state(prototype)
    low_vacuum = build_interface(
        prototype,
        strain,
        InterfaceBuildConfig(z_padding=1.5, vacuum_padding=5.0),
    )
    high_vacuum = build_interface(
        prototype,
        strain,
        InterfaceBuildConfig(z_padding=1.5, vacuum_padding=20.0),
    )

    low_c = low_vacuum.atoms.cell.lengths()[2]
    high_c = high_vacuum.atoms.cell.lengths()[2]

    assert high_c > low_c
    assert high_c - low_c == pytest.approx(15.0, abs=1.0e-6)
    assert not hasattr(candidate, "_build")
