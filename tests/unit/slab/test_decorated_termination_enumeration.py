from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from calm.symmetry.surface_group import (
    SurfaceSymmetryProvenance,
    SurfaceSymmetryResolution,
)
from calm.slab.oriented import terminations as enumeration
from calm.slab.oriented.termination_identity import TERMINATION_IDENTITY_VERSION
from calm.slab.oriented.transforms import ORIENTED_SLAB_TRANSFORMS_INFO_KEY
from oriented_slab_fixtures import current_compact_transforms


def _identity_symmetry_resolution() -> SurfaceSymmetryResolution:
    return SurfaceSymmetryResolution(
        operations=(np.eye(2, dtype=int),),
        provenance=SurfaceSymmetryProvenance(
            mode="identity_only",
            status="identity_only",
            operation_count=1,
            symprec=1e-5,
            angle_tolerance=1e-8,
            metric_tolerance=1e-5,
            max_metric_residual=0.0,
            backend=None,
            backend_version=None,
        ),
    )


class _Block:
    def __init__(self, *, cell, positions, symbols):
        self._cell = np.asarray(cell, dtype=float)
        self._positions = np.asarray(positions, dtype=float)
        self._symbols = list(symbols)

    def get_cell(self):
        return self._cell.copy()

    def get_positions(self):
        return self._positions.copy()

    def get_chemical_symbols(self):
        return list(self._symbols)


class _ScaledBlock:
    def __init__(self, scaled_positions):
        self._scaled_positions = np.asarray(scaled_positions, dtype=float)
        self.wrap_calls = 0

    def copy(self):
        return _ScaledBlock(self._scaled_positions.copy())

    def get_scaled_positions(self, *, wrap=False):
        del wrap
        return self._scaled_positions.copy()

    def set_scaled_positions(self, scaled_positions):
        self._scaled_positions = np.asarray(scaled_positions, dtype=float)

    def wrap(self, *, eps):
        del eps
        self.wrap_calls += 1


def test_extracts_abc_stacking_translation_from_tilted_c_vector():
    block = _Block(
        cell=[
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [1.0 / 3.0, 2.0 / 3.0, 1.0],
        ],
        positions=[[0.0, 0.0, 0.0]],
        symbols=["X"],
    )

    layers, period, translation = enumeration._extract_decorated_periodic_layers(
        block,
        layer_tolerance_A=1e-5,
    )

    assert len(layers) == 1
    assert period == 1.0
    np.testing.assert_allclose(translation, [1.0 / 3.0, 2.0 / 3.0])


def test_surface_frame_aligns_normal_with_stacking_vector():
    cell = np.array(
        [
            [2.0, 0.0, 0.0],
            [-1.0, -2.0, 0.0],
            [1.0, 0.5, 3.0],
        ]
    )

    normal, period, translation = enumeration._surface_frame(cell)

    np.testing.assert_allclose(normal, [0.0, 0.0, 1.0])
    assert period == 3.0
    np.testing.assert_allclose(translation, [0.375, -0.25])


def test_periodic_cut_is_scaled_by_finite_repeat_count():
    block = _ScaledBlock([[0.0, 0.0, 0.0], [0.0, 0.0, 0.125]])

    shifted = enumeration._shift_periodic_cut(
        block,
        0.75,
        repeat_count=4,
    )

    np.testing.assert_allclose(
        shifted.get_scaled_positions(),
        [[0.0, 0.0, 0.8125], [0.0, 0.0, 0.9375]],
    )
    assert shifted.wrap_calls == 1


def test_vacuum_insertion_preserves_selected_cleavage_boundary(monkeypatch):
    captured = {}
    sentinel = object()

    def fake_add_vacuum(atoms, vacuum, **kwargs):
        captured.update(kwargs)
        captured["atoms"] = atoms
        captured["vacuum"] = vacuum
        return sentinel, {}

    monkeypatch.setattr(
        "calm.slab.oriented.builder._add_vacuum_along_cartesian_z",
        fake_add_vacuum,
    )
    block = object()

    result = enumeration._add_boundary_vacuum(
        block,
        vacuum=8.0,
        center_slab=True,
    )

    assert result is sentinel
    assert captured["atoms"] is block
    assert captured["vacuum"] == 8.0
    assert captured["unwrap_first"] is False


