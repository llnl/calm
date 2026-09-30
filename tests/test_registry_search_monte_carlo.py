from __future__ import annotations

import numpy as np
import pytest

from calm.interface.refinement.registry import monte_carlo_registry_search


def _periodic_l2_energy(x: np.ndarray, x_opt: np.ndarray) -> float:
    """Periodic squared distance on a 2-torus."""

    dx = np.abs(x - x_opt)
    dx = np.minimum(dx, 1.0 - dx)
    return float(np.sum(dx * dx))


def test_monte_carlo_registry_search_is_deterministic_and_improves_score() -> None:
    x_opt = np.array([0.23, 0.71], dtype=float)

    def energy_fn(x: np.ndarray) -> float:
        return _periodic_l2_energy(x, x_opt)

    x0 = [0.0, 0.0]
    start_score = energy_fn(np.asarray(x0, dtype=float))

    res = monte_carlo_registry_search(
        energy_fn,
        x0=x0,
        n_steps=1500,
        step_scale=0.15,
        temperature=0.05,
        seed=123,
        keep_trace=False,
    )

    assert res.n_steps == 1500
    assert res.score <= start_score

    # With a fixed seed and a reasonable number of steps, we should get
    # close to the known optimum for this smooth objective.
    best = np.asarray(res.translation, dtype=float)
    assert _periodic_l2_energy(best, x_opt) < 5e-3

    # Deterministic for a fixed seed.
    res2 = monte_carlo_registry_search(
        energy_fn,
        x0=x0,
        n_steps=1500,
        step_scale=0.15,
        temperature=0.05,
        seed=123,
        keep_trace=False,
    )
    assert res.translation == res2.translation
    assert res.score == res2.score


def _torus_delta(a: float, b: float) -> float:
    """Shortest signed delta on the unit torus."""
    return float((a - b + 0.5) % 1.0 - 0.5)


def test_monte_carlo_registry_search_can_optimize_z_padding() -> None:
    """When z_bounds is provided, MC explores both translation and z_padding."""

    x_opt = np.array([0.25, 0.75], dtype=float)
    z_opt = 2.5

    def energy_fn(x: np.ndarray) -> float:
        # x is length-3 when z_bounds is enabled: (t1, t2, z_padding)
        dx = _torus_delta(float(x[0]), float(x_opt[0]))
        dy = _torus_delta(float(x[1]), float(x_opt[1]))
        dz = float(x[2]) - z_opt
        return float(dx * dx + dy * dy + dz * dz)

    res = monte_carlo_registry_search(
        energy_fn,
        x0=(0.0, 0.0),
        z0=1.0,
        z_bounds=(1.0, 4.0),
        n_steps=4000,
        step_scale=0.15,
        z_step_scale=0.25,
        temperature=0.05,
        seed=123,
        keep_trace=False,
        p_translate=0.80,
    )

    assert res.z_padding is not None
    assert abs(res.z_padding - z_opt) < 0.30

    assert abs(_torus_delta(res.translation[0], float(x_opt[0]))) < 0.10
    assert abs(_torus_delta(res.translation[1], float(x_opt[1]))) < 0.10

    # Energy should be small near the optimum.
    assert res.score < 0.20


def test_monte_carlo_registry_search_rejects_nonfinite_initial_score() -> None:
    def objective(_x: np.ndarray) -> float:
        return float("nan")

    with pytest.raises(ValueError, match="initial registry objective"):
        monte_carlo_registry_search(objective, x0=(0.0, 0.0), n_steps=1)


def test_monte_carlo_registry_search_rejects_nonfinite_controls() -> None:
    objective = lambda x: float(np.sum(np.asarray(x, dtype=float) ** 2))

    with pytest.raises(ValueError, match="step_scale must be finite"):
        monte_carlo_registry_search(
            objective,
            x0=(0.0, 0.0),
            n_steps=1,
            step_scale=float("nan"),
        )
    with pytest.raises(ValueError, match="temperature must be finite"):
        monte_carlo_registry_search(
            objective,
            x0=(0.0, 0.0),
            n_steps=1,
            temperature=float("inf"),
        )
    with pytest.raises(TypeError, match="n_steps must be an integer"):
        monte_carlo_registry_search(objective, x0=(0.0, 0.0), n_steps=1.5)
    with pytest.raises(ValueError, match="seed must be non-negative"):
        monte_carlo_registry_search(objective, x0=(0.0, 0.0), n_steps=1, seed=-1)
    with pytest.raises(TypeError, match="keep_trace must be a bool"):
        monte_carlo_registry_search(
            objective,
            x0=(0.0, 0.0),
            n_steps=1,
            keep_trace=1,
        )


def test_z_aware_objective_type_error_is_not_masked_by_signature_fallback() -> None:
    calls = 0

    def objective(_t: np.ndarray, _z: float) -> float:
        nonlocal calls
        calls += 1
        raise TypeError("objective implementation failure")

    with pytest.raises(TypeError, match="objective implementation failure"):
        monte_carlo_registry_search(
            objective,
            x0=(0.0, 0.0),
            z0=1.0,
            n_steps=1,
        )
    assert calls == 1


def test_nonfinite_proposals_are_rejected() -> None:
    proposed = 0

    def objective(_x: np.ndarray) -> float:
        nonlocal proposed
        proposed += 1
        if proposed > 1:
            return float("inf")
        return 1.0

    result = monte_carlo_registry_search(
        objective,
        x0=(0.25, 0.75),
        n_steps=3,
        step_scale=0.2,
        temperature=1.0,
        seed=5,
        keep_trace=True,
    )

    assert result.translation == (0.25, 0.75)
    assert result.score == 1.0
    assert result.n_accepted == 0
    assert result.trace is not None
    assert all(current == best == 1.0 for _, current, best in result.trace)


def test_finite_score_ties_are_accepted_but_keep_first_best_state() -> None:
    result = monte_carlo_registry_search(
        lambda _x: 1.0,
        x0=(0.25, 0.75),
        n_steps=3,
        step_scale=0.2,
        temperature=0.0,
        seed=5,
        keep_trace=True,
    )

    assert result.translation == (0.25, 0.75)
    assert result.score == 1.0
    assert result.n_accepted == result.n_steps == 3
    assert result.trace is not None
    assert all(current == best == 1.0 for _, current, best in result.trace)
