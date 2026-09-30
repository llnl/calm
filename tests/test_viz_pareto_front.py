from __future__ import annotations

import calm.viz.pareto as vp


def test_pareto_front_2d_basic_minimization() -> None:
    # Two non-dominated points (trade-off), two dominated points
    pts = [
        {"id": "A", "x": 1.0, "y": 2.0},
        {"id": "B", "x": 2.0, "y": 1.0},
        {"id": "C", "x": 2.0, "y": 2.0},  # dominated
        {"id": "D", "x": 3.0, "y": 3.0},  # dominated
    ]

    res = vp.pareto_front_2d(
        pts,
        x="x",
        y="y",
        ids="id",
        strict=True,
        minimize=(True, True),
    )

    assert res.front_ids == ["A", "B"]
    assert res.front_idx == [0, 1]


def test_pareto_front_2d_handles_missing_values() -> None:
    pts = [
        {"id": "A", "x": 1.0, "y": 2.0},
        {"id": "B", "x": None, "y": 1.0},  # invalid
        {"id": "C", "x": 2.0, "y": 1.0},
    ]

    res = vp.pareto_front_2d(pts, x="x", y="y", ids="id")
    assert "B" not in res.front_ids
