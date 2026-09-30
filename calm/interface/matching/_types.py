"""Internal data objects for coupled-v2 surface enumeration."""

from __future__ import annotations

from dataclasses import dataclass, field
from numbers import Integral, Real
from typing import TYPE_CHECKING, Literal

import numpy as np

from calm.symmetry.surface_group import SurfaceSymmetryProvenance

from calm.interface.matching.audit import CoupledMatchEnumerationAudit

if TYPE_CHECKING:
    from calm.interface.types import AffineInvariantStrain2D, ZMStrain2D


def _matrix_2d(name: str, value: object, *, integer: bool = False) -> np.ndarray:
    """Return one validated finite 2x2 matrix."""

    matrix = np.asarray(value)
    if matrix.shape != (2, 2):
        raise ValueError(f"{name} must have shape (2, 2)")
    if integer:
        if matrix.dtype.kind not in {"i", "u"}:
            raise TypeError(f"{name} must contain exact integers")
        return np.asarray(matrix, dtype=int)
    output = np.asarray(matrix, dtype=float)
    if not np.all(np.isfinite(output)):
        raise ValueError(f"{name} must contain only finite values")
    return output


def _determinant_exact(matrix: np.ndarray) -> int:
    return int(matrix[0, 0]) * int(matrix[1, 1]) - int(matrix[0, 1]) * int(matrix[1, 0])


def _matrix_scale(*matrices: np.ndarray) -> float:
    return max(
        1.0,
        *(float(np.max(np.abs(matrix))) for matrix in matrices),
    )


@dataclass(frozen=True)
class SurfaceCellMember2D:
    """One exact HNF member with separate shape and oriented reductions."""

    k: int
    H: np.ndarray
    shape_basis: np.ndarray
    shape_gram: np.ndarray
    shape_U: np.ndarray
    shape_embedding: np.ndarray
    oriented_basis: np.ndarray
    oriented_gram: np.ndarray
    oriented_N: np.ndarray
    oriented_U: np.ndarray
    oriented_embedding: np.ndarray
    surface_orbit_key: tuple[int, int, int, int]
    condition_number: float

    def __post_init__(self) -> None:
        if isinstance(self.k, (bool, np.bool_)) or not isinstance(self.k, Integral):
            raise TypeError("k must be a positive integer")
        if int(self.k) <= 0:
            raise ValueError("k must be a positive integer")

        H = _matrix_2d("H", self.H, integer=True)
        shape_basis = _matrix_2d("shape_basis", self.shape_basis)
        shape_gram = _matrix_2d("shape_gram", self.shape_gram)
        shape_U = _matrix_2d("shape_U", self.shape_U, integer=True)
        shape_embedding = _matrix_2d("shape_embedding", self.shape_embedding)
        oriented_basis = _matrix_2d("oriented_basis", self.oriented_basis)
        oriented_gram = _matrix_2d("oriented_gram", self.oriented_gram)
        oriented_N = _matrix_2d("oriented_N", self.oriented_N, integer=True)
        oriented_U = _matrix_2d("oriented_U", self.oriented_U, integer=True)
        oriented_embedding = _matrix_2d("oriented_embedding", self.oriented_embedding)

        if abs(_determinant_exact(H)) != int(self.k):
            raise ValueError("abs(det(H)) must equal k")
        if abs(_determinant_exact(shape_U)) != 1:
            raise ValueError("shape_U must be unimodular")
        if _determinant_exact(oriented_U) != 1:
            raise ValueError("oriented_U must have determinant +1")
        if not np.array_equal(oriented_N, H @ oriented_U):
            raise ValueError("oriented_N must equal H @ oriented_U")

        scale = _matrix_scale(
            shape_basis,
            shape_gram,
            oriented_basis,
            oriented_gram,
        )
        atol = 1e-10 * scale
        if not np.allclose(
            shape_gram,
            shape_basis.T @ shape_basis,
            rtol=1e-10,
            atol=atol,
        ):
            raise ValueError("shape_gram must equal shape_basis.T @ shape_basis")
        if not np.allclose(
            oriented_gram,
            oriented_basis.T @ oriented_basis,
            rtol=1e-10,
            atol=atol,
        ):
            raise ValueError(
                "oriented_gram must equal oriented_basis.T @ oriented_basis"
            )
        if not np.allclose(
            shape_embedding.T @ shape_embedding,
            np.eye(2),
            rtol=1e-10,
            atol=1e-10,
        ):
            raise ValueError("shape_embedding must be orthogonal")
        if not np.allclose(
            oriented_embedding.T @ oriented_embedding,
            np.eye(2),
            rtol=1e-10,
            atol=1e-10,
        ) or not np.isclose(
            np.linalg.det(oriented_embedding),
            1.0,
            rtol=1e-10,
            atol=1e-10,
        ):
            raise ValueError("oriented_embedding must be a proper rotation")

        key = tuple(int(value) for value in self.surface_orbit_key)
        if len(key) != 4:
            raise ValueError("surface_orbit_key must contain four integers")
        if isinstance(self.condition_number, (bool, np.bool_)) or not isinstance(
            self.condition_number, Real
        ):
            raise TypeError("condition_number must be a finite positive real")
        condition = float(self.condition_number)
        if not np.isfinite(condition) or condition <= 0.0:
            raise ValueError("condition_number must be finite and positive")

        object.__setattr__(self, "k", int(self.k))
        object.__setattr__(self, "H", H)
        object.__setattr__(self, "shape_basis", shape_basis)
        object.__setattr__(self, "shape_gram", shape_gram)
        object.__setattr__(self, "shape_U", shape_U)
        object.__setattr__(self, "shape_embedding", shape_embedding)
        object.__setattr__(self, "oriented_basis", oriented_basis)
        object.__setattr__(self, "oriented_gram", oriented_gram)
        object.__setattr__(self, "oriented_N", oriented_N)
        object.__setattr__(self, "oriented_U", oriented_U)
        object.__setattr__(self, "oriented_embedding", oriented_embedding)
        object.__setattr__(self, "surface_orbit_key", key)
        object.__setattr__(self, "condition_number", condition)


