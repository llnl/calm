"""Monte Carlo registry search on a fractional translation torus.

The dependency-light kernel explores a two-dimensional fractional registry and,
optionally, a scalar internal-gap coordinate.  The objective is supplied by the
caller; lower finite values are preferred.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from math import isfinite, log
from numbers import Integral
from typing import Any, Callable, Mapping, Sequence

import numpy as np

EnergyFn = Callable[..., float]
EnergyEvaluator = Callable[[np.ndarray, float | None], float]
Temperature = float | Callable[[int], float]

REGISTRY_SEARCH_PROTOCOL = "fractional_translation_torus_metropolis"
REGISTRY_SEARCH_PROTOCOL_VERSION = 1
REGISTRY_SEARCH_RNG = "numpy.random.PCG64"
REGISTRY_SEARCH_RNG_VERSION = 1
REGISTRY_SEARCH_TRACE_VERSION = 1
REGISTRY_TORUS_REPRESENTATIVE = "half_open_unit_square_[0,1)^2"
REGISTRY_TRANSLATION_PROPOSAL = (
    "incremental_isotropic_gaussian_in_fractional_coordinates"
)
REGISTRY_GAP_PROPOSAL = "incremental_gaussian_absolute_length_then_clip"
REGISTRY_ACCEPTANCE_RULE = "metropolis_log_space_equal_scores_accepted"
REGISTRY_BEST_TIE_RULE = "strict_lower_score_first_encountered"
REGISTRY_PROVENANCE_COMPLETE = "complete_v1"
REGISTRY_PROVENANCE_LEGACY = "legacy_incomplete"
REGISTRY_PROVENANCE_INVALID = "invalid"
PERSISTED_REGISTRY_IMPLEMENTATION = "translation_torus_metropolis_v3"
PERSISTED_REGISTRY_OBJECTIVE = "unrelaxed_total_energy_density_eV_per_A2"
PERSISTED_REGISTRY_SCORE_UNITS = "eV_per_A2"
PERSISTED_REGISTRY_TEMPERATURE = 0.03


def classify_registry_provenance(value: object) -> str:
    """Classify persisted or returned registry-search provenance."""

    if not isinstance(value, Mapping):
        return REGISTRY_PROVENANCE_INVALID
    if "protocol" not in value and "protocol_version" not in value:
        return REGISTRY_PROVENANCE_LEGACY
    required = {
        "protocol",
        "protocol_version",
        "rng",
        "trace_version",
        "score_units",
        "nonfinite_trace_encoding",
        "initial_translation",
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
        "p_z_requested",
        "p_z_effective",
        "p_translate_effective",
        "random_draw_order",
    }
    if not required.issubset(value):
        return REGISTRY_PROVENANCE_INVALID

    expected = {
        "protocol": REGISTRY_SEARCH_PROTOCOL,
        "protocol_version": REGISTRY_SEARCH_PROTOCOL_VERSION,
        "nonfinite_trace_encoding": "named_strings",
        "translation_space": "fractional_final_common_surface_basis",
        "translation_metric": "euclidean_in_fractional_coordinates",
        "torus_representative": REGISTRY_TORUS_REPRESENTATIVE,
        "translation_proposal": REGISTRY_TRANSLATION_PROPOSAL,
        "acceptance_rule": REGISTRY_ACCEPTANCE_RULE,
        "best_tie_rule": REGISTRY_BEST_TIE_RULE,
        "nonfinite_proposal_rule": "reject_without_acceptance_draw",
        "random_draw_order": (
            "optional_move_selector; proposal_normal_draws; "
            "uphill_acceptance_uniform_only"
        ),
    }
    if any(
        value.get(key) != expected_value for key, expected_value in expected.items()
    ):
        return REGISTRY_PROVENANCE_INVALID

    rng = value.get("rng")
    if not isinstance(rng, Mapping):
        return REGISTRY_PROVENANCE_INVALID
    if (
        rng.get("bit_generator") != REGISTRY_SEARCH_RNG
        or rng.get("version") != REGISTRY_SEARCH_RNG_VERSION
        or rng.get("seed_mode") not in {"explicit", "entropy"}
    ):
        return REGISTRY_PROVENANCE_INVALID
    seed = rng.get("seed")
    if rng.get("seed_mode") == "explicit":
        if isinstance(seed, bool) or not isinstance(seed, Integral) or seed < 0:
            return REGISTRY_PROVENANCE_INVALID
    elif seed is not None:
        return REGISTRY_PROVENANCE_INVALID

    units = value.get("score_units")
    if not isinstance(units, str) or not units.strip():
        return REGISTRY_PROVENANCE_INVALID
    if value.get("temperature_units") != units:
        return REGISTRY_PROVENANCE_INVALID
    try:
        step_scale = float(value.get("step_scale"))
        p_z_requested = float(value.get("p_z_requested"))
        p_z_effective = float(value.get("p_z_effective"))
        p_translate_effective = float(value.get("p_translate_effective"))
    except (TypeError, ValueError):
        return REGISTRY_PROVENANCE_INVALID
    if (
        not all(
            isfinite(item)
            for item in (
                step_scale,
                p_z_requested,
                p_z_effective,
                p_translate_effective,
            )
        )
        or step_scale < 0.0
        or not 0.0 <= p_z_requested <= 1.0
        or not 0.0 <= p_z_effective <= 1.0
        or not 0.0 <= p_translate_effective <= 1.0
        or abs((p_z_effective + p_translate_effective) - 1.0) > 1e-12
    ):
        return REGISTRY_PROVENANCE_INVALID

    initial_translation = value.get("initial_translation")
    if (
        not isinstance(initial_translation, (list, tuple))
        or len(initial_translation) != 2
    ):
        return REGISTRY_PROVENANCE_INVALID
    try:
        translation = tuple(float(component) for component in initial_translation)
    except (TypeError, ValueError):
        return REGISTRY_PROVENANCE_INVALID
    if not all(
        isfinite(component) and 0.0 <= component < 1.0 for component in translation
    ):
        return REGISTRY_PROVENANCE_INVALID

    if not isinstance(value.get("gap_coordinate_enabled"), bool):
        return REGISTRY_PROVENANCE_INVALID
    if not isinstance(value.get("gap_search_enabled"), bool):
        return REGISTRY_PROVENANCE_INVALID
    if value.get("gap_search_enabled") and not value.get("gap_coordinate_enabled"):
        return REGISTRY_PROVENANCE_INVALID

    temperature = value.get("temperature")
    if temperature == "callable":
        schedule = value.get("temperature_schedule_id")
        if not isinstance(schedule, str) or not schedule.strip():
            return REGISTRY_PROVENANCE_INVALID
    else:
        try:
            temperature_value = float(temperature)
        except (TypeError, ValueError):
            return REGISTRY_PROVENANCE_INVALID
        if not isfinite(temperature_value) or temperature_value < 0.0:
            return REGISTRY_PROVENANCE_INVALID
        if value.get("temperature_schedule_id") != "constant":
            return REGISTRY_PROVENANCE_INVALID

    return REGISTRY_PROVENANCE_COMPLETE


@dataclass(frozen=True)
class RegistryProposalRecord:
    """One fully specified proposal and post-decision Markov state."""

    step: int
    move_kind: str
    move_selector: float | None
    translation_increment: tuple[float, float] | None
    gap_increment: float | None
    proposed_translation: tuple[float, float]
    proposed_z: float | None
    proposed_score: float
    temperature: float
    acceptance_uniform: float | None
    log_acceptance_ratio: float | None
    accepted: bool
    current_translation: tuple[float, float]
    current_z: float | None
    current_score: float
    best_translation: tuple[float, float]
    best_z: float | None
    best_score: float

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-native representation of this proposal record."""

        def json_float(value: float | None) -> float | str | None:
            if value is None or isfinite(value):
                return value
            if value > 0.0:
                return "positive_infinity"
            if value < 0.0:
                return "negative_infinity"
            return "not_a_number"

        return {
            "step": self.step,
            "move_kind": self.move_kind,
            "move_selector": json_float(self.move_selector),
            "translation_increment": (
                None
                if self.translation_increment is None
                else list(self.translation_increment)
            ),
            "gap_increment": json_float(self.gap_increment),
            "proposed_translation": list(self.proposed_translation),
            "proposed_z": json_float(self.proposed_z),
            "proposed_score": json_float(self.proposed_score),
            "temperature": json_float(self.temperature),
            "acceptance_uniform": json_float(self.acceptance_uniform),
            "log_acceptance_ratio": json_float(self.log_acceptance_ratio),
            "accepted": self.accepted,
            "current_translation": list(self.current_translation),
            "current_z": json_float(self.current_z),
            "current_score": json_float(self.current_score),
            "best_translation": list(self.best_translation),
            "best_z": json_float(self.best_z),
            "best_score": json_float(self.best_score),
        }


