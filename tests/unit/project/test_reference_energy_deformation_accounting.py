"""Dependency-light tests for calculated strained-bulk deformation accounting."""

from __future__ import annotations

import copy
from types import SimpleNamespace

import numpy as np
import pytest

from calm.interface.energy.contract import UnsupportedReferenceWorkflowError

from calm.project.application.followups.reference_energy import (
    _apply_bulk_deformation,
    _map_reference_deformation_to_conventional,
    _reference_deformation_state,
    _require_supported_reference_cell_mode,
    _validate_reference_target_basis,
)
from calm.slab.oriented.cell_contract import (
    INTERFACE_DEFORMATION_ACCOUNTING_INFO_KEY,
    INTERFACE_RELAXATION_DEFORMATION_INFO_KEY,
)
from calm.slab.oriented.transforms import ORIENTED_SLAB_TRANSFORMS_INFO_KEY
from oriented_slab_fixtures import current_compact_transforms


def _source_accounting() -> dict[str, object]:
    identity = np.eye(3)
    lower_interface = np.diag([1.1, 0.9, 1.0])
    upper_interface = np.diag([0.95, 1.05, 1.0])
    return {
        "policy": "composed_slab_deformation",
        "version": 1,
        "lower": {
            "F_construction_slab": identity.tolist(),
            "F_interface_slab": lower_interface.tolist(),
            "F_total_slab": lower_interface.tolist(),
        },
        "upper": {
            "F_construction_slab": identity.tolist(),
            "F_interface_slab": upper_interface.tolist(),
            "F_total_slab": upper_interface.tolist(),
        },
    }


def _accounting(*, relaxed: bool) -> dict[str, object]:
    source = _source_accounting()
    out: dict[str, object] = {
        INTERFACE_DEFORMATION_ACCOUNTING_INFO_KEY: source,
    }
    if relaxed:
        relaxation = np.diag([1.02, 0.98, 1.0])
        out[INTERFACE_RELAXATION_DEFORMATION_INFO_KEY] = {
            "policy": "composed_interface_relaxation_deformation",
            "version": 1,
            "source_policy": source["policy"],
            "source_version": source["version"],
            "cell_mode": "interface_in_plane",
            "composition_count": 1,
            "initial_cell_A": np.diag([2.0, 3.0, 8.0]).tolist(),
            "final_cell_A": np.diag([2.04, 2.94, 8.0]).tolist(),
            "F_relaxation_interface": relaxation.tolist(),
            "lower": {
                "F_total_post_relaxation_slab": (
                    relaxation
                    @ np.asarray(source["lower"]["F_total_slab"], dtype=float)
                ).tolist(),
            },
            "upper": {
                "F_total_post_relaxation_slab": (
                    relaxation
                    @ np.asarray(source["upper"]["F_total_slab"], dtype=float)
                ).tolist(),
            },
        }
    return out


def test_reference_deformation_uses_pre_relaxation_total_when_unrelaxed() -> None:
    total, provenance = _reference_deformation_state(
        _accounting(relaxed=False),
        side="a",
    )

    np.testing.assert_allclose(total, np.diag([1.1, 0.9, 1.0]))
    assert provenance["state"] == "pre_relaxation"
    assert "F_relaxation_interface" not in provenance


def test_reference_deformation_uses_post_relaxation_total_when_present() -> None:
    total, provenance = _reference_deformation_state(
        _accounting(relaxed=True),
        side="b",
    )

    expected = np.diag([1.02, 0.98, 1.0]) @ np.diag([0.95, 1.05, 1.0])
    np.testing.assert_allclose(total, expected)
    assert provenance["state"] == "post_relaxation"
    assert provenance["relaxation_cell_mode"] == "interface_in_plane"
    assert provenance["relaxation_composition_count"] == 1


def test_reference_deformation_maps_through_the_persisted_slab_gauge() -> None:
    atoms = SimpleNamespace(
        info={
            ORIENTED_SLAB_TRANSFORMS_INFO_KEY: current_compact_transforms(
                interface_ready=True
            )
        }
    )
    rotation = np.array([[0.0, -1.0], [1.0, 0.0]])
    total = np.diag([1.2, 0.8, 1.0])

    mapped = _map_reference_deformation_to_conventional(
        slab_atoms=atoms,
        rotation_2d=rotation,
        F_total_slab=total,
        side="a",
    )

    gauge = np.eye(3)
    gauge[:2, :2] = rotation
    np.testing.assert_allclose(mapped, gauge.T @ total @ gauge)


class _BulkAtoms:
    def __init__(self, cell: np.ndarray) -> None:
        self._cell = np.asarray(cell, dtype=float)
        self.scale_atoms = None

    def copy(self) -> "_BulkAtoms":
        return copy.deepcopy(self)

    def get_cell(self) -> np.ndarray:
        return self._cell.copy()

    def set_cell(self, cell: np.ndarray, *, scale_atoms: bool) -> None:
        self._cell = np.asarray(cell, dtype=float)
        self.scale_atoms = bool(scale_atoms)


def test_bulk_reference_applies_total_deformation_with_scaled_positions() -> None:
    atoms = _BulkAtoms(np.diag([2.0, 3.0, 4.0]))
    deformation = np.array(
        [[1.1, 0.2, 0.0], [0.0, 0.9, 0.0], [0.0, 0.0, 1.0]]
    )

    strained = _apply_bulk_deformation(atoms, deformation)

    np.testing.assert_allclose(
        strained.get_cell().T,
        deformation @ atoms.get_cell().T,
    )
    assert strained.scale_atoms is True
    np.testing.assert_allclose(atoms.get_cell(), np.diag([2.0, 3.0, 4.0]))


class _SlabAtoms:
    def __init__(self, cell: np.ndarray) -> None:
        self.cell = np.asarray(cell, dtype=float)

    def get_cell(self) -> np.ndarray:
        return self.cell.copy()


def test_reference_deformation_must_reproduce_authoritative_interface_basis() -> None:
    slab = _SlabAtoms(np.diag([2.0, 3.0, 8.0]))
    deformation = np.diag([1.1, 0.9, 1.0])
    target = np.diag([2.2, 2.7])

    _validate_reference_target_basis(
        slab_atoms=slab,
        matrix=np.eye(2, dtype=int),
        rotation=np.eye(2),
        F_total_slab=deformation,
        target_basis=target,
        side="a",
    )

    with pytest.raises(ValueError, match="does not reproduce"):
        _validate_reference_target_basis(
            slab_atoms=slab,
            matrix=np.eye(2, dtype=int),
            rotation=np.eye(2),
            F_total_slab=deformation,
            target_basis=np.diag([2.3, 2.7]),
            side="a",
        )


def test_variable_cell_mode_is_supported_only_for_strained_bulk_references() -> None:
    interface = SimpleNamespace(
        params={"relaxation_settings": {"relax_cell": True}}
    )

    _require_supported_reference_cell_mode(
        interface,
        formula="interface_excess_strained_bulk",
    )
    with pytest.raises(UnsupportedReferenceWorkflowError, match="fixed-cell"):
        _require_supported_reference_cell_mode(
            interface,
            formula="work_of_separation_unrelaxed_surfaces",
        )
