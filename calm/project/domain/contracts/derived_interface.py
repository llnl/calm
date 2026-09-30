"""Exact-current persisted contract for derived-interface specifications."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import isfinite
from numbers import Real
from typing import Any

from calm.project.domain.contracts.strain_state import canonical_strain_state

DERIVED_INTERFACE_SPEC_VERSION = 1
DERIVED_INTERFACE_SPEC_SCHEMA = "calm.derived_interface"
DERIVED_INTERFACE_STAGES = frozenset(
    {"built", "strain_partitioned", "registry_refined", "relaxed"}
)

_REQUIRED_FIELDS = frozenset(
    {
        "version",
        "schema",
        "prototype",
        "stage",
        "strain_alpha",
        "registry_shift_frac_a",
        "z_padding",
        "vacuum",
        "params",
    }
)
_OPTIONAL_FIELDS = frozenset({"strain_state", "atoms_artifact_uid", "artifact_refs"})
_ALLOWED_FIELDS = _REQUIRED_FIELDS | _OPTIONAL_FIELDS
_RESERVED_PARAM_FIELDS = frozenset(
    {
        "version",
        "schema",
        "schema_version",
        "prototype",
        "prototype_uid",
        "prototype_uid_full",
        "candidate_uid",
        "build_uid",
        "stage",
        "kind",
        "refinement_stage",
        "strain_alpha",
        "alpha",
        "partition_alpha",
        "registry_shift_frac_a",
        "registry_shift_frac_b",
        "registry_shift",
        "translation",
        "translation_frac",
        "lateral_shift",
        "z_padding",
        "gap",
        "interface_gap",
        "separation",
        "vacuum",
        "strain_state",
        "strain_tensor",
        "deformation_gradient",
        "atoms",
        "structure",
        "atoms_json",
        "payload_json",
        "parent_uid",
        "parent_interface_uid",
    }
)


def canonical_interface_stage(value: Any) -> str:
    """Return one exact current interface stage."""

    if not isinstance(value, str):
        raise TypeError("Derived-interface stage must be a string.")
    if value not in DERIVED_INTERFACE_STAGES:
        allowed = ", ".join(sorted(DERIVED_INTERFACE_STAGES))
        raise ValueError(
            f"Unsupported derived-interface stage {value!r}; expected one of: {allowed}."
        )
    return value


def _nonempty_string(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise TypeError(f"{name} must be a non-empty, whitespace-trimmed string.")
    return value


def _finite_real(name: str, value: Any, *, nonnegative: bool) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{name} must be a finite real number.")
    result = float(value)
    if not isfinite(result):
        raise ValueError(f"{name} must be finite.")
    if nonnegative and result < 0.0:
        raise ValueError(f"{name} must be non-negative.")
    return result


def _canonical_json_value(name: str, value: Any) -> Any:
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError(f"{name} must not contain non-finite values.")
        return value
    if isinstance(value, list):
        return [
            _canonical_json_value(f"{name}[{index}]", item)
            for index, item in enumerate(value)
        ]
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            canonical_key = _nonempty_string(f"{name} key", key)
            result[canonical_key] = _canonical_json_value(
                f"{name}.{canonical_key}",
                item,
            )
        return result
    raise TypeError(f"{name} must contain only JSON-native values.")


def canonical_registry_shift(value: Any) -> list[float]:
    """Return a unique two-component coordinate on the fractional torus."""

    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError("registry_shift_frac_a must be a two-value sequence.")
    if len(value) != 2:
        raise ValueError("registry_shift_frac_a must contain exactly two values.")
    components = [
        _finite_real(
            f"registry_shift_frac_a[{index}]",
            component,
            nonnegative=False,
        )
        for index, component in enumerate(value)
    ]
    return [float(component % 1.0) for component in components]


def canonical_derived_interface_spec(
    spec: Mapping[str, Any],
    *,
    prototype_uid_full: str,
) -> dict[str, Any]:
    """Validate and canonicalize one exact-current persisted specification."""

    if not isinstance(spec, Mapping):
        raise TypeError("Derived-interface spec must be a mapping.")
    stored = dict(spec)
    missing = sorted(_REQUIRED_FIELDS - stored.keys())
    if missing:
        raise ValueError(
            "Derived-interface spec is missing required current field(s): "
            + ", ".join(missing)
            + "."
        )
    unsupported = sorted(stored.keys() - _ALLOWED_FIELDS)
    if unsupported:
        raise ValueError(
            "Derived-interface spec contains unsupported or historical field(s): "
            + ", ".join(unsupported)
            + "."
        )

    version = stored["version"]
    if isinstance(version, bool) or not isinstance(version, int):
        raise TypeError("Derived-interface spec version must be an integer.")
    if int(version) != DERIVED_INTERFACE_SPEC_VERSION:
        raise ValueError(
            "Unsupported derived-interface spec version "
            f"{version!r}; expected {DERIVED_INTERFACE_SPEC_VERSION}."
        )
    schema = _nonempty_string(
        "Derived-interface spec schema",
        stored["schema"],
    )
    if schema != DERIVED_INTERFACE_SPEC_SCHEMA:
        raise ValueError(
            "Unsupported derived-interface spec schema "
            f"{schema!r}; expected {DERIVED_INTERFACE_SPEC_SCHEMA!r}."
        )

    expected_prototype = _nonempty_string(
        "prototype_uid_full",
        prototype_uid_full,
    )
    prototype = _nonempty_string(
        "Derived-interface spec prototype",
        stored["prototype"],
    )
    if prototype != expected_prototype:
        raise ValueError(
            "Derived-interface spec prototype does not match the authoritative "
            "prototype_uid_full column."
        )

    alpha = _finite_real("strain_alpha", stored["strain_alpha"], nonnegative=False)
    if not 0.0 <= alpha <= 1.0:
        raise ValueError("strain_alpha must lie in [0, 1].")
    shift = canonical_registry_shift(stored["registry_shift_frac_a"])
    z_padding = _finite_real("z_padding", stored["z_padding"], nonnegative=True)

    vacuum_raw = stored["vacuum"]
    vacuum = (
        None
        if vacuum_raw is None
        else _finite_real("vacuum", vacuum_raw, nonnegative=True)
    )

    params_raw = stored["params"]
    if not isinstance(params_raw, Mapping):
        raise TypeError("Derived-interface params must be a mapping.")
    params = _canonical_json_value("Derived-interface params", params_raw)
    reserved = sorted(_RESERVED_PARAM_FIELDS & params.keys())
    if reserved:
        raise ValueError(
            "Derived-interface params contain reserved schema field(s): "
            + ", ".join(reserved)
            + "."
        )

    canonical: dict[str, Any] = {
        "schema": DERIVED_INTERFACE_SPEC_SCHEMA,
        "version": DERIVED_INTERFACE_SPEC_VERSION,
        "prototype": expected_prototype,
        "stage": canonical_interface_stage(stored["stage"]),
        "strain_alpha": alpha,
        "registry_shift_frac_a": shift,
        "z_padding": z_padding,
        "vacuum": vacuum,
        "params": params,
    }

    if "strain_state" in stored:
        strain_state = stored["strain_state"]
        if not isinstance(strain_state, Mapping):
            raise TypeError("Derived-interface strain_state must be a mapping.")
        canonical["strain_state"] = canonical_strain_state(
            strain_state,
            prototype_uid_full=expected_prototype,
            strain_alpha=alpha,
        )

    if "atoms_artifact_uid" in stored:
        artifact_uid = _nonempty_string(
            "atoms_artifact_uid",
            stored["atoms_artifact_uid"],
        )
        canonical["atoms_artifact_uid"] = artifact_uid

    if "artifact_refs" in stored:
        refs = stored["artifact_refs"]
        if not isinstance(refs, list):
            raise TypeError("artifact_refs must be a list.")
        if len(refs) != 1:
            raise ValueError(
                "Current derived-interface artifact_refs must contain exactly "
                "one atoms artifact reference."
            )
        ref = refs[0]
        if not isinstance(ref, Mapping):
            raise TypeError("artifact_refs[0] must be a mapping.")
        fields = dict(ref)
        expected_fields = {"artifact_uid", "kind", "role", "uri"}
        if set(fields) != expected_fields:
            raise ValueError(
                "artifact_refs[0] must contain exactly: "
                + ", ".join(sorted(expected_fields))
                + "."
            )
        for field_name in sorted(expected_fields):
            fields[field_name] = _nonempty_string(
                f"artifact_refs[0].{field_name}",
                fields[field_name],
            )
        artifact_uid = canonical.get("atoms_artifact_uid")
        if artifact_uid is None:
            raise ValueError(
                "artifact_refs requires the exact current atoms_artifact_uid."
            )
        if (
            fields["artifact_uid"] != artifact_uid
            or fields["kind"] != "interface_atoms"
            or fields["role"] != "derived_interface_atoms"
        ):
            raise ValueError(
                "atoms_artifact_uid must identify the exact current "
                "interface_atoms artifact reference."
            )
        canonical["artifact_refs"] = [fields]
    elif "atoms_artifact_uid" in canonical:
        raise ValueError(
            "atoms_artifact_uid requires an exact current artifact_refs entry."
        )

    return canonical