@dataclass(frozen=True)
class _ProposalDraw:
    translation: np.ndarray
    z: float | None
    move_kind: str
    move_selector: float | None
    translation_increment: tuple[float, float] | None
    gap_increment: float | None


@dataclass(frozen=True)
class _AcceptanceDecision:
    accepted: bool
    acceptance_uniform: float | None
    log_acceptance_ratio: float | None


@dataclass(frozen=True)
class RegistrySearchResult:
    """Best finite state observed during a Monte Carlo registry search."""

    translation: tuple[float, float]
    score: float
    n_steps: int
    n_accepted: int
    seed: int | None = None
    z_padding: float | None = None
    trace: tuple[tuple[int, float, float], ...] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    proposal_trace: tuple[RegistryProposalRecord, ...] | None = None


def _finite_float(name: str, value: object) -> float:
    """Return ``value`` as a finite float or raise a clear validation error."""

    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{name} must be a real scalar.") from exc
    if not isfinite(result):
        raise ValueError(f"{name} must be finite.")
    return result


def _nonempty_text(name: str, value: object) -> str:
    """Return one nonempty stripped text value."""

    if not isinstance(value, str) or not value.strip():
        raise TypeError(f"{name} must be a nonempty string.")
    return value.strip()


def _unit_probability(name: str, value: object) -> float:
    """Validate one finite probability in the closed unit interval."""

    result = _finite_float(name, value)
    if not 0.0 <= result <= 1.0:
        raise ValueError(f"{name} must be in [0, 1].")
    return result


