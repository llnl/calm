from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace

import numpy as np
import pytest

from calm.slab.oriented._thickness import (
    SLAB_TARGET_WIDTH_POLICY,
    SlabThicknessLimitError,
    interplanar_spacing_A,
    plan_target_width_layers,
    target_width_is_satisfied,
)


def test_cubic_interplanar_spacing_and_boundary_inclusion() -> None:
    cell = np.diag([4.0, 4.0, 4.0])
    assert interplanar_spacing_A(cell, (1, 0, 0)) == pytest.approx(4.0)
    assert interplanar_spacing_A(cell, (2, 0, 0)) == pytest.approx(4.0)

    exact = plan_target_width_layers(
        cell,
        (1, 0, 0),
        target_width_A=8.0,
        width_tolerance_A=0.0,
        max_n_layers=3,
    )
    assert exact.policy == SLAB_TARGET_WIDTH_POLICY
    assert exact.required_layers == 3
    assert exact.nominal_plane_span_A == pytest.approx(8.0)

    inside_tolerance = plan_target_width_layers(
        cell,
        (1, 0, 0),
        target_width_A=8.0001,
        width_tolerance_A=0.001,
        max_n_layers=3,
    )
    assert inside_tolerance.required_layers == 3


def test_skewed_row_cell_uses_the_correct_reciprocal_normal() -> None:
    cell = np.array(
        [
            [2.0, 0.0, 0.0],
            [1.0, 3.0, 0.0],
            [0.0, 0.0, 4.0],
        ]
    )
    assert interplanar_spacing_A(cell, (1, 0, 0)) == pytest.approx(
        np.sqrt(18.0 / 5.0)
    )
    assert interplanar_spacing_A(cell, (0, 1, 0)) == pytest.approx(3.0)


def test_target_width_cap_fails_instead_of_silent_undershoot() -> None:
    cell = np.diag([4.0, 4.0, 4.0])
    with pytest.raises(SlabThicknessLimitError, match="requires at least 4 layers"):
        plan_target_width_layers(
            cell,
            (1, 0, 0),
            target_width_A=8.1,
            width_tolerance_A=0.0,
            max_n_layers=3,
        )


def test_measured_atom_span_uses_inclusive_tolerance() -> None:
    assert target_width_is_satisfied(
        7.999,
        target_width_A=8.0,
        width_tolerance_A=0.001,
    )
    assert not target_width_is_satisfied(
        7.998,
        target_width_A=8.0,
        width_tolerance_A=0.001,
    )


def test_project_builder_unpacks_selected_termination_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from calm.project.application.slabs import _build_selected_slab_atoms

    class FakeAtoms:
        def get_positions(self) -> np.ndarray:
            return np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 1.0]])

    fake_atoms = FakeAtoms()
    fake_module = ModuleType("calm.slab.oriented.terminations")

    def fake_build_slab_with_termination(*_args: object, **_kwargs: object):
        return fake_atoms, "selected-label"

    fake_module.build_slab_with_termination = fake_build_slab_with_termination  # type: ignore[attr-defined]
    monkeypatch.setitem(
        sys.modules,
        "calm.slab.oriented.terminations",
        fake_module,
    )

    atoms, label, actual_layers = _build_selected_slab_atoms(
        bulk_obj=SimpleNamespace(),
        miller=(1, 0, 0),
        layers=4,
        vacuum=10.0,
        reduce_inplane=True,
        center_slab=True,
        termination_shift=1,
        termination_metadata={"label": "requested-label"},
        target_width=None,
        width_tolerance=0.0,
        max_n_layers=10,
    )

    assert atoms is fake_atoms
    assert label == "selected-label"
    assert actual_layers == 4


def test_project_builder_measures_selected_slab_and_increments_layers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from calm.project.application.slabs import _build_selected_slab_atoms

    calls: list[int] = []

    class FakeAtoms:
        def __init__(self, layers: int) -> None:
            self._layers = layers

        def get_positions(self) -> np.ndarray:
            # The planner starts at three layers for a 2 A target in a 1 A
            # spacing.  This selected termination has only a 1 A span at that
            # layer count, so the authoritative builder must measure and retry.
            span = float(self._layers - 2)
            return np.array([[0.0, 0.0, 0.0], [0.0, 0.0, span]])

    fake_module = ModuleType("calm.slab.oriented.model")

    def fake_build_oriented_slab(*_args: object, layers: int, **_kwargs: object):
        calls.append(layers)
        return SimpleNamespace(slab=FakeAtoms(layers))

    fake_module.build_oriented_slab = fake_build_oriented_slab  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "calm.slab.oriented.model", fake_module)

    bulk_obj = SimpleNamespace(
        conv=SimpleNamespace(cell=SimpleNamespace(array=np.eye(3)))
    )
    atoms, label, actual_layers = _build_selected_slab_atoms(
        bulk_obj=bulk_obj,
        miller=(1, 0, 0),
        layers=9,
        vacuum=10.0,
        reduce_inplane=True,
        center_slab=True,
        termination_shift=0,
        termination_metadata=None,
        target_width=2.0,
        width_tolerance=0.0,
        max_n_layers=4,
    )

    assert calls == [3, 4]
    assert label == "default"
    assert actual_layers == 4
    assert np.ptp(atoms.get_positions()[:, 2]) == pytest.approx(2.0)


@pytest.mark.parametrize(
    ("kwargs", "error"),
    [
        ({"target_width_A": 0.0}, ValueError),
        ({"width_tolerance_A": -1.0}, ValueError),
        ({"max_n_layers": 0}, ValueError),
        ({"max_n_layers": True}, TypeError),
    ],
)
def test_target_width_controls_are_strict(kwargs: dict[str, object], error: type[Exception]) -> None:
    inputs = {
        "target_width_A": 4.0,
        "width_tolerance_A": 0.0,
        "max_n_layers": 3,
    }
    inputs.update(kwargs)
    with pytest.raises(error):
        plan_target_width_layers(
            np.eye(3),
            (1, 0, 0),
            **inputs,
        )


def test_target_width_policy_is_identity_affecting_only_when_requested() -> None:
    from calm.keys.uid import slab_spec_uid
    from calm.slab.oriented._thickness import (
        SLAB_TARGET_WIDTH_POLICY_VERSION,
        target_width_policy_metadata,
    )

    metadata = target_width_policy_metadata()
    assert metadata["target_width_policy_version"] == SLAB_TARGET_WIDTH_POLICY_VERSION

    ordinary = {"miller": (1, 0, 0), "n_layers": 4, "target_width": None}
    explicit_legacy_shape = dict(ordinary)
    assert slab_spec_uid(ordinary) == slab_spec_uid(explicit_legacy_shape)

    from calm.keys.uid import hash_obj

    target = {"miller": (1, 0, 0), "n_layers": 4, "target_width": 8.0}
    target_with_policy = {**target, **metadata}
    authoritative_uid = slab_spec_uid(target)
    assert authoritative_uid == slab_spec_uid(target_with_policy)
    assert authoritative_uid != slab_spec_uid(ordinary)
    assert authoritative_uid != "sspec:" + hash_obj(target, float_decimals=12)