@dataclass(frozen=True)
class SurfaceCellOrbit2D:
    """One comparison orbit retaining every exact admitted HNF member."""

    key: tuple[int, int, int, int]
    representative: SurfaceCellMember2D
    members: tuple[SurfaceCellMember2D, ...]

    def __post_init__(self) -> None:
        key = tuple(int(value) for value in self.key)
        if len(key) != 4:
            raise ValueError("key must contain four integers")
        members = tuple(self.members)
        if not members:
            raise ValueError("members cannot be empty")
        if any(member.surface_orbit_key != key for member in members):
            raise ValueError("every member must have the orbit key")
        representative_signature = tuple(
            int(value) for value in self.representative.H.ravel()
        )
        member_signatures = {
            tuple(int(value) for value in member.H.ravel()) for member in members
        }
        if representative_signature not in member_signatures:
            raise ValueError("representative must be one of the orbit members")
        object.__setattr__(self, "key", key)
        object.__setattr__(self, "members", members)


@dataclass(frozen=True)
class BasisCorrespondence2D:
    """One exact integer B-side basis map admitted by the strain bound."""

    U_B: np.ndarray
    principal_strains: np.ndarray
    transformed_gram_B: np.ndarray

    def __post_init__(self) -> None:
        transform = _matrix_2d("U_B", self.U_B, integer=True)
        if abs(_determinant_exact(transform)) != 1:
            raise ValueError("U_B must be unimodular")

        strains = np.asarray(self.principal_strains, dtype=float)
        if strains.shape != (2,):
            raise ValueError("principal_strains must have shape (2,)")
        if not np.all(np.isfinite(strains)):
            raise ValueError("principal_strains must contain only finite values")

        transformed = _matrix_2d(
            "transformed_gram_B",
            self.transformed_gram_B,
        )
        scale = float(np.max(np.abs(transformed)))
        if scale <= 0.0:
            raise ValueError("transformed_gram_B must be positive definite")
        if not np.allclose(
            transformed,
            transformed.T,
            rtol=1e-12,
            atol=1e-12 * scale,
        ):
            raise ValueError("transformed_gram_B must be symmetric")
        normalized = transformed / scale
        if float(normalized[0, 0]) <= 0.0 or float(np.linalg.det(normalized)) <= 0.0:
            raise ValueError("transformed_gram_B must be positive definite")

        object.__setattr__(self, "U_B", transform)
        object.__setattr__(self, "principal_strains", strains)
        object.__setattr__(self, "transformed_gram_B", transformed)


@dataclass(frozen=True)
class PairIdentityPolicy2D:
    """Scientific policies defining exact coupled-pair identity."""

    pair_symmetry: Literal["proper", "full"]
    correspondence_orientation: Literal["proper", "all"]
    identify_material_exchange: bool
    key_version: int = 1

    def __post_init__(self) -> None:
        if self.pair_symmetry not in {"proper", "full"}:
            raise ValueError("pair_symmetry must be 'proper' or 'full'")
        if self.correspondence_orientation not in {"proper", "all"}:
            raise ValueError("correspondence_orientation must be 'proper' or 'all'")
        if not isinstance(self.identify_material_exchange, bool):
            raise TypeError("identify_material_exchange must be a bool")
        if isinstance(self.key_version, (bool, np.bool_)) or not isinstance(
            self.key_version, Integral
        ):
            raise TypeError("key_version must be a positive integer")
        if int(self.key_version) <= 0:
            raise ValueError("key_version must be a positive integer")
        object.__setattr__(self, "key_version", int(self.key_version))


