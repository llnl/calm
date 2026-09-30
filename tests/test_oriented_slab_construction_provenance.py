"""End-to-end transformation provenance for oriented slab construction."""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("ase")
pytest.importorskip("spglib")

from ase.build import bulk

from calm.bulk.bulk import Bulk
from calm.slab.oriented.builder import build_oriented_slab


def _canonical_matrix(payload: dict[str, object] | None) -> np.ndarray:
    if payload is None:
        return np.eye(3, dtype=int)
    return np.asarray(payload["L_diag"], dtype=int)


def test_primary_transform_chain_reconstructs_periodic_block_cell() -> None:
    conventional = bulk("Al", "fcc", a=4.05, cubic=True)
    bulk_object = Bulk(conventional)

    result = build_oriented_slab(
        bulk_object,
        hkl=(1, 1, 0),
        layers=3,
        reduce_inplane=True,
        reduce_c_tilt=True,
        orthogonalize_c=True,
        vacuum=7.5,
    )
    transforms = result.transforms

    cell = transforms.P_supercell_row @ bulk_object.prim.cell.array
    cell = cell @ transforms.R_conv_to_ungauged().T
    cell = transforms.U_inplane_col.T @ cell
    cell = cell @ transforms.R_align.T
    if transforms.L_c_tilt_row is not None:
        cell = transforms.L_c_tilt_row @ cell
    if transforms.F_orthogonalize_c_slab is not None:
        cell = cell @ transforms.F_orthogonalize_c_slab.T
    cell = _canonical_matrix(transforms.canonical_sign_fix) @ cell

    assert np.allclose(cell, result.block.cell.array, atol=2e-9, rtol=0.0)
    assert transforms.supercell_reference == "primitive"
    assert transforms.miller_primitive is not None
    assert transforms.vacuum_info is not None
    assert transforms.vacuum_info["vacuum_per_side"] == pytest.approx(7.5)
    assert np.allclose(
        result.slab.cell.array[:2],
        result.block.cell.array[:2],
        atol=2e-10,
        rtol=0.0,
    )
    assert result.slab.cell.array[2, 2] > result.block.cell.array[2, 2]


def test_primary_transform_payload_preserves_new_reference_fields() -> None:
    conventional = bulk("Cu", "fcc", a=3.61, cubic=True)
    result = build_oriented_slab(
        Bulk(conventional),
        hkl=(1, 1, 1),
        layers=2,
        reduce_inplane=False,
        reduce_c_tilt=False,
        vacuum=None,
    )

    payload = result.transforms.to_dict()
    restored = type(result.transforms).from_dict(payload)

    assert payload["supercell_reference"] == "primitive"
    assert payload["miller_primitive"] is not None
    assert restored.supercell_reference == "primitive"
    assert restored.miller_primitive == result.transforms.miller_primitive
    assert restored.canonical_sign_fix == result.transforms.canonical_sign_fix
