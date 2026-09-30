"""Exact-current structure-backed bulk fixtures for successful tests.

Malformed-state tests should mutate a fresh payload returned here so each
failure remains explicit and the valid baseline continues to mirror the
current persisted writer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from calm.bulk.provenance import (
    CALM_BULK_CANONICALIZATION_TRANSFORMS_INFO_KEY,
    get_bulk_canonicalization_transforms,
    stamp_bulk_canonicalization_transforms,
)
from current_structure_fixtures import current_atoms_payload


@dataclass
class _Cell:
    array: np.ndarray


@dataclass
class _Atoms:
    cell: _Cell
    numbers: np.ndarray
    info: dict[str, object] = field(default_factory=dict)

    def get_atomic_numbers(self) -> np.ndarray:
        return self.numbers.copy()


def _atoms(
    cell_columns: np.ndarray,
    numbers: tuple[int, ...],
) -> _Atoms:
    return _Atoms(
        cell=_Cell(np.asarray(cell_columns, dtype=float).T.copy()),
        numbers=np.asarray(numbers, dtype=int),
    )


def current_bulk_payload() -> dict[str, Any]:
    """Return one fresh exact-current structure-backed bulk payload."""

    cell_input_columns = np.diag([4.0, 4.0, 4.0])
    conventional_to_primitive = np.array(
        [
            [0.0, 0.5, 0.5],
            [0.5, 0.0, 0.5],
            [0.5, 0.5, 0.0],
        ]
    )
    submitted = _atoms(cell_input_columns, (13, 13, 13, 13))
    conventional = _atoms(cell_input_columns, (13, 13, 13, 13))
    primitive = _atoms(cell_input_columns @ conventional_to_primitive, (13,))
    dataset = {
        "transformation_matrix": np.eye(3),
        "origin_shift": [0.0, 0.0, 0.0],
        "std_rotation_matrix": np.eye(3),
        "number": 225,
        "international": "Fm-3m",
        "hall_number": 523,
        "hall": "-F 4 2 3",
        "choice": "",
        "equivalent_atoms": [0, 0, 0, 0],
        "crystallographic_orbits": [0, 0, 0, 0],
        "mapping_to_primitive": [0, 0, 0, 0],
        "std_mapping_to_primitive": [0, 0, 0, 0],
    }
    stamp_bulk_canonicalization_transforms(
        atoms_input=submitted,
        atoms_conventional=conventional,
        atoms_primitive=primitive,
        symprec=1e-5,
        no_idealize=False,
        dataset=dataset,
        angle_tolerance=-1.0,
        spglib_version="test-2.7.0",
    )
    record = get_bulk_canonicalization_transforms(conventional)
    assert record is not None
    key = CALM_BULK_CANONICALIZATION_TRANSFORMS_INFO_KEY
    provenance_json = conventional.info[key]

    return {
        "atoms": current_atoms_payload(
            numbers=submitted.numbers.tolist(),
            cell=submitted.cell.array.tolist(),
        ),
        "atoms_conventional": current_atoms_payload(
            numbers=conventional.numbers.tolist(),
            cell=conventional.cell.array.tolist(),
            info={key: provenance_json},
        ),
        "atoms_primitive": current_atoms_payload(
            numbers=primitive.numbers.tolist(),
            cell=primitive.cell.array.tolist(),
            info={key: provenance_json},
        ),
        "fingerprint": {"fixture": "fcc-al"},
        "derived": {
            "formula": "Al",
            "n_atoms": 4,
            "spacegroup": {"international": "Fm-3m", "number": 225},
        },
        "characterization": {},
        "meta": {},
        "standardization": {
            "symprec": record.symprec,
            "no_idealize": record.no_idealize,
            "angle_tolerance": record.angle_tolerance,
            "spglib_version": record.spglib_version,
            "spacegroup": {"international": "Fm-3m", "number": 225},
            "formula": "Al",
            "provenance_info_key": key,
            "provenance": record.to_dict(),
        },
    }
