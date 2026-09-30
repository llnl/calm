"""Dependency-light persistence checks for interface deformation provenance."""

from __future__ import annotations

import copy

import numpy as np
import pytest

from calm.project.application.derived_interfaces import DerivedInterfaceService
from calm.slab.oriented.cell_contract import (
    INTERFACE_DEFORMATION_ACCOUNTING_INFO_KEY,
    INTERFACE_RELAXATION_DEFORMATION_INFO_KEY,
    record_interface_relaxation_deformation,
)


class _Cell:
    def __init__(self, array):
        self.array = np.asarray(array, dtype=float)


class _Atoms:
    def __init__(self, cell, info):
        self.cell = _Cell(cell)
        self.info = copy.deepcopy(info)


def _source() -> dict[str, object]:
    identity = np.eye(3).tolist()
    return {
        "policy": "composed_slab_deformation",
        "version": 1,
        "lower": {
            "F_construction_slab": identity,
            "F_interface_slab": identity,
            "F_total_slab": identity,
        },
        "upper": {
            "F_construction_slab": identity,
            "F_interface_slab": identity,
            "F_total_slab": identity,
        },
    }


def _payload(info: dict[str, object]) -> dict[str, object]:
    return {
        "numbers": [1],
        "cell": np.diag([2.0, 2.0, 8.0]).tolist(),
        "scaled_positions": [[0.0, 0.0, 0.0]],
        "pbc": [True, True, True],
        "info": copy.deepcopy(info),
    }


def test_mapping_serialization_preserves_valid_deformation_provenance() -> None:
    source = _source()
    atoms = _Atoms(
        np.diag([2.0, 2.0, 8.0]),
        {INTERFACE_DEFORMATION_ACCOUNTING_INFO_KEY: source},
    )
    relaxation = record_interface_relaxation_deformation(
        atoms,
        initial_cell=atoms.cell.array,
        final_cell=atoms.cell.array,
        cell_mode="fixed",
    )
    assert relaxation is not None

    serialized = DerivedInterfaceService._serialize_atoms(_payload(atoms.info))

    assert serialized["info"][INTERFACE_DEFORMATION_ACCOUNTING_INFO_KEY] == source
    assert (
        serialized["info"][INTERFACE_RELAXATION_DEFORMATION_INFO_KEY]
        == relaxation
    )


def test_mapping_serialization_rejects_inconsistent_deformation_provenance() -> None:
    source = _source()
    source["lower"]["F_total_slab"] = np.diag([1.1, 1.0, 1.0]).tolist()

    with pytest.raises(ValueError, match="must equal"):
        DerivedInterfaceService._serialize_atoms(
            _payload({INTERFACE_DEFORMATION_ACCOUNTING_INFO_KEY: source})
        )
