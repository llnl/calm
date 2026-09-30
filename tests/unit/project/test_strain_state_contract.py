"""Exact-current interface strain-state persistence contract."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from calm.project.domain.contracts.strain_state import (
    STRAIN_STATE_DEFORMATION_SCOPE,
    STRAIN_STATE_SCHEMA,
    STRAIN_STATE_VERSION,
    canonical_strain_state,
    strain_state_from_current_object,
)


def _hencky_rms(matrix: np.ndarray) -> float:
    singular_values = np.linalg.svd(matrix[:2, :2], compute_uv=False)
    return float(np.sqrt(np.mean(np.log(singular_values) ** 2)))


def _state(**overrides):
    F_A = np.diag([1.1, 1.0, 1.0])
    F_B = np.diag([0.9, 1.0, 1.0])
    F_tot = np.linalg.solve(F_B, F_A)
    values = {
        "schema": STRAIN_STATE_SCHEMA,
        "version": STRAIN_STATE_VERSION,
        "prototype_uid_full": "proto:1",
        "strain_model_uid": "smodel:abc123",
        "strain_alpha": 0.25,
        "deformation_scope": STRAIN_STATE_DEFORMATION_SCOPE,
        "deformation_accounting_policy": "composed_slab_deformation",
        "deformation_accounting_version": 1,
        "F_tot": F_tot.tolist(),
        "F_A": F_A.tolist(),
        "F_B": F_B.tolist(),
        "E_A_rms": _hencky_rms(F_A),
        "E_B_rms": _hencky_rms(F_B),
    }
    values.update(overrides)
    return values


def test_current_strain_state_is_versioned_and_exact() -> None:
    canonical = canonical_strain_state(
        _state(),
        prototype_uid_full="proto:1",
        strain_alpha=0.25,
    )

    assert canonical == _state()
    assert canonical["deformation_scope"] == "incremental_interface_matching"
    assert canonical["F_tot"][0][0] == pytest.approx(1.1 / 0.9)


@pytest.mark.parametrize(
    "override, match",
    [
        ({"schema_version": 1}, "unsupported or historical"),
        ({"alpha": 0.25}, "unsupported or historical"),
        ({"strain_tensor_a": [[1.0] * 3] * 3}, "unsupported or historical"),
        ({"version": 1.0}, "version must be an integer"),
        ({"version": 1}, "Unsupported strain_state version"),
        ({"strain_model_uid": "strain:model"}, "current smodel: UID"),
        ({"deformation_scope": "total"}, "incremental interface matching"),
        ({"deformation_accounting_policy": "other"}, "composed slab-deformation"),
    ],
)
def test_current_strain_state_rejects_historical_or_coercive_forms(
    override,
    match,
) -> None:
    with pytest.raises((TypeError, ValueError), match=match):
        canonical_strain_state(
            _state(**override),
            prototype_uid_full="proto:1",
            strain_alpha=0.25,
        )


def test_current_strain_state_verifies_parent_and_partition() -> None:
    with pytest.raises(ValueError, match="authoritative derived-interface prototype"):
        canonical_strain_state(
            _state(prototype_uid_full="proto:other"),
            prototype_uid_full="proto:1",
            strain_alpha=0.25,
        )

    with pytest.raises(ValueError, match="does not match the derived-interface"):
        canonical_strain_state(
            _state(strain_alpha=0.5),
            prototype_uid_full="proto:1",
            strain_alpha=0.25,
        )



def test_current_strain_state_verifies_incremental_kinematics() -> None:
    with pytest.raises(ValueError, match=r"inverse\(F_B\) @ F_A"):
        canonical_strain_state(
            _state(F_tot=np.eye(3).tolist()),
            prototype_uid_full="proto:1",
            strain_alpha=0.25,
        )

    z_shear = np.eye(3)
    z_shear[0, 2] = 0.1
    with pytest.raises(ValueError, match="unchanged z column"):
        canonical_strain_state(
            _state(F_A=z_shear.tolist()),
            prototype_uid_full="proto:1",
            strain_alpha=0.25,
        )

    with pytest.raises(ValueError, match="E_A_rms is inconsistent"):
        canonical_strain_state(
            _state(E_A_rms=0.0),
            prototype_uid_full="proto:1",
            strain_alpha=0.25,
        )


def test_public_strain_state_declares_incremental_scope() -> None:
    from calm.interface.results import StrainState

    state = StrainState(
        prototype_uid="proto:1",
        strain_model_uid="smodel:abc123",
        F_tot=np.eye(3),
        F_A=np.eye(3),
        F_B=np.eye(3),
        E_A_rms=0.0,
        E_B_rms=0.0,
    )

    assert state.signature()["deformation_scope"] == STRAIN_STATE_DEFORMATION_SCOPE
    assert state.to_dict()["deformation_scope"] == STRAIN_STATE_DEFORMATION_SCOPE

def test_current_kernel_object_converts_at_one_explicit_boundary() -> None:
    current = SimpleNamespace(
        prototype_uid="proto:1",
        strain_model_uid="smodel:abc123",
        F_tot=np.eye(3),
        F_A=np.eye(3),
        F_B=np.eye(3),
        E_A_rms=0.0,
        E_B_rms=0.0,
        raw=SimpleNamespace(alpha=0.25),
    )

    stored = strain_state_from_current_object(
        current,
        prototype_uid_full="proto:1",
        strain_alpha=0.25,
    )

    assert stored["schema"] == STRAIN_STATE_SCHEMA
    assert stored["deformation_scope"] == STRAIN_STATE_DEFORMATION_SCOPE
    assert stored["deformation_accounting_policy"] == "composed_slab_deformation"
    assert stored["F_A"] == np.eye(3).tolist()

    current.raw.alpha = 0.5
    with pytest.raises(ValueError, match="alpha does not match"):
        strain_state_from_current_object(
            current,
            prototype_uid_full="proto:1",
            strain_alpha=0.25,
        )