@dataclass(frozen=True)
class PairCanonicalization2D:
    """Exact canonical pair key and witnesses for the selected policy."""

    key: tuple[int, ...]
    canonical_matrix: np.ndarray
    point_operation_A: np.ndarray
    point_operation_B: np.ndarray
    common_right_transform: np.ndarray
    pivot_rows: tuple[int, int]
    material_exchange_applied: bool

    def __post_init__(self) -> None:
        key = tuple(int(value) for value in self.key)
        if len(key) != 8:
            raise ValueError("key must contain eight integers")
        canonical = np.asarray(self.canonical_matrix)
        if canonical.shape != (4, 2) or canonical.dtype.kind not in {
            "i",
            "u",
        }:
            raise TypeError("canonical_matrix must be an exact integer 4x2 matrix")
        if tuple(int(value) for value in canonical.ravel()) != key:
            raise ValueError("key must flatten canonical_matrix")
        operation_a = _matrix_2d(
            "point_operation_A", self.point_operation_A, integer=True
        )
        operation_b = _matrix_2d(
            "point_operation_B", self.point_operation_B, integer=True
        )
        right = _matrix_2d(
            "common_right_transform",
            self.common_right_transform,
            integer=True,
        )
        if abs(_determinant_exact(operation_a)) != 1:
            raise ValueError("point_operation_A must be unimodular")
        if abs(_determinant_exact(operation_b)) != 1:
            raise ValueError("point_operation_B must be unimodular")
        if abs(_determinant_exact(right)) != 1:
            raise ValueError("common_right_transform must be unimodular")
        pivot = tuple(int(value) for value in self.pivot_rows)
        if len(pivot) != 2 or not (0 <= pivot[0] < pivot[1] < 4):
            raise ValueError("pivot_rows must select two ordered rows from 0..3")
        if not isinstance(self.material_exchange_applied, bool):
            raise TypeError("material_exchange_applied must be a bool")
        object.__setattr__(self, "key", key)
        object.__setattr__(self, "canonical_matrix", canonical.astype(int))
        object.__setattr__(self, "point_operation_A", operation_a)
        object.__setattr__(self, "point_operation_B", operation_b)
        object.__setattr__(self, "common_right_transform", right)
        object.__setattr__(self, "pivot_rows", pivot)


def _matrix_4x2(name: str, value: object, *, integer: bool = False) -> np.ndarray:
    """Return one validated finite 4x2 matrix."""

    matrix = np.asarray(value)
    if matrix.shape != (4, 2):
        raise ValueError(f"{name} must have shape (4, 2)")
    if integer:
        if matrix.dtype.kind not in {"i", "u"}:
            raise TypeError(f"{name} must contain exact integers")
        return np.asarray(matrix, dtype=int)
    output = np.asarray(matrix, dtype=float)
    if not np.all(np.isfinite(output)):
        raise ValueError(f"{name} must contain only finite values")
    return output


def _positive_integer_value(name: str, value: object) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral):
        raise TypeError(f"{name} must be a positive integer")
    result = int(value)
    if result <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return result


def _finite_nonnegative_value(name: str, value: object) -> float:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        raise TypeError(f"{name} must be a finite nonnegative real")
    result = float(value)
    if not np.isfinite(result) or result < 0.0:
        raise ValueError(f"{name} must be a finite nonnegative real")
    return result


