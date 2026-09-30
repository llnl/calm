"""Dependency-light contracts for oriented and interface-ready slab cells."""

from __future__ import annotations

import numpy as np
import pytest

from calm.slab.oriented.cell_contract import (
    INTERFACE_DEFORMATION_ACCOUNTING_INFO_KEY,
    INTERFACE_READY_SLAB_CELL_POLICY,
    INTERFACE_READY_SLAB_CELL_POLICY_VERSION,
    INTERFACE_RELAXATION_DEFORMATION_INFO_KEY,
    canonical_interface_deformation_accounting,
    assess_oriented_surface_cell,
    compose_slab_deformations,
    interface_deformation_diagnostics,
    record_interface_relaxation_deformation,
    require_interface_ready_slab_cell,
    require_interface_stackable_slab,
    validate_interface_deformation_provenance,
    validate_persisted_interface_deformation_payload,
)
from calm.slab.oriented.transforms import ORIENTED_SLAB_TRANSFORMS_INFO_KEY
from oriented_slab_fixtures import current_compact_transforms


def test_skew_inplane_cell_is_interface_ready_when_c_is_vertical() -> None:
    cell = np.array(
        [
            [3.1, 0.0, 0.0],
            [1.2, 2.7, 0.0],
            [0.0, 0.0, 18.0],
        ]
    )

    assessment = require_interface_ready_slab_cell(cell)

    assert assessment.interface_ready is True
    assert assessment.signed_inplane_area > 0.0
    assert assessment.signed_volume > 0.0
    assert assessment.c_inplane_norm == pytest.approx(0.0)
    assert INTERFACE_READY_SLAB_CELL_POLICY == "interface_ready_slab_cell"
    assert INTERFACE_READY_SLAB_CELL_POLICY_VERSION == 1


def test_periodic_stacking_translation_is_allowed_only_for_precursor_contract() -> None:
    cell = np.array(
        [
            [3.0, 0.0, 0.0],
            [-1.5, 2.598076211353316, 0.0],
            [-1.0, 0.5, 8.0],
        ]
    )

    assessment = assess_oriented_surface_cell(cell)
    assert assessment.interface_ready is False
    assert assessment.c_inplane_norm > 0.0

    with pytest.raises(ValueError, match="not interface-ready"):
        require_interface_ready_slab_cell(cell)


def test_interface_ready_contract_rejects_left_handed_or_misoriented_cells() -> None:
    with pytest.raises(ValueError, match="right-handed and nonsingular"):
        require_interface_ready_slab_cell(
            [[2.0, 0.0, 0.0], [0.0, -3.0, 0.0], [0.0, 0.0, 4.0]]
        )

    with pytest.raises(ValueError, match="must lie in the global xy plane"):
        require_interface_ready_slab_cell(
            [[2.0, 0.0, 0.1], [0.0, 3.0, 0.0], [0.0, 0.0, 4.0]]
        )


def test_cell_contract_is_scale_invariant() -> None:
    cell = np.array(
        [
            [2.0, 0.0, 0.0],
            [0.7, 1.8, 0.0],
            [0.0, 0.0, 5.0],
        ]
    )

    reference = require_interface_ready_slab_cell(cell)
    for scale in (1.0e-150, 1.0e150):
        scaled = require_interface_ready_slab_cell(scale * cell)
        assert scaled.interface_ready is True
        assert scaled.c_tilt_ratio == pytest.approx(reference.c_tilt_ratio)


class _Cell:
    def __init__(self, array):
        self.array = np.asarray(array, dtype=float)


class _AtomsLike:
    def __init__(self, cell, payload):
        self.cell = _Cell(cell)
        self.info = {ORIENTED_SLAB_TRANSFORMS_INFO_KEY: payload}


