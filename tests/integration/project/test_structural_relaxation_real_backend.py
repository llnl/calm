from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("ase")

from calm.project.bootstrap import open_workspace
from test_helpers import make_test_bulk


def test_real_interface_relaxation_persists_calculator_backed_result(
    tmp_path: Path,
) -> None:
    ws = open_workspace(root=tmp_path)
    bulk_a = make_test_bulk(ws, "Al", "fcc", 4.05)
    bulk_b = make_test_bulk(ws, "Cu", "fcc", 3.61)
    slab_a = ws.build_slabs(bulk_a.id_short, millers=[(1, 1, 1)])[0]
    slab_b = ws.build_slabs(bulk_b.id_short, millers=[(2, 0, 0)])[0]
    search = ws.start_prototype_search(
        slab_a.id_short,
        slab_b.id_short,
        n_candidates=1,
    )
    prototype = ws.list_prototypes(run=search.id_short, limit=1)[0]
    seed = ws.create_derived_interface(
        prototype.id_short,
        label="relaxation_seed",
        strain_alpha=0.5,
        z_padding=2.0,
        vacuum=10.0,
        stage="registry_refined",
    )
    assert seed.atoms_artifact_uid is None
    from calm.slab.oriented.cell_contract import (
        INTERFACE_DEFORMATION_ACCOUNTING_INFO_KEY,
        INTERFACE_RELAXATION_DEFORMATION_INFO_KEY,
    )

    seed_atoms = ws.materialize_derived_interface_atoms(seed.uid_full)
    source_accounting = seed_atoms.info[
        INTERFACE_DEFORMATION_ACCOUNTING_INFO_KEY
    ]

    rows = ws.run_relaxation_stage(
        [seed.id_short],
        protocol="ionic_positions_v1",
        convergence={"force_tol": 100.0},
        max_steps=2,
        relax_cell=False,
        backend="real",
        resume=False,
    )

    assert len(rows) == 1
    assert rows[0]["status"] == "completed"
    relaxed_uid = rows[0]["relaxed_interface_uid"]
    assert relaxed_uid
    relaxed = ws.get_derived_interface(relaxed_uid)
    params = dict((relaxed.spec or {}).get("params") or {})
    assert relaxed.stage == "relaxed"
    assert params["scientific_authority"] == "calculator_backed"
    assert params["converged"] is True
    assert params["optimizer"] == "BFGS"
    assert params["cell_filter"] is None

    relaxed_atoms = ws.get_derived_interface_atoms(relaxed_uid)
    assert (
        relaxed_atoms.info[INTERFACE_DEFORMATION_ACCOUNTING_INFO_KEY]
        == source_accounting
    )
    relaxation_accounting = relaxed_atoms.info[
        INTERFACE_RELAXATION_DEFORMATION_INFO_KEY
    ]
    assert relaxation_accounting["cell_mode"] == "fixed"
    assert params["deformation_accounting"] == relaxation_accounting

    reopened = open_workspace(root=tmp_path)
    reopened_atoms = reopened.get_derived_interface_atoms(relaxed_uid)
    assert (
        reopened_atoms.info[INTERFACE_DEFORMATION_ACCOUNTING_INFO_KEY]
        == source_accounting
    )
    assert (
        reopened_atoms.info[INTERFACE_RELAXATION_DEFORMATION_INFO_KEY]
        == relaxation_accounting
    )

    results = ws.list_followup_results(
        run=rows[0]["run_uid"],
        kind="relaxation_stage",
    )
    assert len(results) == 1
    payload = dict(results[0].payload or {})
    assert payload["convergence_certificate"]["residual_satisfied"] is True
    assert payload["backend_identity"]["calculator_specs"]