def _positive_step_count(value: object) -> int:
    """Validate the exact positive integer proposal count."""

    if isinstance(value, bool) or not isinstance(value, Integral):
        raise TypeError("n_steps must be an integer.")
    result = int(value)
    if result <= 0:
        raise ValueError("n_steps must be positive.")
    return result


def _validated_seed(value: object | None) -> int | None:
    """Validate a NumPy-compatible nonnegative integer seed."""

    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise TypeError("seed must be an integer or None.")
    result = int(value)
    if result < 0:
        raise ValueError("seed must be non-negative.")
    return result


def _wrap_unit(x: np.ndarray) -> np.ndarray:
    """Wrap a finite two-vector into the canonical unit-cell representative."""

    y = np.asarray(x, dtype=float).reshape(2)
    if not np.all(np.isfinite(y)):
        raise ValueError("registry translation must contain only finite values.")
    return y - np.floor(y)


def _clamp(z: float, z_min: float, z_max: float | None) -> float:
    """Clamp one finite gap coordinate to its validated bounds."""

    zc = _finite_float("z", z)
    if zc < z_min:
        zc = z_min
    if z_max is not None and zc > z_max:
        zc = z_max
    return zc


def _call_energy_fn(energy_fn: EnergyFn, t: np.ndarray, z: float | None) -> float:
    """Fallback objective dispatch for callables without inspectable signatures.

    Normal Python callables are dispatched once by :func:`_prepare_energy_evaluator`
    without executing speculative calls.  This compatibility fallback preserves
    support for opaque extension callables whose signatures cannot be inspected.
    """

    if z is None:
        return float(energy_fn(t))

    zf = float(z)
    try:
        return float(energy_fn(t, zf))
    except TypeError:
        pass
    try:
        return float(energy_fn(t, z_padding=zf))
    except TypeError:
        pass
    try:
        return float(energy_fn(np.array([t[0], t[1], zf], dtype=float)))
    except TypeError:
        pass
    return float(energy_fn(t))


