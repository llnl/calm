import numpy as np

from calm.interface.refinement.registry import monte_carlo_registry_search


def test_registry_search_z_padding_respects_bounds_and_passes_z_to_energy_fn() -> None:
    """When z-moves are enabled, proposed z-padding values should stay in-bounds.

    This test is intentionally *not* about convergence. It verifies:
      - z moves occur (p_z=1.0)
      - z values are clamped to bounds
      - energy_fn receives z_padding values
    """

    seen_z: list[float] = []

    def energy_fn(_t: np.ndarray, z_padding: float) -> float:
        seen_z.append(float(z_padding))
        # Lower is better; makes it easy to reason about monotonic improvements.
        return float(z_padding)

    res = monte_carlo_registry_search(
        energy_fn,
        # Keep translation fixed so the test isolates z-padding behavior.
        x0=(0.1, 0.2),
        step_scale=0.0,
        n_steps=10,
        temperature=0.0,
        seed=123,
        keep_trace=True,
        # Enable z moves.
        z0=1.5,
        z_step_scale=0.5,
        z_bounds=(1.0, 2.0),
        p_z=1.0,
    )

    assert res.z_padding is not None
    assert res.translation == (0.1, 0.2)

    assert len(seen_z) > 1  # initial + proposals
    assert all(1.0 <= z <= 2.0 for z in seen_z)
    assert any(abs(z - 1.5) > 1e-12 for z in seen_z)


def test_registry_search_energy_fn_can_accept_state_vector_len3() -> None:
    """Support energy_fn(x) where x=[t1,t2,z] when z moves are enabled."""

    seen_shapes: list[tuple[int, ...]] = []

    def energy_state(x: np.ndarray) -> float:
        seen_shapes.append(tuple(x.shape))
        # Interpret x[2] as z_padding
        return float((x[2] - 0.0) ** 2)

    res = monte_carlo_registry_search(
        energy_state,
        x0=(0.0, 0.0, 1.0),
        step_scale=0.0,
        n_steps=5,
        temperature=0.0,
        seed=0,
        # Enable z moves.
        z_step_scale=0.25,
        z_bounds=(0.0, 2.0),
        p_z=1.0,
    )

    assert res.z_padding is not None
    assert (3,) in seen_shapes
