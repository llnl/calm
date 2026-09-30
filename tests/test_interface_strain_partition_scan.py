from __future__ import annotations

from typing import cast

import numpy as np

from calm.interface.refinement.partition import scan_geodesic_strain_partitions


def test_scan_geodesic_strain_partitions_selects_best_alpha() -> None:
    # Simple SPD(3) Gram matrices; only the in-plane (2x2) block matters.
    S_A = np.eye(3)
    S_B = np.eye(3)
    S_B[0, 0] = 1.21
    S_B[1, 1] = 1.21

    # Choose a grid that contains the target exactly to avoid tolerance debates.
    alphas = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    target = 0.3

    def score_fn(strain_state):
        # Lower is better; unique minimum at `target` within the chosen grid.
        return float((cast(float, strain_state.alpha) - target) ** 2)

    res = scan_geodesic_strain_partitions(S_A, S_B, alphas=alphas, score_fn=score_fn)

    assert res.best.alpha == target
    assert res.best.score == 0.0
    assert res.n_evaluated == len(alphas)