def _prepare_energy_evaluator(
    energy_fn: EnergyFn,
    *,
    z_enabled: bool,
) -> EnergyEvaluator:
    """Select one supported objective signature without masking objective errors."""

    if not callable(energy_fn):
        raise TypeError("energy_fn must be callable.")
    if not z_enabled:
        return lambda t, _z: float(energy_fn(t))

    probe_t = np.zeros(2, dtype=float)
    probe_z = 0.0
    probe_state = np.zeros(3, dtype=float)
    try:
        signature = inspect.signature(energy_fn)
    except (TypeError, ValueError):
        return lambda t, z: _call_energy_fn(energy_fn, t, z)

    patterns: tuple[tuple[str, tuple[Any, ...], dict[str, Any]], ...] = (
        ("translation_and_z", (probe_t, probe_z), {}),
        ("translation_and_keyword_z", (probe_t,), {"z_padding": probe_z}),
        ("state_vector", (probe_state,), {}),
        ("translation_only", (probe_t,), {}),
    )
    selected: str | None = None
    for name, args, kwargs in patterns:
        try:
            signature.bind(*args, **kwargs)
        except TypeError:
            continue
        selected = name
        break

    if selected is None:
        raise TypeError(
            "energy_fn must accept t, (t, z), (t, *, z_padding=z), or a "
            "three-component state vector."
        )
    if selected == "translation_and_z":
        return lambda t, z: float(energy_fn(t, float(z)))
    if selected == "translation_and_keyword_z":
        return lambda t, z: float(energy_fn(t, z_padding=float(z)))
    if selected == "state_vector":
        return lambda t, z: float(
            energy_fn(np.array([t[0], t[1], float(z)], dtype=float))
        )
    return lambda t, _z: float(energy_fn(t))


def _validated_controls(
    *,
    n_steps: object,
    step_scale: object,
    z_step_scale: object,
    p_z: object,
    p_translate: object | None,
    seed: object | None,
    temperature: Temperature,
    keep_trace: object,
) -> tuple[int, float, float, float, float | None, int | None, float | None]:
    """Validate scalar search controls and return normalized values."""

    n_steps_i = _positive_step_count(n_steps)
    if not isinstance(keep_trace, bool):
        raise TypeError("keep_trace must be a bool.")
    step_scale_f = _finite_float("step_scale", step_scale)
    z_step_scale_f = _finite_float("z_step_scale", z_step_scale)
    if step_scale_f < 0.0 or z_step_scale_f < 0.0:
        raise ValueError("proposal scales must be non-negative.")
    p_z_f = _unit_probability("p_z", p_z)
    p_translate_f: float | None = None
    if p_translate is not None:
        p_translate_f = _unit_probability("p_translate", p_translate)
        p_z_f = 1.0 - p_translate_f
    seed_i = _validated_seed(seed)
    static_temperature: float | None = None
    if not callable(temperature):
        static_temperature = _finite_float("temperature", temperature)
        if static_temperature < 0.0:
            raise ValueError("temperature must be non-negative.")
    return (
        n_steps_i,
        step_scale_f,
        z_step_scale_f,
        p_z_f,
        p_translate_f,
        seed_i,
        static_temperature,
    )


