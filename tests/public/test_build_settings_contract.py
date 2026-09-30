"""Contract tests for basic-facing interface build settings."""

from __future__ import annotations

import pytest

from calm import BuildSettings


def test_build_settings_propagates_gap_and_vacuum_separately() -> None:
    """Public gap/vacuum settings should not collapse to one internal knob."""
    _strain_model, build_config = BuildSettings(
        gap=2.25,
        vacuum=17.5,
        translation=(0.25, 0.75),
    ).to_internal()

    assert build_config.z_padding == pytest.approx(2.25)
    assert build_config.vacuum_padding == pytest.approx(17.5)
    assert build_config.translation_frac == pytest.approx((0.25, 0.75))


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"alpha": float("nan")}, "alpha must be finite"),
        ({"gap": float("inf")}, "gap must be finite"),
        ({"vacuum": float("nan")}, "vacuum must be finite"),
        ({"translation": (0.0, float("inf"))}, "two finite fractional"),
    ],
)
def test_build_settings_rejects_nonfinite_geometry(kwargs, message) -> None:
    with pytest.raises(ValueError, match=message):
        BuildSettings(**kwargs).validate()
