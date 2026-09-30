from __future__ import annotations

from dataclasses import dataclass, replace
from types import SimpleNamespace

import numpy as np
import pytest

import calm.interface.matching._orchestrator as coupled
import calm.interface.matching._surface_symmetry as surface_symmetry
import calm.interface.pipeline as pipeline
from calm.interface.config import InterfaceBuildConfig
from calm.interface.model import SupercellRecipe2D
from calm.interface.results import StrainState
from calm.math2d.paired_lattice import determinantal_divisor_rank2
from reference.coupled_match_reference import (
    FULL_SQUARE_GROUP,
    IDENTITY_PAIR_KEY_FULL,
    SIGMA5_PAIR_KEY_FULL,
)


@dataclass(frozen=True)
class _Cell:
    array: np.ndarray


@dataclass(frozen=True)
class _AtomsLike:
    cell: _Cell


@dataclass(frozen=True)
class _Slab:
    atoms: _AtomsLike
    hkl: tuple[int, int, int] = (0, 0, 1)
    n_atoms: int = 1


class _BuiltAtoms:
    def __init__(self) -> None:
        self.info: dict[str, object] = {}


def _square_slab() -> _Slab:
    return _Slab(atoms=_AtomsLike(cell=_Cell(np.diag([1.0, 1.0, 10.0]))))


def _square_group() -> tuple[np.ndarray, ...]:
    return tuple(
        np.asarray(operation, dtype=int).reshape(2, 2)
        for operation in FULL_SQUARE_GROUP
    )