def _initial_translation(
    rng: np.random.Generator,
    x0: Sequence[float] | None,
    z0: float | None,
) -> tuple[np.ndarray, float | None]:
    """Return the canonical initial translation and optional embedded gap."""

    if x0 is None:
        return rng.random(2), z0
    x0_arr = np.asarray(list(x0), dtype=float).ravel()
    if x0_arr.size < 2:
        raise ValueError("x0 must contain at least two values.")
    if not np.all(np.isfinite(x0_arr)):
        raise ValueError("x0 must contain only finite values.")
    embedded_z = z0
    if embedded_z is None and x0_arr.size >= 3:
        embedded_z = float(x0_arr[2])
    return _wrap_unit(x0_arr[:2]), embedded_z


def _validated_z_bounds(
    z_bounds: tuple[float, float] | None,
) -> tuple[float, float | None]:
    """Return validated optional internal-gap bounds."""

    if z_bounds is None:
        return 0.0, None
    try:
        bounds_size = len(z_bounds)
    except TypeError as exc:
        raise TypeError("z_bounds must be a (z_min, z_max) pair.") from exc
    if bounds_size != 2:
        raise ValueError("z_bounds must contain exactly two values.")
    z_min = _finite_float("z_bounds[0]", z_bounds[0])
    z_max = _finite_float("z_bounds[1]", z_bounds[1])
    if z_min < 0.0:
        raise ValueError("z_bounds must not permit a negative internal gap.")
    if z_min > z_max:
        raise ValueError("z_bounds must satisfy z_min <= z_max.")
    return z_min, z_max


def _gap_search_enabled(
    z0: float | None,
    z_bounds: tuple[float, float] | None,
    z_step_scale: float,
) -> bool:
    """Return whether the optional gap coordinate participates in the search."""

    return z0 is not None or z_bounds is not None or z_step_scale > 0.0


def _effective_gap_step_scale(
    requested: float,
    *,
    has_bounds: bool,
    z_min: float,
    z_max: float | None,
) -> float:
    """Return the requested or automatically derived gap proposal scale."""

    if has_bounds and requested == 0.0 and z_max is not None and z_min < z_max:
        return 0.1 * (z_max - z_min)
    return requested


def _default_initial_gap(
    z0: float | None,
    *,
    z_min: float,
    z_max: float | None,
) -> float:
    """Return and validate the initial optional gap coordinate."""

    initial = z0
    if initial is None:
        initial = 0.5 * (z_min + z_max) if z_max is not None else z_min
    value = _finite_float("z0", initial)
    if value < 0.0:
        raise ValueError("z0 must be non-negative.")
    return value


def _initial_gap_state(
    *,
    z0: float | None,
    z_bounds: tuple[float, float] | None,
    z_step_scale_requested: float,
) -> tuple[bool, float | None, float, float | None, float]:
    """Initialize the optional gap coordinate and effective proposal scale."""

    if not _gap_search_enabled(z0, z_bounds, z_step_scale_requested):
        return False, None, 0.0, None, z_step_scale_requested

    z_min, z_max = _validated_z_bounds(z_bounds)
    z_step_scale = _effective_gap_step_scale(
        z_step_scale_requested,
        has_bounds=z_bounds is not None,
        z_min=z_min,
        z_max=z_max,
    )
    initial_z = _default_initial_gap(z0, z_min=z_min, z_max=z_max)
    return (
        True,
        _clamp(initial_z, z_min=z_min, z_max=z_max),
        z_min,
        z_max,
        z_step_scale,
    )


def _temperature_at(
    temperature: Temperature,
    static_temperature: float | None,
    step: int,
) -> float:
    """Evaluate and validate the score-temperature for one proposal."""

    if not callable(temperature):
        return float(static_temperature)
    value = _finite_float(f"temperature({step})", temperature(step))
    if value < 0.0:
        raise ValueError("temperature must be non-negative.")
    return value


