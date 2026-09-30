from __future__ import annotations

import json
from math import log

import numpy as np
import pytest

from calm.interface.refinement.registry import (
    REGISTRY_ACCEPTANCE_RULE,
    REGISTRY_BEST_TIE_RULE,
    REGISTRY_PROVENANCE_COMPLETE,
    REGISTRY_PROVENANCE_INVALID,
    REGISTRY_PROVENANCE_LEGACY,
    REGISTRY_SEARCH_PROTOCOL,
    REGISTRY_SEARCH_PROTOCOL_VERSION,
    classify_registry_provenance,
    monte_carlo_registry_search,
)


def _periodic_energy(x: np.ndarray) -> float:
    delta = (np.asarray(x, dtype=float) - np.array([0.2, 0.7]) + 0.5) % 1.0 - 0.5
    return float(delta @ delta)


def test_seeded_translation_trace_has_frozen_pcg64_golden_vector() -> None:
    result = monte_carlo_registry_search(
        _periodic_energy,
        x0=(0.0, 0.0),
        n_steps=4,
        step_scale=0.15,
        temperature=0.05,
        seed=123,
        keep_trace=True,
        score_units="eV",
    )

    assert result.translation == (0.0, 0.0)
    assert result.score == 0.13000000000000003
    assert result.n_accepted == 2
    assert result.trace == (
        (1, 0.18130311388977974, 0.13000000000000003),
        (2, 0.18130311388977974, 0.13000000000000003),
        (3, 0.18130311388977974, 0.13000000000000003),
        (4, 0.22468401489705464, 0.13000000000000003),
    )

    proposals = result.proposal_trace
    assert proposals is not None
    assert [record.move_kind for record in proposals] == ["translation"] * 4
    assert [record.accepted for record in proposals] == [True, False, False, True]
    assert proposals[0].translation_increment == (
        -0.1483682025521776,
        -0.05516799772018248,
    )
    assert proposals[0].acceptance_uniform == 0.22035987277261138
    assert proposals[0].log_acceptance_ratio == -1.0260622777955941
    assert proposals[3].proposed_translation == (
        0.8032734300239783,
        0.9594071000803861,
    )

    metadata = result.metadata
    assert metadata["protocol"] == REGISTRY_SEARCH_PROTOCOL
    assert metadata["protocol_version"] == REGISTRY_SEARCH_PROTOCOL_VERSION
    assert metadata["rng"] == {
        "bit_generator": "numpy.random.PCG64",
        "version": 1,
        "seed": 123,
        "seed_mode": "explicit",
    }
    assert metadata["score_units"] == metadata["temperature_units"] == "eV"
    assert metadata["translation_metric"] == "euclidean_in_fractional_coordinates"
    assert metadata["p_translate_effective"] == 1.0
    assert classify_registry_provenance(metadata) == REGISTRY_PROVENANCE_COMPLETE


def test_gap_trace_records_move_selector_clipping_and_draw_order() -> None:
    def objective(t: np.ndarray, z: float) -> float:
        delta = (np.asarray(t, dtype=float) - np.array([0.2, 0.7]) + 0.5) % 1.0 - 0.5
        return float(delta @ delta + (z - 1.5) ** 2)

    result = monte_carlo_registry_search(
        objective,
        x0=(0.0, 0.0),
        z0=1.0,
        z_bounds=(0.5, 2.0),
        n_steps=3,
        step_scale=0.1,
        z_step_scale=0.2,
        p_translate=0.5,
        temperature=0.1,
        seed=7,
        keep_trace=True,
        score_units="eV",
    )

    assert result.translation == (0.02987455375084699, 0.9725862144637782)
    assert result.z_padding == 1.2680430491109067
    records = result.proposal_trace
    assert records is not None
    assert [record.move_kind for record in records] == [
        "translation",
        "gap",
        "gap",
    ]
    assert records[0].move_selector == 0.625095466604667
    assert records[1].gap_increment == -0.09093415703434451
    assert records[1].acceptance_uniform == 0.8735534453962619
    assert records[2].gap_increment == 0.2680430491109067
    assert records[2].acceptance_uniform is None
    assert result.metadata["boundary_rule"] == "inclusive_clip"
    assert result.metadata["gap_search_enabled"] is True
    assert result.metadata["p_z_effective"] == 0.5
    assert result.metadata["p_translate_effective"] == 0.5


