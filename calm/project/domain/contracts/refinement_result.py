"""Exact-current persisted contracts for interface-refinement results.

The SQL table retains generic scalar columns for indexing.  These helpers make
the versioned result payload authoritative and verify that every scalar column
is an exact projection of that payload on both write and read.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import isclose, isfinite
from numbers import Integral, Real
from typing import Any

from calm.project.domain.contracts.derived_interface import canonical_registry_shift

STRAIN_PARTITION_RESULT_SCHEMA = "calm.strain_partition_result"
REGISTRY_SEARCH_RESULT_SCHEMA = "calm.registry_search_result"
REFINEMENT_RESULT_VERSION = 1
STRAIN_PARTITION_RESULT_VERSION = 2
REFINEMENT_RESULT_KINDS = frozenset({"strain_partition_scan", "registry_search"})

_STRAIN_METRICS = frozenset({"potential_energy_density_eV_per_A2", "gamma_eV_per_A2"})
_STRAIN_POINT_FIELDS = frozenset(
    {
        "alpha",
        "side_a_principal_log_strains",
        "side_b_principal_log_strains",
        "side_a_max_abs_principal_log_strain",
        "side_b_max_abs_principal_log_strain",
        "side_a_airm_distance",
        "side_b_airm_distance",
        "potential_energy_eV",
        "area_A2",
        "interface_area_A2",
        "potential_energy_density_eV_per_A2",
        "gamma_eV_per_A2",
        "gamma_J_per_m2",
        "n_fu_slab_A",
        "n_fu_slab_B",
        "mu_bulk_A_eV_per_fu",
        "mu_bulk_B_eV_per_fu",
        "energy_reference",
    }
)
_STRAIN_PAYLOAD_FIELDS = frozenset(
    {
        "schema",
        "version",
        "result_stage",
        "selection",
        "points",
        "calculator",
        "calculator_fingerprint",
    }
)
_REGISTRY_PAYLOAD_FIELDS = frozenset(
    {
        "schema",
        "version",
        "result_stage",
        "registry_shift_frac_a",
        "z_padding",
        "vacuum",
        "objective",
        "objective_units",
        "score",
        "n_steps",
        "n_accepted",
        "trace",
        "proposal_trace",
        "calculator",
        "calculator_fingerprint",
        "provenance",
    }
)
_REGISTRY_TRACE_FIELDS = frozenset({"step", "current_score", "best_score"})
_REGISTRY_RNG_FIELDS = frozenset({"bit_generator", "version", "seed", "seed_mode"})
_REGISTRY_PROVENANCE_FIELDS = frozenset(
    {
        "protocol",
        "protocol_version",
        "rng",
        "trace_version",
        "score_units",
        "nonfinite_trace_encoding",
        "initial_translation",
        "initial_z",
        "translation_space",
        "translation_metric",
        "torus_representative",
        "translation_proposal",
        "step_scale",
        "temperature",
        "temperature_schedule_id",
        "temperature_units",
        "acceptance_rule",
        "best_tie_rule",
        "nonfinite_proposal_rule",
        "gap_coordinate_enabled",
        "gap_search_enabled",
        "gap_coordinate",
        "gap_units",
        "gap_proposal",
        "z_step_scale",
        "z_step_scale_requested",
        "z_bounds",
        "p_z_requested",
        "p_z_effective",
        "p_translate_requested",
        "p_translate_effective",
        "boundary_rule",
        "random_draw_order",
        "implementation",
        "alpha",
        "fixed_z_padding",
        "fixed_vacuum_padding",
        "z_search_enabled",
        "requested_seed",
        "seed_derivation",
        "seed_derivation_version",
    }
)
_PROPOSAL_FIELDS = frozenset(
    {
        "step",
        "move_kind",
        "move_selector",
        "translation_increment",
        "gap_increment",
        "proposed_translation",
        "proposed_z",
        "proposed_score",
        "temperature",
        "acceptance_uniform",
        "log_acceptance_ratio",
        "accepted",
        "current_translation",
        "current_z",
        "current_score",
        "best_translation",
        "best_z",
        "best_score",
    }
)
_NONFINITE_NAMES = frozenset({"positive_infinity", "negative_infinity", "not_a_number"})


def _nonempty_string(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise TypeError(f"{name} must be a non-empty, whitespace-trimmed string.")
    return value


def _finite_real(name: str, value: Any, *, nonnegative: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{name} must be a finite real number.")
    result = float(value)
    if not isfinite(result):
        raise ValueError(f"{name} must be finite.")
    if nonnegative and result < 0.0:
        raise ValueError(f"{name} must be non-negative.")
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
            out[canonical_key] = _canonical_json_value(
                f"{name}.{canonical_key}",
                item,
            )
        return out
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [
            _canonical_json_value(f"{name}[{index}]", item)
            for index, item in enumerate(value)
        ]
    raise TypeError(f"{name} must contain only JSON-native values.")


def _canonical_calculator(
    value: Any,
    fingerprint: Any,
) -> tuple[dict[str, Any], str]:
    if not isinstance(value, Mapping):
        raise TypeError("Refinement result calculator must be a mapping.")
    from calm.calculators.spec import CalculatorSpec

    expected_fields = {
        "schema_version",
        "family",
        "model",
        "version",
        "source",
        "device",
        "dtype",
        "options",
    }
    stored = _require_exact_fields(
        "Refinement result calculator",
        value,
        frozenset(expected_fields),
    )
    spec = CalculatorSpec.from_dict(stored)
    canonical = spec.to_dict()
    if canonical != stored:
        raise ValueError(
            "Refinement result calculator must use the exact current "
            "CalculatorSpec representation."
        )
    stored_fingerprint = _nonempty_string(
        "Refinement result calculator_fingerprint",
        fingerprint,
    )
    expected_fingerprint = spec.fingerprint()
    if stored_fingerprint != expected_fingerprint:
        raise ValueError(
            "Refinement result calculator_fingerprint does not match calculator."
        )
    return canonical, stored_fingerprint


def _target_columns(
    *,
    prototype_uid_full: str | None,
    target_uid_full: str | None,
    target_kind: str | None,
) -> tuple[str, str, str]:
    prototype_uid = _nonempty_string(
        "Refinement result prototype_uid_full",
        prototype_uid_full,
    )
    target_uid = _nonempty_string(
        "Refinement result target_uid_full",
        target_uid_full,
    )
    kind = _nonempty_string("Refinement result target_kind", target_kind)
    if kind not in {"prototype", "interface"}:
        raise ValueError(
            "Refinement result target_kind must be 'prototype' or 'interface'."
        )
    if kind == "prototype" and target_uid != prototype_uid:
        raise ValueError(
            "Prototype-targeted refinement results require target_uid_full to "
            "equal prototype_uid_full."
        )
    if kind == "interface" and not target_uid.startswith("iface:"):
        raise ValueError(
            "Interface-targeted refinement results require an iface: target UID."
        )
    return prototype_uid, target_uid, kind


def _canonical_strain_point(
    value: Any,
    *,
    index: int,
    normalize_optional_nonfinite: bool,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"Strain-partition point {index} must be a mapping.")
    stored = _require_exact_fields(
        f"Strain-partition point {index}",
        value,
        _STRAIN_POINT_FIELDS,
    )

    def optional(name: str) -> float | None:
        raw = stored[name]
        if raw is None:
            return None
        if isinstance(raw, bool) or not isinstance(raw, Real):
            raise TypeError(
                f"Strain-partition point {index} {name} must be numeric or None."
            )
        result = float(raw)
        if not isfinite(result):
            if normalize_optional_nonfinite:
                return None
            raise ValueError(
                f"Strain-partition point {index} {name} must be finite or None."
            )
        return result

    def principal_log_strains(name: str) -> list[float]:
        raw = stored[name]
        if not isinstance(raw, list) or len(raw) != 2:
            raise TypeError(
                f"Strain-partition point {index} {name} must be a two-value JSON list."
            )
        values = [
            _finite_real(
                f"Strain-partition point {index} {name}[{axis}]",
                item,
            )
            for axis, item in enumerate(raw)
        ]
        if values != sorted(values):
            raise ValueError(
                f"Strain-partition point {index} {name} must be "
                "ordered from smallest to largest."
            )
        return values

    alpha = _finite_real(
        f"Strain-partition point {index} alpha",
        stored["alpha"],
    )
    if not 0.0 <= alpha <= 1.0:
        raise ValueError(f"Strain-partition point {index} alpha must lie in [0, 1].")
    side_a_principal = principal_log_strains("side_a_principal_log_strains")
    side_b_principal = principal_log_strains("side_b_principal_log_strains")
    side_a_max = _finite_real(
        f"Strain-partition point {index} side_a_max_abs_principal_log_strain",
        stored["side_a_max_abs_principal_log_strain"],
        nonnegative=True,
    )
    side_b_max = _finite_real(
        f"Strain-partition point {index} side_b_max_abs_principal_log_strain",
        stored["side_b_max_abs_principal_log_strain"],
        nonnegative=True,
    )
    expected_side_a_max = max(abs(item) for item in side_a_principal)
    expected_side_b_max = max(abs(item) for item in side_b_principal)
    if side_a_max != expected_side_a_max:
        raise ValueError(
            f"Strain-partition point {index} side-A maximum principal "
            "strain does not match its principal strains."
        )
    if side_b_max != expected_side_b_max:
        raise ValueError(
            f"Strain-partition point {index} side-B maximum principal "
            "strain does not match its principal strains."
        )

    side_a_distance = _finite_real(
        f"Strain-partition point {index} side_a_airm_distance",
        stored["side_a_airm_distance"],
        nonnegative=True,
    )
    side_b_distance = _finite_real(
        f"Strain-partition point {index} side_b_airm_distance",
        stored["side_b_airm_distance"],
        nonnegative=True,
    )
    expected_side_a_distance = 2.0 * (
        sum(item * item for item in side_a_principal) ** 0.5
    )
    expected_side_b_distance = 2.0 * (
        sum(item * item for item in side_b_principal) ** 0.5
    )
    if not isclose(
        side_a_distance,
        expected_side_a_distance,
        rel_tol=1e-12,
        abs_tol=1e-14,
    ):
        raise ValueError(
            f"Strain-partition point {index} side-A AIRM distance does "
            "not match its principal strains."
        )
    if not isclose(
        side_b_distance,
        expected_side_b_distance,
        rel_tol=1e-12,
        abs_tol=1e-14,
    ):
        raise ValueError(
            f"Strain-partition point {index} side-B AIRM distance does "
            "not match its principal strains."
        )
    total_distance = side_a_distance + side_b_distance
    if not isclose(
        side_a_distance,
        alpha * total_distance,
        rel_tol=1e-10,
        abs_tol=1e-12,
    ) or not isclose(
        side_b_distance,
        (1.0 - alpha) * total_distance,
        rel_tol=1e-10,
        abs_tol=1e-12,
    ):
        raise ValueError(
            f"Strain-partition point {index} per-side AIRM distances do "
            "not follow the constant-speed geodesic alpha convention."
        )

    area = _finite_real(
        f"Strain-partition point {index} area_A2",
        stored["area_A2"],
    )
    if area <= 0.0:
        raise ValueError(f"Strain-partition point {index} area_A2 must be positive.")
    interface_area = _finite_real(
        f"Strain-partition point {index} interface_area_A2",
        stored["interface_area_A2"],
    )
    if interface_area <= 0.0:
        raise ValueError(
            f"Strain-partition point {index} interface_area_A2 must be positive."
        )
    if interface_area != area:
        raise ValueError(
            f"Strain-partition point {index} interface_area_A2 must equal "
            "the authoritative area_A2 energy normalization."
        )
    energy_reference = _nonempty_string(
        f"Strain-partition point {index} energy_reference",
        stored["energy_reference"],
    )
    if energy_reference != "strained_bulk":
        raise ValueError(
            "Current strain-partition points require energy_reference='strained_bulk'."
        )

    return {
        "alpha": alpha,
        "side_a_principal_log_strains": side_a_principal,
        "side_b_principal_log_strains": side_b_principal,
        "side_a_max_abs_principal_log_strain": side_a_max,
        "side_b_max_abs_principal_log_strain": side_b_max,
        "side_a_airm_distance": side_a_distance,
        "side_b_airm_distance": side_b_distance,
        "potential_energy_eV": _finite_real(
            f"Strain-partition point {index} potential_energy_eV",
            stored["potential_energy_eV"],
        ),
        "area_A2": area,
        "interface_area_A2": interface_area,
        "potential_energy_density_eV_per_A2": _finite_real(
            f"Strain-partition point {index} potential_energy_density_eV_per_A2",
            stored["potential_energy_density_eV_per_A2"],
        ),
        "gamma_eV_per_A2": optional("gamma_eV_per_A2"),
        "gamma_J_per_m2": optional("gamma_J_per_m2"),
        "n_fu_slab_A": _optional_nonnegative_int(
            f"Strain-partition point {index} n_fu_slab_A",
            stored["n_fu_slab_A"],
        ),
        "n_fu_slab_B": _optional_nonnegative_int(
            f"Strain-partition point {index} n_fu_slab_B",
            stored["n_fu_slab_B"],
        ),
        "mu_bulk_A_eV_per_fu": optional("mu_bulk_A_eV_per_fu"),
        "mu_bulk_B_eV_per_fu": optional("mu_bulk_B_eV_per_fu"),
        "energy_reference": energy_reference,
    }


def _canonical_strain_payload(
    payload: Mapping[str, Any],
    *,
    best_energy: float | None,
    param1: float | None,
    param2: float | None,
    n_points: int | None,
    normalize_optional_nonfinite: bool,
) -> dict[str, Any]:
    stored = _require_exact_fields(
        "Strain-partition result payload",
        payload,
        _STRAIN_PAYLOAD_FIELDS,
    )
    if stored["schema"] != STRAIN_PARTITION_RESULT_SCHEMA:
        raise ValueError(
            "Unsupported strain-partition result schema; expected "
            f"{STRAIN_PARTITION_RESULT_SCHEMA!r}."
        )
    version = stored["version"]
    if isinstance(version, bool) or not isinstance(version, int):
        raise TypeError("Strain-partition result version must be an integer.")
    if version != STRAIN_PARTITION_RESULT_VERSION:
        raise ValueError(
            "Unsupported strain-partition result version; expected "
            f"{STRAIN_PARTITION_RESULT_VERSION}."
        )
    if stored["result_stage"] != "strain_partitioned":
        raise ValueError(
            "Current strain-partition results require result_stage="
            "'strain_partitioned'."
        )

    raw_points = stored["points"]
    if not isinstance(raw_points, list) or not raw_points:
        raise ValueError("Strain-partition result points must be a non-empty list.")
    points = [
        _canonical_strain_point(
            point,
            index=index,
            normalize_optional_nonfinite=normalize_optional_nonfinite,
        )
        for index, point in enumerate(raw_points)
    ]
    alphas = [point["alpha"] for point in points]
    if alphas != sorted(set(alphas)):
        raise ValueError(
            "Strain-partition result points must use strictly increasing unique alphas."
        )
    total_distances = [
        point["side_a_airm_distance"] + point["side_b_airm_distance"]
        for point in points
    ]
    reference_distance = total_distances[0]
    if any(
        not isclose(
            distance,
            reference_distance,
            rel_tol=1e-10,
            abs_tol=1e-12,
        )
        for distance in total_distances[1:]
    ):
        raise ValueError(
            "Strain-partition result points must preserve one total AIRM "
            "distance across the geodesic scan."
        )

    selection_raw = stored["selection"]
    if not isinstance(selection_raw, Mapping):
        raise TypeError("Strain-partition result selection must be a mapping.")
    selection = _require_exact_fields(
        "Strain-partition result selection",
        selection_raw,
        frozenset({"metric", "alpha", "value"}),
    )
    metric = _nonempty_string(
        "Strain-partition selection metric",
        selection["metric"],
    )
    if metric not in _STRAIN_METRICS:
        raise ValueError(
            "Strain-partition selection metric must use one exact current name."
        )
    selected_alpha = _finite_real(
        "Strain-partition selection alpha",
        selection["alpha"],
    )
    selected_value = _finite_real(
        "Strain-partition selection value",
        selection["value"],
    )
    matching = [point for point in points if point["alpha"] == selected_alpha]
    if len(matching) != 1:
        raise ValueError(
            "Strain-partition selection alpha must identify exactly one point."
        )
    if matching[0][metric] != selected_value:
        raise ValueError(
            "Strain-partition selection value does not match the selected point."
        )

    if (
        best_energy is None
        or _finite_real("Strain-partition best_energy", best_energy) != selected_value
    ):
        raise ValueError("Strain-partition best_energy must equal selection.value.")
    if (
        param1 is None
        or _finite_real("Strain-partition param1", param1) != selected_alpha
    ):
        raise ValueError("Strain-partition param1 must equal selection.alpha.")
    if param2 is not None:
        raise ValueError("Strain-partition param2 must be None.")
    if n_points is None or _nonnegative_int(
        "Strain-partition n_points", n_points
    ) != len(points):
        raise ValueError(
            "Strain-partition n_points must equal the number of persisted points."
        )

    calculator, fingerprint = _canonical_calculator(
        stored["calculator"],
        stored["calculator_fingerprint"],
    )
    return {
        "schema": STRAIN_PARTITION_RESULT_SCHEMA,
        "version": STRAIN_PARTITION_RESULT_VERSION,
        "result_stage": "strain_partitioned",
        "selection": {
            "metric": metric,
            "alpha": selected_alpha,
            "value": selected_value,
        },
        "points": points,
        "calculator": calculator,
        "calculator_fingerprint": fingerprint,
    }


def _encoded_real(name: str, value: Any) -> float | str | None:
    if value is None:
        return None
    if isinstance(value, str):
        if value not in _NONFINITE_NAMES:
            raise ValueError(f"{name} contains an unsupported named value.")
        return value
    return _finite_real(name, value)


def _canonical_translation(name: str, value: Any) -> list[float]:
    shift = canonical_registry_shift(value)
    if list(value) != shift:
        raise ValueError(f"{name} must already use the [0, 1) torus representative.")
    return shift


def _canonical_proposal(value: Any, *, index: int) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"Registry proposal_trace item {index} must be a mapping.")
    stored = _require_exact_fields(
        f"Registry proposal_trace item {index}",
        value,
        _PROPOSAL_FIELDS,
    )
    step = _nonnegative_int(
        f"Registry proposal_trace item {index} step",
        stored["step"],
    )
    if step <= 0:
        raise ValueError("Registry proposal_trace steps must be positive.")
    move_kind = _nonempty_string(
        f"Registry proposal_trace item {index} move_kind",
        stored["move_kind"],
    )
    if move_kind != "translation":
        raise ValueError("Current persisted registry refinement is translation-only.")
    increment = stored["translation_increment"]
    if not isinstance(increment, list) or len(increment) != 2:
        raise ValueError(
            f"Registry proposal_trace item {index} translation_increment "
            "must contain two values."
        )
    translation_increment = [
        _finite_real(
            f"Registry proposal_trace item {index} translation_increment[{axis}]",
            item,
        )
        for axis, item in enumerate(increment)
    ]
    accepted = stored["accepted"]
    if not isinstance(accepted, bool):
        raise TypeError(
            f"Registry proposal_trace item {index} accepted must be a bool."
        )
    selector = _optional_finite(
        f"Registry proposal_trace item {index} move_selector",
        stored["move_selector"],
    )
    acceptance_uniform = _optional_finite(
        f"Registry proposal_trace item {index} acceptance_uniform",
        stored["acceptance_uniform"],
    )
    if acceptance_uniform is not None and not 0.0 <= acceptance_uniform <= 1.0:
        raise ValueError("Registry proposal acceptance_uniform must lie in [0, 1].")
    if stored["gap_increment"] is not None:
        raise ValueError(
            "Translation-only registry proposals require gap_increment=None."
        )
    for field in ("proposed_z", "current_z", "best_z"):
        if stored[field] is not None:
            raise ValueError(
                f"Translation-only registry proposals require {field}=None."
            )
    return {
        "step": step,
        "move_kind": move_kind,
        "move_selector": selector,
        "translation_increment": translation_increment,
        "gap_increment": None,
        "proposed_translation": _canonical_translation(
            f"Registry proposal_trace item {index} proposed_translation",
            stored["proposed_translation"],
        ),
        "proposed_z": None,
        "proposed_score": _encoded_real(
            f"Registry proposal_trace item {index} proposed_score",
            stored["proposed_score"],
        ),
        "temperature": _finite_real(
            f"Registry proposal_trace item {index} temperature",
            stored["temperature"],
            nonnegative=True,
        ),
        "acceptance_uniform": acceptance_uniform,
        "log_acceptance_ratio": _encoded_real(
            f"Registry proposal_trace item {index} log_acceptance_ratio",
            stored["log_acceptance_ratio"],
        ),
        "accepted": accepted,
        "current_translation": _canonical_translation(
            f"Registry proposal_trace item {index} current_translation",
            stored["current_translation"],
        ),
        "current_z": None,
        "current_score": _finite_real(
            f"Registry proposal_trace item {index} current_score",
            stored["current_score"],
        ),
        "best_translation": _canonical_translation(
            f"Registry proposal_trace item {index} best_translation",
            stored["best_translation"],
        ),
        "best_z": None,
        "best_score": _finite_real(
            f"Registry proposal_trace item {index} best_score",
            stored["best_score"],
        ),
    }


def _canonical_registry_payload(
    payload: Mapping[str, Any],
    *,
    best_energy: float | None,
    param1: float | None,
    param2: float | None,
    n_points: int | None,
) -> dict[str, Any]:
    stored = _require_exact_fields(
        "Registry-search result payload",
        payload,
        _REGISTRY_PAYLOAD_FIELDS,
    )
    if stored["schema"] != REGISTRY_SEARCH_RESULT_SCHEMA:
        raise ValueError(
            "Unsupported registry-search result schema; expected "
            f"{REGISTRY_SEARCH_RESULT_SCHEMA!r}."
        )
    version = stored["version"]
    if isinstance(version, bool) or not isinstance(version, int):
        raise TypeError("Registry-search result version must be an integer.")
    if version != REFINEMENT_RESULT_VERSION:
        raise ValueError("Unsupported registry-search result version; expected 1.")
    if stored["result_stage"] != "registry_refined":
        raise ValueError(
            "Current registry-search results require result_stage='registry_refined'."
        )

    from calm.interface.refinement.registry import (
        PERSISTED_REGISTRY_OBJECTIVE,
        PERSISTED_REGISTRY_SCORE_UNITS,
        PERSISTED_REGISTRY_TEMPERATURE,
        REGISTRY_PROVENANCE_COMPLETE,
        classify_registry_provenance,
    )
    from calm.interface.refinement.contract import (
        REGISTRY_SEED_DERIVATION,
        REGISTRY_SEED_DERIVATION_VERSION,
    )

    shift = _canonical_translation(
        "Registry-search result registry_shift_frac_a",
        stored["registry_shift_frac_a"],
    )
    z_padding = _finite_real(
        "Registry-search result z_padding",
        stored["z_padding"],
        nonnegative=True,
    )
    vacuum = _optional_finite("Registry-search result vacuum", stored["vacuum"])
    if vacuum is not None and vacuum < 0.0:
        raise ValueError("Registry-search result vacuum must be non-negative.")
    objective = _nonempty_string(
        "Registry-search result objective",
        stored["objective"],
    )
    units = _nonempty_string(
        "Registry-search result objective_units",
        stored["objective_units"],
    )
    if objective != PERSISTED_REGISTRY_OBJECTIVE:
        raise ValueError("Registry-search result objective is not current.")
    if units != PERSISTED_REGISTRY_SCORE_UNITS:
        raise ValueError("Registry-search result objective_units are not current.")
    score = _finite_real("Registry-search result score", stored["score"])
    n_steps = _nonnegative_int("Registry-search result n_steps", stored["n_steps"])
    if n_steps <= 0:
        raise ValueError("Registry-search result n_steps must be positive.")
    n_accepted = _nonnegative_int(
        "Registry-search result n_accepted",
        stored["n_accepted"],
    )
    if n_accepted > n_steps:
        raise ValueError("Registry-search result n_accepted cannot exceed n_steps.")

    raw_trace = stored["trace"]
    if not isinstance(raw_trace, list) or len(raw_trace) != n_steps:
        raise ValueError(
            "Registry-search result trace must contain exactly n_steps entries."
        )
    trace: list[dict[str, Any]] = []
    for index, item in enumerate(raw_trace):
        if not isinstance(item, Mapping):
            raise TypeError(f"Registry trace item {index} must be a mapping.")
        row = _require_exact_fields(
            f"Registry trace item {index}",
            item,
            _REGISTRY_TRACE_FIELDS,
        )
        step = _nonnegative_int(f"Registry trace item {index} step", row["step"])
        if step != index + 1:
            raise ValueError("Registry trace steps must be consecutive and one-based.")
        trace.append(
            {
                "step": step,
                "current_score": _finite_real(
                    f"Registry trace item {index} current_score",
                    row["current_score"],
                ),
                "best_score": _finite_real(
                    f"Registry trace item {index} best_score",
                    row["best_score"],
                ),
            }
        )
    if trace[-1]["best_score"] != score:
        raise ValueError(
            "Registry-search result score must equal the final trace best_score."
        )

    raw_proposals = stored["proposal_trace"]
    if not isinstance(raw_proposals, list) or len(raw_proposals) != n_steps:
        raise ValueError(
            "Registry-search result proposal_trace must contain exactly n_steps entries."
        )
    proposals = [
        _canonical_proposal(item, index=index)
        for index, item in enumerate(raw_proposals)
    ]
    if [item["step"] for item in proposals] != list(range(1, n_steps + 1)):
        raise ValueError(
            "Registry proposal_trace steps must be consecutive and one-based."
        )
    if sum(bool(item["accepted"]) for item in proposals) != n_accepted:
        raise ValueError(
            "Registry-search result n_accepted must equal accepted proposal count."
        )
    for index, (trace_item, proposal) in enumerate(zip(trace, proposals, strict=True)):
        if proposal["current_score"] != trace_item["current_score"]:
            raise ValueError(
                f"Registry proposal_trace item {index} current_score does not "
                "match the compact trace."
            )
        if proposal["best_score"] != trace_item["best_score"]:
            raise ValueError(
                f"Registry proposal_trace item {index} best_score does not "
                "match the compact trace."
            )
    if proposals[-1]["best_translation"] != shift:
        raise ValueError(
            "Registry-search result translation must equal the final proposal "
            "best_translation."
        )
    if proposals[-1]["best_score"] != score:
        raise ValueError(
            "Registry-search result score must equal the final proposal best_score."
        )

    provenance_raw = stored["provenance"]
    if not isinstance(provenance_raw, Mapping):
        raise TypeError("Registry-search result provenance must be a mapping.")
    provenance_raw = _require_exact_fields(
        "Registry-search result provenance",
        provenance_raw,
        _REGISTRY_PROVENANCE_FIELDS,
    )
    provenance = _canonical_json_value(
        "Registry-search result provenance",
        provenance_raw,
    )
    if classify_registry_provenance(provenance) != REGISTRY_PROVENANCE_COMPLETE:
        raise ValueError(
            "Registry-search result provenance is incomplete or inconsistent."
        )
    rng_raw = provenance.get("rng")
    if not isinstance(rng_raw, Mapping):
        raise TypeError("Registry-search provenance rng must be a mapping.")
    rng = _require_exact_fields(
        "Registry-search provenance rng",
        rng_raw,
        _REGISTRY_RNG_FIELDS,
    )
    if rng.get("seed_mode") != "explicit":
        raise ValueError(
            "Persisted registry refinement requires an explicit reproducible seed."
        )
    _nonnegative_int("Registry-search provenance rng seed", rng.get("seed"))
    if provenance.get("implementation") != "translation_torus_metropolis_v3":
        raise ValueError("Registry-search result implementation is not current.")
    alpha = _finite_real("Registry-search provenance alpha", provenance.get("alpha"))
    if not 0.0 <= alpha <= 1.0:
        raise ValueError("Registry-search provenance alpha must lie in [0, 1].")
    if provenance.get("trace_version") != 1:
        raise ValueError("Registry-search provenance trace_version is not current.")
    if provenance.get("score_units") != units:
        raise ValueError(
            "Registry-search provenance score_units do not match objective_units."
        )
    if provenance.get("temperature") != PERSISTED_REGISTRY_TEMPERATURE:
        raise ValueError("Registry-search provenance temperature is not current.")
    if any(
        proposal["temperature"] != PERSISTED_REGISTRY_TEMPERATURE
        for proposal in proposals
    ):
        raise ValueError(
            "Registry proposal temperatures must match the persisted constant "
            "temperature."
        )
    if provenance.get("temperature_schedule_id") != "constant":
        raise ValueError(
            "Registry-search provenance temperature schedule is not current."
        )
    if provenance.get("initial_z") is not None:
        raise ValueError(
            "Translation-only registry provenance requires initial_z=None."
        )
    if provenance.get("z_search_enabled") is not False:
        raise ValueError("Current persisted registry refinement is translation-only.")
    if provenance.get("gap_coordinate_enabled") is not False:
        raise ValueError(
            "Current persisted registry refinement disables the gap coordinate."
        )
    if provenance.get("gap_search_enabled") is not False:
        raise ValueError("Current persisted registry refinement disables gap search.")
    if provenance.get("gap_proposal") is not None:
        raise ValueError(
            "Translation-only registry provenance requires gap_proposal=None."
        )
    if provenance.get("z_bounds") is not None:
        raise ValueError("Translation-only registry provenance requires z_bounds=None.")
    if provenance.get("boundary_rule") is not None:
        raise ValueError(
            "Translation-only registry provenance requires boundary_rule=None."
        )
    if provenance.get("z_step_scale") != 0.0:
        raise ValueError(
            "Translation-only registry provenance requires z_step_scale=0."
        )
    if provenance.get("z_step_scale_requested") != 0.0:
        raise ValueError(
            "Translation-only registry provenance requires z_step_scale_requested=0."
        )
    if provenance.get("p_z_requested") != 0.25:
        raise ValueError("Current registry provenance requires p_z_requested=0.25.")
    if provenance.get("p_z_effective") != 0.0:
        raise ValueError(
            "Translation-only registry provenance requires p_z_effective=0."
        )
    if provenance.get("p_translate_requested") is not None:
        raise ValueError(
            "Current registry provenance requires p_translate_requested=None."
        )
    if provenance.get("p_translate_effective") != 1.0:
        raise ValueError(
            "Translation-only registry provenance requires p_translate_effective=1."
        )
    if provenance.get("gap_coordinate") != "absolute_internal_gap":
        raise ValueError("Registry-search provenance gap_coordinate is not current.")
    if provenance.get("gap_units") != "caller_length_units":
        raise ValueError("Registry-search provenance gap_units are not current.")
    step_scale = _finite_real(
        "Registry-search provenance step_scale",
        provenance.get("step_scale"),
    )
    if step_scale <= 0.0:
        raise ValueError("Registry-search provenance step_scale must be positive.")
    if any(proposal["move_selector"] is not None for proposal in proposals):
        raise ValueError(
            "Translation-only registry proposals require move_selector=None."
        )
    _canonical_translation(
        "Registry-search provenance initial_translation",
        provenance.get("initial_translation"),
    )
    if provenance.get("fixed_z_padding") != z_padding:
        raise ValueError(
            "Registry-search provenance fixed_z_padding does not match result."
        )
    if provenance.get("fixed_vacuum_padding") != vacuum:
        raise ValueError(
            "Registry-search provenance fixed_vacuum_padding does not match result."
        )
    requested_seed = provenance.get("requested_seed")
    if requested_seed is not None:
        _nonnegative_int("Registry-search provenance requested_seed", requested_seed)
    if provenance.get("seed_derivation") != REGISTRY_SEED_DERIVATION:
        raise ValueError("Registry-search provenance seed_derivation is not current.")
    if provenance.get("seed_derivation_version") != REGISTRY_SEED_DERIVATION_VERSION:
        raise ValueError(
            "Registry-search provenance seed_derivation_version is not current."
        )

    if (
        best_energy is None
        or _finite_real("Registry-search best_energy", best_energy) != score
    ):
        raise ValueError("Registry-search best_energy must equal payload score.")
    if param1 is None or _finite_real("Registry-search param1", param1) != shift[0]:
        raise ValueError("Registry-search param1 must equal registry_shift_frac_a[0].")
    if param2 is None or _finite_real("Registry-search param2", param2) != shift[1]:
        raise ValueError("Registry-search param2 must equal registry_shift_frac_a[1].")
    if (
        n_points is None
        or _nonnegative_int("Registry-search n_points", n_points) != n_steps
    ):
        raise ValueError("Registry-search n_points must equal payload n_steps.")

    calculator, fingerprint = _canonical_calculator(
        stored["calculator"],
        stored["calculator_fingerprint"],
    )
    return {
        "schema": REGISTRY_SEARCH_RESULT_SCHEMA,
        "version": REFINEMENT_RESULT_VERSION,
        "result_stage": "registry_refined",
        "registry_shift_frac_a": shift,
        "z_padding": z_padding,
        "vacuum": vacuum,
        "objective": objective,
        "objective_units": units,
        "score": score,
        "n_steps": n_steps,
        "n_accepted": n_accepted,
        "trace": trace,
        "proposal_trace": proposals,
        "calculator": calculator,
        "calculator_fingerprint": fingerprint,
        "provenance": provenance,
    }


def refinement_result_target(
    *,
    prototype_uid_full: str | None,
    target_uid_full: str | None,
    target_kind: str | None,
) -> tuple[str, str, str]:
    """Return one exact authoritative refinement target triple."""

    return _target_columns(
        prototype_uid_full=prototype_uid_full,
        target_uid_full=target_uid_full,
        target_kind=target_kind,
    )


def canonical_refinement_result_payload(
    *,
    kind: str,
    payload: Mapping[str, Any],
    prototype_uid_full: str | None,
    target_uid_full: str | None,
    target_kind: str | None,
    best_energy: float | None,
    param1: float | None,
    param2: float | None,
    n_points: int | None,
) -> dict[str, Any]:
    """Validate one current refinement result and its scalar projections."""

    if kind not in REFINEMENT_RESULT_KINDS:
        raise ValueError(f"Unsupported refinement result kind {kind!r}.")
    _target_columns(
        prototype_uid_full=prototype_uid_full,
        target_uid_full=target_uid_full,
        target_kind=target_kind,
    )
    if kind == "strain_partition_scan":
        return _canonical_strain_payload(
            payload,
            best_energy=best_energy,
            param1=param1,
            param2=param2,
            n_points=n_points,
            normalize_optional_nonfinite=False,
        )
    return _canonical_registry_payload(
        payload,
        best_energy=best_energy,
        param1=param1,
        param2=param2,
        n_points=n_points,
    )


def make_strain_partition_result_payload(
    *,
    points: Sequence[Mapping[str, Any]],
    target_metric: str,
    target_alpha: float,
    target_value: float,
    calculator: Mapping[str, Any],
    calculator_fingerprint: str,
) -> dict[str, Any]:
    """Create one exact strain-partition result payload from kernel output."""

    raw = {
        "schema": STRAIN_PARTITION_RESULT_SCHEMA,
        "version": STRAIN_PARTITION_RESULT_VERSION,
        "result_stage": "strain_partitioned",
        "selection": {
            "metric": target_metric,
            "alpha": target_alpha,
            "value": target_value,
        },
        "points": list(points),
        "calculator": dict(calculator),
        "calculator_fingerprint": calculator_fingerprint,
    }
    return _canonical_strain_payload(
        raw,
        best_energy=target_value,
        param1=target_alpha,
        param2=None,
        n_points=len(points),
        normalize_optional_nonfinite=True,
    )


def make_registry_search_result_payload(
    *,
    registry_shift_frac_a: Sequence[float],
    z_padding: float,
    vacuum: float | None,
    objective: str,
    objective_units: str,
    score: float,
    n_steps: int,
    n_accepted: int,
    trace: Sequence[Sequence[float]],
    proposal_trace: Sequence[Mapping[str, Any]],
    calculator: Mapping[str, Any],
    calculator_fingerprint: str,
    provenance: Mapping[str, Any],
) -> dict[str, Any]:
    """Create one exact registry-search result payload from kernel output."""

    trace_rows = [
        {
            "step": int(item[0]),
            "current_score": float(item[1]),
            "best_score": float(item[2]),
        }
        for item in trace
    ]
    raw = {
        "schema": REGISTRY_SEARCH_RESULT_SCHEMA,
        "version": REFINEMENT_RESULT_VERSION,
        "result_stage": "registry_refined",
        "registry_shift_frac_a": list(registry_shift_frac_a),
        "z_padding": z_padding,
        "vacuum": vacuum,
        "objective": objective,
        "objective_units": objective_units,
        "score": score,
        "n_steps": n_steps,
        "n_accepted": n_accepted,
        "trace": trace_rows,
        "proposal_trace": [dict(item) for item in proposal_trace],
        "calculator": dict(calculator),
        "calculator_fingerprint": calculator_fingerprint,
        "provenance": dict(provenance),
    }
    return _canonical_registry_payload(
        raw,
        best_energy=score,
        param1=float(registry_shift_frac_a[0]),
        param2=float(registry_shift_frac_a[1]),
        n_points=n_steps,
    )


def strain_partition_selection(
    payload: Mapping[str, Any],
) -> tuple[str, float, float]:
    """Return ``(metric, alpha, value)`` from an already-current payload."""

    selection = payload["selection"]
    if not isinstance(selection, Mapping):
        raise TypeError("Strain-partition result selection must be a mapping.")
    return (
        str(selection["metric"]),
        float(selection["alpha"]),
        float(selection["value"]),
    )


def registry_result_state(
    payload: Mapping[str, Any],
) -> tuple[tuple[float, float], float, float | None]:
    """Return exact registry translation, internal gap, and boundary vacuum."""

    shift = payload["registry_shift_frac_a"]
    vacuum = payload["vacuum"]
    return (
        (float(shift[0]), float(shift[1])),
        float(payload["z_padding"]),
        None if vacuum is None else float(vacuum),
    )


__all__ = [
    "REFINEMENT_RESULT_KINDS",
    "REFINEMENT_RESULT_VERSION",
    "REGISTRY_SEARCH_RESULT_SCHEMA",
    "STRAIN_PARTITION_RESULT_SCHEMA",
    "STRAIN_PARTITION_RESULT_VERSION",
    "canonical_refinement_result_payload",
    "make_registry_search_result_payload",
    "make_strain_partition_result_payload",
    "refinement_result_target",
    "registry_result_state",
    "strain_partition_selection",
]