def test_interface_stackable_contract_admits_recorded_construction_deformation(
) -> None:
    cell = np.diag([2.0, 3.0, 8.0])
    payload = current_compact_transforms(interface_ready=True)
    F_construction = np.array(
        [
            [1.0, 0.0, -0.25],
            [0.0, 1.0, 0.125],
            [0.0, 0.0, 1.0],
        ]
    )
    payload["shear_info"] = {
        "F_shear_cart": F_construction.tolist(),
        "c_xy_norm_before": 1.0,
        "c_xy_norm_after": 0.0,
    }
    atoms = _AtomsLike(cell, payload)

    assert require_interface_stackable_slab(atoms).interface_ready

    gauge = np.array(
        [[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]]
    )
    F_interface = np.diag([1.02, 0.98, 1.0])
    composition = compose_slab_deformations(
        atoms,
        F_interface,
        gauge_rotation=gauge,
    )
    expected_construction = gauge @ F_construction @ gauge.T
    assert np.allclose(composition.F_construction, expected_construction)
    assert np.allclose(
        composition.F_total,
        F_interface @ expected_construction,
    )


def test_strained_bulk_reference_composes_construction_shear() -> None:
    from calm.interface.energy.reference import _strained_bulk_deformation

    cell = np.diag([2.0, 3.0, 8.0])
    payload = current_compact_transforms(interface_ready=True)
    F_construction = np.array(
        [
            [1.0, 0.0, -0.25],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ]
    )
    payload["shear_info"] = {
        "F_shear_cart": F_construction.tolist(),
        "c_xy_norm_before": 0.5,
        "c_xy_norm_after": 0.0,
    }
    payload["M_conv_to_slab_cart"] = F_construction.tolist()
    payload["M_slab_to_conv_cart"] = np.linalg.inv(F_construction).tolist()
    slab = type("SlabLike", (), {"atoms": _AtomsLike(cell, payload)})()
    F_interface = np.diag([1.03, 0.97, 1.0])

    deformation = _strained_bulk_deformation(
        slab,
        None,
        F_interface,
    )

    assert np.allclose(deformation.F_construction_slab, F_construction)
    assert np.allclose(
        deformation.F_total_slab,
        F_interface @ F_construction,
    )
    assert np.allclose(deformation.F_total_conv, deformation.F_total_slab)


def test_strained_bulk_composition_respects_slab_and_matching_gauges() -> None:
    from calm.interface.energy.reference import _strained_bulk_deformation

    cell = np.diag([2.0, 3.0, 8.0])
    R_conv_to_slab = np.array(
        [[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]]
    )
    gauge = np.array(
        [[0.0, 1.0, 0.0], [-1.0, 0.0, 0.0], [0.0, 0.0, 1.0]]
    )
    F_construction = np.array(
        [[1.0, 0.0, -0.2], [0.0, 1.0, 0.1], [0.0, 0.0, 1.0]]
    )
    F_interface = np.array(
        [[1.02, 0.03, 0.0], [0.0, 0.98, 0.0], [0.0, 0.0, 1.0]]
    )
    payload = current_compact_transforms(interface_ready=True)
    payload["R_conv_to_slab"] = R_conv_to_slab.tolist()
    payload["R_slab_to_conv"] = R_conv_to_slab.T.tolist()
    payload["shear_info"] = {
        "F_shear_cart": F_construction.tolist(),
        "c_xy_norm_before": 0.5,
        "c_xy_norm_after": 0.0,
    }
    payload["M_conv_to_slab_cart"] = (
        F_construction @ R_conv_to_slab
    ).tolist()
    payload["M_slab_to_conv_cart"] = (
        R_conv_to_slab.T @ np.linalg.inv(F_construction)
    ).tolist()
    slab = type("SlabLike", (), {"atoms": _AtomsLike(cell, payload)})()

    deformation = _strained_bulk_deformation(
        slab,
        None,
        F_interface,
        gauge_rotation=gauge,
    )

    expected_construction_slab = gauge @ F_construction @ gauge.T
    expected_total_slab = F_interface @ expected_construction_slab
    expected_Q = R_conv_to_slab.T @ gauge.T
    assert np.allclose(
        deformation.F_construction_slab,
        expected_construction_slab,
    )
    assert np.allclose(deformation.F_total_slab, expected_total_slab)
    assert np.allclose(
        deformation.F_total_conv,
        expected_Q @ expected_total_slab @ expected_Q.T,
    )


