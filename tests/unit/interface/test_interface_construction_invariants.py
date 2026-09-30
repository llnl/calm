"""Dependency-light invariants for atomistic interface construction."""

from __future__ import annotations

import sys
import types

import numpy as np
import pytest

from calm.interface.building._kernel import (
    PreparedInterfaceStructure,
    _embed_2x2_in_3x3,
    _validate_inplane_orthogonal_gauge,
    _validate_supercell_matrix,
    build_interface_atoms,
    build_prepared_interface_atoms,
    prepare_interface_atoms,
    quantize_translation_frac,
)
from calm.slab.oriented.transforms import ORIENTED_SLAB_TRANSFORMS_INFO_KEY
from oriented_slab_fixtures import current_compact_transforms


class _Cell:
    def __init__(self, array):
        self.array = np.asarray(array, dtype=float)


class _AtomsLike:
    def __init__(self, positions, cell):
        self.positions = np.asarray(positions, dtype=float)
        self.cell = _Cell(cell)
        self.pbc = (False, False, False)
        self.info = {}

    def copy(self):
        copied = _AtomsLike(self.positions.copy(), self.cell.array.copy())
        copied.pbc = tuple(self.pbc)
        copied.info = dict(self.info)
        return copied

    def __len__(self):
        return int(self.positions.shape[0])

    def set_cell(self, cell, scale_atoms=False):
        assert scale_atoms is False
        self.cell = _Cell(cell)

    def translate(self, vector):
        self.positions = self.positions + np.asarray(vector, dtype=float)

    def get_scaled_positions(self, wrap=False):
        del wrap
        return self.positions @ np.linalg.inv(self.cell.array)

    def set_scaled_positions(self, scaled):
        self.positions = np.asarray(scaled, dtype=float) @ self.cell.array

    def wrap(self):
        raise AssertionError("full 3D wrapping must not be used")

    def __iadd__(self, other):
        self.positions = np.vstack([self.positions, other.positions])
        return self


def _install_fake_ase_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = types.ModuleType("calm.structure.ase_adapter")

    def make_supercell_col(atoms, matrix):
        matrix = np.asarray(matrix, dtype=int)
        determinant = int(round(np.linalg.det(matrix)))
        if abs(determinant) != 1:
            raise AssertionError("fixture supports unimodular supercells only")
        copied = atoms.copy()
        copied.set_cell(matrix.T @ copied.cell.array, scale_atoms=False)
        return copied

    def wrap_xy_clamp_z(atoms, eps=1.0e-8):
        scaled = atoms.get_scaled_positions(wrap=False)
        scaled[:, :2] = np.mod(scaled[:, :2], 1.0)
        scaled[:, 2] = np.clip(scaled[:, 2], 0.0, 1.0 - eps)
        atoms.set_scaled_positions(scaled)

    adapter.make_supercell_col = make_supercell_col
    adapter.wrap_xy_clamp_z = wrap_xy_clamp_z
    monkeypatch.setitem(sys.modules, "calm.structure.ase_adapter", adapter)


def _identity_inputs():
    return {
        "N_A3": np.eye(3, dtype=int),
        "N_B3": np.eye(3, dtype=int),
        "R_A3": np.eye(3),
        "R_B3": np.eye(3),
        "F_A": np.eye(3),
        "F_B": np.eye(3),
    }


def test_prepared_interface_build_matches_one_shot_and_is_mutation_isolated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_ase_adapter(monkeypatch)
    cell = np.array(
        [[2.0, 0.0, 0.0], [0.25, 1.5, 0.0], [0.0, 0.0, 4.0]],
        dtype=float,
    )
    lower = _AtomsLike([[0.1, 0.2, -0.2], [0.4, 0.3, 0.5]], cell)
    upper = _AtomsLike([[0.2, 0.1, -0.1], [0.7, 0.6, 0.4]], cell)
    prepared = prepare_interface_atoms(
        lower,
        upper,
        **_identity_inputs(),
        z_padding=1.25,
        vacuum_padding=2.0,
    )

    for translation in ((0.0, 0.0), (0.25, 0.75), (1.25, -0.25)):
        one_shot = build_interface_atoms(
            lower,
            upper,
            **_identity_inputs(),
            translation_frac=translation,
            z_padding=1.25,
            vacuum_padding=2.0,
        )
        reused = build_prepared_interface_atoms(
            prepared,
            translation_frac=translation,
        )
        assert np.array_equal(reused.atoms.positions, one_shot.atoms.positions)
        assert np.array_equal(reused.atoms.cell.array, one_shot.atoms.cell.array)
        assert np.array_equal(reused.lower_indices, one_shot.lower_indices)
        assert np.array_equal(reused.upper_indices, one_shot.upper_indices)

    first = build_prepared_interface_atoms(
        prepared,
        translation_frac=(0.25, 0.75),
    )
    first.atoms.positions[:] = 999.0
    first.c1[:] = 999.0
    second = build_prepared_interface_atoms(
        prepared,
        translation_frac=(0.25, 0.75),
    )
    assert not np.any(second.atoms.positions == 999.0)
    assert not np.any(second.c1 == 999.0)
    assert prepared.c1.flags.writeable is False
    assert prepared.c2.flags.writeable is False