def test_boundary_vacuum_persists_representation_provenance(monkeypatch):
    provenance = {
        "vacuum_per_side": 8.0,
        "orthogonal_vacuum_axis": True,
        "c_xy_norm_before": 0.75,
        "c_xy_norm_after": 0.0,
    }
    slab = SimpleNamespace(
        info={
            ORIENTED_SLAB_TRANSFORMS_INFO_KEY: current_compact_transforms()
        }
    )

    monkeypatch.setattr(
        "calm.slab.oriented.builder._add_vacuum_along_cartesian_z",
        lambda *args, **kwargs: (slab, provenance),
    )

    result = enumeration._add_boundary_vacuum(
        object(),
        vacuum=8.0,
        center_slab=True,
    )

    assert result is slab
    payload = result.info[ORIENTED_SLAB_TRANSFORMS_INFO_KEY]
    assert payload["vacuum_info"] == provenance


def test_identify_terminations_uses_decorated_motif_not_stoichiometry(
    monkeypatch,
):
    block = _Block(
        cell=np.diag([1.0, 1.0, 2.0]),
        positions=[
            [0.0, 0.0, 0.0],
            [0.5, 0.0, 0.0],
            [0.0, 0.0, 1.0],
            [0.25, 0.25, 1.0],
        ],
        symbols=["X", "X", "X", "X"],
    )
    monkeypatch.setattr(
        "calm.slab.oriented.model.build_oriented_slab",
        lambda *args, **kwargs: SimpleNamespace(block=block),
    )
    monkeypatch.setattr(
        enumeration,
        "_surface_symmetry_operations",
        lambda *args, **kwargs: _identity_symmetry_resolution(),
    )

    candidates = enumeration.identify_unique_terminations(
        SimpleNamespace(symprec=1e-5),
        (0, 0, 1),
        layers=4,
        tolerance=1e-5,
    )

    assert len(candidates) == 2
    assert {item["label"] for item in candidates} == {"X₂"}
    assert all(
        item["termination_identity_version"] == TERMINATION_IDENTITY_VERSION
        for item in candidates
    )
    assert len(
        {item["termination_identity"]["digest"] for item in candidates}
    ) == 2


def test_atom_reordering_does_not_change_identified_classes(monkeypatch):
    cell = np.diag([1.0, 1.0, 2.0])
    first = _Block(
        cell=cell,
        positions=[[0.0, 0.0, 0.0], [0.25, 0.0, 1.0]],
        symbols=["H", "He"],
    )
    second = _Block(
        cell=cell,
        positions=[[0.25, 0.0, 1.0], [0.0, 0.0, 0.0]],
        symbols=["He", "H"],
    )
    current = {"block": first}
    monkeypatch.setattr(
        "calm.slab.oriented.model.build_oriented_slab",
        lambda *args, **kwargs: SimpleNamespace(block=current["block"]),
    )
    monkeypatch.setattr(
        enumeration,
        "_surface_symmetry_operations",
        lambda *args, **kwargs: _identity_symmetry_resolution(),
    )
    bulk = SimpleNamespace(symprec=1e-5)

    ids_first = [
        item["termination_identity"]
        for item in enumeration.identify_unique_terminations(
            bulk,
            (0, 0, 1),
            layers=3,
            tolerance=1e-5,
        )
    ]
    current["block"] = second
    ids_second = [
        item["termination_identity"]
        for item in enumeration.identify_unique_terminations(
            bulk,
            (0, 0, 1),
            layers=3,
            tolerance=1e-5,
        )
    ]

    assert ids_first == ids_second


def test_enumerated_termination_preserves_legacy_triple_unpacking():
    result = enumeration.EnumeratedTermination(
        slab=object(),
        label="A",
        shift=2,
        metadata={"termination_identity_version": 2},
    )

    slab, label, shift = result

    assert slab is result.slab
    assert label == "A"
    assert shift == 2
    assert len(result) == 3
    assert result[0] is result.slab
    assert result[1:] == ("A", 2)