@dataclass(frozen=True)
class SourceMatchProvenance2D:
    """Exact source state and source-to-primitive repetition witness."""

    source_H_A: np.ndarray
    source_H_B: np.ndarray
    source_orbit_key_A: tuple[int, int, int, int]
    source_orbit_key_B: tuple[int, int, int, int]
    source_N_A: np.ndarray
    source_N_B: np.ndarray
    correspondence_U_B: np.ndarray
    source_pair_matrix: np.ndarray
    source_right_factor: np.ndarray
    repeat_index: int
    maximal_minors: tuple[int, ...]

    def __post_init__(self) -> None:
        source_h_a = _matrix_2d("source_H_A", self.source_H_A, integer=True)
        source_h_b = _matrix_2d("source_H_B", self.source_H_B, integer=True)
        orbit_key_a = tuple(int(value) for value in self.source_orbit_key_A)
        orbit_key_b = tuple(int(value) for value in self.source_orbit_key_B)
        if len(orbit_key_a) != 4 or len(orbit_key_b) != 4:
            raise ValueError("source orbit keys must contain four integers")
        source_n_a = _matrix_2d("source_N_A", self.source_N_A, integer=True)
        source_n_b = _matrix_2d("source_N_B", self.source_N_B, integer=True)
        correspondence = _matrix_2d(
            "correspondence_U_B",
            self.correspondence_U_B,
            integer=True,
        )
        source_pair = _matrix_4x2(
            "source_pair_matrix",
            self.source_pair_matrix,
            integer=True,
        )
        right_factor = _matrix_2d(
            "source_right_factor",
            self.source_right_factor,
            integer=True,
        )
        repeat_index = _positive_integer_value("repeat_index", self.repeat_index)
        minors = tuple(int(value) for value in self.maximal_minors)
        if len(minors) != 6:
            raise ValueError("maximal_minors must contain six integers")
        if abs(_determinant_exact(correspondence)) != 1:
            raise ValueError("correspondence_U_B must be unimodular")
        if abs(_determinant_exact(right_factor)) != repeat_index:
            raise ValueError("abs(det(source_right_factor)) must equal repeat_index")
        expected_pair = np.vstack([source_n_a, source_n_b @ correspondence])
        if not np.array_equal(source_pair, expected_pair):
            raise ValueError(
                "source_pair_matrix must stack source_N_A and "
                "source_N_B @ correspondence_U_B"
            )

        object.__setattr__(self, "source_H_A", source_h_a)
        object.__setattr__(self, "source_H_B", source_h_b)
        object.__setattr__(self, "source_orbit_key_A", orbit_key_a)
        object.__setattr__(self, "source_orbit_key_B", orbit_key_b)
        object.__setattr__(self, "source_N_A", source_n_a)
        object.__setattr__(self, "source_N_B", source_n_b)
        object.__setattr__(self, "correspondence_U_B", correspondence)
        object.__setattr__(self, "source_pair_matrix", source_pair)
        object.__setattr__(self, "source_right_factor", right_factor)
        object.__setattr__(self, "repeat_index", repeat_index)
        object.__setattr__(self, "maximal_minors", minors)