def test_strained_bulk_requires_exact_maps_for_construction_shear() -> None:
    from calm.interface.energy.reference import _strained_bulk_deformation

    cell = np.diag([2.0, 3.0, 8.0])
    payload = current_compact_transforms(interface_ready=True)
    payload["shear_info"] = {
        "F_shear_cart": [
            [1.0, 0.0, -0.2],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ],
        "c_xy_norm_before": 0.5,
        "c_xy_norm_after": 0.0,
    }
    payload.pop("M_conv_to_slab_cart")
    payload.pop("M_slab_to_conv_cart")
    slab = type("SlabLike", (), {"atoms": _AtomsLike(cell, payload)})()

    with pytest.raises(ValueError, match="requires both Cartesian maps"):
        _strained_bulk_deformation(slab, None, np.eye(3))


def test_strained_bulk_rejects_inconsistent_transform_provenance() -> None:
    from calm.interface.energy.reference import _strained_bulk_deformation

    cell = np.diag([2.0, 3.0, 8.0])
    payload = current_compact_transforms(interface_ready=True)
    F_construction = np.array(
        [[1.0, 0.0, -0.2], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    )
    payload["shear_info"] = {
        "F_shear_cart": F_construction.tolist(),
        "c_xy_norm_before": 0.5,
        "c_xy_norm_after": 0.0,
    }
    slab = type("SlabLike", (), {"atoms": _AtomsLike(cell, payload)})()

    with pytest.raises(ValueError, match="M_conv_to_slab_cart is inconsistent"):
        _strained_bulk_deformation(slab, None, np.eye(3))

class _BulkCell:
    def __init__(self, cell):
        self.cell = _Cell(cell)

    def copy(self):
        return _BulkCell(self.cell.array.copy())

    def set_cell(self, cell, scale_atoms=False):
        assert scale_atoms is True
        self.cell = _Cell(cell)


def test_get_strained_bulk_applies_total_deformation_to_pristine_bulk() -> None:
    from calm.interface.energy.reference import get_strained_bulk

    source_cell = np.diag([2.0, 3.0, 8.0])
    pristine_cell_columns = np.diag([4.0, 5.0, 6.0])
    payload = current_compact_transforms(interface_ready=True)
    F_construction = np.array(
        [[1.0, 0.0, -0.2], [0.0, 1.0, 0.1], [0.0, 0.0, 1.0]]
    )
    payload["shear_info"] = {
        "F_shear_cart": F_construction.tolist(),
        "c_xy_norm_before": 0.5,
        "c_xy_norm_after": 0.0,
    }
    payload["M_conv_to_slab_cart"] = F_construction.tolist()
    payload["M_slab_to_conv_cart"] = np.linalg.inv(F_construction).tolist()
    atoms = _AtomsLike(source_cell, payload)
    bulk = type(
        "BulkLike",
        (),
        {
            "conv": _BulkCell(pristine_cell_columns.T),
            "conv_cell": pristine_cell_columns,
        },
    )()
    slab = type("SlabLike", (), {"atoms": atoms, "bulk": bulk})()
    F_interface = np.diag([1.02, 0.98, 1.0])

    strained = get_strained_bulk(slab, None, F_interface)

    expected_total = F_interface @ F_construction
    assert np.allclose(
        strained.cell.array.T,
        expected_total @ pristine_cell_columns,
    )


def _interface_accounting_payload(
    *,
    lower_construction: np.ndarray | None = None,
    lower_interface: np.ndarray | None = None,
    upper_construction: np.ndarray | None = None,
    upper_interface: np.ndarray | None = None,
) -> dict[str, object]:
    lower_source = (
        np.eye(3)
        if lower_construction is None
        else np.asarray(lower_construction, dtype=float)
    )
    lower = (
        np.eye(3)
        if lower_interface is None
        else np.asarray(lower_interface, dtype=float)
    )
    upper_source = (
        np.eye(3)
        if upper_construction is None
        else np.asarray(upper_construction, dtype=float)
    )
    upper = (
        np.eye(3)
        if upper_interface is None
        else np.asarray(upper_interface, dtype=float)
    )
    return {
        "policy": "composed_slab_deformation",
        "version": 1,
        "lower": {
            "F_construction_slab": lower_source.tolist(),
            "F_interface_slab": lower.tolist(),
            "F_total_slab": (lower @ lower_source).tolist(),
        },
        "upper": {
            "F_construction_slab": upper_source.tolist(),
            "F_interface_slab": upper.tolist(),
            "F_total_slab": (upper @ upper_source).tolist(),
        },
    }


def test_interface_deformation_accounting_rejects_tampered_total() -> None:
    payload = _interface_accounting_payload(
        lower_interface=np.diag([1.02, 0.98, 1.0])
    )
    payload["lower"]["F_total_slab"] = np.eye(3).tolist()

    with pytest.raises(ValueError, match="must equal"):
        canonical_interface_deformation_accounting(payload)


def test_fixed_cell_relaxation_preserves_source_accounting() -> None:
    cell = np.diag([2.0, 3.0, 8.0])
    atoms = _AtomsLike(cell, current_compact_transforms(interface_ready=True))
    source = _interface_accounting_payload(
        lower_interface=np.diag([1.02, 0.98, 1.0]),
        upper_interface=np.diag([0.99, 1.01, 1.0]),
    )
    atoms.info[INTERFACE_DEFORMATION_ACCOUNTING_INFO_KEY] = source

    relaxation = record_interface_relaxation_deformation(
        atoms,
        initial_cell=cell,
        final_cell=cell,
        cell_mode="fixed",
    )

    assert atoms.info[INTERFACE_DEFORMATION_ACCOUNTING_INFO_KEY] == source
    assert relaxation is not None
    assert relaxation["cell_mode"] == "fixed"
    assert relaxation["composition_count"] == 1
    assert np.allclose(relaxation["F_relaxation_interface"], np.eye(3))
    assert (
        relaxation["lower"]["F_total_post_relaxation_slab"]
        == source["lower"]["F_total_slab"]
    )
    validate_interface_deformation_provenance(atoms, require_source=True)


def test_interface_cell_relaxation_composes_with_both_source_sides() -> None:
    initial = np.diag([2.0, 3.0, 8.0])
    final = np.array(
        [[2.1, 0.1, 0.0], [0.0, 2.9, 0.0], [0.0, 0.0, 8.0]],
        dtype=float,
    )
    atoms = _AtomsLike(final, current_compact_transforms(interface_ready=True))
    source = _interface_accounting_payload(
        lower_interface=np.diag([1.02, 0.98, 1.0]),
        upper_interface=np.array(
            [[0.99, 0.02, 0.0], [0.0, 1.01, 0.0], [0.0, 0.0, 1.0]]
        ),
    )
    atoms.info[INTERFACE_DEFORMATION_ACCOUNTING_INFO_KEY] = source

    relaxation = record_interface_relaxation_deformation(
        atoms,
        initial_cell=initial,
        final_cell=final,
        cell_mode="interface_in_plane",
    )

    assert relaxation is not None
    expected_relaxation = final.T @ np.linalg.inv(initial.T)
    assert np.allclose(
        relaxation["F_relaxation_interface"], expected_relaxation
    )
    for side in ("lower", "upper"):
        expected = expected_relaxation @ np.asarray(
            source[side]["F_total_slab"], dtype=float
        )
        assert np.allclose(
            relaxation[side]["F_total_post_relaxation_slab"], expected
        )
    validated = validate_interface_deformation_provenance(
        atoms, require_source=True
    )
    assert validated[INTERFACE_RELAXATION_DEFORMATION_INFO_KEY] == relaxation

    persisted = {
        "numbers": [1],
        "cell": final.tolist(),
        "scaled_positions": [[0.0, 0.0, 0.0]],
        "pbc": [True, True, True],
        "info": dict(atoms.info),
    }
    validate_persisted_interface_deformation_payload(
        persisted, require_source=True
    )


def test_interface_deformation_diagnostics_separate_incremental_and_total() -> None:
    cell = np.diag([2.0, 3.0, 8.0])
    lower_construction = np.diag([1.10, 1.0, 1.0])
    lower_matching = np.diag([1.0, 0.90, 1.0])
    upper_matching = np.diag([0.98, 1.02, 1.0])
    source = _interface_accounting_payload(
        lower_construction=lower_construction,
        lower_interface=lower_matching,
        upper_interface=upper_matching,
    )
    info = {INTERFACE_DEFORMATION_ACCOUNTING_INFO_KEY: source}
    strain_state = {
        "F_A": lower_matching.tolist(),
        "F_B": upper_matching.tolist(),
    }

    diagnostics = interface_deformation_diagnostics(
        info,
        current_cell=cell,
        strain_state=strain_state,
    )

    assert diagnostics["deformation_state"] == "pre_relaxation"
    assert diagnostics["lower"]["construction"][
        "max_abs_principal_log_strain"
    ] == pytest.approx(abs(np.log(1.10)))
    assert diagnostics["lower"]["incremental_matching"][
        "max_abs_principal_log_strain"
    ] == pytest.approx(abs(np.log(0.90)))
    expected_total = lower_matching @ lower_construction
    expected_total_max = np.max(np.abs(np.log(np.linalg.svd(expected_total)[1])))
    assert diagnostics["lower"]["current_total"][
        "max_abs_principal_log_strain"
    ] == pytest.approx(expected_total_max)
    assert diagnostics["relaxation_cell"][
        "max_abs_principal_log_strain"
    ] == pytest.approx(0.0)


def test_interface_deformation_diagnostics_use_post_relaxation_total() -> None:
    initial = np.diag([2.0, 3.0, 8.0])
    final = np.diag([2.04, 2.94, 8.0])
    atoms = _AtomsLike(final, current_compact_transforms(interface_ready=True))
    source = _interface_accounting_payload(
        lower_interface=np.diag([1.02, 0.98, 1.0]),
        upper_interface=np.diag([0.99, 1.01, 1.0]),
    )
    atoms.info[INTERFACE_DEFORMATION_ACCOUNTING_INFO_KEY] = source
    record_interface_relaxation_deformation(
        atoms,
        initial_cell=initial,
        final_cell=final,
        cell_mode="interface_in_plane",
    )

    diagnostics = interface_deformation_diagnostics(
        atoms.info,
        current_cell=final,
    )

    relaxation = final.T @ np.linalg.inv(initial.T)
    expected = relaxation @ np.asarray(
        source["lower"]["F_total_slab"], dtype=float
    )
    expected_max = np.max(np.abs(np.log(np.linalg.svd(expected)[1])))
    assert diagnostics["deformation_state"] == "post_relaxation"
    assert diagnostics["lower"]["current_total"][
        "max_abs_principal_log_strain"
    ] == pytest.approx(expected_max)


def test_interface_deformation_diagnostics_reject_mismatched_strain_state() -> None:
    source = _interface_accounting_payload(
        lower_interface=np.diag([1.02, 0.98, 1.0])
    )
    with pytest.raises(ValueError, match="strain_state F_A does not match"):
        interface_deformation_diagnostics(
            {INTERFACE_DEFORMATION_ACCOUNTING_INFO_KEY: source},
            current_cell=np.diag([2.0, 3.0, 8.0]),
            strain_state={
                "F_A": np.eye(3).tolist(),
                "F_B": np.eye(3).tolist(),
            },
        )


def test_repeated_relaxation_composes_cumulative_cell_deformation() -> None:
    initial = np.diag([2.0, 3.0, 8.0])
    intermediate = np.array(
        [[2.1, 0.0, 0.0], [0.05, 2.95, 0.0], [0.0, 0.0, 8.0]]
    )
    final = np.array(
        [[2.05, 0.08, 0.0], [0.02, 3.02, 0.0], [0.0, 0.0, 8.0]]
    )
    atoms = _AtomsLike(intermediate, current_compact_transforms(interface_ready=True))
    atoms.info[INTERFACE_DEFORMATION_ACCOUNTING_INFO_KEY] = (
        _interface_accounting_payload()
    )
    first = record_interface_relaxation_deformation(
        atoms,
        initial_cell=initial,
        final_cell=intermediate,
        cell_mode="interface_in_plane",
    )
    assert first is not None

    atoms.cell = _Cell(final)
    second = record_interface_relaxation_deformation(
        atoms,
        initial_cell=intermediate,
        final_cell=final,
        cell_mode="interface_in_plane",
    )
    assert second is not None
    expected = final.T @ np.linalg.inv(initial.T)
    assert second["composition_count"] == 2
    assert np.allclose(second["F_relaxation_interface"], expected)
    validate_interface_deformation_provenance(atoms, require_source=True)
