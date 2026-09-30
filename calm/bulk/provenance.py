"""Exact-current provenance for spglib bulk standardization.

Spglib standardization owns a change of basis ``P``, an origin shift ``p``,
and, when metric idealization is enabled, a Cartesian proper rotation ``R``.
CALM stores that complete relation together with the verified conventional-to-
primitive map and selected symmetry-dataset metadata.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Mapping

import numpy as np

from calm.structure.standardization import (
    canonical_fractional_vector3,
    exact_bool,
    exact_integer,
    exact_nonnegative_integer,
    finite_matrix3,
    mapping_value,
    nonnegative_finite_float,
    positive_finite_float,
    primitive_reduction_check,
    spglib_angle_tolerance,
    standardization_relation,
)

if TYPE_CHECKING:  # pragma: no cover
    from ase import Atoms


CALM_BULK_CANONICALIZATION_TRANSFORMS_INFO_KEY = (
    "calm_bulk_canonicalization_transforms_json"
)
"""Key used in ``Atoms.info`` for bulk-standardization provenance."""

BULK_CANONICALIZATION_SCHEMA_VERSION = 3

_CURRENT_PROVENANCE_FIELDS = frozenset(
    {
        "schema_version",
        "basis",
        "symprec",
        "no_idealize",
        "transformation_matrix_input_from_standardized",
        "origin_shift_standardized_frac",
        "rigid_rotation_standardized_cart",
        "conventional_to_primitive_col",
        "conventional_relation_verified",
        "primitive_relation_verified",
        "conventional_max_abs_residual",
        "primitive_max_abs_residual",
        "conventional_relative_residual",
        "primitive_relative_residual",
        "primitive_multiplicity",
        "primitive_volume_ratio",
        "primitive_composition_verified",
        "primitive_volume_verified",
        "angle_tolerance",
        "spglib_version",
        "spacegroup_number",
        "international_symbol",
        "hall_number",
        "hall_symbol",
        "choice",
        "equivalent_atoms",
        "crystallographic_orbits",
        "mapping_to_primitive",
        "std_mapping_to_primitive",
    }
)


def parse_bulk_canonicalization_transforms(
    value: Any,
) -> "BulkCanonicalizationTransforms":
    """Parse one present exact-current bulk-standardization record.

    Absence is owned by the caller because a missing ``Atoms.info`` key and a
    malformed present value are materially different project states.  Present
    empty strings, invalid JSON, non-mapping JSON, and unsupported carriers all
    raise instead of being converted into missing provenance.
    """

    if isinstance(value, Mapping):
        decoded = dict(value)
    elif isinstance(value, str):
        raw = value.strip()
        if not raw:
            raise ValueError("bulk-standardization provenance JSON must be non-empty.")
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "bulk-standardization provenance contains invalid JSON."
            ) from exc
        if not isinstance(parsed, Mapping):
            raise TypeError(
                "bulk-standardization provenance JSON must decode to a mapping."
            )
        decoded = dict(parsed)
    else:
        raise TypeError(
            "bulk-standardization provenance must be a mapping or JSON string."
        )
    return BulkCanonicalizationTransforms.from_dict(decoded)


def _optional_int(value: object | None) -> int | None:
    if value is None:
        return None
    return exact_integer("integer provenance value", value)


def _integer_list(value: object | None) -> list[int] | None:
    if value is None:
        return None
    raw = np.asarray(value, dtype=object)
    if raw.ndim != 1:
        raise ValueError("atom mappings must be one-dimensional integer arrays.")
    values: list[int] = []
    for item in raw.tolist():
        number = exact_integer("atom mapping", item)
        if number < 0:
            raise ValueError("atom mappings must contain nonnegative integers.")
        values.append(number)
    return values


def _required(data: Mapping[str, Any], name: str) -> Any:
    if name not in data:
        raise ValueError(
            f"bulk-standardization provenance is missing required field {name!r}."
        )
    return data[name]


@dataclass(frozen=True)
class BulkCanonicalizationTransforms:
    """Current provenance record for one spglib bulk standardization."""

    schema_version: int
    basis: str
    symprec: float
    no_idealize: bool

    transformation_matrix_input_from_standardized: np.ndarray
    origin_shift_standardized_frac: np.ndarray
    rigid_rotation_standardized_cart: np.ndarray
    conventional_to_primitive_col: np.ndarray
    conventional_relation_verified: bool
    primitive_relation_verified: bool
    conventional_max_abs_residual: float
    primitive_max_abs_residual: float
    conventional_relative_residual: float
    primitive_relative_residual: float
    primitive_multiplicity: int
    primitive_volume_ratio: float
    primitive_composition_verified: bool
    primitive_volume_verified: bool
    angle_tolerance: float
    spglib_version: str

    spacegroup_number: int | None = None
    international_symbol: str | None = None
    hall_number: int | None = None
    hall_symbol: str | None = None
    choice: str | None = None
    equivalent_atoms: list[int] | None = None
    crystallographic_orbits: list[int] | None = None
    mapping_to_primitive: list[int] | None = None
    std_mapping_to_primitive: list[int] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": int(self.schema_version),
            "basis": str(self.basis),
            "symprec": float(self.symprec),
            "no_idealize": bool(self.no_idealize),
            "transformation_matrix_input_from_standardized": (
                self.transformation_matrix_input_from_standardized.tolist()
            ),
            "origin_shift_standardized_frac": (
                self.origin_shift_standardized_frac.tolist()
            ),
            "rigid_rotation_standardized_cart": (
                self.rigid_rotation_standardized_cart.tolist()
            ),
            "conventional_to_primitive_col": (
                self.conventional_to_primitive_col.tolist()
            ),
            "conventional_relation_verified": bool(self.conventional_relation_verified),
            "primitive_relation_verified": bool(self.primitive_relation_verified),
            "conventional_max_abs_residual": float(self.conventional_max_abs_residual),
            "primitive_max_abs_residual": float(self.primitive_max_abs_residual),
            "conventional_relative_residual": float(
                self.conventional_relative_residual
            ),
            "primitive_relative_residual": float(self.primitive_relative_residual),
            "primitive_multiplicity": int(self.primitive_multiplicity),
            "primitive_volume_ratio": float(self.primitive_volume_ratio),
            "primitive_composition_verified": bool(self.primitive_composition_verified),
            "primitive_volume_verified": bool(self.primitive_volume_verified),
            "angle_tolerance": float(self.angle_tolerance),
            "spglib_version": str(self.spglib_version),
            "spacegroup_number": self.spacegroup_number,
            "international_symbol": self.international_symbol,
            "hall_number": self.hall_number,
            "hall_symbol": self.hall_symbol,
            "choice": self.choice,
            "equivalent_atoms": self.equivalent_atoms,
            "crystallographic_orbits": self.crystallographic_orbits,
            "mapping_to_primitive": self.mapping_to_primitive,
            "std_mapping_to_primitive": self.std_mapping_to_primitive,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any],
    ) -> "BulkCanonicalizationTransforms":
        unexpected = sorted(set(data) - _CURRENT_PROVENANCE_FIELDS)
        if unexpected:
            raise ValueError(
                "bulk-standardization provenance contains unsupported fields: "
                + ", ".join(unexpected)
            )

        schema_version = exact_nonnegative_integer(
            "schema_version",
            _required(data, "schema_version"),
        )
        if schema_version != BULK_CANONICALIZATION_SCHEMA_VERSION:
            raise ValueError(
                "unsupported bulk-standardization provenance schema version: "
                f"expected {BULK_CANONICALIZATION_SCHEMA_VERSION}, got "
                f"{schema_version}."
            )
        basis = _required(data, "basis")
        if basis != "column":
            raise ValueError("bulk-standardization provenance basis must be 'column'.")

        record = cls(
            schema_version=schema_version,
            basis="column",
            symprec=positive_finite_float(
                "symprec",
                _required(data, "symprec"),
            ),
            no_idealize=exact_bool(
                "no_idealize",
                _required(data, "no_idealize"),
            ),
            transformation_matrix_input_from_standardized=finite_matrix3(
                "transformation_matrix_input_from_standardized",
                _required(data, "transformation_matrix_input_from_standardized"),
            ),
            origin_shift_standardized_frac=canonical_fractional_vector3(
                "origin_shift_standardized_frac",
                _required(data, "origin_shift_standardized_frac"),
            ),
            rigid_rotation_standardized_cart=finite_matrix3(
                "rigid_rotation_standardized_cart",
                _required(data, "rigid_rotation_standardized_cart"),
            ),
            conventional_to_primitive_col=finite_matrix3(
                "conventional_to_primitive_col",
                _required(data, "conventional_to_primitive_col"),
            ),
            conventional_relation_verified=exact_bool(
                "conventional_relation_verified",
                _required(data, "conventional_relation_verified"),
            ),
            primitive_relation_verified=exact_bool(
                "primitive_relation_verified",
                _required(data, "primitive_relation_verified"),
            ),
            conventional_max_abs_residual=nonnegative_finite_float(
                "conventional_max_abs_residual",
                _required(data, "conventional_max_abs_residual"),
            ),
            primitive_max_abs_residual=nonnegative_finite_float(
                "primitive_max_abs_residual",
                _required(data, "primitive_max_abs_residual"),
            ),
            conventional_relative_residual=nonnegative_finite_float(
                "conventional_relative_residual",
                _required(data, "conventional_relative_residual"),
            ),
            primitive_relative_residual=nonnegative_finite_float(
                "primitive_relative_residual",
                _required(data, "primitive_relative_residual"),
            ),
            primitive_multiplicity=exact_nonnegative_integer(
                "primitive_multiplicity",
                _required(data, "primitive_multiplicity"),
            ),
            primitive_volume_ratio=positive_finite_float(
                "primitive_volume_ratio",
                _required(data, "primitive_volume_ratio"),
            ),
            primitive_composition_verified=exact_bool(
                "primitive_composition_verified",
                _required(data, "primitive_composition_verified"),
            ),
            primitive_volume_verified=exact_bool(
                "primitive_volume_verified",
                _required(data, "primitive_volume_verified"),
            ),
            angle_tolerance=spglib_angle_tolerance(_required(data, "angle_tolerance")),
            spglib_version=_nonempty_string(
                "spglib_version",
                _required(data, "spglib_version"),
            ),
            spacegroup_number=_optional_int(data.get("spacegroup_number")),
            international_symbol=_optional_string(data.get("international_symbol")),
            hall_number=_optional_int(data.get("hall_number")),
            hall_symbol=_optional_string(data.get("hall_symbol")),
            choice=_optional_string(data.get("choice")),
            equivalent_atoms=_integer_list(data.get("equivalent_atoms")),
            crystallographic_orbits=_integer_list(data.get("crystallographic_orbits")),
            mapping_to_primitive=_integer_list(data.get("mapping_to_primitive")),
            std_mapping_to_primitive=_integer_list(
                data.get("std_mapping_to_primitive")
            ),
        )
        _validate_current_record(record)
        return record


def _nonempty_string(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string.")
    result = value.strip()
    if not result:
        raise ValueError(f"{name} must be a nonempty string.")
    return result


def _optional_string(value: object | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError("string provenance values must be strings.")
    return value


def _validate_current_record(record: BulkCanonicalizationTransforms) -> None:
    checks = (
        (
            record.conventional_relation_verified,
            "current conventional-cell relation is not verified.",
        ),
        (
            record.primitive_relation_verified,
            "current primitive-cell relation is not verified.",
        ),
        (
            record.primitive_composition_verified,
            "current primitive composition is not verified.",
        ),
        (
            record.primitive_volume_verified,
            "current primitive volume is not verified.",
        ),
    )
    for value, message in checks:
        if value is not True:
            raise ValueError(message)
    if record.primitive_multiplicity not in {1, 2, 3, 4}:
        raise ValueError("current primitive multiplicity is invalid.")

    _require_nonsingular(
        record.transformation_matrix_input_from_standardized,
        "current transformation matrix",
    )
    _require_nonsingular(
        record.conventional_to_primitive_col,
        "current primitive transform",
    )
    _require_proper_rotation(record.rigid_rotation_standardized_cart)
    origin_shift = record.origin_shift_standardized_frac
    if np.any(origin_shift < 0.0) or np.any(origin_shift >= 1.0):
        raise ValueError("current origin shift must lie in [0, 1).")


def _require_nonsingular(matrix: np.ndarray, name: str) -> None:
    if abs(float(np.linalg.det(matrix))) <= np.finfo(float).eps:
        raise ValueError(f"{name} must be nonsingular.")


def _require_proper_rotation(rotation: np.ndarray) -> None:
    if not np.allclose(
        rotation.T @ rotation,
        np.eye(3),
        rtol=1e-10,
        atol=1e-10,
    ):
        raise ValueError("current rigid rotation must be orthogonal.")
    if not np.isclose(
        float(np.linalg.det(rotation)),
        1.0,
        rtol=1e-10,
        atol=1e-10,
    ):
        raise ValueError("current rigid rotation must be proper.")


def _require_close_scalar(name: str, stored: float, recomputed: float) -> None:
    scale = max(abs(float(stored)), abs(float(recomputed)), 1.0)
    absolute_tolerance = 128.0 * np.finfo(float).eps * scale
    if not np.isclose(
        float(stored),
        float(recomputed),
        rtol=1e-12,
        atol=absolute_tolerance,
    ):
        raise ValueError(
            f"stored bulk-standardization {name} does not match the "
            "recomputed current relation."
        )


def _require_close_matrix(
    name: str,
    stored: np.ndarray,
    recomputed: np.ndarray,
) -> None:
    scale = max(
        float(np.max(np.abs(stored))),
        float(np.max(np.abs(recomputed))),
        1.0,
    )
    absolute_tolerance = 128.0 * np.finfo(float).eps * scale
    if not np.allclose(
        stored,
        recomputed,
        rtol=1e-12,
        atol=absolute_tolerance,
    ):
        raise ValueError(
            f"stored bulk-standardization {name} does not match the "
            "recomputed current relation."
        )


def validate_bulk_canonicalization_relations(
    *,
    cell_input_rows: object,
    cell_conventional_rows: object,
    cell_primitive_rows: object,
    numbers_conventional: object,
    numbers_primitive: object,
    record: BulkCanonicalizationTransforms,
) -> None:
    """Verify one record against the structures it claims to relate.

    Parsing proves that the record is internally well formed.  This operation
    independently recomputes the submitted-to-conventional lattice relation and
    the conventional-to-primitive reduction from the persisted structures so a
    syntactically valid but detached record cannot be trusted as current state.
    """

    relation = standardization_relation(
        cell_input_rows=cell_input_rows,
        cell_conventional_rows=cell_conventional_rows,
        cell_primitive_rows=cell_primitive_rows,
        transformation_matrix=(record.transformation_matrix_input_from_standardized),
        origin_shift=record.origin_shift_standardized_frac,
        rigid_rotation=record.rigid_rotation_standardized_cart,
        no_idealize=record.no_idealize,
        symprec=record.symprec,
    )
    if not relation.conventional_verified or not relation.primitive_verified:
        raise ValueError(
            "bulk-standardization provenance does not reconstruct the stored "
            "current cells."
        )

    primitive_check = primitive_reduction_check(
        cell_conventional_rows=cell_conventional_rows,
        cell_primitive_rows=cell_primitive_rows,
        numbers_conventional=numbers_conventional,
        numbers_primitive=numbers_primitive,
        symprec=record.symprec,
    )

    _require_close_matrix(
        "conventional_to_primitive_col",
        record.conventional_to_primitive_col,
        relation.conventional_to_primitive,
    )
    _require_close_scalar(
        "conventional_max_abs_residual",
        record.conventional_max_abs_residual,
        relation.conventional_max_abs_residual,
    )
    _require_close_scalar(
        "primitive_max_abs_residual",
        record.primitive_max_abs_residual,
        relation.primitive_max_abs_residual,
    )
    _require_close_scalar(
        "conventional_relative_residual",
        record.conventional_relative_residual,
        relation.conventional_relative_residual,
    )
    _require_close_scalar(
        "primitive_relative_residual",
        record.primitive_relative_residual,
        relation.primitive_relative_residual,
    )
    if record.primitive_multiplicity != primitive_check.multiplicity:
        raise ValueError(
            "stored bulk-standardization primitive multiplicity does not match "
            "the persisted cells."
        )
    _require_close_scalar(
        "primitive_volume_ratio",
        record.primitive_volume_ratio,
        primitive_check.volume_ratio,
    )


def _dataset_record(
    *,
    dataset: object,
    atoms_input: "Atoms",
    atoms_conventional: "Atoms",
    atoms_primitive: "Atoms",
    symprec: float,
    no_idealize: bool,
) -> dict[str, Any]:
    transformation = mapping_value(dataset, "transformation_matrix")
    origin_shift = mapping_value(dataset, "origin_shift")
    rotation = mapping_value(dataset, "std_rotation_matrix", np.eye(3))
    if transformation is None or origin_shift is None:
        raise ValueError(
            "spglib symmetry dataset is missing transformation_matrix or origin_shift."
        )
    relation = standardization_relation(
        cell_input_rows=atoms_input.cell.array,
        cell_conventional_rows=atoms_conventional.cell.array,
        cell_primitive_rows=atoms_primitive.cell.array,
        transformation_matrix=transformation,
        origin_shift=origin_shift,
        rigid_rotation=rotation,
        no_idealize=no_idealize,
        symprec=symprec,
    )
    if not relation.conventional_verified or not relation.primitive_verified:
        raise ValueError(
            "spglib standardization provenance does not reconstruct the returned cells."
        )
    primitive_check = primitive_reduction_check(
        cell_conventional_rows=atoms_conventional.cell.array,
        cell_primitive_rows=atoms_primitive.cell.array,
        numbers_conventional=atoms_conventional.get_atomic_numbers(),
        numbers_primitive=atoms_primitive.get_atomic_numbers(),
        symprec=symprec,
    )
    return {
        "relation": relation,
        "primitive_check": primitive_check,
        "spacegroup_number": _optional_int(mapping_value(dataset, "number")),
        "international_symbol": _optional_string(
            mapping_value(dataset, "international")
        ),
        "hall_number": _optional_int(mapping_value(dataset, "hall_number")),
        "hall_symbol": _optional_string(mapping_value(dataset, "hall")),
        "choice": _optional_string(mapping_value(dataset, "choice")),
        "equivalent_atoms": _integer_list(mapping_value(dataset, "equivalent_atoms")),
        "crystallographic_orbits": _integer_list(
            mapping_value(dataset, "crystallographic_orbits")
        ),
        "mapping_to_primitive": _integer_list(
            mapping_value(dataset, "mapping_to_primitive")
        ),
        "std_mapping_to_primitive": _integer_list(
            mapping_value(dataset, "std_mapping_to_primitive")
        ),
    }


def stamp_bulk_canonicalization_transforms(
    *,
    atoms_input: "Atoms",
    atoms_conventional: "Atoms",
    atoms_primitive: "Atoms",
    symprec: float,
    dataset: object,
    no_idealize: bool = False,
    angle_tolerance: float = -1.0,
    spglib_version: str = "unknown",
) -> None:
    """Stamp exact-current standardization provenance into both output cells."""

    tolerance = positive_finite_float("symprec", symprec)
    preserve_metric = exact_bool("no_idealize", no_idealize)
    angle_tolerance_value = spglib_angle_tolerance(angle_tolerance)
    version = _nonempty_string("spglib_version", spglib_version)

    dataset_fields = _dataset_record(
        dataset=dataset,
        atoms_input=atoms_input,
        atoms_conventional=atoms_conventional,
        atoms_primitive=atoms_primitive,
        symprec=tolerance,
        no_idealize=preserve_metric,
    )
    relation = dataset_fields.pop("relation")
    primitive_check = dataset_fields.pop("primitive_check")

    record = BulkCanonicalizationTransforms(
        schema_version=BULK_CANONICALIZATION_SCHEMA_VERSION,
        basis="column",
        symprec=tolerance,
        no_idealize=preserve_metric,
        transformation_matrix_input_from_standardized=(
            relation.transformation_matrix_input_from_standardized
        ),
        origin_shift_standardized_frac=relation.origin_shift_standardized,
        rigid_rotation_standardized_cart=relation.rigid_rotation_standardized,
        conventional_to_primitive_col=relation.conventional_to_primitive,
        conventional_relation_verified=relation.conventional_verified,
        primitive_relation_verified=relation.primitive_verified,
        conventional_max_abs_residual=relation.conventional_max_abs_residual,
        primitive_max_abs_residual=relation.primitive_max_abs_residual,
        conventional_relative_residual=relation.conventional_relative_residual,
        primitive_relative_residual=relation.primitive_relative_residual,
        primitive_multiplicity=primitive_check.multiplicity,
        primitive_volume_ratio=primitive_check.volume_ratio,
        primitive_composition_verified=primitive_check.composition_verified,
        primitive_volume_verified=primitive_check.volume_verified,
        angle_tolerance=angle_tolerance_value,
        spglib_version=version,
        **dataset_fields,
    )
    _validate_current_record(record)
    payload = record.to_json()
    atoms_conventional.info[CALM_BULK_CANONICALIZATION_TRANSFORMS_INFO_KEY] = payload
    atoms_primitive.info[CALM_BULK_CANONICALIZATION_TRANSFORMS_INFO_KEY] = payload


def get_bulk_canonicalization_transforms(
    atoms: "Atoms",
) -> BulkCanonicalizationTransforms | None:
    """Read and validate current standardization provenance from a structure."""

    info = getattr(atoms, "info", None)
    if info is None:
        return None
    if not isinstance(info, Mapping):
        raise TypeError("Atoms.info must be a mapping.")
    key = CALM_BULK_CANONICALIZATION_TRANSFORMS_INFO_KEY
    if key not in info:
        return None
    return parse_bulk_canonicalization_transforms(info[key])
