"""Shared deterministic contract for authoritative CALM datasets."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from math import isfinite
from numbers import Integral, Real
from typing import Any, Iterable, Mapping

from calm.serialization.json import canonical_json as _canonical_json


class DatasetIdentityConflictError(ValueError):
    """A dataset name or deterministic identity conflicts with persisted state."""


DATASET_CONTENT_FINGERPRINT_VERSION = 1

DATASET_SPLIT_POLICY = "sha256_decimal_seed_colon_group_utf8_prefix64"
DATASET_SPLIT_POLICY_VERSION = 2
DATASET_SPLIT_HASH_ALGORITHM = "sha256"
DATASET_SPLIT_HASH_PREFIX_BYTES = 8
DATASET_SPLIT_UNIT_DENOMINATOR = 2**64
DATASET_SPLIT_INTERVAL_POLICY = "half_open_train_validation_test"
DATASET_SPLIT_COORDINATE_POLICY = "unsigned_big_endian_prefix64_divide_2_pow_64"
DATASET_SPLIT_V2_COMPARISON_POLICY = "exact_u64_ratio_vs_binary64_threshold_ratios"
DATASET_SPLIT_COMPLETE_STATUS = "complete_v2"
DATASET_SPLIT_INVALID_STATUS = "invalid"

_DATASET_STORAGE_FIELDS = {
    "authority",
    "created_at",
    "dataset_index",
    "dataset_uid_full",
    "id_short",
    "index",
    "project_dataset_id",
    "project_dataset_item_id",
    "project_dataset_item_uid",
    "project_dataset_uid",
    "uid_full",
}

DATASET_SCHEMAS: dict[str, dict[str, Any]] = {
    "calm.interface_learning.v1": {
        "source_kind": "joined_interface_record",
        "required_fields": (
            "source_uid_full",
            "source_kind",
            "interface_uid_full",
            "prototype_uid_full",
            "relaxation_followup_uid",
            "raw_energy_followup_uid",
            "features",
            "targets",
            "group_id",
            "split",
            "provenance",
        ),
    },
    "calm.interface.v1": {
        "source_kind": "interface",
        "required_fields": (
            "source_uid_full",
            "source_kind",
            "interface_uid_full",
            "prototype_uid_full",
            "stage",
        ),
    },
    "calm.raw_energy.v1": {
        "source_kind": "raw_energy",
        "required_fields": (
            "source_uid_full",
            "source_kind",
            "run_uid_full",
            "interface_uid_full",
            "prototype_uid_full",
            "quantity",
            "energy_eV",
            "units",
            "backend_identity",
        ),
    },
    "calm.thermodynamic.v1": {
        "source_kind": "thermodynamic_quantity",
        "required_fields": (
            "source_uid_full",
            "source_kind",
            "run_uid_full",
            "interface_uid_full",
            "prototype_uid_full",
            "raw_energy_followup_uid",
            "quantity",
            "formula_id",
            "value_eV_per_A2",
            "value_J_per_m2",
            "normalization_area_A2",
            "n_interfaces",
            "convention",
            "references",
        ),
    },
}


def canonical_dataset_schema(value: str) -> str:
    """Return one exact current dataset schema identifier."""

    if not isinstance(value, str):
        raise TypeError("Dataset schema must be a string.")
    if value != value.strip():
        raise ValueError("Dataset schema must not have surrounding whitespace.")
    if value not in DATASET_SCHEMAS:
        raise ValueError(
            "Unsupported dataset schema. Expected one of: "
            + ", ".join(sorted(DATASET_SCHEMAS))
        )
    return value


def dataset_schema_contract(value: str) -> Mapping[str, Any]:
    return DATASET_SCHEMAS[canonical_dataset_schema(value)]


def dataset_group_uid(group_by: Mapping[str, Any]) -> str:
    """Return the deterministic identity for one leakage-control group."""

    values = dict(group_by)
    if not values or any(value is None for value in values.values()):
        raise ValueError("Dataset group values must be non-empty and complete.")
    digest = hashlib.sha256(_canonical_json(values).encode("utf-8")).hexdigest()
    return f"dataset_group:{digest}"


@dataclass(frozen=True)
class DatasetSplitDecision:
    """Reconstructible assignment of one leakage-control group."""

    policy_version: int
    group_id: str
    seed: int
    input_bytes_hex: str
    sha256_hex: str
    hash_prefix_hex: str
    hash_prefix_u64: int
    unit_coordinate: float
    split_name: str
    train_fraction: float
    validation_fraction: float
    test_fraction: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy": DATASET_SPLIT_POLICY,
            "policy_version": self.policy_version,
            "hash_algorithm": DATASET_SPLIT_HASH_ALGORITHM,
            "hash_prefix_bytes": DATASET_SPLIT_HASH_PREFIX_BYTES,
            "coordinate_policy": DATASET_SPLIT_COORDINATE_POLICY,
            "comparison_policy": DATASET_SPLIT_V2_COMPARISON_POLICY,
            "interval_policy": DATASET_SPLIT_INTERVAL_POLICY,
            "group_id": self.group_id,
            "seed": self.seed,
            "input_bytes_hex": self.input_bytes_hex,
            "sha256_hex": self.sha256_hex,
            "hash_prefix_hex": self.hash_prefix_hex,
            "hash_prefix_u64": str(self.hash_prefix_u64),
            "unit_denominator": str(DATASET_SPLIT_UNIT_DENOMINATOR),
            "unit_coordinate": self.unit_coordinate,
            "unit_coordinate_hex": self.unit_coordinate.hex(),
            "fractions": {
                "train": self.train_fraction,
                "validation": self.validation_fraction,
                "test": self.test_fraction,
            },
            "split": self.split_name,
        }


def dataset_split_contract() -> dict[str, Any]:
    """Return the self-describing current grouped-split contract."""

    return {
        "policy": DATASET_SPLIT_POLICY,
        "policy_version": DATASET_SPLIT_POLICY_VERSION,
        "input_grammar": "ascii_decimal_seed + b':' + utf8_group_id",
        "seed_encoding": "canonical_base10_integer_without_plus_or_leading_zeroes",
        "group_id_encoding": "utf8_exact_string_bytes",
        "hash_algorithm": DATASET_SPLIT_HASH_ALGORITHM,
        "hash_prefix_bytes": DATASET_SPLIT_HASH_PREFIX_BYTES,
        "hash_prefix_byte_order": "big",
        "coordinate_policy": DATASET_SPLIT_COORDINATE_POLICY,
        "comparison_policy": DATASET_SPLIT_V2_COMPARISON_POLICY,
        "unit_denominator": str(DATASET_SPLIT_UNIT_DENOMINATOR),
        "interval_policy": DATASET_SPLIT_INTERVAL_POLICY,
        "intervals": {
            "train": "[0, train_fraction)",
            "validation": ("[train_fraction, train_fraction + validation_fraction)"),
            "test": "[train_fraction + validation_fraction, 1)",
        },
        "assignment_scope": "whole_leakage_control_group",
        "prototype_closure_required": True,
    }


def _dataset_split_policy_version(split: Mapping[str, Any]) -> int:
    if "policy_version" not in split:
        raise ValueError("Dataset split settings must declare policy_version=2.")
    value = split["policy_version"]
    if not isinstance(value, Integral) or isinstance(value, bool):
        raise TypeError("Dataset split policy_version must be an integer.")
    version = int(value)
    if version != DATASET_SPLIT_POLICY_VERSION:
        raise ValueError(
            "Unsupported dataset split policy_version; expected "
            f"{DATASET_SPLIT_POLICY_VERSION}."
        )
    return version


def _dataset_split_fractions(split: Mapping[str, Any]) -> tuple[float, float, float]:
    raw = (
        split["train_fraction"],
        split["validation_fraction"],
        split["test_fraction"],
    )
    if any(isinstance(value, bool) or not isinstance(value, Real) for value in raw):
        raise TypeError("Dataset split fractions must be real numbers.")
    fractions = tuple(float(value) for value in raw)
    if any(not isfinite(value) or value < 0.0 for value in fractions):
        raise ValueError("Dataset split fractions must be finite and non-negative.")
    if abs(sum(fractions) - 1.0) > 1.0e-12:
        raise ValueError("Dataset split fractions must sum to 1.0.")
    return fractions


def _dataset_split_seed(split: Mapping[str, Any]) -> int:
    seed = split["seed"]
    if not isinstance(seed, Integral) or isinstance(seed, bool):
        raise TypeError("Dataset split seed must be an integer.")
    return int(seed)


def dataset_split_input_bytes(*, seed: int, group_id: str) -> bytes:
    """Return the exact bytes hashed by the current split policy."""

    if not isinstance(seed, Integral) or isinstance(seed, bool):
        raise TypeError("Dataset split seed must be an integer.")
    if not isinstance(group_id, str) or not group_id.strip():
        raise ValueError("Dataset split group_id must be a non-empty string.")
    return str(int(seed)).encode("ascii") + b":" + group_id.encode("utf-8")


def _u64_coordinate_less_than_binary64_threshold(
    prefix_u64: int,
    threshold: float,
) -> bool:
    numerator, denominator = float(threshold).as_integer_ratio()
    return prefix_u64 * denominator < numerator * DATASET_SPLIT_UNIT_DENOMINATOR


def _dataset_split_name_from_prefix_u64(
    prefix_u64: int,
    *,
    train_fraction: float,
    validation_fraction: float,
) -> str:
    """Map one unsigned 64-bit prefix through the current half-open policy."""

    if isinstance(prefix_u64, bool) or not isinstance(prefix_u64, Integral):
        raise TypeError("Dataset split hash prefix must be an integer.")
    prefix = int(prefix_u64)
    if prefix < 0 or prefix >= DATASET_SPLIT_UNIT_DENOMINATOR:
        raise ValueError("Dataset split hash prefix must be in [0, 2**64).")
    validation_end = float(train_fraction + validation_fraction)
    if _u64_coordinate_less_than_binary64_threshold(prefix, train_fraction):
        return "train"
    if _u64_coordinate_less_than_binary64_threshold(prefix, validation_end):
        return "validation"
    return "test"


def dataset_split_decision(
    *,
    group_id: str,
    split: Mapping[str, Any],
) -> DatasetSplitDecision:
    """Return the exact versioned hash, coordinate, and split assignment."""

    train_fraction, validation_fraction, test_fraction = _dataset_split_fractions(split)
    policy_version = _dataset_split_policy_version(split)
    seed = _dataset_split_seed(split)
    input_bytes = dataset_split_input_bytes(seed=seed, group_id=group_id)
    digest = hashlib.sha256(input_bytes).digest()
    prefix_bytes = digest[:DATASET_SPLIT_HASH_PREFIX_BYTES]
    prefix_u64 = int.from_bytes(prefix_bytes, "big", signed=False)
    coordinate = prefix_u64 / float(DATASET_SPLIT_UNIT_DENOMINATOR)
    split_name = _dataset_split_name_from_prefix_u64(
        prefix_u64,
        train_fraction=train_fraction,
        validation_fraction=validation_fraction,
    )
    return DatasetSplitDecision(
        policy_version=policy_version,
        group_id=group_id,
        seed=seed,
        input_bytes_hex=input_bytes.hex(),
        sha256_hex=digest.hex(),
        hash_prefix_hex=prefix_bytes.hex(),
        hash_prefix_u64=prefix_u64,
        unit_coordinate=coordinate,
        split_name=split_name,
        train_fraction=train_fraction,
        validation_fraction=validation_fraction,
        test_fraction=test_fraction,
    )


def dataset_split_name(
    *,
    group_id: str,
    split: Mapping[str, Any],
) -> str:
    """Assign one whole group under the selected split contract."""

    return dataset_split_decision(group_id=group_id, split=split).split_name


def dataset_split_provenance_status(
    value: Any,
    *,
    group_id: str,
    split: Mapping[str, Any],
) -> str:
    """Classify persisted split provenance under the current contract."""

    if not isinstance(value, Mapping):
        return DATASET_SPLIT_INVALID_STATUS
    try:
        expected = dataset_split_decision(group_id=group_id, split=split).to_dict()
    except (KeyError, TypeError, ValueError, OverflowError):
        return DATASET_SPLIT_INVALID_STATUS
    if dict(value) != expected:
        return DATASET_SPLIT_INVALID_STATUS
    return DATASET_SPLIT_COMPLETE_STATUS


def canonical_dataset_item_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    """Remove storage coordinates from one scientific dataset-item payload."""

    if any(not isinstance(key, str) for key in row):
        raise TypeError("Dataset item payload keys must be strings.")
    payload = {
        key: value
        for key, value in row.items()
        if key not in _DATASET_STORAGE_FIELDS and not key.endswith("_id_short")
    }
    refs = payload.get("artifact_refs")
    if isinstance(refs, (list, tuple)):
        payload["artifact_refs"] = sorted(refs, key=_canonical_json)
    return payload


def dataset_content_fingerprint(
    *,
    schema: str,
    settings: Mapping[str, Any],
    rows: Iterable[Mapping[str, Any]],
) -> str:
    """Fingerprint scientific membership independently of retrieval ordering."""

    items = [canonical_dataset_item_payload(row) for row in rows]
    items.sort(
        key=lambda row: (
            str(row.get("source_uid_full") or ""),
            _canonical_json(row),
        )
    )
    payload = {
        "fingerprint_version": DATASET_CONTENT_FINGERPRINT_VERSION,
        "schema_version": canonical_dataset_schema(schema),
        "settings": dict(settings),
        "items": items,
    }
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return f"dataset_content:{digest}"


def _finite_float(value: Any) -> bool:
    try:
        return not isinstance(value, bool) and isfinite(float(value))
    except (TypeError, ValueError, OverflowError):
        return False


def _exact_integer(value: Any, *, positive: bool = False) -> bool:
    if isinstance(value, bool):
        return False
    try:
        result = int(value)
        exact = isfinite(float(value)) and float(value) == float(result)
    except (TypeError, ValueError, OverflowError):
        return False
    return exact and (not positive or result > 0)


def _declared_dtype_matches(value: Any, dtype: str) -> bool:
    if dtype == "bool":
        return isinstance(value, bool)
    if dtype == "str":
        return isinstance(value, str)
    if dtype == "int":
        return _exact_integer(value)
    if dtype == "float":
        return _finite_float(value)
    return False


def _declaration_mapping(
    declarations: Any,
    *,
    container_name: str,
) -> tuple[dict[str, Mapping[str, Any]] | None, list[str]]:
    if not isinstance(declarations, (list, tuple)):
        return None, [f"dataset settings {container_name!r} must be a sequence"]
    declared = {
        str(declaration.get("name")): declaration
        for declaration in declarations
        if isinstance(declaration, Mapping) and declaration.get("name")
    }
    return declared, []


def _declared_value_message(
    *,
    name: str,
    declaration: Mapping[str, Any],
    value: Any,
    container_name: str,
) -> str | None:
    singular = container_name[:-1]
    if value is None:
        if bool(declaration.get("required", True)):
            return f"declared {singular} {name!r} is missing"
        return None
    dtype = str(declaration.get("dtype") or "float")
    if _declared_dtype_matches(value, dtype):
        return None
    return f"declared {singular} {name!r} must be {dtype}"


def _declared_value_messages(
    values: Any,
    declarations: Any,
    *,
    container_name: str,
) -> list[str]:
    if not isinstance(values, Mapping):
        return []
    declared, messages = _declaration_mapping(
        declarations,
        container_name=container_name,
    )
    if declared is None:
        return messages
    if set(values) != set(declared):
        return [
            f"field {container_name!r} keys must match declared names "
            f"{sorted(declared)!r}"
        ]
    return [
        message
        for name, declaration in declared.items()
        if (
            message := _declared_value_message(
                name=name,
                declaration=declaration,
                value=values.get(name),
                container_name=container_name,
            )
        )
        is not None
    ]


def _relaxation_provenance_messages(value: Any) -> list[str]:
    if not isinstance(value, Mapping):
        return ["provenance.relaxation must be a mapping"]
    messages: list[str] = []
    if value.get("scientific_authority") != "calculator_backed":
        messages.append("relaxation provenance must be calculator-backed")
    if value.get("converged") is not True:
        messages.append("relaxation provenance must record converged=True")
    if value.get("residual_satisfied") is not True:
        messages.append("relaxation provenance must record residual_satisfied=True")
    return messages


def _raw_energy_provenance_messages(value: Any) -> list[str]:
    if not isinstance(value, Mapping):
        return ["provenance.raw_energy must be a mapping"]
    messages: list[str] = []
    if value.get("scientific_authority") != "calculator_backed":
        messages.append("raw-energy provenance must be calculator-backed")
    if not _finite_float(value.get("energy_eV")):
        messages.append("raw-energy provenance must record a finite energy_eV")
    return messages


def _thermodynamic_identity_messages(value: Mapping[str, Any]) -> list[str]:
    messages: list[str] = []
    if not value.get("quantity"):
        messages.append("thermodynamic provenance must record quantity")
    if not value.get("formula_id"):
        messages.append("thermodynamic provenance must record formula_id")
    if not isinstance(value.get("convention"), Mapping) or not value.get("convention"):
        messages.append("thermodynamic provenance must record convention")
    if not isinstance(value.get("units"), Mapping) or not value.get("units"):
        messages.append("thermodynamic provenance must record units")
    return messages


def _thermodynamic_reference_messages(value: Mapping[str, Any]) -> list[str]:
    messages: list[str] = []
    compatibility = value.get("calculator_compatibility")
    verification = value.get("verification_status")
    if verification != "verified":
        messages.append(
            "thermodynamic provenance must have verification_status='verified'"
        )
    if not isinstance(compatibility, Mapping) or not compatibility:
        messages.append("thermodynamic provenance must record calculator_compatibility")
    elif compatibility.get("status") != verification:
        messages.append(
            "thermodynamic verification_status must match calculator compatibility"
        )
    reference_source = value.get("reference_source")
    if not isinstance(reference_source, Mapping) or not reference_source.get("mode"):
        messages.append("thermodynamic provenance must record reference_source mode")
    if (
        value.get("formula_id") == "work_of_adhesion_relaxed_surfaces"
        and isinstance(compatibility, Mapping)
        and not compatibility.get("reference_protocol")
    ):
        messages.append(
            "relaxed work-of-adhesion provenance must record reference_protocol"
        )
    return messages


def _thermodynamic_measure_messages(value: Mapping[str, Any]) -> list[str]:
    messages: list[str] = []
    area = value.get("normalization_area_A2")
    if not _finite_float(area) or float(area or 0.0) <= 0.0:
        messages.append(
            "thermodynamic provenance must record a positive finite "
            "normalization_area_A2"
        )
    if not _exact_integer(value.get("n_interfaces"), positive=True):
        messages.append(
            "thermodynamic provenance must record a positive integer n_interfaces"
        )
    return messages


def _thermodynamic_provenance_messages(value: Any) -> list[str]:
    if not isinstance(value, Mapping):
        return ["provenance.thermodynamic must be a mapping"]
    messages = _thermodynamic_identity_messages(value)
    messages.extend(_thermodynamic_reference_messages(value))
    messages.extend(_thermodynamic_measure_messages(value))
    return messages


def _scientific_provenance_messages(provenance: Any, terminal_kind: Any) -> list[str]:
    if not isinstance(provenance, Mapping):
        return []
    messages = _relaxation_provenance_messages(provenance.get("relaxation"))
    messages.extend(_raw_energy_provenance_messages(provenance.get("raw_energy")))
    if terminal_kind == "thermodynamic_quantity":
        messages.extend(
            _thermodynamic_provenance_messages(provenance.get("thermodynamic"))
        )
    return messages


def _joined_lineage_messages(
    row: Mapping[str, Any],
    provenance: Mapping[str, Any],
    group_by: Mapping[str, Any],
) -> list[str]:
    messages: list[str] = []
    lineage_fields = {
        "prototype_uid_full": "prototype_uid_full",
        "relaxed_interface_uid_full": "interface_uid_full",
        "relaxation_followup_uid": "relaxation_followup_uid",
        "raw_energy_followup_uid": "raw_energy_followup_uid",
        "thermodynamic_followup_uid": "thermodynamic_followup_uid",
        "terminal_source_uid_full": "source_uid_full",
    }
    for provenance_key, row_key in lineage_fields.items():
        expected = row.get(row_key)
        actual = provenance.get(provenance_key)
        if expected is None and actual is None:
            continue
        if str(actual or "") != str(expected or ""):
            messages.append(f"provenance.{provenance_key} must match field {row_key!r}")

    aliases = {
        "lineage.prototype": row.get("prototype_uid_full"),
        "lineage.relaxed_interface": row.get("interface_uid_full"),
        "lineage.relaxation_result": row.get("relaxation_followup_uid"),
        "lineage.raw_energy_result": row.get("raw_energy_followup_uid"),
        "lineage.thermodynamic_result": row.get("thermodynamic_followup_uid"),
        "lineage.terminal_source": row.get("source_uid_full"),
    }
    for path, expected in aliases.items():
        if path not in group_by:
            continue
        if str(group_by.get(path) or "") != str(expected or ""):
            messages.append(
                f"group value {path!r} must match authoritative joined lineage"
            )
    return messages


def _group_split_message(
    *,
    group_id: str,
    split_name: str,
    group_splits: dict[str, str],
) -> str | None:
    if not group_id or not split_name:
        return None
    previous_split = group_splits.setdefault(group_id, split_name)
    if previous_split == split_name:
        return None
    return f"group {group_id!r} occurs in both {previous_split!r} and {split_name!r}"


def _prototype_group_message(
    *,
    prototype_uid: str,
    group_id: str,
    source_uid: str,
    prototype_groups: dict[str, str],
) -> str | None:
    if not prototype_uid or not group_id:
        return None
    previous_group = prototype_groups.setdefault(prototype_uid, group_id)
    if previous_group == group_id:
        return None
    return (
        f"prototype {prototype_uid!r} is fragmented across groups "
        f"{previous_group!r} and {group_id!r} at source {source_uid!r}"
    )


def _raw_lineage_duplicate_message(
    *,
    raw_uid: str,
    source_uid: str,
    raw_sources: dict[str, str],
) -> str | None:
    if not raw_uid:
        return None
    previous_source = raw_sources.setdefault(raw_uid, source_uid)
    if previous_source == source_uid:
        return None
    return (
        f"raw-energy lineage {raw_uid!r} occurs under multiple terminal sources "
        f"{previous_source!r} and {source_uid!r}"
    )


def _mapping_path(value: Any, key: str) -> Any:
    if not isinstance(value, Mapping):
        return None
    return value.get(key)


def _thermodynamic_semantics_signature(row: Mapping[str, Any]) -> str | None:
    if row.get("terminal_source_kind") != "thermodynamic_quantity":
        return None
    provenance = row.get("provenance")
    thermo = _mapping_path(provenance, "thermodynamic")
    if not isinstance(thermo, Mapping):
        return None
    reference_source = thermo.get("reference_source")
    compatibility = thermo.get("calculator_compatibility")
    return _canonical_json(
        {
            "quantity": thermo.get("quantity"),
            "formula_id": thermo.get("formula_id"),
            "n_interfaces": thermo.get("n_interfaces"),
            "convention": thermo.get("convention"),
            "units": thermo.get("units"),
            "reference_mode": _mapping_path(reference_source, "mode"),
            "reference_protocol": _mapping_path(
                compatibility,
                "reference_protocol",
            ),
        }
    )


def validate_learning_dataset_collection(
    rows: Iterable[Mapping[str, Any]],
) -> list[str]:
    """Return cross-row leakage and target-semantics violations."""

    messages: list[str] = []
    group_splits: dict[str, str] = {}
    prototype_groups: dict[str, str] = {}
    raw_sources: dict[str, str] = {}
    thermodynamic_semantics: str | None = None

    for row in rows:
        source_uid = str(row.get("source_uid_full") or "<unknown>")
        group_id = str(row.get("group_id") or "")
        split_name = str(row.get("split") or "")
        prototype_uid = str(row.get("prototype_uid_full") or "")
        for message in (
            _group_split_message(
                group_id=group_id,
                split_name=split_name,
                group_splits=group_splits,
            ),
            _prototype_group_message(
                prototype_uid=prototype_uid,
                group_id=group_id,
                source_uid=source_uid,
                prototype_groups=prototype_groups,
            ),
            _raw_lineage_duplicate_message(
                raw_uid=str(row.get("raw_energy_followup_uid") or ""),
                source_uid=source_uid,
                raw_sources=raw_sources,
            ),
        ):
            if message is not None:
                messages.append(message)

        signature = _thermodynamic_semantics_signature(row)
        if signature is None:
            continue
        if thermodynamic_semantics is None:
            thermodynamic_semantics = signature
        elif thermodynamic_semantics != signature:
            messages.append(
                "thermodynamic target semantics differ across joined rows; "
                f"source {source_uid!r} has a different formula, convention, "
                "unit, interface-count, or reference protocol"
            )
    return messages


def _failed_row(row: Mapping[str, Any]) -> bool:
    return bool(row.get("failure")) or row.get("status") in {
        "failed",
        "error",
        "skipped",
    }


def _missing_value(value: Any) -> bool:
    return value is None or value == "" or value == {} or value == []


def _required_field_messages(
    row: Mapping[str, Any],
    *,
    required_fields: Iterable[str],
    failed: bool,
    allow_failed: bool,
) -> list[str]:
    failed_minimum = {
        "source_uid_full",
        "source_kind",
        "run_uid_full",
        "interface_uid_full",
        "prototype_uid_full",
        "raw_energy_followup_uid",
    }
    return [
        f"required field {field!r} is missing"
        for field in required_fields
        if not (failed and allow_failed and field not in failed_minimum)
        if _missing_value(row.get(field))
    ]


def _schema_identity_messages(
    row: Mapping[str, Any],
    *,
    canonical: str,
    source_kind: str,
) -> list[str]:
    messages: list[str] = []
    if row.get("schema_version") != canonical:
        messages.append(
            f"schema_version must be {canonical!r}, got {row.get('schema_version')!r}"
        )
    if row.get("source_kind") != source_kind:
        messages.append(
            "source_kind does not match dataset schema: "
            f"expected {source_kind!r}, got {row.get('source_kind')!r}"
        )
    return messages


def _numeric_field_messages(row: Mapping[str, Any]) -> list[str]:
    messages: list[str] = []
    for field in (
        "energy_eV",
        "value_eV_per_A2",
        "value_J_per_m2",
        "normalization_area_A2",
    ):
        value = row.get(field)
        if value is None:
            continue
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError):
            messages.append(f"field {field!r} must be numeric")
            continue
        if not isfinite(number):
            messages.append(f"field {field!r} must be finite")
        if field == "normalization_area_A2" and number <= 0.0:
            messages.append("normalization_area_A2 must be positive")
    return messages


def _mapping_field_messages(row: Mapping[str, Any]) -> list[str]:
    return [
        f"field {container_name!r} must be a mapping"
        for container_name in ("features", "targets")
        if row.get(container_name) is not None
        and not isinstance(row.get(container_name), Mapping)
    ]


def _group_assignment_messages(
    row: Mapping[str, Any],
    *,
    settings: Mapping[str, Any],
    group_by: Mapping[str, Any],
    group_id: Any,
) -> list[str]:
    declared_group_by = tuple(str(value) for value in (settings.get("group_by") or []))
    if set(group_by) != set(declared_group_by):
        return ["field 'group_by' keys must match the dataset declaration"]
    try:
        expected_group = dataset_group_uid(group_by)
    except (TypeError, ValueError) as exc:
        return [str(exc)]

    messages: list[str] = []
    if group_id != expected_group:
        messages.append("field 'group_id' does not match declared group values")
    split_settings = settings.get("split")
    if not isinstance(split_settings, Mapping):
        return messages
    try:
        expected_split = dataset_split_name(
            group_id=expected_group,
            split=split_settings,
        )
    except (KeyError, TypeError, ValueError) as exc:
        messages.append(f"invalid dataset split settings: {exc}")
        return messages
    if row.get("split") != expected_split:
        messages.append(
            "field 'split' does not match the deterministic group assignment"
        )
    return messages


def _split_provenance_messages(
    row: Mapping[str, Any],
    *,
    settings: Mapping[str, Any],
    group_id: Any,
) -> list[str]:
    split_settings = settings.get("split")
    if not isinstance(split_settings, Mapping):
        return []
    if not isinstance(group_id, str) or not group_id.strip():
        return []
    status = dataset_split_provenance_status(
        row.get("split_provenance"),
        group_id=group_id,
        split=split_settings,
    )
    recorded = row.get("split_contract_status")
    messages: list[str] = []
    if recorded is not None and recorded != status:
        messages.append("field 'split_contract_status' does not match split provenance")
    if status == DATASET_SPLIT_INVALID_STATUS:
        messages.append(
            "field 'split_provenance' does not match the deterministic split contract"
        )
    return messages


def _learning_item_messages(
    row: Mapping[str, Any],
    *,
    settings: Mapping[str, Any] | None,
) -> list[str]:
    messages: list[str] = []
    group_by = row.get("group_by")
    provenance = row.get("provenance")
    group_id = row.get("group_id")
    if not isinstance(group_by, Mapping) or not group_by:
        messages.append("field 'group_by' must be a non-empty mapping")
    if not isinstance(provenance, Mapping) or not provenance:
        messages.append("field 'provenance' must be a non-empty mapping")
    if row.get("split") not in {"train", "validation", "test"}:
        messages.append("field 'split' must be train, validation, or test")
    if not isinstance(group_id, str) or not group_id.strip():
        messages.append("field 'group_id' must be a non-empty string")
    messages.extend(
        _scientific_provenance_messages(
            provenance,
            row.get("terminal_source_kind"),
        )
    )
    if isinstance(provenance, Mapping) and isinstance(group_by, Mapping):
        messages.extend(_joined_lineage_messages(row, provenance, group_by))
    if settings is None:
        return messages
    if isinstance(group_by, Mapping):
        messages.extend(
            _group_assignment_messages(
                row,
                settings=settings,
                group_by=group_by,
                group_id=group_id,
            )
        )
    messages.extend(
        _split_provenance_messages(
            row,
            settings=settings,
            group_id=group_id,
        )
    )
    for container_name in ("features", "targets"):
        messages.extend(
            _declared_value_messages(
                row.get(container_name),
                settings.get(container_name),
                container_name=container_name,
            )
        )
    return messages


def _n_interfaces_messages(row: Mapping[str, Any]) -> list[str]:
    value = row.get("n_interfaces")
    if value is None or _exact_integer(value, positive=True):
        return []
    return ["n_interfaces must be a positive integer"]


def validate_dataset_item_values(
    row: Mapping[str, Any],
    *,
    schema: str,
    allow_failed: bool = False,
    settings: Mapping[str, Any] | None = None,
) -> list[str]:
    """Return value-level validation messages for one canonical item row."""

    canonical = canonical_dataset_schema(schema)
    contract = DATASET_SCHEMAS[canonical]
    messages = _required_field_messages(
        row,
        required_fields=contract["required_fields"],
        failed=_failed_row(row),
        allow_failed=allow_failed,
    )
    messages.extend(
        _schema_identity_messages(
            row,
            canonical=canonical,
            source_kind=str(contract["source_kind"]),
        )
    )
    messages.extend(_numeric_field_messages(row))
    messages.extend(_mapping_field_messages(row))
    if canonical == "calm.interface_learning.v1":
        messages.extend(_learning_item_messages(row, settings=settings))
    messages.extend(_n_interfaces_messages(row))
    return messages
