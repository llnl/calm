"""Exact-current persisted contract for slab and surface records."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
import json
from math import isfinite, sqrt
import re
from numbers import Integral, Real
from typing import Any

from calm.slab.oriented.cell_contract import (
    INTERFACE_READY_SLAB_CELL_POLICY,
    INTERFACE_READY_SLAB_CELL_POLICY_VERSION,
    assess_oriented_surface_cell,
    require_interface_ready_slab_cell,
)
from calm.slab.oriented.transforms import (
    ORIENTED_SLAB_TRANSFORMS_INFO_KEY,
    from_transforms_payload,
)
from calm.symmetry.surface_group import SurfaceSymmetryProvenance

SLAB_RECORD_SCHEMA = "calm.slab_record"
SLAB_RECORD_VERSION = 1

_TOP_LEVEL_FIELDS = frozenset(
    {"schema", "version", "params", "user_payload", "termination", "structure"}
)
_TERMINATION_FIELDS = frozenset({"label", "shift", "top", "bottom", "identity"})
_TERMINATION_IDENTITY_FIELDS = frozenset(
    {
        "version",
        "scheme",
        "primary",
        "top",
        "bottom",
        "pair",
        "decorated_stacking_period_layers",
        "stacking_translation_order",
        "stacking_translation_frac",
        "cut_fractional",
        "layer_tolerance_A",
        "position_tolerance_frac",
        "stacking_tolerance_frac",
        "surface_symmetry",
    }
)
_STRUCTURE_FIELDS = frozenset(
    {
        "atoms",
        "n_atoms",
        "area_A2",
        "formula",
        "slab_thickness_A",
        "vacuum_A",
        "layers",
        "characterization",
    }
)
_RESERVED_USER_FIELDS = frozenset(
    {
        "schema",
        "version",
        "bulk_uid_full",
        "bulk_id_short",
        "miller",
        "atoms",
        "params",
        "termination",
        "termination_label",
        "termination_shift",
        "termination_top",
        "termination_bottom",
        "termination_identity",
        "termination_identity_version",
        "termination_identity_scheme",
        "termination_top_identity",
        "termination_bottom_identity",
        "termination_pair_identity",
        "surface_symmetry",
        "area",
        "surface_area",
        "area_A2",
        "natoms",
        "n_atoms",
        "formula",
        "thickness",
        "vacuum",
        "layers",
        "derived",
        "characterization",
        "polar",
    }
)


def _exact_fields(name: str, value: Any, fields: frozenset[str]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping.")
    stored = dict(value)
    missing = sorted(fields - stored.keys())
    if missing:
        raise ValueError(
            f"{name} is missing required current field(s): " + ", ".join(missing) + "."
        )
    unsupported = sorted(stored.keys() - fields)
    if unsupported:
        raise ValueError(
            f"{name} contains unsupported or historical field(s): "
            + ", ".join(unsupported)
            + "."
        )
    return stored


def _nonempty_string(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise TypeError(f"{name} must be a non-empty, whitespace-trimmed string.")
    return value


def _optional_string(name: str, value: Any) -> str | None:
    if value is None:
        return None
    return _nonempty_string(name, value)


def _exact_int(name: str, value: Any, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise TypeError(f"{name} must be an exact integer.")
    result = int(value)
    if minimum is not None and result < minimum:
        raise ValueError(f"{name} must be at least {minimum}.")
    return result


def _finite_real(name: str, value: Any, *, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{name} must be a finite real number.")
    result = float(value)
    if not isfinite(result):
        raise ValueError(f"{name} must be finite.")
    if minimum is not None and result < minimum:
        raise ValueError(f"{name} must be at least {minimum}.")
    return result


def _optional_real(
    name: str, value: Any, *, minimum: float | None = None
) -> float | None:
    if value is None:
        return None
    return _finite_real(name, value, minimum=minimum)


def _json_value(name: str, value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError(f"{name} must not contain non-finite values.")
        return value
    if isinstance(value, list):
        return [_json_value(f"{name}[{i}]", item) for i, item in enumerate(value)]
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            canonical_key = _nonempty_string(f"{name} key", key)
            result[canonical_key] = _json_value(f"{name}.{canonical_key}", item)
        return result
    raise TypeError(f"{name} must contain only JSON-native values.")


def canonical_miller(value: Any) -> tuple[int, int, int]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError("A slab Miller index must be a three-integer sequence.")
    if len(value) != 3:
        raise ValueError("A slab Miller index must contain exactly three values.")
    result = tuple(_exact_int(f"miller[{i}]", item) for i, item in enumerate(value))
    if result == (0, 0, 0):
        raise ValueError("A slab Miller index cannot be (0, 0, 0).")
    return result


def _identity_mapping(
    name: str,
    value: Any,
    *,
    version: int,
    scheme: str,
    orientation: str | None,
) -> dict[str, Any]:
    fields = (
        frozenset({"version", "scheme", "digest"})
        if orientation is None
        else frozenset({"version", "scheme", "orientation", "digest"})
    )
    stored = _exact_fields(name, value, fields)
    result = _json_value(name, stored)
    if result["version"] != version:
        raise ValueError(f"{name}.version must equal {version}.")
    if result["scheme"] != scheme:
        raise ValueError(f"{name}.scheme must equal {scheme!r}.")
    if orientation is not None and result["orientation"] != orientation:
        raise ValueError(f"{name}.orientation must equal {orientation!r}.")
    digest = result["digest"]
    if (
        not isinstance(digest, str)
        or re.fullmatch(r"sha256:[0-9a-f]{64}", digest) is None
    ):
        raise ValueError(
            f"{name}.digest must contain a sha256: prefix followed by "
            "64 lowercase hexadecimal characters."
        )
    return result


def _canonical_termination_identity(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    stored = _exact_fields(
        "Slab termination identity",
        value,
        _TERMINATION_IDENTITY_FIELDS,
    )
    version = _exact_int("termination identity version", stored["version"])
    if version != 2:
        raise ValueError("Current slab termination identities require version 2.")
    scheme = _nonempty_string("termination identity scheme", stored["scheme"])
    if scheme != "decorated_periodic_halfspace_v2":
        raise ValueError(
            "Current slab termination identity scheme must be "
            "'decorated_periodic_halfspace_v2'."
        )
    primary = _identity_mapping(
        "termination identity primary",
        stored["primary"],
        version=2,
        scheme=scheme,
        orientation="plus_surface_normal",
    )
    top = _identity_mapping(
        "termination identity top",
        stored["top"],
        version=2,
        scheme=scheme,
        orientation="plus_surface_normal",
    )
    bottom = _identity_mapping(
        "termination identity bottom",
        stored["bottom"],
        version=2,
        scheme=scheme,
        orientation="minus_surface_normal",
    )
    pair = _identity_mapping(
        "termination identity pair",
        stored["pair"],
        version=2,
        scheme="ordered_termination_pair_v2",
        orientation=None,
    )
    if primary != top:
        raise ValueError("Slab termination identity primary must equal top.")
    pair_payload = {
        "version": 2,
        "scheme": "ordered_termination_pair_v2",
        "top": top,
        "bottom": bottom,
    }
    encoded_pair = json.dumps(
        pair_payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    expected_pair_digest = f"sha256:{sha256(encoded_pair).hexdigest()}"
    if pair["digest"] != expected_pair_digest:
        raise ValueError(
            "Slab termination pair digest does not match the ordered top/bottom identities."
        )
    translation = stored["stacking_translation_frac"]
    if isinstance(translation, (str, bytes)) or not isinstance(translation, Sequence):
        raise TypeError("stacking_translation_frac must be a two-value sequence.")
    if len(translation) != 2:
        raise ValueError("stacking_translation_frac must contain two values.")
    symmetry_raw = stored["surface_symmetry"]
    if not isinstance(symmetry_raw, Mapping):
        raise TypeError("surface_symmetry must be a current provenance mapping.")
    symmetry = SurfaceSymmetryProvenance(**dict(symmetry_raw))
    if symmetry.status == "failed":
        raise ValueError("Persisted slab surface_symmetry provenance cannot be failed.")
    cut = _finite_real("cut_fractional", stored["cut_fractional"])
    if not 0.0 <= cut < 1.0:
        raise ValueError("cut_fractional must lie in [0, 1).")
    return {
        "version": 2,
        "scheme": scheme,
        "primary": primary,
        "top": top,
        "bottom": bottom,
        "pair": pair,
        "decorated_stacking_period_layers": _exact_int(
            "decorated_stacking_period_layers",
            stored["decorated_stacking_period_layers"],
            minimum=1,
        ),
        "stacking_translation_order": _exact_int(
            "stacking_translation_order",
            stored["stacking_translation_order"],
            minimum=1,
        ),
        "stacking_translation_frac": [
            _finite_real(f"stacking_translation_frac[{i}]", item)
            for i, item in enumerate(translation)
        ],
        "cut_fractional": cut,
        "layer_tolerance_A": _finite_real(
            "layer_tolerance_A", stored["layer_tolerance_A"], minimum=0.0
        ),
        "position_tolerance_frac": _finite_real(
            "position_tolerance_frac",
            stored["position_tolerance_frac"],
            minimum=0.0,
        ),
        "stacking_tolerance_frac": _finite_real(
            "stacking_tolerance_frac",
            stored["stacking_tolerance_frac"],
            minimum=0.0,
        ),
        "surface_symmetry": symmetry.to_dict(),
    }


def _canonical_termination(value: Any) -> dict[str, Any]:
    stored = _exact_fields("Slab termination", value, _TERMINATION_FIELDS)
    shift = _exact_int("termination shift", stored["shift"], minimum=0)
    identity = _canonical_termination_identity(stored["identity"])
    label = _optional_string("termination label", stored["label"])
    top = _optional_string("termination top", stored["top"])
    bottom = _optional_string("termination bottom", stored["bottom"])
    named = (label is not None, top is not None, bottom is not None)
    if any(named) and not all(named):
        raise ValueError(
            "Current slab termination metadata requires label, top, and bottom together."
        )
    if shift != 0 and label is None:
        raise ValueError(
            "A nonzero termination shift requires named termination metadata."
        )
    if identity is not None and label is None:
        raise ValueError(
            "Versioned termination identity requires label, top, and bottom compositions."
        )
    return {
        "label": label,
        "shift": shift,
        "top": top,
        "bottom": bottom,
        "identity": identity,
    }


def _canonical_atoms(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise TypeError("Slab structure atoms must be a mapping or null.")
    atoms = _json_value("Slab structure atoms", value)
    required = {"numbers", "cell", "scaled_positions", "pbc"}
    missing = sorted(required - atoms.keys())
    if missing:
        raise ValueError(
            "Slab structure atoms are missing required current field(s): "
            + ", ".join(missing)
            + "."
        )
    numbers = atoms["numbers"]
    positions = atoms["scaled_positions"]
    cell = atoms["cell"]
    pbc = atoms["pbc"]
    if not isinstance(numbers, list) or not numbers:
        raise ValueError("Slab structure atoms.numbers must be a non-empty list.")
    for index, number in enumerate(numbers):
        _exact_int(f"atoms.numbers[{index}]", number, minimum=1)
    if not isinstance(positions, list) or len(positions) != len(numbers):
        raise ValueError(
            "Slab structure atoms.scaled_positions must contain one row per atom."
        )
    for i, row in enumerate(positions):
        if not isinstance(row, list) or len(row) != 3:
            raise ValueError(f"atoms.scaled_positions[{i}] must contain three values.")
        for j, item in enumerate(row):
            _finite_real(f"atoms.scaled_positions[{i}][{j}]", item)
    if not isinstance(cell, list) or len(cell) != 3:
        raise ValueError("Slab structure atoms.cell must contain three rows.")
    for i, row in enumerate(cell):
        if not isinstance(row, list) or len(row) != 3:
            raise ValueError(f"atoms.cell[{i}] must contain three values.")
        for j, item in enumerate(row):
            _finite_real(f"atoms.cell[{i}][{j}]", item)
    a = [float(item) for item in cell[0]]
    b = [float(item) for item in cell[1]]
    c = [float(item) for item in cell[2]]
    signed_volume = (
        a[0] * (b[1] * c[2] - b[2] * c[1])
        - a[1] * (b[0] * c[2] - b[2] * c[0])
        + a[2] * (b[0] * c[1] - b[1] * c[0])
    )
    if signed_volume <= 0.0:
        raise ValueError(
            "Materialized current slab structures require a right-handed "
            "cell; its determinant must be positive."
        )
    if (
        not isinstance(pbc, list)
        or len(pbc) != 3
        or any(not isinstance(item, bool) for item in pbc)
    ):
        raise ValueError("Slab structure atoms.pbc must contain three booleans.")

    info = atoms.get("info")
    if not isinstance(info, Mapping):
        raise ValueError(
            "Materialized current slab structures require an atoms.info mapping."
        )
    if ORIENTED_SLAB_TRANSFORMS_INFO_KEY not in info:
        raise ValueError(
            "Materialized current slab structures are missing required "
            f"{ORIENTED_SLAB_TRANSFORMS_INFO_KEY!r} provenance."
        )
    transforms = from_transforms_payload(info[ORIENTED_SLAB_TRANSFORMS_INFO_KEY])
    canonical_info = dict(info)
    canonical_info[ORIENTED_SLAB_TRANSFORMS_INFO_KEY] = transforms.payload
    atoms["info"] = canonical_info
    return atoms


def _atoms_area(atoms: Mapping[str, Any]) -> float:
    cell = atoms["cell"]
    a = [float(item) for item in cell[0]]
    b = [float(item) for item in cell[1]]
    cross = (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )
    return sqrt(sum(item * item for item in cross))


def _canonical_structure(value: Any) -> dict[str, Any]:
    stored = _exact_fields("Slab structure", value, _STRUCTURE_FIELDS)
    atoms = _canonical_atoms(stored["atoms"])
    vacuum = _optional_real("Slab vacuum", stored["vacuum_A"], minimum=0.0)
    n_atoms_raw = stored["n_atoms"]
    area_raw = stored["area_A2"]
    if atoms is None:
        realized_fields = {
            "n_atoms": n_atoms_raw,
            "area_A2": area_raw,
            "formula": stored["formula"],
            "slab_thickness_A": stored["slab_thickness_A"],
            "vacuum_A": stored["vacuum_A"],
            "layers": stored["layers"],
            "characterization": stored["characterization"],
        }
        present = sorted(
            key for key, item in realized_fields.items() if item is not None
        )
        if present:
            raise ValueError(
                "Spec-only slabs must not persist realized structure field(s): "
                + ", ".join(present)
                + "."
            )
        n_atoms = None
        area = None
    else:
        cell = atoms["cell"]
        assess_oriented_surface_cell(cell, name="Materialized slab cell")
        if vacuum is not None and vacuum > 0.0:
            require_interface_ready_slab_cell(
                cell,
                name="Materialized positive-vacuum slab cell",
            )
            transforms = from_transforms_payload(
                atoms["info"][ORIENTED_SLAB_TRANSFORMS_INFO_KEY]
            )
            vacuum_info = transforms.extra.get("vacuum_info")
            if not isinstance(vacuum_info, Mapping):
                raise ValueError(
                    "Materialized positive-vacuum slabs require vacuum_info "
                    "provenance."
                )
            if vacuum_info.get("cell_policy") != INTERFACE_READY_SLAB_CELL_POLICY:
                raise ValueError(
                    "Materialized positive-vacuum slabs require the current "
                    "interface-ready cell policy provenance."
                )
            if (
                vacuum_info.get("cell_policy_version")
                != INTERFACE_READY_SLAB_CELL_POLICY_VERSION
            ):
                raise ValueError(
                    "Materialized positive-vacuum slabs have an unsupported "
                    "interface-ready cell policy version."
                )
            if vacuum_info.get("interface_ready") is not True:
                raise ValueError(
                    "Materialized positive-vacuum slabs must be marked "
                    "interface-ready."
                )
            if vacuum_info.get("orthogonal_vacuum_axis") is not True:
                raise ValueError(
                    "Materialized positive-vacuum slabs must record an "
                    "orthogonal vacuum axis."
                )
            if vacuum_info.get("canonicalization_mode") not in {
                "already_orthogonal",
                "boundary_reembedding",
            }:
                raise ValueError(
                    "Materialized positive-vacuum slabs require a supported "
                    "vacuum canonicalization mode."
                )
            if (
                vacuum_info.get("canonicalization_applies_physical_strain")
                is not False
            ):
                raise ValueError(
                    "Vacuum-axis canonicalization must not be recorded as a "
                    "physical strain."
                )
        n_atoms = _exact_int("Slab structure n_atoms", n_atoms_raw, minimum=1)
        if n_atoms != len(atoms["numbers"]):
            raise ValueError("Slab structure n_atoms does not match atoms.numbers.")
        area = _finite_real("Slab structure area_A2", area_raw, minimum=0.0)
        if area <= 0.0:
            raise ValueError("Materialized slab structure area_A2 must be positive.")
        expected_area = _atoms_area(atoms)
        tolerance = 1e-10 * max(1.0, expected_area)
        if abs(area - expected_area) > tolerance:
            raise ValueError(
                "Slab structure area_A2 does not match the atomistic cell."
            )
    layers_raw = stored["layers"]
    layers = (
        None if layers_raw is None else _exact_int("Slab layers", layers_raw, minimum=1)
    )
    characterization_raw = stored["characterization"]
    characterization = (
        None
        if characterization_raw is None
        else _json_value("Slab characterization", characterization_raw)
    )
    return {
        "atoms": atoms,
        "n_atoms": n_atoms,
        "area_A2": area,
        "formula": _optional_string("Slab formula", stored["formula"]),
        "slab_thickness_A": _optional_real(
            "Slab thickness", stored["slab_thickness_A"], minimum=0.0
        ),
        "vacuum_A": vacuum,
        "layers": layers,
        "characterization": characterization,
    }


def canonical_slab_record_payload(
    value: Mapping[str, Any],
    *,
    bulk_uid_full: str,
    miller: Sequence[int],
) -> dict[str, Any]:
    """Validate one exact-current slab payload against authoritative columns."""

    _nonempty_string("bulk_uid_full", bulk_uid_full)
    canonical_miller(miller)
    stored = _exact_fields("Slab record payload", value, _TOP_LEVEL_FIELDS)
    schema = _nonempty_string("Slab record schema", stored["schema"])
    if schema != SLAB_RECORD_SCHEMA:
        raise ValueError(
            f"Unsupported slab record schema {schema!r}; expected {SLAB_RECORD_SCHEMA!r}."
        )
    version = _exact_int("Slab record version", stored["version"])
    if version != SLAB_RECORD_VERSION:
        raise ValueError(
            f"Unsupported slab record version {version!r}; expected {SLAB_RECORD_VERSION}."
        )
    params_raw = stored["params"]
    if not isinstance(params_raw, Mapping):
        raise TypeError("Slab build params must be a mapping.")
    params = _json_value("Slab build params", params_raw)
    user_raw = stored["user_payload"]
    if not isinstance(user_raw, Mapping):
        raise TypeError("Slab user_payload must be a mapping.")
    user_payload = _json_value("Slab user_payload", user_raw)
    reserved = sorted(_RESERVED_USER_FIELDS & user_payload.keys())
    if reserved:
        raise ValueError(
            "Slab user_payload contains reserved scientific field(s): "
            + ", ".join(reserved)
            + "."
        )
    return {
        "schema": SLAB_RECORD_SCHEMA,
        "version": SLAB_RECORD_VERSION,
        "params": params,
        "user_payload": user_payload,
        "termination": _canonical_termination(stored["termination"]),
        "structure": _canonical_structure(stored["structure"]),
    }


def slab_atoms_payload(payload: Mapping[str, Any]) -> dict[str, Any] | None:
    structure = payload.get("structure")
    if not isinstance(structure, Mapping):
        return None
    atoms = structure.get("atoms")
    return dict(atoms) if isinstance(atoms, Mapping) else None


__all__ = [
    "SLAB_RECORD_SCHEMA",
    "SLAB_RECORD_VERSION",
    "canonical_miller",
    "canonical_slab_record_payload",
    "slab_atoms_payload",
]
