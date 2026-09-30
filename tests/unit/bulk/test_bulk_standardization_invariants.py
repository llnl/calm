"""Dependency-light invariants for bulk standardization and identity."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pytest

from calm.structure.standardization import (
    DEFAULT_SPGLIB_ANGLE_TOLERANCE,
    canonical_fractional_species_rows,
    exact_bool,
    exact_integer_matrix3,
    finite_cell_rows,
    positive_finite_float,
    primitive_reduction_check,
    spglib_angle_tolerance,
    standardization_relation,
)
from calm.bulk.provenance import (
    CALM_BULK_CANONICALIZATION_TRANSFORMS_INFO_KEY,
    BulkCanonicalizationTransforms,
    get_bulk_canonicalization_transforms,
    stamp_bulk_canonicalization_transforms,
    validate_bulk_canonicalization_relations,
)


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
    numbers: tuple[int, ...] = (13,),
) -> _Atoms:
    return _Atoms(
        _Cell(np.asarray(cell_columns, dtype=float).T.copy()),
        np.asarray(numbers, dtype=int),
    )


def test_standardization_relation_reconstructs_p_p_and_r_chain() -> None:
    A_input = np.diag([4.0, 5.0, 6.0])
    P = np.array(
        [
            [0.0, 1.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 0.0, -1.0],
        ]
    )
    R = np.array(
        [
            [0.0, -1.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0],
        ]
    )
    P_c = np.array(
        [
            [0.0, 0.5, 0.5],
            [0.5, 0.0, 0.5],
            [0.5, 0.5, 0.0],
        ]
    )
    A_conventional = R @ A_input @ np.linalg.inv(P)
    A_primitive = A_conventional @ P_c

    relation = standardization_relation(
        cell_input_rows=A_input.T,
        cell_conventional_rows=A_conventional.T,
        cell_primitive_rows=A_primitive.T,
        transformation_matrix=P,
        origin_shift=[1.25, -0.5, 0.0],
        rigid_rotation=R,
        no_idealize=False,
        symprec=1e-5,
    )

    assert relation.conventional_verified is True
    assert relation.primitive_verified is True
    assert np.allclose(relation.origin_shift_standardized, [0.25, 0.5, 0.0])
    assert np.allclose(relation.conventional_to_primitive, P_c)


def test_origin_shift_wraps_negative_roundoff_to_zero() -> None:
    cell = np.diag([3.0, 4.0, 5.0])

    relation = standardization_relation(
        cell_input_rows=cell.T,
        cell_conventional_rows=cell.T,
        cell_primitive_rows=cell.T,
        transformation_matrix=np.eye(3),
        origin_shift=[-1e-18, 1.0, 2.25],
        rigid_rotation=np.eye(3),
        no_idealize=False,
        symprec=1e-5,
    )

    assert np.array_equal(
        relation.origin_shift_standardized,
        np.array([0.0, 0.0, 0.25]),
    )
    assert not np.signbit(relation.origin_shift_standardized).any()


def test_no_idealize_uses_change_of_basis_without_dataset_rotation() -> None:
    A_input = np.diag([3.0, 4.0, 5.0])
    P = np.diag([1.0, -1.0, -1.0])
    R = np.array(
        [
            [0.0, -1.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0],
        ]
    )
    A_conventional = A_input @ np.linalg.inv(P)

    relation = standardization_relation(
        cell_input_rows=A_input.T,
        cell_conventional_rows=A_conventional.T,
        cell_primitive_rows=A_conventional.T,
        transformation_matrix=P,
        origin_shift=[0.0, 0.0, 0.0],
        rigid_rotation=R,
        no_idealize=True,
        symprec=1e-5,
    )

    assert relation.conventional_verified is True
    assert np.allclose(relation.rigid_rotation_standardized, R)


def test_current_provenance_roundtrips_verified_relations() -> None:
    A_input = np.diag([4.0, 4.0, 4.0])
    P = np.eye(3)
    R = np.eye(3)
    P_c = np.array(
        [
            [0.0, 0.5, 0.5],
            [0.5, 0.0, 0.5],
            [0.5, 0.5, 0.0],
        ]
    )
    input_atoms = _atoms(A_input, (13, 13, 13, 13))
    conventional = _atoms(A_input, (13, 13, 13, 13))
    primitive = _atoms(A_input @ P_c, (13,))
    dataset = {
        "transformation_matrix": P,
        "origin_shift": [-1e-18, 1.0, 2.25],
        "std_rotation_matrix": R,
        "number": 221,
        "international": "Pm-3m",
        "hall_number": 517,
        "hall": "-P 4 2 3",
        "choice": "",
        "equivalent_atoms": [0, 0, 0, 0],
        "crystallographic_orbits": [0, 0, 0, 0],
        "mapping_to_primitive": [0, 0, 0, 0],
        "std_mapping_to_primitive": [0, 0, 0, 0],
    }

    stamp_bulk_canonicalization_transforms(
        atoms_input=input_atoms,
        atoms_conventional=conventional,
        atoms_primitive=primitive,
        symprec=1e-5,
        no_idealize=False,
        dataset=dataset,
        angle_tolerance=DEFAULT_SPGLIB_ANGLE_TOLERANCE,
        spglib_version="test-2.7.0",
    )

    assert CALM_BULK_CANONICALIZATION_TRANSFORMS_INFO_KEY in conventional.info
    record = get_bulk_canonicalization_transforms(conventional)
    assert record is not None
    assert record.schema_version == 3
    assert record.conventional_relation_verified is True
    assert record.primitive_relation_verified is True
    assert record.spacegroup_number == 221
    assert record.primitive_multiplicity == 4
    assert record.primitive_volume_ratio == pytest.approx(4.0)
    assert record.primitive_composition_verified is True
    assert record.primitive_volume_verified is True
    assert record.angle_tolerance == DEFAULT_SPGLIB_ANGLE_TOLERANCE
    assert record.spglib_version == "test-2.7.0"
    assert np.array_equal(
        record.origin_shift_standardized_frac,
        np.array([0.0, 0.0, 0.25]),
    )
    assert np.allclose(record.conventional_to_primitive_col, P_c)


def test_representation_rows_wrap_round_and_sort_periodic_equivalents() -> None:
    positions_a, species_a = canonical_fractional_species_rows(
        scaled_positions=[[1.0 - 1e-13, -0.0, 0.5], [0.25, 0.25, 0.25]],
        numbers=[29, 13],
        decimals=12,
    )
    positions_b, species_b = canonical_fractional_species_rows(
        scaled_positions=[[0.25, 0.25, 0.25], [0.0, 0.0, 0.5]],
        numbers=[13, 29],
        decimals=12,
    )

    assert np.array_equal(species_a, species_b)
    assert np.array_equal(positions_a, positions_b)
    assert not np.signbit(positions_a).any()


@pytest.mark.parametrize("value", [0.0, -1.0, float("nan"), float("inf")])
def test_symprec_contract_rejects_nonpositive_or_nonfinite_values(value: float) -> None:
    with pytest.raises(ValueError):
        positive_finite_float("symprec", value)


@pytest.mark.parametrize("value", [-1.0, 0.0, 0.25])
def test_angle_tolerance_accepts_heuristic_or_nonnegative_values(
    value: float,
) -> None:
    assert spglib_angle_tolerance(value) == value


@pytest.mark.parametrize("value", [-2.0, float("nan"), float("inf")])
def test_angle_tolerance_rejects_invalid_values(value: float) -> None:
    with pytest.raises(ValueError):
        spglib_angle_tolerance(value)


def test_angle_tolerance_rejects_boolean_values() -> None:
    with pytest.raises(TypeError):
        spglib_angle_tolerance(True)


def test_boolean_contract_rejects_truthy_non_booleans() -> None:
    with pytest.raises(TypeError):
        exact_bool("no_idealize", 1)


def test_cell_contract_rejects_scale_relative_singularity() -> None:
    with pytest.raises(ValueError, match="nonsingular"):
        finite_cell_rows(np.diag([1.0, 1.0, 1e-16]))


def test_present_malformed_provenance_does_not_become_missing() -> None:
    atoms = _atoms(np.eye(3))
    assert get_bulk_canonicalization_transforms(atoms) is None

    key = CALM_BULK_CANONICALIZATION_TRANSFORMS_INFO_KEY
    atoms.info[key] = "not-json"
    with pytest.raises(ValueError, match="invalid JSON"):
        get_bulk_canonicalization_transforms(atoms)


def test_current_provenance_verifier_rejects_detached_persisted_cells() -> None:
    A = np.diag([4.0, 4.0, 4.0])
    P_c = np.array(
        [
            [0.0, 0.5, 0.5],
            [0.5, 0.0, 0.5],
            [0.5, 0.5, 0.0],
        ]
    )
    input_atoms = _atoms(A, (13, 13, 13, 13))
    conventional = _atoms(A, (13, 13, 13, 13))
    primitive = _atoms(A @ P_c, (13,))
    dataset = {
        "transformation_matrix": np.eye(3),
        "origin_shift": [0.0, 0.0, 0.0],
        "std_rotation_matrix": np.eye(3),
    }
    stamp_bulk_canonicalization_transforms(
        atoms_input=input_atoms,
        atoms_conventional=conventional,
        atoms_primitive=primitive,
        symprec=1e-5,
        no_idealize=False,
        dataset=dataset,
    )
    record = get_bulk_canonicalization_transforms(conventional)
    assert record is not None

    validate_bulk_canonicalization_relations(
        cell_input_rows=input_atoms.cell.array,
        cell_conventional_rows=conventional.cell.array,
        cell_primitive_rows=primitive.cell.array,
        numbers_conventional=conventional.numbers,
        numbers_primitive=primitive.numbers,
        record=record,
    )

    detached_primitive = primitive.cell.array.copy()
    detached_primitive[0, 0] += 0.25
    with pytest.raises(ValueError, match="does not reconstruct|does not match"):
        validate_bulk_canonicalization_relations(
            cell_input_rows=input_atoms.cell.array,
            cell_conventional_rows=conventional.cell.array,
            cell_primitive_rows=detached_primitive,
            numbers_conventional=conventional.numbers,
            numbers_primitive=primitive.numbers,
            record=record,
        )


def test_current_parser_rejects_coerced_incomplete_or_noncurrent_fields() -> None:
    A = np.diag([4.0, 4.0, 4.0])
    P_c = np.array(
        [
            [0.0, 0.5, 0.5],
            [0.5, 0.0, 0.5],
            [0.5, 0.5, 0.0],
        ]
    )
    input_atoms = _atoms(A, (13, 13, 13, 13))
    conventional = _atoms(A, (13, 13, 13, 13))
    primitive = _atoms(A @ P_c, (13,))
    dataset = {
        "transformation_matrix": np.eye(3),
        "origin_shift": [0.0, 0.0, 0.0],
        "std_rotation_matrix": np.eye(3),
    }
    stamp_bulk_canonicalization_transforms(
        atoms_input=input_atoms,
        atoms_conventional=conventional,
        atoms_primitive=primitive,
        symprec=1e-5,
        no_idealize=False,
        dataset=dataset,
    )
    record = get_bulk_canonicalization_transforms(conventional)
    assert record is not None
    payload = record.to_dict()

    boundary_shift = dict(payload)
    boundary_shift["origin_shift_standardized_frac"] = [
        -1e-18,
        1.0,
        2.25,
    ]
    restored = BulkCanonicalizationTransforms.from_dict(boundary_shift)
    assert np.array_equal(
        restored.origin_shift_standardized_frac,
        np.array([0.0, 0.0, 0.25]),
    )

    coerced_flag = dict(payload)
    coerced_flag["primitive_volume_verified"] = 1
    with pytest.raises(TypeError, match="Boolean"):
        BulkCanonicalizationTransforms.from_dict(coerced_flag)

    incomplete = dict(payload)
    incomplete.pop("primitive_multiplicity")
    with pytest.raises(ValueError, match="missing required"):
        BulkCanonicalizationTransforms.from_dict(incomplete)

    missing_version = dict(payload)
    missing_version.pop("spglib_version")
    with pytest.raises(ValueError, match="missing required"):
        BulkCanonicalizationTransforms.from_dict(missing_version)

    invalid_angle = dict(payload)
    invalid_angle["angle_tolerance"] = -2.0
    with pytest.raises(ValueError, match="angle_tolerance"):
        BulkCanonicalizationTransforms.from_dict(invalid_angle)

    for noncurrent in (1, 2, 4):
        wrong_version = dict(payload)
        wrong_version["schema_version"] = noncurrent
        with pytest.raises(ValueError, match="unsupported.*schema version"):
            BulkCanonicalizationTransforms.from_dict(wrong_version)

    missing_schema = dict(payload)
    missing_schema.pop("schema_version")
    with pytest.raises(ValueError, match="missing required field"):
        BulkCanonicalizationTransforms.from_dict(missing_schema)

    legacy_fields = {
        "integer_tol",
        "S_input_to_conventional_col",
        "S_input_to_primitive_col",
        "max_abs_err_input_to_conventional",
        "max_abs_err_input_to_primitive",
        "is_integer_input_to_conventional",
        "is_integer_input_to_primitive",
        "det_input_to_conventional",
        "det_input_to_primitive",
    }
    assert legacy_fields.isdisjoint(payload)

    legacy_payload = dict(payload)
    legacy_payload["S_input_to_conventional_col"] = np.eye(3).tolist()
    with pytest.raises(ValueError, match="unsupported fields"):
        BulkCanonicalizationTransforms.from_dict(legacy_payload)


def test_primitive_reduction_check_verifies_multiplicity_and_composition() -> None:
    A_conventional = np.diag([4.0, 4.0, 4.0])
    P_c = np.array(
        [
            [0.0, 0.5, 0.5],
            [0.5, 0.0, 0.5],
            [0.5, 0.5, 0.0],
        ]
    )
    check = primitive_reduction_check(
        cell_conventional_rows=A_conventional.T,
        cell_primitive_rows=(A_conventional @ P_c).T,
        numbers_conventional=[13, 13, 13, 13],
        numbers_primitive=[13],
        symprec=1e-5,
    )

    assert check.multiplicity == 4
    assert check.volume_ratio == pytest.approx(4.0)
    assert check.composition_verified is True
    assert check.volume_verified is True


def test_exact_integer_rotation_rejects_fractional_entries() -> None:
    with pytest.raises(ValueError, match="exact integer"):
        exact_integer_matrix3(
            "rotation",
            np.eye(3) + np.diag([0.25, 0.0, 0.0]),
        )