def test_equal_scores_are_accepted_without_replacing_first_best() -> None:
    result = monte_carlo_registry_search(
        lambda _x: 1.0,
        x0=(0.25, 0.75),
        n_steps=2,
        step_scale=0.2,
        temperature=0.0,
        seed=5,
        keep_trace=True,
    )

    assert result.translation == (0.25, 0.75)
    assert result.n_accepted == 2
    assert result.metadata["acceptance_rule"] == REGISTRY_ACCEPTANCE_RULE
    assert result.metadata["best_tie_rule"] == REGISTRY_BEST_TIE_RULE
    assert result.proposal_trace is not None
    assert all(record.acceptance_uniform is None for record in result.proposal_trace)
    assert all(record.accepted for record in result.proposal_trace)
    assert all(record.best_translation == (0.25, 0.75) for record in result.proposal_trace)


def test_uphill_acceptance_is_compared_in_log_space() -> None:
    calls = 0

    def objective(_x: np.ndarray) -> float:
        nonlocal calls
        calls += 1
        return 0.0 if calls == 1 else 2.0

    result = monte_carlo_registry_search(
        objective,
        x0=(0.0, 0.0),
        n_steps=1,
        step_scale=0.1,
        temperature=0.5,
        seed=9,
        keep_trace=True,
    )

    record = result.proposal_trace[0]
    assert record.log_acceptance_ratio == -4.0
    assert record.acceptance_uniform is not None
    assert record.accepted == (log(record.acceptance_uniform) < -4.0)


def test_callable_temperature_requires_stable_schedule_identifier() -> None:
    schedule = lambda step: 1.0 / step
    with pytest.raises(ValueError, match="temperature_schedule_id"):
        monte_carlo_registry_search(
            _periodic_energy,
            x0=(0.0, 0.0),
            n_steps=1,
            temperature=schedule,
            seed=1,
        )

    result = monte_carlo_registry_search(
        _periodic_energy,
        x0=(0.0, 0.0),
        n_steps=1,
        temperature=schedule,
        temperature_schedule_id="inverse_step_v1",
        seed=1,
    )
    assert result.metadata["temperature_schedule_id"] == "inverse_step_v1"


def test_registry_provenance_quarantines_legacy_and_malformed_records() -> None:
    assert classify_registry_provenance({"temperature": 0.03}) == REGISTRY_PROVENANCE_LEGACY
    assert classify_registry_provenance(None) == REGISTRY_PROVENANCE_INVALID
    assert (
        classify_registry_provenance(
            {
                "protocol": REGISTRY_SEARCH_PROTOCOL,
                "protocol_version": REGISTRY_SEARCH_PROTOCOL_VERSION,
            }
        )
        == REGISTRY_PROVENANCE_INVALID
    )

    complete = monte_carlo_registry_search(
        _periodic_energy,
        x0=(0.0, 0.0),
        n_steps=1,
        seed=1,
    ).metadata
    malformed = dict(complete)
    malformed["translation_proposal"] = "cartesian_uniform"
    assert classify_registry_provenance(malformed) == REGISTRY_PROVENANCE_INVALID

    malformed = dict(complete)
    malformed["p_translate_effective"] = 0.25
    assert classify_registry_provenance(malformed) == REGISTRY_PROVENANCE_INVALID


def test_nonfinite_proposal_trace_is_strict_json_native() -> None:
    calls = 0

    def objective(_x: np.ndarray) -> float:
        nonlocal calls
        calls += 1
        return 0.0 if calls == 1 else float("inf")

    result = monte_carlo_registry_search(
        objective,
        x0=(0.0, 0.0),
        n_steps=1,
        step_scale=0.1,
        temperature=0.0,
        seed=4,
        keep_trace=True,
    )

    record = result.proposal_trace[0]
    payload = record.to_dict()
    assert payload["proposed_score"] == "positive_infinity"
    assert payload["log_acceptance_ratio"] is None
    assert result.metadata["nonfinite_trace_encoding"] == "named_strings"
    json.dumps(payload, allow_nan=False)


def test_fixed_gap_objective_does_not_claim_gap_proposals() -> None:
    result = monte_carlo_registry_search(
        lambda _translation, z: float(z),
        x0=(0.0, 0.0),
        z0=1.5,
        n_steps=1,
        step_scale=0.1,
        z_step_scale=0.0,
        p_z=0.75,
        temperature=0.0,
        seed=2,
        keep_trace=True,
    )

    assert result.metadata["gap_coordinate_enabled"] is True
    assert result.metadata["gap_search_enabled"] is False
    assert result.metadata["p_z_requested"] == 0.75
    assert result.metadata["p_z_effective"] == 0.0
    assert result.metadata["p_translate_effective"] == 1.0
    assert result.proposal_trace[0].move_kind == "translation"