@dataclass(frozen=True)
class PrimitiveMatchCandidate2D:
    """One deterministic primitive representative of a coupled match class."""

    primitive_N_A: np.ndarray
    primitive_N_B: np.ndarray
    build_N_A: np.ndarray
    build_N_B: np.ndarray
    build_common_right_transform: np.ndarray
    build_R_A: np.ndarray
    build_R_B: np.ndarray
    pair_canonicalization: PairCanonicalization2D
    pair_identity_policy: PairIdentityPolicy2D
    source_provenance: SourceMatchProvenance2D
    ai_strain: AffineInvariantStrain2D
    zm_strain: ZMStrain2D
    atom_count: int
    d_size: float
    match_score: float
    w_match: float

    def __post_init__(self) -> None:
        from calm.interface.types import AffineInvariantStrain2D, ZMStrain2D

        primitive_a = _matrix_2d("primitive_N_A", self.primitive_N_A, integer=True)
        primitive_b = _matrix_2d("primitive_N_B", self.primitive_N_B, integer=True)
        build_a = _matrix_2d("build_N_A", self.build_N_A, integer=True)
        build_b = _matrix_2d("build_N_B", self.build_N_B, integer=True)
        build_right = _matrix_2d(
            "build_common_right_transform",
            self.build_common_right_transform,
            integer=True,
        )
        build_r_a = _matrix_2d("build_R_A", self.build_R_A)
        build_r_b = _matrix_2d("build_R_B", self.build_R_B)
        atom_count = _positive_integer_value("atom_count", self.atom_count)
        d_size = _finite_nonnegative_value("d_size", self.d_size)
        match_score = _finite_nonnegative_value("match_score", self.match_score)
        w_match = _finite_nonnegative_value("w_match", self.w_match)
        if w_match > 1.0:
            raise ValueError("w_match must be no greater than one")
        if _determinant_exact(build_right) != 1:
            raise ValueError("build_common_right_transform must have determinant +1")
        for name, rotation in (("build_R_A", build_r_a), ("build_R_B", build_r_b)):
            if not np.allclose(
                rotation.T @ rotation,
                np.eye(2),
                rtol=1e-10,
                atol=1e-10,
            ) or not np.isclose(
                abs(float(np.linalg.det(rotation))),
                1.0,
                rtol=1e-10,
                atol=1e-10,
            ):
                raise ValueError(f"{name} must be an orthogonal gauge")
        # Handedness belongs to the complete physical basis
        # ``R @ B_parent @ N``.  The parent slab basis is intentionally absent
        # from this exact integer/policy record, so the orchestrator and public
        # prototype validate handedness where that basis is available.
        primitive_pair = np.vstack([primitive_a, primitive_b])
        build_pair = np.vstack([build_a, build_b])
        if not np.array_equal(primitive_pair @ build_right, build_pair):
            raise ValueError(
                "build maps must apply one common right transform to the primitive pair"
            )
        if not np.array_equal(
            primitive_pair @ self.source_provenance.source_right_factor,
            self.source_provenance.source_pair_matrix,
        ):
            raise ValueError(
                "source provenance must reconstruct from the primitive pair"
            )
        if not isinstance(self.ai_strain, AffineInvariantStrain2D):
            raise TypeError("ai_strain must be an AffineInvariantStrain2D")
        if not isinstance(self.zm_strain, ZMStrain2D):
            raise TypeError("zm_strain must be a ZMStrain2D")
        if self.pair_canonicalization.key != tuple(
            int(value) for value in self.pair_canonicalization.canonical_matrix.ravel()
        ):
            raise ValueError("pair canonicalization key is inconsistent")
        if not isinstance(self.pair_identity_policy, PairIdentityPolicy2D):
            raise TypeError("pair_identity_policy must be a PairIdentityPolicy2D")

        object.__setattr__(self, "primitive_N_A", primitive_a)
        object.__setattr__(self, "primitive_N_B", primitive_b)
        object.__setattr__(self, "build_N_A", build_a)
        object.__setattr__(self, "build_N_B", build_b)
        object.__setattr__(self, "build_common_right_transform", build_right)
        object.__setattr__(self, "build_R_A", build_r_a)
        object.__setattr__(self, "build_R_B", build_r_b)
        object.__setattr__(self, "atom_count", atom_count)
        object.__setattr__(self, "d_size", d_size)
        object.__setattr__(self, "match_score", match_score)
        object.__setattr__(self, "w_match", w_match)


@dataclass
class PrimitiveMatchClass2D:
    """One exact primitive pair class with deterministic source aggregation."""

    pair_key: tuple[int, ...]
    representative: PrimitiveMatchCandidate2D
    source_count: int = 1
    source_index_pairs: set[tuple[int, int]] = field(default_factory=set)
    repeat_indices: set[int] = field(default_factory=set)

    def __post_init__(self) -> None:
        key = tuple(int(value) for value in self.pair_key)
        if len(key) != 8:
            raise ValueError("pair_key must contain eight integers")
        if self.representative.pair_canonicalization.key != key:
            raise ValueError("representative must have pair_key")
        self.source_count = _positive_integer_value("source_count", self.source_count)
        self.source_index_pairs = {
            (int(first), int(second)) for first, second in self.source_index_pairs
        }
        if any(first <= 0 or second <= 0 for first, second in self.source_index_pairs):
            raise ValueError("source_index_pairs must contain positive indices")
        self.repeat_indices = {int(value) for value in self.repeat_indices}
        if any(value <= 0 for value in self.repeat_indices):
            raise ValueError("repeat_indices must be positive")
        self.pair_key = key


@dataclass(frozen=True)
class PrimitiveMatchSearchResult:
    """Complete coupled-v2 class population and symmetry provenance."""

    match_classes: tuple[PrimitiveMatchClass2D, ...]
    surface_symmetry_a: SurfaceSymmetryProvenance
    surface_symmetry_b: SurfaceSymmetryProvenance
    enumeration_audit: CoupledMatchEnumerationAudit | None = None
    implementation: str = "primitive_coupled_pair_v2"

    def __post_init__(self) -> None:
        classes = tuple(self.match_classes)
        keys = tuple(match_class.pair_key for match_class in classes)
        if len(set(keys)) != len(keys):
            raise ValueError("match_classes must contain unique pair keys")
        if self.implementation != "primitive_coupled_pair_v2":
            raise ValueError("unsupported primitive match implementation")
        if self.enumeration_audit is not None:
            if not isinstance(
                self.enumeration_audit,
                CoupledMatchEnumerationAudit,
            ):
                raise TypeError(
                    "enumeration_audit must be a CoupledMatchEnumerationAudit"
                )
            self.enumeration_audit.validate()
        object.__setattr__(self, "match_classes", classes)
