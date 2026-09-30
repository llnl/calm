from __future__ import annotations

import numpy as np

from calm.public.projections.slab import normalize_slab_row
from calm.slab.oriented.terminations import _cluster_atoms_by_z
from slab_record_fixtures import (
    current_atoms,
    current_slab_payload,
    current_slab_uid,
    current_termination_identity,
)


class _AtomsLike:
    def __init__(self, *, positions, symbols):
        self._positions = np.asarray(positions, dtype=float)
        self._symbols = list(symbols)

    def get_positions(self):
        return self._positions.copy()

    def get_chemical_symbols(self):
        return list(self._symbols)


def _surface_row(
    *,
    atoms: dict[str, object],
    label: str | None = None,
    top: str | None = None,
    bottom: str | None = None,
) -> dict[str, object]:
    bulk_uid_full = "bulk:test:termination"
    miller = (0, 0, 1)
    identity = None if label is None else current_termination_identity(label)
    payload = current_slab_payload(
        bulk_uid_full=bulk_uid_full,
        miller=miller,
        label=label,
        top=top,
        bottom=bottom,
        identity=identity,
        atoms=atoms,
    )
    return {
        "uid_full": current_slab_uid(
            bulk_uid_full=bulk_uid_full,
            miller=miller,
            payload=payload,
        ),
        "id_short": "s_term",
        "bulk_uid_full": bulk_uid_full,
        "bulk_id_short": "b_term",
        "miller": miller,
        "payload": payload,
    }


def _layered_atoms(numbers: list[int], z_values: list[float]) -> dict[str, object]:
    atoms = current_atoms()
    atoms["numbers"] = list(numbers)
    atoms["cell"] = [
        [4.0, 0.0, 0.0],
        [0.0, 4.0, 0.0],
        [0.0, 0.0, 10.0],
    ]
    atoms["scaled_positions"] = [
        [0.0, 0.0, float(z) / 10.0]
        for z in z_values
    ]
    return atoms


def test_cluster_atoms_by_z_simple_layers():
    atoms = _AtomsLike(
        positions=[[0.0, 0.0, 0.5], [0.0, 0.0, 6.0]],
        symbols=["Li", "O"],
    )

    layers = _cluster_atoms_by_z(atoms, tolerance=0.3)

    assert len(layers) == 2
    assert layers[0].composition.startswith("Li")
    assert layers[1].composition.startswith("O")


def test_current_surface_projection_does_not_infer_termination_from_atoms():
    row = normalize_slab_row(
        _surface_row(atoms=_layered_atoms([3, 8], [0.5, 6.0]))
    )

    assert row["termination"] is None
    assert row["termination_top"] is None
    assert row["termination_bottom"] is None


def test_cluster_atoms_by_z_tolerance_effect():
    atoms = _AtomsLike(
        positions=[
            [0.0, 0.0, 0.0],
            [0.0, 0.0, 0.2],
            [0.0, 0.0, 0.8],
        ],
        symbols=["Li", "Li", "O"],
    )

    layers_small_tol = _cluster_atoms_by_z(atoms, tolerance=0.1)
    assert len(layers_small_tol) == 3

    layers_large_tol = _cluster_atoms_by_z(atoms, tolerance=0.3)
    assert len(layers_large_tol) == 2


def test_current_surface_projection_uses_persisted_termination_labels():
    row = normalize_slab_row(
        _surface_row(
            atoms=_layered_atoms([3, 3, 8], [0.5, 0.5, 6.0]),
            label="O",
            top="O",
            bottom="Li₂",
        )
    )

    assert row["termination"] == "O"
    assert row["termination_top"] == "O"
    assert row["termination_bottom"] == "Li₂"
