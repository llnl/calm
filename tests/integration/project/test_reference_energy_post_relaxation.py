from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("ase")
pytest.importorskip("spglib")

from calm.interface.building._geometry import _apply_deformation_gradient
from calm.project.application.followups.reference_energy import (
    _prepare_interface_targets,
    _structure_fingerprint as _structure_fingerprint_for_test,
)
from calm.project.bootstrap import open_workspace
from calm.project.runtime.workspace import Workspace
from calm.slab.oriented.cell_contract import (
    record_interface_relaxation_deformation,
)
from test_helpers import make_test_bulk


def test_variable_cell_interface_references_use_post_relaxation_deformation(
    tmp_path: Path,
) -> None:
    ws = open_workspace(root=tmp_path)
    assert isinstance(ws, Workspace)

    bulk_a = make_test_bulk(ws, "Al", "fcc", 4.05, with_calculator=False)
    bulk_b = make_test_bulk(ws, "Cu", "fcc", 3.61, with_calculator=False)
    slab_a = ws.build_slabs(bulk_a.id_short, millers=[(1, 0, 0)])[0]
    slab_b = ws.build_slabs(bulk_b.id_short, millers=[(1, 0, 0)])[0]
    run = ws.start_prototype_search(
        slab_a.id_short,
        slab_b.id_short,
        n_candidates=1,
    )
    prototype = ws.list_prototypes(run=run.id_short, limit=1)[0]

    alpha = 0.4
    built = ws.build_interface_from_prototype(
        prototype.id_short,
        alpha=alpha,
        z_padding=2.0,
        vacuum=10.0,
    )
    relaxed_atoms = built.atoms.copy()
    initial_cell = np.asarray(relaxed_atoms.get_cell(), dtype=float)
    relaxation = np.diag([1.01, 0.99, 1.0])
    _apply_deformation_gradient(relaxed_atoms, relaxation)
    record_interface_relaxation_deformation(
        relaxed_atoms,
        initial_cell=initial_cell,
        final_cell=relaxed_atoms.get_cell(),
        cell_mode="interface_in_plane",
    )
    interface = ws.create_derived_interface(
        prototype.id_short,
        label="variable_cell_reference",
        stage="relaxed",
        strain_alpha=alpha,
        z_padding=2.0,
        vacuum=10.0,
        params={
            "relaxation_settings": {"relax_cell": True},
            "scientific_authority": "calculator_backed",
        },
        atoms=relaxed_atoms,
    )

    with ws._fresh_uow() as uow:
        targets = _prepare_interface_targets(
            uow,
            interface_uid_full=interface.uid_full,
            formula="interface_excess_strained_bulk",
            interface_atoms_loader=ws.materialize_derived_interface_atoms,
        )

    assert {target.reference_kind for target in targets} == {
        "strained_bulk_a",
        "strained_bulk_b",
    }
    expected_area = float(
        np.linalg.norm(
            np.cross(relaxed_atoms.cell.array[0], relaxed_atoms.cell.array[1])
        )
    )
    for target in targets:
        assert target.metadata["reference_area_A2"] == pytest.approx(expected_area)
        assert (
            target.metadata["source_interface_structure_fingerprint"]
            is not None
        )
        deformation = target.metadata["deformation_accounting"]
        assert deformation["state"] == "post_relaxation"
        assert deformation["relaxation_cell_mode"] == "interface_in_plane"
        assert deformation["relaxation_composition_count"] == 1
        assert np.linalg.det(
            np.asarray(
                deformation["F_total_reference_conventional"],
                dtype=float,
            )
        ) > 0.0

    stage = ws.run_reference_energy_stage(
        [interface.uid_full],
        formula="interface_excess_strained_bulk",
        backend="deterministic",
        resume=False,
        partial_resume=False,
    )
    assert len(stage) == 2
    assert all(row["status"] == "completed" for row in stage)
    persisted = ws.list_followup_results(kind="reference_energy")
    assert len(persisted) == 2
    for result in persisted:
        metadata = result.payload["reference"]["metadata"]
        assert metadata["reference_area_A2"] == pytest.approx(expected_area)
        assert metadata["deformation_accounting"]["state"] == "post_relaxation"
        assert (
            metadata["source_interface_structure_fingerprint"]
            == _structure_fingerprint_for_test(relaxed_atoms)
        )