def _propose_state(
    rng: np.random.Generator,
    *,
    translation: np.ndarray,
    z: float | None,
    step_scale: float,
    z_step_scale: float,
    z_min: float,
    z_max: float | None,
    p_z: float,
) -> _ProposalDraw:
    """Draw one proposal without changing the current Markov state."""

    move_selector: float | None = None
    if z is not None and z_step_scale > 0.0:
        move_selector = float(rng.random())
        if move_selector < p_z:
            gap_increment = float(rng.normal(scale=z_step_scale))
            z_prop = _clamp(
                z + gap_increment,
                z_min=z_min,
                z_max=z_max,
            )
            return _ProposalDraw(
                translation=np.asarray(translation, dtype=float).copy(),
                z=z_prop,
                move_kind="gap",
                move_selector=move_selector,
                translation_increment=None,
                gap_increment=gap_increment,
            )

    increment = np.asarray(
        rng.normal(scale=step_scale, size=2),
        dtype=float,
    )
    proposed = _wrap_unit(translation + increment)
    return _ProposalDraw(
        translation=proposed,
        z=z,
        move_kind="translation",
        move_selector=move_selector,
        translation_increment=(float(increment[0]), float(increment[1])),
        gap_increment=None,
    )


def _accept_proposal(
    rng: np.random.Generator,
    *,
    incumbent: float,
    proposed: float,
    temperature: float,
) -> _AcceptanceDecision:
    """Apply the finite-score Metropolis rule in log space."""

    if not isfinite(proposed):
        return _AcceptanceDecision(False, None, None)
    difference = proposed - incumbent
    if difference <= 0.0:
        return _AcceptanceDecision(True, None, 0.0)
    if temperature == 0.0:
        return _AcceptanceDecision(False, None, None)

    acceptance_uniform = float(rng.random())
    with np.errstate(over="ignore", divide="ignore", invalid="ignore"):
        log_acceptance_ratio = float(np.divide(-difference, temperature))
    log_uniform = (
        float("-inf") if acceptance_uniform == 0.0 else log(acceptance_uniform)
    )
    return _AcceptanceDecision(
        log_uniform < log_acceptance_ratio,
        acceptance_uniform,
        log_acceptance_ratio,
    )


def _finalize_registry_result(
    *,
    initial_translation: np.ndarray,
    initial_z: float | None,
    best_translation: np.ndarray,
    best_score: float,
    best_z: float | None,
    n_steps: int,
    n_accepted: int,
    seed: int | None,
    trace: list[tuple[int, float, float]],
    proposal_trace: list[RegistryProposalRecord],
    keep_trace: bool,
    step_scale: float,
    temperature: Temperature,
    temperature_schedule_id: str | None,
    static_temperature: float | None,
    score_units: str,
    z_enabled: bool,
    z_step_scale: float,
    z_step_scale_requested: float,
    z_bounds: tuple[float, float] | None,
    z_min: float,
    z_max: float | None,
    p_z: float,
    p_translate_requested: float | None,
) -> RegistrySearchResult:
    """Assemble the normalized result and complete protocol provenance."""

    stored_bounds = None
    if z_bounds is not None:
        stored_bounds = (float(z_min), float(z_max))
    gap_search_enabled = z_enabled and z_step_scale > 0.0
    effective_p_z = p_z if gap_search_enabled else 0.0
    effective_p_translate = 1.0 - effective_p_z
    metadata: dict[str, Any] = {
        "protocol": REGISTRY_SEARCH_PROTOCOL,
        "protocol_version": REGISTRY_SEARCH_PROTOCOL_VERSION,
        "rng": {
            "bit_generator": REGISTRY_SEARCH_RNG,
            "version": REGISTRY_SEARCH_RNG_VERSION,
            "seed": seed,
            "seed_mode": "explicit" if seed is not None else "entropy",
        },
        "trace_version": REGISTRY_SEARCH_TRACE_VERSION if keep_trace else None,
        "score_units": score_units,
        "nonfinite_trace_encoding": "named_strings",
        "initial_translation": [
            float(initial_translation[0]),
            float(initial_translation[1]),
        ],
        "initial_z": None if initial_z is None else float(initial_z),
        "translation_space": "fractional_final_common_surface_basis",
        "translation_metric": "euclidean_in_fractional_coordinates",
        "torus_representative": REGISTRY_TORUS_REPRESENTATIVE,
        "translation_proposal": REGISTRY_TRANSLATION_PROPOSAL,
        "step_scale": step_scale,
        "temperature": "callable" if callable(temperature) else static_temperature,
        "temperature_schedule_id": (
            temperature_schedule_id if callable(temperature) else "constant"
        ),
        "temperature_units": score_units,
        "acceptance_rule": REGISTRY_ACCEPTANCE_RULE,
        "best_tie_rule": REGISTRY_BEST_TIE_RULE,
        "nonfinite_proposal_rule": "reject_without_acceptance_draw",
        "gap_coordinate_enabled": z_enabled,
        "gap_search_enabled": gap_search_enabled,
        "gap_coordinate": "absolute_internal_gap",
        "gap_units": "caller_length_units",
        "gap_proposal": (REGISTRY_GAP_PROPOSAL if gap_search_enabled else None),
        "z_step_scale": z_step_scale,
        "z_step_scale_requested": z_step_scale_requested,
        "z_bounds": stored_bounds,
        "p_z_requested": p_z,
        "p_z_effective": effective_p_z,
        "p_translate_requested": p_translate_requested,
        "p_translate_effective": effective_p_translate,
        "boundary_rule": ("inclusive_clip" if gap_search_enabled else None),
        "random_draw_order": (
            "optional_move_selector; proposal_normal_draws; "
            "uphill_acceptance_uniform_only"
        ),
    }
    return RegistrySearchResult(
        translation=(float(best_translation[0]), float(best_translation[1])),
        score=float(best_score),
        n_steps=n_steps,
        n_accepted=n_accepted,
        seed=seed,
        z_padding=None if best_z is None else float(best_z),
        trace=tuple(trace) if keep_trace else None,
        metadata=metadata,
        proposal_trace=tuple(proposal_trace) if keep_trace else None,
    )