@pytest.fixture
def index5_classes(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[_Slab, dict[tuple[int, ...], object]]:
    operations = _square_group()
    monkeypatch.setattr(
        surface_symmetry,
        "resolve_surface_pointgroup_2d",
        lambda *_args, **_kwargs: SimpleNamespace(operations=operations),
    )
    monkeypatch.setattr(
        coupled,
        "compute_valid_hnf_index_pairs",
        lambda *_args, **_kwargs: np.array([[5, 5]], dtype=int),
    )
    slab = _square_slab()
    classes = coupled.enumerate_coupled_match_classes_core(
        slab,
        slab,
        k_max=5,
        cond_max=1.0e9,
        w_match=1.0,
        eps_principal_max=1.0e-10,
        N_at_max=100_000,
        surface_metric_tolerance=1.0e-10,
        pair_symmetry_policy="full",
        correspondence_orientation="proper",
        correspondence_entry_limit=100,
    )
    return slab, {match_class.pair_key: match_class for match_class in classes}


def test_supercell_recipe_requires_exact_index_and_explicit_reflection() -> None:
    identity = np.eye(2, dtype=int)
    with pytest.raises(ValueError, match=r"abs\(det\(N_tot\)\)"):
        SupercellRecipe2D(
            k=2,
            N_tot=identity,
            R_sup=np.eye(2),
            hnf_key_pg=(1, 0, 0, 1),
            cond=1.0,
        )

    reflection = np.diag([-1.0, 1.0])
    with pytest.raises(ValueError, match="cannot contain a reflection"):
        SupercellRecipe2D(
            k=1,
            N_tot=np.diag([-1, 1]),
            R_sup=reflection,
            hnf_key_pg=(-1, 0, 0, 1),
            cond=1.0,
        )

    recipe = SupercellRecipe2D(
        k=1,
        N_tot=np.diag([-1, 1]),
        R_sup=reflection,
        hnf_key_pg=(-1, 0, 0, 1),
        cond=1.0,
        gauge_orientation="reflection_allowed",
    )
    assert recipe.gauge_orientation == "reflection_allowed"

    legacy_left_handed = SupercellRecipe2D(
        k=1,
        N_tot=identity,
        R_sup=reflection,
        hnf_key_pg=(1, 0, 0, 1),
        cond=1.0,
        gauge_orientation="reflection_allowed",
    )
    assert legacy_left_handed.gauge_orientation == "reflection_allowed"


def test_common_build_gauge_reflects_only_an_orientation_reversed_side() -> None:
    primitive = np.vstack([np.eye(2, dtype=int), np.diag([-1, 1])])
    build, right, rotation_a, rotation_b = coupled._common_right_build(
        primitive,
        basis_a=np.eye(2),
        basis_b=np.eye(2),
    )

    assert round(np.linalg.det(right)) == 1
    assert np.array_equal(primitive @ right, build)
    assert round(np.linalg.det(rotation_a)) == 1
    assert round(np.linalg.det(rotation_b)) == -1
    assert np.linalg.det(rotation_a @ build[:2, :]) > 0.0
    assert np.linalg.det(rotation_b @ build[2:, :]) > 0.0

def test_repeated_source_projects_to_smaller_primitive_prototype(
    index5_classes: tuple[_Slab, dict[tuple[int, ...], object]],
) -> None:
    slab, classes = index5_classes
    match_class = classes[IDENTITY_PAIR_KEY_FULL]
    prototype = pipeline._prototype_from_primitive_match_class(
        match_class,
        prototype_uid="prototype:identity",
        slab_a=slab,
        slab_b=slab,
        slab_a_uid="slab:a",
        slab_b_uid="slab:b",
    )

    assert prototype.pair_identity is not None
    assert prototype.source_provenance is not None
    assert prototype.pair_identity.primitive_pair_key == IDENTITY_PAIR_KEY_FULL
    assert prototype.supercell_a.k == 1
    assert prototype.supercell_b.k == 1
    assert prototype.n_atoms_interface == 2
    assert prototype.source_provenance.minimum_source_indices == (5, 5)
    assert prototype.source_provenance.repeat_indices == (5,)

    build_pair = np.vstack(
        [prototype.supercell_a.N_tot, prototype.supercell_b.N_tot]
    )
    assert determinantal_divisor_rank2(build_pair) == 1
    assert np.array_equal(
        build_pair
        @ prototype.source_provenance.representative_source_right_factor,
        prototype.source_provenance.representative_source_pair_matrix,
    )
    assert abs(
        round(
            np.linalg.det(
                prototype.source_provenance.representative_source_right_factor
            )
        )
    ) == 5
    assert round(np.linalg.det(prototype.supercell_a.R_sup)) == 1
    assert round(np.linalg.det(prototype.supercell_b.R_sup)) == 1

    payload = prototype.to_dict()
    assert payload["pair_identity"]["primitive_pair_key"] == list(
        IDENTITY_PAIR_KEY_FULL
    )
    assert payload["source_provenance"]["repeat_indices"] == [5]


def test_coupled_prototype_validates_complete_physical_handedness(
    index5_classes: tuple[_Slab, dict[tuple[int, ...], object]],
) -> None:
    slab, classes = index5_classes
    prototype = pipeline._prototype_from_primitive_match_class(
        classes[IDENTITY_PAIR_KEY_FULL],
        prototype_uid="prototype:identity",
        slab_a=slab,
        slab_b=slab,
        slab_a_uid="slab:a",
        slab_b_uid="slab:b",
    )
    reflected_recipe = SupercellRecipe2D(
        k=1,
        N_tot=np.eye(2, dtype=int),
        R_sup=np.diag([-1.0, 1.0]),
        hnf_key_pg=(1, 0, 0, 1),
        cond=1.0,
        gauge_orientation="reflection_allowed",
    )

    with pytest.raises(
        ValueError, match="Coupled-v2 side-A recipe must produce a right-handed"
    ):
        replace(prototype, supercell_a=reflected_recipe)

    left_handed_parent = _Slab(
        atoms=_AtomsLike(cell=_Cell(np.diag([-1.0, 1.0, 10.0])))
    )
    corrected = replace(
        prototype,
        slab_a=left_handed_parent,
        supercell_a=reflected_recipe,
    )
    assert corrected.supercell_a.gauge_orientation == "reflection_allowed"


def test_sigma5_projection_retains_primitive_five_by_five_relation(
    index5_classes: tuple[_Slab, dict[tuple[int, ...], object]],
) -> None:
    slab, classes = index5_classes
    match_class = classes[SIGMA5_PAIR_KEY_FULL]
    prototype = pipeline._prototype_from_primitive_match_class(
        match_class,
        prototype_uid="prototype:sigma5",
        slab_a=slab,
        slab_b=slab,
        slab_a_uid="slab:a",
        slab_b_uid="slab:b",
    )

    assert prototype.pair_identity is not None
    assert prototype.pair_identity.primitive_pair_key == SIGMA5_PAIR_KEY_FULL
    assert prototype.supercell_a.k == 5
    assert prototype.supercell_b.k == 5
    assert prototype.n_atoms_interface == 10
    assert prototype.source_provenance is not None
    assert prototype.source_provenance.repeat_indices == (1,)
    assert prototype.d_cell == pytest.approx(
        match_class.representative.ai_strain.d_cell
    )
    assert prototype.rel_da == pytest.approx(
        match_class.representative.zm_strain.rel_da
    )


def test_build_interface_uses_primitive_maps_and_stamps_pair_policy(
    monkeypatch: pytest.MonkeyPatch,
    index5_classes: tuple[_Slab, dict[tuple[int, ...], object]],
) -> None:
    slab, classes = index5_classes
    prototype = pipeline._prototype_from_primitive_match_class(
        classes[IDENTITY_PAIR_KEY_FULL],
        prototype_uid="prototype:identity",
        slab_a=slab,
        slab_b=slab,
        slab_a_uid="slab:a",
        slab_b_uid="slab:b",
    )
    captured: dict[str, object] = {}

    deformation = SimpleNamespace(
        F_construction=np.eye(3),
        F_interface=np.eye(3),
        F_total=np.eye(3),
    )
    deformation_accounting = SimpleNamespace(
        policy="composed_slab_deformation",
        version=1,
        lower=deformation,
        upper=deformation,
    )

    def fake_build_interface_atoms(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            atoms=_BuiltAtoms(),
            lower_indices=np.array([0], dtype=int),
            upper_indices=np.array([1], dtype=int),
            deformation_accounting=deformation_accounting,
        )

    monkeypatch.setattr(pipeline, "build_interface_atoms", fake_build_interface_atoms)
    strain = StrainState(
        prototype_uid=prototype.prototype_uid,
        strain_model_uid="strain:model",
        F_tot=np.eye(3),
        F_A=np.eye(3),
        F_B=np.eye(3),
        E_A_rms=0.0,
        E_B_rms=0.0,
    )
    interface = pipeline.build_interface(
        prototype,
        strain,
        InterfaceBuildConfig(translation_frac=(0.25, 0.5)),
    )

    assert abs(round(np.linalg.det(np.asarray(captured["N_A3"])[:2, :2]))) == 1
    assert abs(round(np.linalg.det(np.asarray(captured["N_B3"])[:2, :2]))) == 1
    assert interface.atoms.info["calm:primitive_pair_key"] == IDENTITY_PAIR_KEY_FULL
    assert interface.atoms.info["calm:pair_key_version"] == 1
    assert interface.atoms.info["calm:pair_symmetry_policy"] == "full"
    assert interface.atoms.info["calm:correspondence_orientation"] == "proper"
    assert interface.atoms.info["calm:material_exchange_identified"] is False
    accounting = interface.atoms.info["calm:slab_deformation_accounting"]
    assert accounting["policy"] == "composed_slab_deformation"
    assert accounting["version"] == 1
    assert accounting["lower"]["F_total_slab"] == np.eye(3).tolist()



def test_primitive_projection_generates_coupled_uid_when_omitted(
    index5_classes: tuple[_Slab, dict[tuple[int, ...], object]],
) -> None:
    slab, classes = index5_classes
    prototype = pipeline._prototype_from_primitive_match_class(
        classes[IDENTITY_PAIR_KEY_FULL],
        slab_a=slab,
        slab_b=slab,
        slab_a_uid="slab:a",
        slab_b_uid="slab:b",
    )

    assert prototype.prototype_uid.startswith("proto:v3:")
    assert prototype.pair_identity is not None


def test_coupled_matcher_repairs_left_handed_parent_basis_physically() -> None:
    slab = _Slab(
        atoms=_AtomsLike(cell=_Cell(np.diag([-1.0, 1.0, 10.0])))
    )
    identity_group = (np.eye(2, dtype=int),)
    classes = coupled.enumerate_coupled_match_classes_core(
        slab,
        slab,
        k_max=1,
        cond_max=1.0e9,
        w_match=1.0,
        eps_principal_max=1.0e-10,
        N_at_max=100,
        surface_symmetry_mode="identity_only",
        surface_metric_tolerance=1.0e-10,
        pair_symmetry_policy="proper",
        correspondence_orientation="proper",
        correspondence_entry_limit=10,
        point_group_A=identity_group,
        point_group_B=identity_group,
    )

    assert classes
    parent_basis = slab.atoms.cell.array[:2, :2].T
    for match_class in classes:
        candidate = match_class.representative
        assert np.linalg.det(
            candidate.build_R_A @ parent_basis @ candidate.build_N_A
        ) > 0.0
        assert np.linalg.det(
            candidate.build_R_B @ parent_basis @ candidate.build_N_B
        ) > 0.0

    prototype = pipeline._prototype_from_primitive_match_class(
        classes[0],
        prototype_uid="prototype:left-handed-parent",
        slab_a=slab,
        slab_b=slab,
        slab_a_uid="slab:a",
        slab_b_uid="slab:b",
    )
    assert prototype.pair_identity is not None