def test_interface_construction_uses_fractional_torus_and_preserves_z_block(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_ase_adapter(monkeypatch)
    cell = np.diag([2.0, 2.0, 4.0])
    lower = _AtomsLike([[0.0, 0.0, -1.0e-12], [0.0, 0.0, 0.5]], cell)
    upper = _AtomsLike([[0.0, 0.0, -2.0e-12]], cell)

    built = build_interface_atoms(
        lower,
        upper,
        **_identity_inputs(),
        translation_frac=(1.25, -0.75),
        z_padding=1.0,
        vacuum_padding=2.0,
    )

    upper_position = built.atoms.positions[built.upper_indices[0]]
    assert np.allclose(upper_position[:2], [0.5, 0.5])
    assert np.min(built.atoms.positions[:, 2]) >= -1.0e-12
    assert np.max(built.atoms.positions[:, 2]) < built.Lz - 1.0e-6


def test_interface_construction_rejects_mismatched_target_cells(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_ase_adapter(monkeypatch)
    lower = _AtomsLike([[0.0, 0.0, 0.0]], np.diag([2.0, 2.0, 4.0]))
    upper = _AtomsLike([[0.0, 0.0, 0.0]], np.diag([3.0, 2.0, 4.0]))

    with pytest.raises(ValueError, match="do not share one common in-plane basis"):
        build_interface_atoms(
            lower,
            upper,
            **_identity_inputs(),
            translation_frac=(0.0, 0.0),
            z_padding=1.0,
        )


def test_interface_build_requires_right_handed_interface_ready_input_slabs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_ase_adapter(monkeypatch)
    left_handed_cell = np.diag([2.0, -2.0, 4.0])
    lower = _AtomsLike([[0.0, 0.0, 0.0]], left_handed_cell)
    upper = _AtomsLike([[0.0, 0.0, 0.0]], left_handed_cell)
    signed = np.diag([1, -1, 1])

    with pytest.raises(ValueError, match="right-handed and nonsingular"):
        build_interface_atoms(
            lower,
            upper,
            N_A3=signed,
            N_B3=signed,
            R_A3=np.eye(3),
            R_B3=np.eye(3),
            F_A=np.eye(3),
            F_B=np.eye(3),
            translation_frac=(0.0, 0.0),
            z_padding=1.0,
        )

    assert np.array_equal(_validate_supercell_matrix("N", signed), signed)

    singular = np.diag([1, 0, 1])
    with pytest.raises(ValueError, match="nonzero in-plane determinant"):
        _validate_supercell_matrix("N", singular)

    tilted = _AtomsLike(
        [[0.0, 0.0, 0.0]],
        [[2.0, 0.0, 0.0], [0.0, 2.0, 0.0], [0.25, -0.5, 4.0]],
    )
    with pytest.raises(ValueError, match="not interface-ready"):
        build_interface_atoms(
            tilted,
            tilted,
            **_identity_inputs(),
            translation_frac=(0.0, 0.0),
            z_padding=1.0,
        )


def test_interface_build_tracks_composed_source_construction_shear(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_ase_adapter(monkeypatch)
    cell = np.diag([2.0, 2.0, 4.0])
    lower = _AtomsLike([[0.0, 0.0, 0.0]], cell)
    upper = _AtomsLike([[0.0, 0.0, 0.0]], cell)
    F_construction = np.array(
        [
            [1.0, 0.0, -0.125],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ]
    )
    payload = current_compact_transforms(interface_ready=True)
    payload["shear_info"] = {
        "F_shear_cart": F_construction.tolist(),
        "c_xy_norm_before": 0.5,
        "c_xy_norm_after": 0.0,
    }
    lower.info[ORIENTED_SLAB_TRANSFORMS_INFO_KEY] = payload
    F_interface = np.diag([1.02, 1.0, 1.0])

    built = build_interface_atoms(
        lower,
        upper,
        **{**_identity_inputs(), "F_A": F_interface, "F_B": F_interface},
        translation_frac=(0.0, 0.0),
        z_padding=1.0,
    )

    accounting = built.deformation_accounting
    assert accounting is not None
    persisted = built.atoms.info["calm:slab_deformation_accounting"]
    assert persisted["policy"] == "composed_slab_deformation"
    assert np.allclose(
        persisted["lower"]["F_total_slab"],
        F_interface @ F_construction,
    )
    assert accounting.policy == "composed_slab_deformation"
    assert accounting.version == 1
    assert np.allclose(accounting.lower.F_construction, F_construction)
    assert np.allclose(accounting.lower.F_interface, F_interface)
    assert np.allclose(
        accounting.lower.F_total,
        F_interface @ F_construction,
    )
    assert accounting.lower.F_total.flags.writeable is False

def test_prepared_interface_materialization_revalidates_template_cell() -> None:
    tilted = _AtomsLike(
        [[0.0, 0.0, 0.0]],
        [[2.0, 0.0, 0.0], [0.0, 2.0, 0.0], [0.25, 0.0, 4.0]],
    )
    prepared = PreparedInterfaceStructure(
        template_atoms=tilted,
        lower_indices=np.array([0], dtype=int),
        upper_indices=np.array([], dtype=int),
        c1=np.array([2.0, 0.0, 0.0]),
        c2=np.array([0.0, 2.0, 0.0]),
        Lz=4.0,
    )

    with pytest.raises(ValueError, match="not interface-ready"):
        build_prepared_interface_atoms(
            prepared,
            translation_frac=(0.0, 0.0),
        )


def test_reflected_gauge_may_pair_with_signed_supercell(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_ase_adapter(monkeypatch)
    cell = np.diag([2.0, 2.0, 4.0])
    lower = _AtomsLike([[0.0, 0.0, 0.0]], cell)
    upper = _AtomsLike([[0.0, 0.0, 0.0]], cell)
    signed = np.diag([1, -1, 1])
    reflected = np.diag([1.0, -1.0, 1.0])

    built = build_interface_atoms(
        lower,
        upper,
        N_A3=signed,
        N_B3=signed,
        R_A3=reflected,
        R_B3=reflected,
        F_A=np.eye(3),
        F_B=np.eye(3),
        translation_frac=(0.0, 0.0),
        z_padding=1.0,
    )

    assert np.linalg.det(np.vstack([built.c1, built.c2])[:, :2]) > 0.0
    assert np.array_equal(
        _validate_inplane_orthogonal_gauge("R", reflected),
        reflected,
    )


def test_interface_construction_rejects_invalid_discrete_and_cartesian_maps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_ase_adapter(monkeypatch)
    atoms = _AtomsLike([[0.0, 0.0, 0.0]], np.diag([2.0, 2.0, 4.0]))
    inputs = _identity_inputs()

    fractional = dict(inputs)
    fractional["N_A3"] = np.diag([1.5, 1.0, 1.0])
    with pytest.raises(ValueError, match="exact finite integers"):
        build_interface_atoms(
            atoms,
            atoms,
            **fractional,
            translation_frac=(0.0, 0.0),
            z_padding=1.0,
        )

    reflected = dict(inputs)
    reflected["R_A3"] = np.diag([-1.0, 1.0, 1.0])
    with pytest.raises(ValueError, match="right-handed and nonsingular"):
        build_interface_atoms(
            atoms,
            atoms,
            **reflected,
            translation_frac=(0.0, 0.0),
            z_padding=1.0,
        )

    nonorthogonal = dict(inputs)
    nonorthogonal["R_A3"] = np.array(
        [[1.0, 0.1, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    )
    with pytest.raises(ValueError, match="must be orthogonal"):
        build_interface_atoms(
            atoms,
            atoms,
            **nonorthogonal,
            translation_frac=(0.0, 0.0),
            z_padding=1.0,
        )

    coupled = dict(inputs)
    coupled["F_A"] = np.array(
        [[1.0, 0.0, 0.1], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    )
    with pytest.raises(ValueError, match="global Cartesian z axis"):
        build_interface_atoms(
            atoms,
            atoms,
            **coupled,
            translation_frac=(0.0, 0.0),
            z_padding=1.0,
        )


def test_translation_and_embedding_inputs_are_exact_and_finite() -> None:
    with pytest.raises(ValueError, match="finite"):
        quantize_translation_frac((np.nan, 0.0), 8)
    with pytest.raises(ValueError, match="nonnegative integer"):
        quantize_translation_frac((0.0, 0.0), 1.5)
    with pytest.raises(ValueError, match="exact finite integers"):
        _embed_2x2_in_3x3([[1.0, 0.5], [0.0, 1.0]], dtype="int")


def test_internal_build_config_rejects_nonfinite_and_inexact_inputs() -> None:
    from calm.interface.config import InterfaceBuildConfig

    with pytest.raises(ValueError, match="finite and non-negative"):
        InterfaceBuildConfig(z_padding=float("nan"))
    with pytest.raises(ValueError, match="two finite values"):
        InterfaceBuildConfig(translation_frac=(0.0, float("inf")))
    with pytest.raises(TypeError, match="must be an integer"):
        InterfaceBuildConfig(translation_round_decimals=1.5)
    with pytest.raises(ValueError, match="must be non-negative"):
        InterfaceBuildConfig(translation_round_decimals=-1)
