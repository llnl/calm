"""Migration contract for new bounded-gauge SlabSpec controls."""

from __future__ import annotations

from dataclasses import dataclass

from calm.keys.uid import slab_spec_uid, slab_spec_uid_for_bulk


@dataclass(frozen=True)
class _LegacySpec:
    miller: tuple[int, int, int] = (1, 1, 1)
    n_layers: int = 4
    vacuum: float = 10.0


@dataclass(frozen=True)
class _CurrentSpec:
    miller: tuple[int, int, int] = (1, 1, 1)
    n_layers: int = 4
    vacuum: float = 10.0
    primitive_max_denominator: int = 12
    primitive_reduction_max_iter: int = 100
    stacking_search_radius: int = 2
    c_tilt_search: int = 6
    c_tilt_singular_tolerance: float = 1e-12


def test_default_controls_preserve_legacy_slab_spec_uid() -> None:
    assert slab_spec_uid(_CurrentSpec()) == slab_spec_uid(_LegacySpec())
    assert slab_spec_uid_for_bulk(
        _CurrentSpec(),
        bulk_uid="bulk:relaxed",
        bulk_kind="relaxed",
    ) == slab_spec_uid_for_bulk(
        _LegacySpec(),
        bulk_uid="bulk:relaxed",
        bulk_kind="relaxed",
    )


def test_nondefault_controls_are_identity_affecting() -> None:
    baseline = slab_spec_uid(_CurrentSpec())
    assert slab_spec_uid(_CurrentSpec(stacking_search_radius=3)) != baseline
    assert slab_spec_uid(_CurrentSpec(c_tilt_search=7)) != baseline
    assert slab_spec_uid(_CurrentSpec(primitive_max_denominator=24)) != baseline
    assert (
        slab_spec_uid(_CurrentSpec(primitive_reduction_max_iter=101))
        != baseline
    )
    assert (
        slab_spec_uid(_CurrentSpec(c_tilt_singular_tolerance=2e-12))
        != baseline
    )
