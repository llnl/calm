"""Exact-current persisted contracts for energy and thermodynamic results.

The follow-up table retains generic scalar columns for indexing.  These helpers
make each versioned payload authoritative, validate its target relationship,
and verify that the generic columns are exact projections on write and reopen.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import isclose, isfinite
from numbers import Integral, Real
from typing import Any

from calm.interface.energy.contract import (
    EV_PER_A2_TO_J_PER_M2,
    canonical_energy_formula,
    positive_interface_multiplicity,
)

RAW_ENERGY_RESULT_SCHEMA = "calm.raw_energy_result"
REFERENCE_ENERGY_RESULT_SCHEMA = "calm.reference_energy_result"
THERMODYNAMIC_RESULT_SCHEMA = "calm.thermodynamic_result"
ENERGY_RESULT_VERSION = 1
ENERGY_RESULT_KINDS = frozenset(
    {"energy_stage", "reference_energy", "thermodynamic_quantity"}
)

_RAW_DONE_FIELDS = frozenset(
    {
        "schema",
        "version",
        "result_stage",
        "quantity",
        "energy_eV",
        "n_steps",
        "interface_area_A2",
        "area_source",
        "backend",
        "workflow_metadata",
        "artifact_refs",
        "summary",
    }
)
_RAW_FAILED_FIELDS = frozenset(
    {
        "schema",
        "version",
        "result_stage",
        "quantity",
        "backend",
        "workflow_metadata",
        "failure",
    }
)
_REFERENCE_DONE_FIELDS = frozenset(
    {
        "schema",
        "version",
        "result_stage",
        "reference",
        "energy",
        "backend",
        "relaxation",
        "workflow_metadata",
        "artifact_refs",
        "summary",
    }
)
_REFERENCE_FAILED_FIELDS = frozenset(
    {
        "schema",
        "version",
        "result_stage",
        "reference",
        "backend",
        "relaxation",
        "workflow_metadata",
        "failure",
    }
)
_THERMO_DONE_FIELDS = frozenset(
    {
        "schema",
        "version",
        "result_stage",
        "source",
        "quantity",
        "normalization",
        "convention",
        "references",
        "components",
        "calculator_compatibility",
        "units",
    }
)
_THERMO_FAILED_FIELDS = frozenset(
    {
        "schema",
        "version",
        "result_stage",
        "source",
        "convention",
        "references",
        "calculator_compatibility",
        "normalization_area_source_status",
        "failure",
    }
)


_WORKFLOW_METADATA_RESERVED_FIELDS = frozenset(
    {
        "schema",
        "version",
        "result_stage",
        "quantity",
        "energy",
        "energy_eV",
        "energy_units",
        "n_steps",
        "interface_area_A2",
        "area_source",
        "backend",
        "energy_backend",
        "backend_identity",
        "settings",
        "energy_settings",
        "artifact_refs",
        "summary",
        "failure",
        "run_uid_full",
        "prototype_uid_full",
        "target_uid_full",
        "target_kind",
        "reference",
        "source",
        "normalization",
        "convention",
        "references",
        "components",
        "calculator_compatibility",
        "units",
    }
)

_REFERENCE_KIND_BY_FORMULA = {
    "interface_excess_strained_bulk": frozenset({"strained_bulk_a", "strained_bulk_b"}),
    "work_of_separation_unrelaxed_surfaces": frozenset(
        {"isolated_surface_a", "isolated_surface_b"}
    ),
    "work_of_adhesion_relaxed_surfaces": frozenset(
        {"relaxed_surface_a", "relaxed_surface_b"}
    ),
}


def _nonempty_string(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise TypeError(f"{name} must be a non-empty, whitespace-trimmed string.")
    return value


def _finite_real(name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{name} must be a finite real number.")
    result = float(value)
    if not isfinite(result):
        raise ValueError(f"{name} must be finite.")
    return result


def _optional_finite(name: str, value: Any) -> float | None:
    if value is None:
        return None
    return _finite_real(name, value)


def _nonnegative_int(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise TypeError(f"{name} must be a non-negative integer.")
    result = int(value)
    if result < 0:
        raise ValueError(f"{name} must be a non-negative integer.")
    return result


def _positive_int(name: str, value: Any) -> int:
    result = _nonnegative_int(name, value)
    if result < 1:
        raise ValueError(f"{name} must be a positive integer.")
    return result


def _optional_nonnegative_int(name: str, value: Any) -> int | None:
    if value is None:
        return None
    return _nonnegative_int(name, value)


def _require_exact_fields(
    name: str,
    value: Mapping[str, Any],
    fields: frozenset[str],
) -> dict[str, Any]:
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


def _canonical_json_value(name: str, value: Any) -> Any:
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, Integral) and not isinstance(value, bool):
        return int(value)
    if isinstance(value, Real) and not isinstance(value, bool):
        return _finite_real(name, value)
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for key, item in value.items():
            canonical_key = _nonempty_string(f"{name} key", key)
            out[canonical_key] = _canonical_json_value(f"{name}.{canonical_key}", item)
        return out
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [
            _canonical_json_value(f"{name}[{index}]", item)
            for index, item in enumerate(value)
        ]
    raise TypeError(f"{name} must contain only JSON-native values.")


def _canonical_mapping(name: str, value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping.")
    result = _canonical_json_value(name, value)
    assert isinstance(result, dict)
    return result


def _canonical_workflow_metadata(value: Any) -> dict[str, Any]:
    metadata = _canonical_mapping("Energy result workflow_metadata", value)
    duplicates = sorted(metadata.keys() & _WORKFLOW_METADATA_RESERVED_FIELDS)
    if duplicates:
        raise ValueError(
            "Energy result workflow_metadata contains schema-owned or historical "
            "field(s): " + ", ".join(duplicates) + "."
        )
    return metadata


def _canonical_calculator_record(
    name: str,
    value: Any,
    *,
    include_relaxation: bool,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping.")
    fields = {"backend", "identity", "settings", "interface_area_A2"}
    if include_relaxation:
        fields.add("relaxation")
    stored = _require_exact_fields(name, value, frozenset(fields))
    backend = _nonempty_string(f"{name} backend", stored["backend"])
    identity = _canonical_mapping(f"{name} identity", stored["identity"])
    if identity.get("name") != backend:
        raise ValueError(f"{name} identity name must match backend.")
    area = _finite_real(f"{name} interface_area_A2", stored["interface_area_A2"])
    if area <= 0.0:
        raise ValueError(f"{name} interface_area_A2 must be positive.")
    result = {
        "backend": backend,
        "identity": identity,
        "settings": _canonical_mapping(f"{name} settings", stored["settings"]),
        "interface_area_A2": area,
    }
    if include_relaxation:
        relaxation = stored["relaxation"]
        if relaxation is not None:
            if not isinstance(relaxation, Mapping):
                raise TypeError(f"{name} relaxation must be a mapping or None.")
            relaxation_stored = _require_exact_fields(
                f"{name} relaxation",
                relaxation,
                frozenset(
                    {
                        "protocol",
                        "settings",
                        "engine",
                        "source_interface_structure_fingerprint",
                    }
                ),
            )
            relaxation = {
                "protocol": _nonempty_string(
                    f"{name} relaxation protocol", relaxation_stored["protocol"]
                ),
                "settings": _canonical_mapping(
                    f"{name} relaxation settings", relaxation_stored["settings"]
                ),
                "engine": _canonical_mapping(
                    f"{name} relaxation engine", relaxation_stored["engine"]
                ),
                "source_interface_structure_fingerprint": _nonempty_string(
                    f"{name} relaxation source_interface_structure_fingerprint",
                    relaxation_stored["source_interface_structure_fingerprint"],
                ),
            }
        result["relaxation"] = relaxation
    return result


def _canonical_calculator_compatibility(
    value: Any,
    *,
    allow_unresolved: bool = False,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError("Thermodynamic calculator_compatibility must be a mapping.")
    status = value.get("status")
    if status == "unresolved":
        if not allow_unresolved:
            raise ValueError(
                "Completed thermodynamic results cannot use unresolved calculator "
                "compatibility."
            )
        stored = _require_exact_fields(
            "Thermodynamic calculator_compatibility",
            value,
            frozenset({"status", "reason"}),
        )
        return {
            "status": "unresolved",
            "reason": _nonempty_string(
                "Thermodynamic calculator_compatibility reason",
                stored["reason"],
            ),
        }
    if status == "manual_unverified":
        stored = _require_exact_fields(
            "Thermodynamic calculator_compatibility",
            value,
            frozenset({"status", "reference_source"}),
        )
        return {
            "status": "manual_unverified",
            "reference_source": _nonempty_string(
                "Thermodynamic calculator_compatibility reference_source",
                stored["reference_source"],
            ),
        }
    if status != "verified":
        raise ValueError(
            "Thermodynamic calculator_compatibility status must be "
            "'verified' or 'manual_unverified'."
        )
    stored = _require_exact_fields(
        "Thermodynamic calculator_compatibility",
        value,
        frozenset({"status", "raw", "reference"}),
    )
    raw = _canonical_calculator_record(
        "Thermodynamic raw calculator provenance",
        stored["raw"],
        include_relaxation=False,
    )
    reference = _canonical_calculator_record(
        "Thermodynamic reference calculator provenance",
        stored["reference"],
        include_relaxation=True,
    )
    if (
        raw["backend"] != reference["backend"]
        or raw["identity"] != reference["identity"]
        or raw["settings"] != reference["settings"]
    ):
        raise ValueError(
            "Verified thermodynamic calculator provenance must use identical raw "
            "and reference calculators and settings."
        )
    if not isclose(
        raw["interface_area_A2"],
        reference["interface_area_A2"],
        rel_tol=1e-10,
        abs_tol=1e-10,
    ):
        raise ValueError(
            "Verified thermodynamic calculator provenance must use identical raw "
            "and reference interface areas."
        )
    return {"status": "verified", "raw": raw, "reference": reference}


def _canonical_artifact_refs(value: Any) -> list[str]:
    if not isinstance(value, list):
        raise TypeError("Energy result artifact_refs must be a list.")
    refs = [
        _nonempty_string(f"Energy result artifact_refs[{index}]", item)
        for index, item in enumerate(value)
    ]
    if len(refs) != len(set(refs)):
        raise ValueError("Energy result artifact_refs must be unique.")
    return refs


def _canonical_failure(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise TypeError("Energy result failure must be a mapping.")
    stored = _require_exact_fields(
        "Energy result failure",
        value,
        frozenset({"message", "exception_type", "module"}),
    )
    return {
        key: _nonempty_string(f"Energy result failure {key}", stored[key])
        for key in ("message", "exception_type", "module")
    }


def _canonical_backend(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError("Energy result backend must be a mapping.")
    stored = _require_exact_fields(
        "Energy result backend",
        value,
        frozenset({"name", "identity", "settings"}),
    )
    name = _nonempty_string("Energy result backend name", stored["name"])
    identity = _canonical_mapping("Energy result backend identity", stored["identity"])
    identity_name = identity.get("name")
    if identity_name is None:
        raise ValueError("Energy result backend identity must contain name.")
    if _nonempty_string("Energy result backend identity name", identity_name) != name:
        raise ValueError(
            "Energy result backend name does not match backend identity name."
        )
    return {
        "name": name,
        "identity": identity,
        "settings": _canonical_mapping(
            "Energy result backend settings", stored["settings"]
        ),
    }


def _target_columns(
    *,
    prototype_uid_full: str | None,
    target_uid_full: str | None,
    target_kind: str | None,
) -> tuple[str, str, str]:
    prototype_uid = _nonempty_string(
        "Energy result prototype_uid_full", prototype_uid_full
    )
    target_uid = _nonempty_string("Energy result target_uid_full", target_uid_full)
    kind = _nonempty_string("Energy result target_kind", target_kind)
    if kind not in {"prototype", "interface"}:
        raise ValueError(
            "Energy result target_kind must be 'prototype' or 'interface'."
        )
    if kind == "prototype" and target_uid != prototype_uid:
        raise ValueError(
            "Prototype-targeted energy results require target_uid_full to equal "
            "prototype_uid_full."
        )
    return prototype_uid, target_uid, kind


def _validate_header(
    *,
    stored: Mapping[str, Any],
    schema: str,
    result_stage: str,
) -> None:
    if stored["schema"] != schema:
        raise ValueError(f"Unsupported energy result schema; expected {schema!r}.")
    version = stored["version"]
    if isinstance(version, bool) or not isinstance(version, int):
        raise TypeError("Energy result version must be an integer.")
    if version != ENERGY_RESULT_VERSION:
        raise ValueError("Unsupported energy result version; expected 1.")
    if stored["result_stage"] != result_stage:
        raise ValueError(
            f"Current energy result requires result_stage={result_stage!r}."
        )


def _require_failed_projections(
    *,
    best_energy: float | None,
    param1: float | None,
    param2: float | None,
    n_points: int | None,
) -> None:
    if any(value is not None for value in (best_energy, param1, param2, n_points)):
        raise ValueError(
            "Failed energy results require null generic scalar projections."
        )


def _canonical_raw_energy(
    payload: Mapping[str, Any],
    *,
    status: str,
    target_kind: str,
    best_energy: float | None,
    param1: float | None,
    param2: float | None,
    n_points: int | None,
) -> dict[str, Any]:
    failed = status == "failed"
    fields = _RAW_FAILED_FIELDS if failed else _RAW_DONE_FIELDS
    stored = _require_exact_fields("Raw energy result payload", payload, fields)
    _validate_header(
        stored=stored,
        schema=RAW_ENERGY_RESULT_SCHEMA,
        result_stage="energy_failed" if failed else "energy_evaluated",
    )
    if stored["quantity"] != "total_energy":
        raise ValueError("Raw energy result quantity must be 'total_energy'.")
    backend = _canonical_backend(stored["backend"])
    workflow_metadata = _canonical_workflow_metadata(stored["workflow_metadata"])
    if failed:
        _require_failed_projections(
            best_energy=best_energy,
            param1=param1,
            param2=param2,
            n_points=n_points,
        )
        return {
            "schema": RAW_ENERGY_RESULT_SCHEMA,
            "version": ENERGY_RESULT_VERSION,
            "result_stage": "energy_failed",
            "quantity": "total_energy",
            "backend": backend,
            "workflow_metadata": workflow_metadata,
            "failure": _canonical_failure(stored["failure"]),
        }

    energy = _finite_real("Raw energy result energy_eV", stored["energy_eV"])
    steps = _positive_int("Raw energy result n_steps", stored["n_steps"])
    area = _optional_finite(
        "Raw energy result interface_area_A2", stored["interface_area_A2"]
    )
    area_source = stored["area_source"]
    if target_kind == "interface":
        if area is None or area <= 0.0:
            raise ValueError(
                "Interface raw-energy results require a positive interface_area_A2."
            )
        if area_source != "authoritative_interface_cell":
            raise ValueError(
                "Interface raw-energy results require "
                "area_source='authoritative_interface_cell'."
            )
    elif area is not None or area_source is not None:
        raise ValueError(
            "Prototype raw-energy results require null interface area fields."
        )
    if (
        best_energy is None
        or _finite_real("Raw energy best_energy", best_energy) != energy
    ):
        raise ValueError("Raw energy best_energy must equal energy_eV.")
    if param1 is not None or param2 is not None:
        raise ValueError("Raw energy param1 and param2 must be None.")
    if n_points is None or _positive_int("Raw energy n_points", n_points) != steps:
        raise ValueError("Raw energy n_points must equal n_steps.")
    return {
        "schema": RAW_ENERGY_RESULT_SCHEMA,
        "version": ENERGY_RESULT_VERSION,
        "result_stage": "energy_evaluated",
        "quantity": "total_energy",
        "energy_eV": energy,
        "n_steps": steps,
        "interface_area_A2": area,
        "area_source": area_source,
        "backend": backend,
        "workflow_metadata": workflow_metadata,
        "artifact_refs": _canonical_artifact_refs(stored["artifact_refs"]),
        "summary": _canonical_mapping("Raw energy result summary", stored["summary"]),
    }


def _canonical_reference(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError("Reference-energy result reference must be a mapping.")
    stored = _require_exact_fields(
        "Reference-energy result reference",
        value,
        frozenset({"uid_full", "kind", "side", "formula_id", "metadata"}),
    )
    reference_uid = _nonempty_string(
        "Reference-energy result reference uid_full", stored["uid_full"]
    )
    kind = _nonempty_string("Reference-energy result reference kind", stored["kind"])
    side = _nonempty_string("Reference-energy result reference side", stored["side"])
    if side not in {"a", "b"} or not kind.endswith(f"_{side}"):
        raise ValueError(
            "Reference-energy result side must match the reference-kind suffix."
        )
    formula, _ = canonical_energy_formula(stored["formula_id"])
    if kind not in _REFERENCE_KIND_BY_FORMULA[formula]:
        raise ValueError(
            "Reference-energy result kind is incompatible with formula_id."
        )
    metadata = _canonical_mapping(
        "Reference-energy result metadata", stored["metadata"]
    )
    for duplicate in (
        "source_interface_uid_full",
        "target_uid_full",
        "target_kind",
        "reference_uid_full",
        "reference_kind",
        "side",
        "formula_id",
    ):
        if duplicate in metadata:
            raise ValueError(
                "Reference-energy result metadata contains duplicated identity field "
                f"{duplicate!r}."
            )
    return {
        "uid_full": reference_uid,
        "kind": kind,
        "side": side,
        "formula_id": formula,
        "metadata": metadata,
    }


def _canonical_reference_relaxation(
    value: Any, *, formula: str, failed: bool
) -> dict[str, Any] | None:
    if value is None:
        if formula == "work_of_adhesion_relaxed_surfaces":
            raise ValueError(
                "Relaxed-surface reference results require relaxation provenance."
            )
        return None
    if formula != "work_of_adhesion_relaxed_surfaces":
        raise ValueError(
            "Only relaxed-surface reference results may contain relaxation provenance."
        )
    if not isinstance(value, Mapping):
        raise TypeError("Reference-energy result relaxation must be a mapping or None.")
    stored = _require_exact_fields(
        "Reference-energy result relaxation",
        value,
        frozenset({"settings", "summary", "final_structure_fingerprint"}),
    )
    fingerprint = stored["final_structure_fingerprint"]
    if failed:
        if fingerprint is not None:
            fingerprint = _nonempty_string(
                "Reference-energy final_structure_fingerprint", fingerprint
            )
    else:
        fingerprint = _nonempty_string(
            "Reference-energy final_structure_fingerprint", fingerprint
        )
    return {
        "settings": _canonical_mapping(
            "Reference-energy relaxation settings", stored["settings"]
        ),
        "summary": _canonical_mapping(
            "Reference-energy relaxation summary", stored["summary"]
        ),
        "final_structure_fingerprint": fingerprint,
    }


def _canonical_reference_energy(
    payload: Mapping[str, Any],
    *,
    status: str,
    target_kind: str,
    best_energy: float | None,
    param1: float | None,
    param2: float | None,
    n_points: int | None,
) -> dict[str, Any]:
    if target_kind != "interface":
        raise ValueError("Reference-energy results require an interface target.")
    failed = status == "failed"
    fields = _REFERENCE_FAILED_FIELDS if failed else _REFERENCE_DONE_FIELDS
    stored = _require_exact_fields("Reference-energy result payload", payload, fields)
    _validate_header(
        stored=stored,
        schema=REFERENCE_ENERGY_RESULT_SCHEMA,
        result_stage="reference_failed" if failed else "reference_evaluated",
    )
    reference = _canonical_reference(stored["reference"])
    backend = _canonical_backend(stored["backend"])
    relaxation = _canonical_reference_relaxation(
        stored["relaxation"],
        formula=reference["formula_id"],
        failed=failed,
    )
    workflow_metadata = _canonical_workflow_metadata(stored["workflow_metadata"])
    if failed:
        _require_failed_projections(
            best_energy=best_energy,
            param1=param1,
            param2=param2,
            n_points=n_points,
        )
        return {
            "schema": REFERENCE_ENERGY_RESULT_SCHEMA,
            "version": ENERGY_RESULT_VERSION,
            "result_stage": "reference_failed",
            "reference": reference,
            "backend": backend,
            "relaxation": relaxation,
            "workflow_metadata": workflow_metadata,
            "failure": _canonical_failure(stored["failure"]),
        }

    energy_raw = stored["energy"]
    if not isinstance(energy_raw, Mapping):
        raise TypeError("Reference-energy result energy must be a mapping.")
    energy_stored = _require_exact_fields(
        "Reference-energy result energy",
        energy_raw,
        frozenset({"total_eV", "per_formula_unit_eV", "n_steps"}),
    )
    total = _finite_real("Reference-energy result total_eV", energy_stored["total_eV"])
    per_fu = _optional_finite(
        "Reference-energy result per_formula_unit_eV",
        energy_stored["per_formula_unit_eV"],
    )
    steps = _nonnegative_int(
        "Reference-energy result n_steps", energy_stored["n_steps"]
    )
    metadata = reference["metadata"]
    reference_formula_units = _optional_nonnegative_int(
        "Reference-energy metadata reference_formula_units",
        metadata.get("reference_formula_units"),
    )
    interface_formula_units = _optional_nonnegative_int(
        "Reference-energy metadata interface_formula_units",
        metadata.get("interface_formula_units"),
    )
    if reference["kind"].startswith("strained_bulk_"):
        if reference_formula_units is None or reference_formula_units < 1:
            raise ValueError(
                "Strained-bulk references require positive reference_formula_units."
            )
        if interface_formula_units is None or interface_formula_units < 1:
            raise ValueError(
                "Strained-bulk references require positive interface_formula_units."
            )
        expected_per_fu = total / reference_formula_units
        if per_fu is None or not isclose(
            per_fu, expected_per_fu, rel_tol=1e-12, abs_tol=1e-12
        ):
            raise ValueError(
                "Reference-energy per_formula_unit_eV does not match total_eV and "
                "reference_formula_units."
            )
    elif (
        per_fu is not None
        or reference_formula_units is not None
        or interface_formula_units is not None
    ):
        raise ValueError("Surface reference results require null formula-unit fields.")
    if (
        best_energy is None
        or _finite_real("Reference-energy best_energy", best_energy) != total
    ):
        raise ValueError("Reference-energy best_energy must equal energy.total_eV.")
    if per_fu is None:
        if param1 is not None:
            raise ValueError("Surface reference-energy param1 must be None.")
    elif param1 is None or _finite_real("Reference-energy param1", param1) != per_fu:
        raise ValueError(
            "Reference-energy param1 must equal energy.per_formula_unit_eV."
        )
    expected_param2 = (
        None if interface_formula_units is None else float(interface_formula_units)
    )
    if expected_param2 is None:
        if param2 is not None:
            raise ValueError("Surface reference-energy param2 must be None.")
    elif (
        param2 is None
        or _finite_real("Reference-energy param2", param2) != expected_param2
    ):
        raise ValueError("Reference-energy param2 must equal interface_formula_units.")
    if (
        n_points is None
        or _nonnegative_int("Reference-energy n_points", n_points) != steps
    ):
        raise ValueError("Reference-energy n_points must equal energy.n_steps.")
    return {
        "schema": REFERENCE_ENERGY_RESULT_SCHEMA,
        "version": ENERGY_RESULT_VERSION,
        "result_stage": "reference_evaluated",
        "reference": reference,
        "energy": {
            "total_eV": total,
            "per_formula_unit_eV": per_fu,
            "n_steps": steps,
        },
        "backend": backend,
        "relaxation": relaxation,
        "workflow_metadata": workflow_metadata,
        "artifact_refs": _canonical_artifact_refs(stored["artifact_refs"]),
        "summary": _canonical_mapping(
            "Reference-energy result summary", stored["summary"]
        ),
    }


def _canonical_thermo_source(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError("Thermodynamic result source must be a mapping.")
    stored = _require_exact_fields(
        "Thermodynamic result source",
        value,
        frozenset(
            {"raw_energy_followup_uid", "reference_mode", "reference_run_uid_full"}
        ),
    )
    mode = _nonempty_string(
        "Thermodynamic result reference_mode", stored["reference_mode"]
    )
    if mode not in {"static", "by_target_uid"}:
        raise ValueError(
            "Thermodynamic result reference_mode must be 'static' or 'by_target_uid'."
        )
    run_uid = stored["reference_run_uid_full"]
    if run_uid is not None:
        run_uid = _nonempty_string(
            "Thermodynamic result reference_run_uid_full", run_uid
        )
    if mode == "by_target_uid" and run_uid is None:
        raise ValueError(
            "Target-indexed thermodynamic references require reference_run_uid_full."
        )
    return {
        "raw_energy_followup_uid": _nonempty_string(
            "Thermodynamic result raw_energy_followup_uid",
            stored["raw_energy_followup_uid"],
        ),
        "reference_mode": mode,
        "reference_run_uid_full": run_uid,
    }


def _canonical_thermo_convention(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError("Thermodynamic result convention must be a mapping.")
    stored = _require_exact_fields(
        "Thermodynamic result convention",
        value,
        frozenset({"formula", "quantity", "n_interfaces", "area_source"}),
    )
    formula, quantity = canonical_energy_formula(stored["formula"])
    if stored["quantity"] != quantity:
        raise ValueError(
            "Thermodynamic result convention quantity does not match formula."
        )
    area_source = _nonempty_string(
        "Thermodynamic result convention area_source", stored["area_source"]
    )
    if area_source not in {
        "authoritative_interface_area",
        "prototype_interface_area",
    }:
        raise ValueError(
            "Thermodynamic result convention area_source uses an unsupported value."
        )
    return {
        "formula": formula,
        "quantity": quantity,
        "n_interfaces": positive_interface_multiplicity(stored["n_interfaces"]),
        "area_source": area_source,
    }


def _canonical_thermo_references(
    value: Any,
    *,
    formula: str,
    allow_unresolved: bool,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError("Thermodynamic result references must be a mapping.")
    status = value.get("status")
    if status == "unresolved":
        if not allow_unresolved:
            raise ValueError(
                "Completed thermodynamic results cannot use unresolved references."
            )
        stored = _require_exact_fields(
            "Thermodynamic result references",
            value,
            frozenset({"status", "reason"}),
        )
        return {
            "status": "unresolved",
            "reason": _nonempty_string(
                "Thermodynamic result reference-resolution reason",
                stored["reason"],
            ),
        }
    if status != "resolved":
        raise ValueError(
            "Thermodynamic result references status must be 'resolved' or 'unresolved'."
        )
    stored = _require_exact_fields(
        "Thermodynamic result references",
        value,
        frozenset({"status", "source_kind", "result_uids", "values", "metadata"}),
    )
    source_kind = _nonempty_string(
        "Thermodynamic result reference source_kind", stored["source_kind"]
    )
    if source_kind not in {"manual", "calculated"}:
        raise ValueError(
            "Thermodynamic result reference source_kind must be 'manual' or "
            "'calculated'."
        )
    result_uids_raw = stored["result_uids"]
    if not isinstance(result_uids_raw, Mapping):
        raise TypeError("Thermodynamic result reference result_uids must be a mapping.")
    result_uids = {
        _nonempty_string("Thermodynamic reference kind", key): _nonempty_string(
            f"Thermodynamic reference result UID for {key}", item
        )
        for key, item in result_uids_raw.items()
    }
    required_kinds = _REFERENCE_KIND_BY_FORMULA[formula]
    if source_kind == "calculated":
        if set(result_uids) != set(required_kinds):
            raise ValueError(
                "Calculated thermodynamic references require exactly the current "
                "formula's reference-result identities."
            )
    elif result_uids:
        raise ValueError(
            "Manual thermodynamic references cannot contain reference-result UIDs."
        )

    values_raw = stored["values"]
    if not isinstance(values_raw, Mapping):
        raise TypeError("Thermodynamic result reference values must be a mapping.")
    if formula == "interface_excess_strained_bulk":
        values_stored = _require_exact_fields(
            "Thermodynamic result bulk reference values",
            values_raw,
            frozenset(
                {
                    "bulk_a_eV_per_formula_unit",
                    "bulk_b_eV_per_formula_unit",
                    "n_formula_units_a",
                    "n_formula_units_b",
                }
            ),
        )
        values = {
            "bulk_a_eV_per_formula_unit": _finite_real(
                "Thermodynamic bulk A reference energy",
                values_stored["bulk_a_eV_per_formula_unit"],
            ),
            "bulk_b_eV_per_formula_unit": _finite_real(
                "Thermodynamic bulk B reference energy",
                values_stored["bulk_b_eV_per_formula_unit"],
            ),
            "n_formula_units_a": _positive_int(
                "Thermodynamic n_formula_units_a",
                values_stored["n_formula_units_a"],
            ),
            "n_formula_units_b": _positive_int(
                "Thermodynamic n_formula_units_b",
                values_stored["n_formula_units_b"],
            ),
        }
    else:
        values_stored = _require_exact_fields(
            "Thermodynamic result surface reference values",
            values_raw,
            frozenset({"surface_a_total_energy_eV", "surface_b_total_energy_eV"}),
        )
        values = {
            "surface_a_total_energy_eV": _finite_real(
                "Thermodynamic surface A reference energy",
                values_stored["surface_a_total_energy_eV"],
            ),
            "surface_b_total_energy_eV": _finite_real(
                "Thermodynamic surface B reference energy",
                values_stored["surface_b_total_energy_eV"],
            ),
        }
    return {
        "status": "resolved",
        "source_kind": source_kind,
        "result_uids": result_uids,
        "values": values,
        "metadata": _canonical_mapping(
            "Thermodynamic result reference metadata", stored["metadata"]
        ),
    }


def _matching_finite(name: str, value: Any, expected: float) -> float:
    canonical = _finite_real(name, value)
    if not isclose(canonical, expected, rel_tol=1e-12, abs_tol=1e-12):
        raise ValueError(f"{name} does not match the authoritative calculation.")
    return canonical


def _canonical_thermo_components(
    value: Any,
    *,
    formula: str,
    references: Mapping[str, Any],
    area_A2: float,
    n_interfaces: int,
    value_eV_per_A2: float,
) -> dict[str, float]:
    if references.get("status") != "resolved":
        raise ValueError("Completed thermodynamic results require resolved references.")
    if not isinstance(value, Mapping):
        raise TypeError("Thermodynamic result components must be a mapping.")
    values = references["values"]
    denominator = area_A2 * n_interfaces
    if formula == "interface_excess_strained_bulk":
        fields = frozenset(
            {
                "interface_total_energy_eV",
                "bulk_a_reference_total_eV",
                "bulk_b_reference_total_eV",
                "reference_total_eV",
                "excess_energy_eV",
            }
        )
        stored = _require_exact_fields("Thermodynamic result components", value, fields)
        bulk_a = values["bulk_a_eV_per_formula_unit"] * values["n_formula_units_a"]
        bulk_b = values["bulk_b_eV_per_formula_unit"] * values["n_formula_units_b"]
        reference_total = bulk_a + bulk_b
        interface_total = _finite_real(
            "Thermodynamic interface_total_energy_eV",
            stored["interface_total_energy_eV"],
        )
        excess = interface_total - reference_total
        canonical = {
            "interface_total_energy_eV": interface_total,
            "bulk_a_reference_total_eV": _matching_finite(
                "Thermodynamic bulk_a_reference_total_eV",
                stored["bulk_a_reference_total_eV"],
                bulk_a,
            ),
            "bulk_b_reference_total_eV": _matching_finite(
                "Thermodynamic bulk_b_reference_total_eV",
                stored["bulk_b_reference_total_eV"],
                bulk_b,
            ),
            "reference_total_eV": _matching_finite(
                "Thermodynamic reference_total_eV",
                stored["reference_total_eV"],
                reference_total,
            ),
            "excess_energy_eV": _matching_finite(
                "Thermodynamic excess_energy_eV",
                stored["excess_energy_eV"],
                excess,
            ),
        }
        expected_value = excess / denominator
    else:
        numerator_key = (
            "adhesion_energy_eV"
            if formula == "work_of_adhesion_relaxed_surfaces"
            else "separation_energy_eV"
        )
        fields = frozenset(
            {
                "interface_total_energy_eV",
                "surface_a_total_energy_eV",
                "surface_b_total_energy_eV",
                numerator_key,
            }
        )
        stored = _require_exact_fields("Thermodynamic result components", value, fields)
        surface_a = values["surface_a_total_energy_eV"]
        surface_b = values["surface_b_total_energy_eV"]
        interface_total = _finite_real(
            "Thermodynamic interface_total_energy_eV",
            stored["interface_total_energy_eV"],
        )
        numerator = surface_a + surface_b - interface_total
        canonical = {
            "interface_total_energy_eV": interface_total,
            "surface_a_total_energy_eV": _matching_finite(
                "Thermodynamic surface_a_total_energy_eV",
                stored["surface_a_total_energy_eV"],
                surface_a,
            ),
            "surface_b_total_energy_eV": _matching_finite(
                "Thermodynamic surface_b_total_energy_eV",
                stored["surface_b_total_energy_eV"],
                surface_b,
            ),
            numerator_key: _matching_finite(
                f"Thermodynamic {numerator_key}",
                stored[numerator_key],
                numerator,
            ),
        }
        expected_value = numerator / denominator
    if not isclose(
        value_eV_per_A2,
        expected_value,
        rel_tol=1e-12,
        abs_tol=1e-12,
    ):
        raise ValueError(
            "Thermodynamic quantity does not match its references, components, "
            "and normalization."
        )
    return canonical


def _canonical_thermodynamic(
    payload: Mapping[str, Any],
    *,
    status: str,
    target_kind: str,
    best_energy: float | None,
    param1: float | None,
    param2: float | None,
    n_points: int | None,
) -> dict[str, Any]:
    if target_kind != "interface":
        raise ValueError("Thermodynamic results require an interface target.")
    failed = status == "failed"
    fields = _THERMO_FAILED_FIELDS if failed else _THERMO_DONE_FIELDS
    stored = _require_exact_fields("Thermodynamic result payload", payload, fields)
    _validate_header(
        stored=stored,
        schema=THERMODYNAMIC_RESULT_SCHEMA,
        result_stage="thermodynamic_failed" if failed else "thermodynamic_derived",
    )
    source = _canonical_thermo_source(stored["source"])
    convention = _canonical_thermo_convention(stored["convention"])
    formula = convention["formula"]
    n_interfaces = convention["n_interfaces"]
    references = _canonical_thermo_references(
        stored["references"],
        formula=formula,
        allow_unresolved=failed,
    )
    if references.get("status") == "resolved":
        source_kind = references["source_kind"]
        if source_kind == "calculated":
            if (
                source["reference_mode"] != "by_target_uid"
                or source["reference_run_uid_full"] is None
            ):
                raise ValueError(
                    "Calculated thermodynamic references require a target-indexed "
                    "reference run."
                )
        elif (
            source["reference_mode"] != "static"
            or source["reference_run_uid_full"] is not None
        ):
            raise ValueError(
                "Manual thermodynamic references require static source metadata."
            )
    compatibility = _canonical_calculator_compatibility(
        stored["calculator_compatibility"],
        allow_unresolved=failed,
    )
    if (
        references.get("status") == "resolved"
        and compatibility["status"] != "unresolved"
    ):
        source_kind = references["source_kind"]
        if source_kind == "calculated" and compatibility["status"] != "verified":
            raise ValueError(
                "Calculated thermodynamic references require verified calculator "
                "compatibility."
            )
        if source_kind == "manual" and compatibility["status"] != "manual_unverified":
            raise ValueError(
                "Manual thermodynamic references require manual_unverified "
                "calculator compatibility."
            )
    if failed:
        _require_failed_projections(
            best_energy=best_energy,
            param1=param1,
            param2=param2,
            n_points=n_points,
        )
        area_status = stored["normalization_area_source_status"]
        if area_status is not None:
            area_status = _nonempty_string(
                "Thermodynamic result normalization_area_source_status",
                area_status,
            )
        return {
            "schema": THERMODYNAMIC_RESULT_SCHEMA,
            "version": ENERGY_RESULT_VERSION,
            "result_stage": "thermodynamic_failed",
            "source": source,
            "convention": convention,
            "references": references,
            "calculator_compatibility": compatibility,
            "normalization_area_source_status": area_status,
            "failure": _canonical_failure(stored["failure"]),
        }

    quantity_raw = stored["quantity"]
    if not isinstance(quantity_raw, Mapping):
        raise TypeError("Thermodynamic result quantity must be a mapping.")
    quantity_stored = _require_exact_fields(
        "Thermodynamic result quantity",
        quantity_raw,
        frozenset({"name", "formula_id", "value_eV_per_A2", "value_J_per_m2"}),
    )
    name = _nonempty_string(
        "Thermodynamic result quantity name", quantity_stored["name"]
    )
    quantity_formula, quantity_name = canonical_energy_formula(
        quantity_stored["formula_id"]
    )
    if quantity_formula != formula or name != quantity_name:
        raise ValueError("Thermodynamic result quantity does not match its convention.")
    value_eV = _finite_real(
        "Thermodynamic result value_eV_per_A2",
        quantity_stored["value_eV_per_A2"],
    )
    value_j = _finite_real(
        "Thermodynamic result value_J_per_m2",
        quantity_stored["value_J_per_m2"],
    )
    if not isclose(
        value_j,
        value_eV * EV_PER_A2_TO_J_PER_M2,
        rel_tol=1e-12,
        abs_tol=1e-12,
    ):
        raise ValueError(
            "Thermodynamic result SI value does not match the canonical conversion."
        )
    normalization_raw = stored["normalization"]
    if not isinstance(normalization_raw, Mapping):
        raise TypeError("Thermodynamic result normalization must be a mapping.")
    normalization_stored = _require_exact_fields(
        "Thermodynamic result normalization",
        normalization_raw,
        frozenset({"area_A2", "area_source_status", "n_interfaces"}),
    )
    area = _finite_real(
        "Thermodynamic result normalization area_A2",
        normalization_stored["area_A2"],
    )
    if area <= 0.0:
        raise ValueError("Thermodynamic result normalization area must be positive.")
    area_status = _nonempty_string(
        "Thermodynamic result normalization area_source_status",
        normalization_stored["area_source_status"],
    )
    stored_n_interfaces = positive_interface_multiplicity(
        normalization_stored["n_interfaces"]
    )
    if stored_n_interfaces != n_interfaces:
        raise ValueError(
            "Thermodynamic result normalization n_interfaces does not match convention."
        )
    units_raw = stored["units"]
    if not isinstance(units_raw, Mapping):
        raise TypeError("Thermodynamic result units must be a mapping.")
    units = _require_exact_fields(
        "Thermodynamic result units",
        units_raw,
        frozenset({"primary", "secondary"}),
    )
    if units != {"primary": "eV/angstrom^2", "secondary": "J/m^2"}:
        raise ValueError("Thermodynamic result units use unsupported current values.")
    if (
        best_energy is None
        or _finite_real("Thermodynamic best_energy", best_energy) != value_eV
    ):
        raise ValueError(
            "Thermodynamic best_energy must equal quantity.value_eV_per_A2."
        )
    if param1 is None or _finite_real("Thermodynamic param1", param1) != area:
        raise ValueError("Thermodynamic param1 must equal normalization.area_A2.")
    if param2 is None or _finite_real("Thermodynamic param2", param2) != float(
        n_interfaces
    ):
        raise ValueError("Thermodynamic param2 must equal normalization.n_interfaces.")
    if n_points is None or _positive_int("Thermodynamic n_points", n_points) != 1:
        raise ValueError("Thermodynamic n_points must equal 1.")
    return {
        "schema": THERMODYNAMIC_RESULT_SCHEMA,
        "version": ENERGY_RESULT_VERSION,
        "result_stage": "thermodynamic_derived",
        "source": source,
        "quantity": {
            "name": name,
            "formula_id": formula,
            "value_eV_per_A2": value_eV,
            "value_J_per_m2": value_j,
        },
        "normalization": {
            "area_A2": area,
            "area_source_status": area_status,
            "n_interfaces": n_interfaces,
        },
        "convention": convention,
        "references": references,
        "components": _canonical_thermo_components(
            stored["components"],
            formula=formula,
            references=references,
            area_A2=area,
            n_interfaces=n_interfaces,
            value_eV_per_A2=value_eV,
        ),
        "calculator_compatibility": compatibility,
        "units": {"primary": "eV/angstrom^2", "secondary": "J/m^2"},
    }


def canonical_energy_result_payload(
    *,
    kind: str,
    status: str,
    payload: Mapping[str, Any],
    prototype_uid_full: str | None,
    target_uid_full: str | None,
    target_kind: str | None,
    best_energy: float | None,
    param1: float | None,
    param2: float | None,
    n_points: int | None,
) -> dict[str, Any]:
    """Return one exact current payload and verify its SQL projections."""

    if kind not in ENERGY_RESULT_KINDS:
        raise ValueError(f"Unsupported energy result kind: {kind!r}.")
    canonical_status = _nonempty_string("Energy result status", status)
    if canonical_status not in {"done", "completed", "failed"}:
        raise ValueError(
            "Energy result status must be 'done', 'completed', or 'failed'."
        )
    _prototype_uid, _target_uid, canonical_target_kind = _target_columns(
        prototype_uid_full=prototype_uid_full,
        target_uid_full=target_uid_full,
        target_kind=target_kind,
    )
    if kind == "energy_stage":
        return _canonical_raw_energy(
            payload,
            status=canonical_status,
            target_kind=canonical_target_kind,
            best_energy=best_energy,
            param1=param1,
            param2=param2,
            n_points=n_points,
        )
    if kind == "reference_energy":
        return _canonical_reference_energy(
            payload,
            status=canonical_status,
            target_kind=canonical_target_kind,
            best_energy=best_energy,
            param1=param1,
            param2=param2,
            n_points=n_points,
        )
    return _canonical_thermodynamic(
        payload,
        status=canonical_status,
        target_kind=canonical_target_kind,
        best_energy=best_energy,
        param1=param1,
        param2=param2,
        n_points=n_points,
    )


def energy_result_identity_qualifiers(
    *, kind: str, payload: Mapping[str, Any]
) -> dict[str, Any]:
    """Return the result-specific qualifiers included in persisted identity."""

    if kind == "energy_stage":
        return {}
    if kind == "reference_energy":
        reference = payload.get("reference")
        if not isinstance(reference, Mapping):
            raise ValueError("Reference-energy payload is missing reference identity.")
        return {"reference_kind": str(reference["kind"])}
    if kind == "thermodynamic_quantity":
        source = payload.get("source")
        if not isinstance(source, Mapping):
            raise ValueError("Thermodynamic payload is missing source identity.")
        return {"raw_energy_followup_uid": str(source["raw_energy_followup_uid"])}
    raise ValueError(f"Unsupported energy result kind: {kind!r}.")


__all__ = [
    "ENERGY_RESULT_KINDS",
    "ENERGY_RESULT_VERSION",
    "RAW_ENERGY_RESULT_SCHEMA",
    "REFERENCE_ENERGY_RESULT_SCHEMA",
    "THERMODYNAMIC_RESULT_SCHEMA",
    "canonical_energy_result_payload",
    "energy_result_identity_qualifiers",
]