def monte_carlo_registry_search(
    energy_fn: EnergyFn,
    *,
    n_steps: int = 400,
    step_scale: float = 0.25,
    temperature: Temperature = 0.1,
    seed: int | None = None,
    x0: Sequence[float] | None = None,
    keep_trace: bool = False,
    z0: float | None = None,
    z_step_scale: float = 0.0,
    z_bounds: tuple[float, float] | None = None,
    p_z: float = 0.25,
    p_translate: float | None = None,
    temperature_schedule_id: str | None = None,
    score_units: str = "objective_units",
) -> RegistrySearchResult:
    """Run the versioned finite registry-search protocol.

    Translation proposals are incremental isotropic Gaussian draws in the
    *fractional coordinates* of the final common surface basis. They are wrapped
    componentwise into ``[0, 1)^2``. The proposal is therefore not generally
    isotropic in Cartesian space for a skewed or unequal-length basis.

    Optional gap proposals are incremental Gaussian draws in caller length units
    and are clipped inclusively to ``z_bounds``. Downhill and equal-score finite
    proposals are accepted without an acceptance random draw. Uphill finite
    proposals use a log-space Metropolis comparison; nonfinite proposals are
    rejected without an acceptance draw. The first encountered strict best state
    is retained across equal-score visits.

    ``temperature`` has the same units as the objective score. A callable
    schedule requires ``temperature_schedule_id`` so returned provenance can
    identify the caller-owned schedule. Fixed inputs and a fixed integer seed use
    NumPy's explicitly selected PCG64 bit generator. The routine remains a finite
    optimization heuristic, not an equilibrium sampler or global optimizer.
    """

    score_units_s = _nonempty_text("score_units", score_units)
    schedule_id: str | None = None
    if callable(temperature):
        if temperature_schedule_id is None:
            raise ValueError(
                "Callable temperature schedules require temperature_schedule_id."
            )
        schedule_id = _nonempty_text(
            "temperature_schedule_id",
            temperature_schedule_id,
        )
    elif temperature_schedule_id is not None:
        raise ValueError(
            "temperature_schedule_id is only valid for callable temperature schedules."
        )

    (
        n_steps_i,
        step_scale_f,
        z_step_scale_requested,
        p_z_f,
        p_translate_requested,
        seed_i,
        static_temperature,
    ) = _validated_controls(
        n_steps=n_steps,
        step_scale=step_scale,
        z_step_scale=z_step_scale,
        p_z=p_z,
        p_translate=p_translate,
        seed=seed,
        temperature=temperature,
        keep_trace=keep_trace,
    )
    rng = np.random.Generator(np.random.PCG64(seed_i))
    translation, embedded_z = _initial_translation(rng, x0, z0)
    (
        z_enabled,
        z,
        z_min,
        z_max,
        z_step_scale_eff,
    ) = _initial_gap_state(
        z0=embedded_z,
        z_bounds=z_bounds,
        z_step_scale_requested=z_step_scale_requested,
    )

    initial_translation = translation.copy()
    initial_z = z
    evaluate = _prepare_energy_evaluator(energy_fn, z_enabled=z_enabled)
    score = float(evaluate(translation, z))
    if not isfinite(score):
        raise ValueError("The initial registry objective value must be finite.")

    best_translation = translation.copy()
    best_z = z
    best_score = score
    n_accepted = 0
    trace: list[tuple[int, float, float]] = []
    proposal_trace: list[RegistryProposalRecord] = []

    for step in range(1, n_steps_i + 1):
        proposal_temperature = _temperature_at(
            temperature,
            static_temperature,
            step,
        )
        proposal = _propose_state(
            rng,
            translation=translation,
            z=z,
            step_scale=step_scale_f,
            z_step_scale=z_step_scale_eff,
            z_min=z_min,
            z_max=z_max,
            p_z=p_z_f,
        )
        proposed_score = float(evaluate(proposal.translation, proposal.z))
        decision = _accept_proposal(
            rng,
            incumbent=score,
            proposed=proposed_score,
            temperature=proposal_temperature,
        )
        if decision.accepted:
            translation = proposal.translation.copy()
            z = None if proposal.z is None else float(proposal.z)
            score = proposed_score
            n_accepted += 1
            if score < best_score:
                best_score = score
                best_translation = translation.copy()
                best_z = z
        if keep_trace:
            trace.append((step, float(score), float(best_score)))
            proposal_trace.append(
                RegistryProposalRecord(
                    step=step,
                    move_kind=proposal.move_kind,
                    move_selector=proposal.move_selector,
                    translation_increment=proposal.translation_increment,
                    gap_increment=proposal.gap_increment,
                    proposed_translation=(
                        float(proposal.translation[0]),
                        float(proposal.translation[1]),
                    ),
                    proposed_z=(None if proposal.z is None else float(proposal.z)),
                    proposed_score=float(proposed_score),
                    temperature=float(proposal_temperature),
                    acceptance_uniform=decision.acceptance_uniform,
                    log_acceptance_ratio=decision.log_acceptance_ratio,
                    accepted=decision.accepted,
                    current_translation=(
                        float(translation[0]),
                        float(translation[1]),
                    ),
                    current_z=None if z is None else float(z),
                    current_score=float(score),
                    best_translation=(
                        float(best_translation[0]),
                        float(best_translation[1]),
                    ),
                    best_z=None if best_z is None else float(best_z),
                    best_score=float(best_score),
                )
            )

    return _finalize_registry_result(
        initial_translation=initial_translation,
        initial_z=initial_z,
        best_translation=best_translation,
        best_score=best_score,
        best_z=best_z,
        n_steps=n_steps_i,
        n_accepted=n_accepted,
        seed=seed_i,
        trace=trace,
        proposal_trace=proposal_trace,
        keep_trace=keep_trace,
        step_scale=step_scale_f,
        temperature=temperature,
        temperature_schedule_id=schedule_id,
        static_temperature=static_temperature,
        score_units=score_units_s,
        z_enabled=z_enabled,
        z_step_scale=z_step_scale_eff,
        z_step_scale_requested=z_step_scale_requested,
        z_bounds=z_bounds,
        z_min=z_min,
        z_max=z_max,
        p_z=p_z_f,
        p_translate_requested=p_translate_requested,
    )
