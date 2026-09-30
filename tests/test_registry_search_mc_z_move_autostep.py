import numpy as np

from calm.interface.refinement.registry import monte_carlo_registry_search


def test_registry_search_autosets_z_step_scale_when_bounds_provided() -> None:
    """Regression guard: z-padding moves should not be silently disabled.

    A common usage pattern is to provide z-bounds (to keep the search physically
    meaningful) while leaving z_step_scale at its legacy/default value of 0.0.

    In that case, the Monte Carlo kernel should still propose z-padding moves by
    choosing a conservative default proposal width based on the bounds span.
    """

    def energy_fn(state: np.ndarray) -> float:
        # Prefer larger z so the first (deterministic) positive z proposal is accepted.
        if state.size < 3:
            return float("inf")
        return -float(state[2])

    z0 = 1.0
    res = monte_carlo_registry_search(
        energy_fn=energy_fn,
        n_steps=1,
        seed=0,
        step_scale=0.0,
        temperature=0.0,
        # Enable z via bounds, but leave z_step_scale at the legacy/default value.
        z0=z0,
        z_bounds=(0.0, 2.0),
        z_step_scale=0.0,
        # Force the kernel to attempt a z move on the first step.
        p_translate=0.0,
    )

    assert res.z_padding is not None
    assert float(res.z_padding) > z0

    # Metadata should report the requested vs effective proposal width.
    assert float(res.metadata["z_step_scale_requested"]) == 0.0
    assert float(res.metadata["z_step_scale"]) > 0.0
